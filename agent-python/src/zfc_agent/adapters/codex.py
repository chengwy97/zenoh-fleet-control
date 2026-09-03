from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
import shutil
from typing import Any

from .base import AdapterContext, ToolEvent


class CodexExecAdapter:
    name = "codex"
    capabilities = ["non_interactive_run", "json_stream", "cwd", "resume", "cancel", "image_input"]

    async def run(self, payload: dict[str, Any], context: AdapterContext) -> AsyncIterator[ToolEvent]:
        prompt = payload.get("prompt")
        if not prompt:
            yield ToolEvent("error", {"code": "empty_prompt", "message": "payload.prompt is required", "retryable": False})
            return

        options = payload.get("options") or {}
        sandbox = options.get("sandbox", "workspace-write")
        approval = options.get("approval", "never")
        if approval != "never":
            yield ToolEvent("message", {"text": "Codex exec adapter currently supports approval=never only"})

        media = payload.get("media") or []
        image_args: list[str] = []
        attachment_notes: list[str] = []
        for item in media:
            media_type = item.get("media_type", "")
            path = item.get("local_path") or item.get("path")
            if not path:
                continue
            description = item.get("description") or "no additional instruction"
            if media_type.startswith("image/"):
                image_args.extend(["-i", path])
                attachment_notes.append(f"[image] path={path}; instruction={description}")
            elif media_type.startswith("video/"):
                frames, error = await self.extract_video_frames(Path(path), context.cwd, item.get("asset_id", "video"))
                if error:
                    attachment_notes.append(f"[video] path={path}; frame_extraction=failed ({error}); instruction={description}")
                else:
                    for frame in frames:
                        image_args.extend(["-i", str(frame)])
                    attachment_notes.append(f"[video] path={path}; extracted_frames={len(frames)}; instruction={description}")
            elif media_type.startswith("audio/"):
                attachment_notes.append(f"[audio] path={path}; transcription_or_other_processing_is_agent_decision=true; instruction={description}")
            else:
                attachment_notes.append(f"[file] media_type={media_type}; path={path}; inspect_or_process_as_needed=true; instruction={description}")

        full_prompt = prompt
        if attachment_notes:
            full_prompt = prompt + "\n\nAttachments available on the agent filesystem:\n" + "\n".join(attachment_notes)

        if context.native_session_id:
            args = ["codex", "-a", "never", "exec", "resume", "--json", "--skip-git-repo-check"] + image_args + [context.native_session_id, full_prompt]
        else:
            args = ["codex", "-a", "never", "exec", "--json", "--skip-git-repo-check"] + image_args + [
                "--cd", str(context.cwd), "--sandbox", sandbox, full_prompt,
            ]

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stderr_task = asyncio.create_task(proc.stderr.read())
        wait_task = asyncio.create_task(proc.wait())
        started_at = asyncio.get_running_loop().time()
        try:
            while True:
                if context.cancel_event and context.cancel_event.is_set():
                    proc.terminate()
                    try:
                        await asyncio.wait_for(wait_task, 3)
                    except TimeoutError:
                        proc.kill()
                        await wait_task
                    yield ToolEvent("error", {"code": "cancelled", "message": "codex task cancelled", "retryable": False})
                    yield ToolEvent("adapter_result", {"exit_code": None, "status": "cancelled"})
                    return
                if context.timeout_ms and (asyncio.get_running_loop().time() - started_at) * 1000 >= context.timeout_ms:
                    proc.kill()
                    await wait_task
                    yield ToolEvent("error", {"code": "timeout", "message": "codex command timeout", "retryable": True})
                    yield ToolEvent("adapter_result", {"exit_code": None, "status": "timeout"})
                    return
                read_task = asyncio.create_task(proc.stdout.readline())
                done, _ = await asyncio.wait({read_task, wait_task}, timeout=0.1, return_when=asyncio.FIRST_COMPLETED)
                if read_task in done:
                    raw = read_task.result()
                    if raw:
                        line = raw.decode("utf-8", errors="replace").strip()
                        if line:
                            try:
                                yield self.map_codex_event(json.loads(line))
                            except json.JSONDecodeError:
                                yield ToolEvent("stdout", {"text": line})
                    elif wait_task.done():
                        break
                else:
                    read_task.cancel()
                    await asyncio.gather(read_task, return_exceptions=True)
                if wait_task.done() and proc.stdout.at_eof():
                    break
            exit_code = await wait_task
            stderr = (await stderr_task).decode("utf-8", errors="replace").strip()
            if stderr:
                yield ToolEvent("stderr", {"text": stderr})
            yield ToolEvent("adapter_result", {"exit_code": exit_code, "status": "succeeded" if exit_code == 0 else "failed"})
        finally:
            if not wait_task.done():
                proc.kill()
                await wait_task
            if not stderr_task.done():
                stderr_task.cancel()
                await asyncio.gather(stderr_task, return_exceptions=True)

    async def extract_video_frames(self, video: Path, cwd: Path, asset_id: str) -> tuple[list[Path], str | None]:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return [], "ffmpeg is not installed; cannot extract video frames"
        output_dir = cwd / ".zfc" / "derived" / asset_id
        output_dir.mkdir(parents=True, exist_ok=True)
        pattern = output_dir / "frame-%02d.jpg"
        proc = await asyncio.create_subprocess_exec(
            ffmpeg,
            "-y",
            "-i",
            str(video),
            "-vf",
            "fps=1/5,scale='min(1280,iw)':-2",
            "-frames:v",
            "3",
            str(pattern),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        frames = sorted(output_dir.glob("frame-*.jpg"))
        if proc.returncode != 0 or not frames:
            message = stderr.decode("utf-8", errors="replace").strip() or "no frames extracted"
            return [], message
        return frames, None

    def map_codex_event(self, item: dict[str, Any]) -> ToolEvent:
        item_type = item.get("type", "codex_event")
        if item_type == "thread.started":
            return ToolEvent("message", {"text": "codex thread started", "thread_id": item.get("thread_id"), "raw": item})
        if item_type == "turn.started":
            return ToolEvent("progress", {"text": "codex turn started", "raw": item})
        if item_type == "turn.completed":
            return ToolEvent("progress", {"text": "codex turn completed", "raw": item})
        if item_type == "item.completed":
            completed = item.get("item") or {}
            if completed.get("type") == "agent_message":
                return ToolEvent("message", {"text": completed.get("text", ""), "raw": item})
            return ToolEvent("progress", {"text": completed.get("type", "item.completed"), "raw": item})
        return ToolEvent("progress", {"text": item_type, "raw": item})
