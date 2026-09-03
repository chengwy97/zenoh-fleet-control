from __future__ import annotations

import argparse
import asyncio
import base64
import platform
import queue
import threading
import time
import uuid
from pathlib import Path

from . import __version__
from .adapters import AdapterContext, ToolAdapterRegistry
from .config import AgentConfig
from .keyspace import Keyspace
from .media import MediaManifest, MediaStore
from .filesystem import list_directory
from .models import DeviceStatus, from_payload, now_ts, to_json
from .runtime import PendingMessage, SessionRuntime
from .sessions import LocalSession
from .storage import SessionStore, ToolSession
from .transfer import backend_from_config, ref_from_dict
from .zenoh_client import declare_queryable, open_session, put_bytes, put_json, subscribe


def event_payload(cfg: AgentConfig, cmd_id: str, event_id: str, seq: int, kind: str, content: dict) -> str:
    return to_json({
        "version": "v1",
        "username": cfg.username,
        "device_id": cfg.device_id,
        "session_id": cfg.session_id,
        "cmd_id": cmd_id,
        "event_id": event_id,
        "seq": seq,
        "kind": kind,
        "content": content,
        "timestamp": now_ts(),
    })


class Agent:
    def __init__(self, cfg: AgentConfig) -> None:
        self.cfg = cfg
        self.keyspace = Keyspace(cfg.username, cfg.device_id, cfg.session_id)
        self.local_session = LocalSession.create(cfg.username, cfg.device_id, cfg.session_id, cfg.cwd)
        self.zenoh = open_session(cfg.connect)
        self.adapters = ToolAdapterRegistry()
        self.runtime = SessionRuntime()
        self.command_queue: queue.Queue[dict] = queue.Queue()
        self.seen_cmd_ids: set[str] = set()
        self.seq = 0
        self.seq_lock = threading.Lock()
        self.store = SessionStore(cfg.cwd / ".zfc" / "sessions")
        self.media_store = MediaStore(cfg.cwd / ".zfc" / "media")
        self.transfer_backend = backend_from_config(
            cfg.transfer_backend,
            cfg.transfer_store,
            username=cfg.username,
            device_id=cfg.device_id,
            session_id=cfg.session_id,
            file_api_url=cfg.file_api_url,
            file_api_token=cfg.file_api_token,
        )
        self.pending_manifests: dict[str, MediaManifest] = {}
        self.persisted_session = self.store.load(cfg.session_id, cfg.cwd)
        self.worker = threading.Thread(target=self._worker_loop, name="zfc-agent-worker", daemon=True)

    def publish_status(self) -> None:
        device_status = "busy" if self.runtime.running_cmd_id else "online"
        if self.local_session.status in {"ending", "ended"}:
            device_status = "online"
        status = DeviceStatus(
            username=self.cfg.username,
            device_id=self.cfg.device_id,
            name=self.cfg.name,
            platform=platform.system().lower(),
            status=device_status,
            agent_version=__version__,
            active_session_id=self.cfg.session_id,
            last_seen=now_ts(),
            capabilities=["shell", "ai", "codex", "session_resume", "cancel", "media", "list_dir", "set_cwd", "transfer_import", "transfer_export"],
        )
        put_json(self.zenoh, self.keyspace.presence, "online")
        put_json(self.zenoh, self.keyspace.status, status.json())
        put_json(self.zenoh, self.keyspace.session_state, self.local_session.state().json())

    def publish_event(self, cmd_id: str, kind: str, content: dict) -> None:
        with self.seq_lock:
            self.seq += 1
            seq = self.seq
        event_id = f"evt_{uuid.uuid4().hex}"
        put_json(self.zenoh, self.keyspace.event(event_id), event_payload(self.cfg, cmd_id, event_id, seq, kind, content))

    def publish_result(self, cmd_id: str, status: str, exit_code: int | None, summary: str, output: dict) -> None:
        put_json(self.zenoh, self.keyspace.result(cmd_id), to_json({
            "version": "v1",
            "username": self.cfg.username,
            "device_id": self.cfg.device_id,
            "session_id": self.cfg.session_id,
            "cmd_id": cmd_id,
            "status": status,
            "exit_code": exit_code,
            "summary": summary,
            "output": output,
            "completed_at": now_ts(),
        }))

    def on_command(self, sample) -> None:
        try:
            command = from_payload(sample.payload)
        except Exception as exc:
            print(f"invalid command payload: {exc}")
            return
        cmd_id = command.get("cmd_id")
        if not cmd_id:
            return
        with self.runtime.lock:
            if cmd_id in self.seen_cmd_ids:
                self.publish_event(cmd_id, "message", {"text": "duplicate command ignored"})
                return
            self.seen_cmd_ids.add(cmd_id)
            if self.runtime.ending:
                self.publish_event(cmd_id, "error", {"code": "session_ended", "message": "session is ending or ended", "retryable": False})
                self.publish_result(cmd_id, "cancelled", None, "session ended", {})
                return
            if self.runtime.running_cmd_id and command.get("type") == "run_ai":
                self.runtime.pending.append(PendingMessage(command))
                self.publish_event(cmd_id, "accepted", {"type": "run_ai", "queued": True})
                self.publish_event(cmd_id, "message", {"text": "message queued until current task completes"})
                return
        self.command_queue.put(command)

    def on_directory_query(self, query) -> None:
        try:
            payload = from_payload(query.payload) if query.payload else {}
            response = {
                "version": "v1",
                "username": self.cfg.username,
                "device_id": self.cfg.device_id,
                "root": str(self.cfg.root),
                "cwd": str(self.local_session.cwd),
                **list_directory(self.cfg.root, self.local_session.cwd, payload.get("path")),
                "timestamp": now_ts(),
            }
            query.reply(self.keyspace.directory_queryable, to_json(response))
        except Exception as exc:
            query.reply_err(to_json({
                "version": "v1",
                "code": "directory_query_failed",
                "message": str(exc),
                "retryable": True,
            }))

    def on_control(self, sample) -> None:
        try:
            control = from_payload(sample.payload)
        except Exception as exc:
            print(f"invalid control payload: {exc}")
            return
        control_type = control.get("type")
        cmd_id = control.get("cmd_id") or self.runtime.running_cmd_id
        if control_type in {"cancel", "end_session"}:
            should_end_now = False
            with self.runtime.lock:
                self.runtime.cancel_event.set()
                if control_type == "end_session":
                    self.runtime.ending = True
                    self.local_session.status = "ending"
                    should_end_now = self.runtime.running_cmd_id is None
            put_json(self.zenoh, self.keyspace.session_state, self.local_session.state().json())
            if should_end_now:
                self._end_session()
            if cmd_id:
                self.publish_event(cmd_id, "message", {"text": "cancellation requested"})
            return
        if control_type == "approval_response":
            if cmd_id:
                self.publish_event(cmd_id, "error", {"code": "approval_not_supported", "message": "approval forwarding is not implemented in the Codex exec adapter", "retryable": False})
            return
        if cmd_id:
            self.publish_event(cmd_id, "error", {"code": "unsupported_control", "message": str(control_type), "retryable": False})

    def on_media_chunk(self, sample) -> None:
        key = str(sample.key_expr)
        parts = key.split("/")
        if len(parts) < 10:
            return
        asset_id = parts[7]
        index = int(parts[9])
        payload = sample.payload.to_bytes() if hasattr(sample.payload, "to_bytes") else bytes(sample.payload)
        self.media_store.write_chunk(asset_id, index, payload)
        manifest = self.pending_manifests.get(asset_id)
        if manifest:
            self._try_finalize_media(manifest)

    def on_media_manifest(self, sample) -> None:
        try:
            manifest_data = from_payload(sample.payload)
            manifest = MediaManifest(**manifest_data)
            if manifest.transfer:
                self._materialize_media_transfer(manifest)
            else:
                self.pending_manifests[manifest.asset_id] = manifest
                self._try_finalize_media(manifest)
        except Exception as exc:
            print(f"invalid media manifest: {exc}")

    def _try_finalize_media(self, manifest: MediaManifest) -> None:
        try:
            self.media_store.finalize(manifest)
        except ValueError as exc:
            # Chunks can arrive after the manifest. Keep it pending and retry on each chunk.
            if "missing media chunk" in str(exc) or "media chunks are missing" in str(exc):
                return
            self.pending_manifests.pop(manifest.asset_id, None)
            self.publish_event(manifest.asset_id, "error", {"code": "media_finalize_failed", "message": str(exc), "retryable": False})
            return
        except Exception as exc:
            self.pending_manifests.pop(manifest.asset_id, None)
            self.publish_event(manifest.asset_id, "error", {"code": "media_finalize_failed", "message": str(exc), "retryable": False})
            return
        self.pending_manifests.pop(manifest.asset_id, None)
        self._publish_media_ready(manifest)

    def _materialize_media_transfer(self, manifest: MediaManifest) -> None:
        try:
            if not manifest.transfer:
                raise ValueError("media transfer ref is missing")
            ref = ref_from_dict(manifest.transfer)
            asset_dir = self.media_store.root / manifest.asset_id
            extracted_root = self.transfer_backend.import_to_cwd(ref, asset_dir, ".", asset_dir)
            self.media_store.finalize_materialized(manifest, extracted_root)
            self._publish_media_ready(manifest)
        except Exception as exc:
            self.publish_event(manifest.asset_id, "error", {"code": "media_transfer_failed", "message": str(exc), "retryable": True})

    def _publish_media_ready(self, manifest: MediaManifest) -> None:
        self.publish_event(manifest.asset_id, "media_ref", {
            "asset_id": manifest.asset_id,
            "name": manifest.name,
            "media_type": manifest.media_type,
            "description": manifest.description,
            "transport": "transfer" if manifest.transfer else "zenoh_chunks",
        })

    def _worker_loop(self) -> None:
        while True:
            command = self.command_queue.get()
            if command is None:
                return
            asyncio.run(self._execute(command))
            should_end = False
            next_command = None
            with self.runtime.lock:
                if self.runtime.ending:
                    should_end = True
                elif self.runtime.pending:
                    next_command = self.runtime.pending.popleft().command
            if should_end:
                self._end_session()
                continue
            if next_command:
                self.command_queue.put(next_command)

    async def _execute(self, command: dict) -> None:
        cmd_id = command["cmd_id"]
        if command.get("type") == "set_cwd":
            await self._set_cwd(command)
            return
        if command.get("type") in {"import_transfer", "export_transfer"}:
            await self._transfer(command)
            return
        adapter_name, adapter_payload = self._resolve_adapter(command)
        adapter = self.adapters.get(adapter_name)
        self.publish_event(cmd_id, "accepted", {"type": command.get("type"), "tool": adapter_name})
        if not adapter:
            self.publish_event(cmd_id, "error", {"code": "unsupported_tool", "message": adapter_name, "retryable": False})
            self.publish_result(cmd_id, "failed", None, "unsupported tool", {})
            return

        with self.runtime.lock:
            self.runtime.running_cmd_id = cmd_id
            self.runtime.active_tool = adapter_name
            self.runtime.cancel_event.clear()
        self.local_session.status = "running"
        self.local_session.active_cmd_id = cmd_id
        put_json(self.zenoh, self.keyspace.session_state, self.local_session.state().json())
        self.publish_status()

        exit_code: int | None = 0
        result_status = "succeeded"
        event_count = 0
        try:
            adapter_payload = self._resolve_media(adapter_payload)
            native_session = self.persisted_session.tools.get(adapter_name)
            context = AdapterContext(
                cwd=self.local_session.cwd,
                timeout_ms=command.get("timeout_ms"),
                native_session_id=native_session.native_session_id if native_session else None,
                cancel_event=self.runtime.cancel_event,
            )
            async for tool_event in adapter.run(adapter_payload, context):
                if tool_event.kind == "adapter_result":
                    exit_code = tool_event.content.get("exit_code")
                    result_status = tool_event.content.get("status", "succeeded")
                    continue
                event_count += 1
                self.publish_event(cmd_id, tool_event.kind, tool_event.content)
                if adapter_name == "codex":
                    thread_id = tool_event.content.get("thread_id")
                    if thread_id:
                        self.persisted_session.tools["codex"] = ToolSession(native_session_id=thread_id, updated_at=now_ts())
                        self.store.save(self.persisted_session)
            if result_status == "cancelled":
                self.publish_result(cmd_id, "cancelled", exit_code, "task cancelled", {"event_count": event_count, "tool": adapter_name})
            elif result_status == "timeout":
                self.publish_result(cmd_id, "timeout", exit_code, "task timeout", {"event_count": event_count, "tool": adapter_name})
            else:
                status = "succeeded" if exit_code in {0, None} else "failed"
                self.publish_result(cmd_id, status, exit_code, "command completed", {"event_count": event_count, "tool": adapter_name})
        except Exception as exc:  # pragma: no cover - defensive prototype boundary
            self.publish_event(cmd_id, "error", {"code": "execution_error", "message": str(exc), "retryable": False})
            self.publish_result(cmd_id, "failed", None, "execution error", {"tool": adapter_name})
        finally:
            with self.runtime.lock:
                self.runtime.running_cmd_id = None
                self.runtime.active_tool = None
            self.local_session.active_cmd_id = None
            self.local_session.status = "ending" if self.runtime.ending else "idle"
            put_json(self.zenoh, self.keyspace.session_state, self.local_session.state().json())
            self.publish_status()

    def _resolve_media(self, payload: dict) -> dict:
        resolved = dict(payload)
        media = []
        for item in payload.get("media") or []:
            asset_id = item.get("asset_id")
            if not asset_id:
                raise ValueError("media item requires asset_id")
            manifest, path = self.media_store.resolve(asset_id)
            media.append({
                "asset_id": manifest.asset_id,
                "local_path": str(path),
                "media_type": manifest.media_type,
                "name": manifest.name,
                "description": item.get("description") or manifest.description,
            })
        resolved["media"] = media
        return resolved

    async def _set_cwd(self, command: dict) -> None:
        cmd_id = command["cmd_id"]
        payload = command.get("payload") or {}
        self.publish_event(cmd_id, "accepted", {"type": "set_cwd"})
        if self.runtime.running_cmd_id:
            self.publish_event(cmd_id, "error", {"code": "session_busy", "message": "cannot change cwd while command is running", "retryable": True})
            self.publish_result(cmd_id, "failed", None, "cwd change failed", {})
            return
        try:
            listing = list_directory(self.cfg.root, self.local_session.cwd, payload.get("path"))
            self.local_session.cwd = Path(listing["path"])
            self.publish_event(cmd_id, "cwd_changed", {"cwd": listing["path"], "relative_path": listing["relative_path"]})
            self.publish_event(cmd_id, "directory_listing", listing)
            put_json(self.zenoh, self.keyspace.session_state, self.local_session.state().json())
            self.publish_result(cmd_id, "succeeded", 0, "cwd changed", {"cwd": listing["path"], "relative_path": listing["relative_path"]})
        except (ValueError, FileNotFoundError, NotADirectoryError, PermissionError) as exc:
            self.publish_event(cmd_id, "error", {"code": "cwd_invalid", "message": str(exc), "retryable": True})
            self.publish_result(cmd_id, "failed", None, "cwd change failed", {})

    async def _transfer(self, command: dict) -> None:
        cmd_id = command["cmd_id"]
        payload = command.get("payload") or {}
        self.publish_event(cmd_id, "accepted", {"type": command.get("type"), "backend": self.transfer_backend.name})
        try:
            if command.get("type") == "import_transfer":
                ref = ref_from_dict(payload["transfer"])
                destination = self.transfer_backend.import_to_cwd(ref, self.local_session.cwd, payload.get("target_path"), self.cfg.root)
                listing = list_directory(self.cfg.root, self.local_session.cwd, ".")
                self.publish_event(cmd_id, "transfer_imported", {"transfer_id": ref.transfer_id, "destination": str(destination)})
                self.publish_event(cmd_id, "directory_listing", listing)
                self.publish_result(cmd_id, "succeeded", 0, "transfer imported", {"transfer_id": ref.transfer_id, "destination": str(destination)})
                return
            ref = self.transfer_backend.export_from_cwd(self.local_session.cwd, payload.get("path"), self.cfg.root)
            self.publish_event(cmd_id, "transfer_export_ready", {"transfer": ref.to_dict()})
            self.publish_result(cmd_id, "succeeded", 0, "transfer exported", {"transfer": ref.to_dict()})
        except Exception as exc:
            self.publish_event(cmd_id, "error", {"code": "transfer_failed", "message": str(exc), "retryable": True})
            self.publish_result(cmd_id, "failed", None, "transfer failed", {})

    def _resolve_adapter(self, command: dict) -> tuple[str, dict]:
        payload = command.get("payload") or {}
        if command.get("type") == "run_shell":
            return "shell", payload
        if command.get("type") == "run_ai":
            return payload.get("tool", "codex"), payload
        return "unsupported", payload

    def _end_session(self) -> None:
        self.runtime.pending.clear()
        self.local_session.status = "ended"
        self.local_session.ended_at = now_ts()
        self.local_session.active_cmd_id = None
        self.store.delete(self.cfg.session_id)
        put_json(self.zenoh, self.keyspace.session_state, self.local_session.state().json())
        self.publish_status()

    def run(self) -> None:
        self.publish_status()
        self.worker.start()
        command_sub = subscribe(self.zenoh, self.keyspace.commands, self.on_command)
        control_sub = subscribe(self.zenoh, self.keyspace.control, self.on_control)
        media_chunk_sub = subscribe(self.zenoh, self.keyspace.media_chunks, self.on_media_chunk)
        media_manifest_sub = subscribe(self.zenoh, self.keyspace.media_manifests, self.on_media_manifest)
        directory_queryable = declare_queryable(self.zenoh, self.keyspace.directory_queryable, self.on_directory_query)
        print(f"zfc-agent online: {self.keyspace.commands}")
        try:
            while True:
                self.publish_status()
                time.sleep(5)
        except KeyboardInterrupt:
            with self.runtime.lock:
                self.runtime.cancel_event.set()
            put_json(self.zenoh, self.keyspace.presence, "offline")
            print("zfc-agent stopped")
        finally:
            self.command_queue.put(None)
            self.worker.join(timeout=5)
            for sub in (command_sub, control_sub, media_chunk_sub, media_manifest_sub, directory_queryable):
                if hasattr(sub, "undeclare"):
                    sub.undeclare()
            if hasattr(self.zenoh, "close"):
                self.zenoh.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="zenoh-fleet-control Python agent")
    parser.add_argument("--username")
    parser.add_argument("--device-id")
    parser.add_argument("--session-id")
    parser.add_argument("--root", help="agent filesystem root; cwd must stay inside it")
    parser.add_argument("--cwd")
    parser.add_argument("--name")
    parser.add_argument("--config", help="JSON config file with root, cwd, username, device_id, session_id, name, connect, and transfer settings")
    parser.add_argument("--transfer-backend", choices=["local_spool", "tus", "s3", "minio"])
    parser.add_argument("--transfer-store", help="local cache/spool directory for transfer backends")
    parser.add_argument("--file-api-url", help="zfc-file-api base URL for s3/minio transfer backend")
    parser.add_argument("--file-api-token", help="Bearer token for zfc-file-api")
    parser.add_argument("--connect", help="Zenoh router endpoint, e.g. tcp/127.0.0.1:7447")
    return parser


def main() -> None:
    cfg = AgentConfig.from_args(build_parser().parse_args())
    Agent(cfg).run()


if __name__ == "__main__":
    main()
