from __future__ import annotations

import argparse
import json
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .auth import mint_token, verify_password
from .config import BridgeSettings
from .zenoh_client import get as zenoh_get
from .zenoh_client import open_session, put_json, subscribe


class LoginRequest(BaseModel):
    username: str
    password: str


class CommandRequest(BaseModel):
    username: str
    device_id: str
    session_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ControlRequest(BaseModel):
    username: str
    device_id: str
    session_id: str
    type: str
    cmd_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass
class BridgeState:
    tokens: dict[str, dict[str, Any]] = field(default_factory=dict)
    sessions: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    devices: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)


MAX_SESSION_EVENTS = 1000


def _payload_text(sample: Any) -> str:
    payload = sample.payload
    if hasattr(payload, "to_string"):
        return payload.to_string()
    if isinstance(payload, bytes):
        return payload.decode("utf-8")
    return str(payload)


def _parse_key(key: str) -> tuple[str | None, str | None, str | None, str | None]:
    parts = key.split("/")
    if len(parts) < 4 or parts[0] != "u":
        return None, None, None, None
    username = parts[1]
    if len(parts) < 4 or parts[2] != "fleet":
        return username, None, None, None
    device_id = parts[3]
    if len(parts) == 5:
        return username, device_id, None, parts[4]
    session_id = None
    if len(parts) >= 6 and parts[4] == "sessions":
        session_id = parts[5]
    return username, device_id, session_id, "/".join(parts[6:]) if len(parts) > 6 else None


def _require_token(state: BridgeState, authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    token = authorization.removeprefix("Bearer ").strip()
    token_info = state.tokens.get(token)
    if not token_info:
        raise HTTPException(status_code=401, detail="unauthorized")
    if int(token_info["expires_at"]) <= int(time.time()):
        state.tokens.pop(token, None)
        raise HTTPException(status_code=401, detail="token expired")
    return str(token_info["username"])


def _require_same_target(path_username: str, path_device_id: str, path_session_id: str, body_username: str, body_device_id: str, body_session_id: str) -> None:
    if (path_username, path_device_id, path_session_id) != (body_username, body_device_id, body_session_id):
        raise HTTPException(status_code=400, detail="request body target does not match URL target")


def _session_key(username: str, device_id: str, session_id: str) -> tuple[str, str, str]:
    return username, device_id, session_id


def _session_record(state: BridgeState, username: str, device_id: str, session_id: str) -> dict[str, Any]:
    return state.sessions.setdefault(
        _session_key(username, device_id, session_id),
        {"username": username, "device_id": device_id, "session_id": session_id},
    )


def create_app(settings: BridgeSettings | None = None, zenoh_session: Any | None = None) -> FastAPI:
    settings = settings or BridgeSettings.from_env()
    state = BridgeState()
    zenoh = zenoh_session or open_session(settings.connect)
    subscriptions: list[Any] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        subscriptions.extend([
            subscribe(zenoh, "u/*/fleet/*/status", ingest),
            subscribe(zenoh, "u/*/fleet/*/sessions/*/state", ingest),
            subscribe(zenoh, "u/*/fleet/*/sessions/*/results/*", ingest),
            subscribe(zenoh, "u/*/fleet/*/sessions/*/events/*", ingest),
        ])
        try:
            yield
        finally:
            for sub in subscriptions:
                if hasattr(sub, "undeclare"):
                    sub.undeclare()
            if hasattr(zenoh, "close"):
                zenoh.close()

    app = FastAPI(title="zfc-bridge-api", version=__version__, lifespan=lifespan)

    def ingest(sample: Any) -> None:
        key = str(sample.key_expr)
        username, device_id, session_id, tail = _parse_key(key)
        if not username or not device_id:
            return
        payload_text = _payload_text(sample)
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = payload_text
        if tail == "status":
            device = {"username": username, "device_id": device_id}
            if isinstance(payload, dict):
                device.update(payload)
            else:
                device["status"] = payload
            state.devices[(username, device_id)] = device
            return
        if tail == "state" and session_id:
            session = _session_record(state, username, device_id, session_id)
            if isinstance(payload, dict):
                session.update(payload)
            else:
                session["state"] = payload
            state.sessions[(username, device_id, session_id)] = session
            return
        if session_id and tail and tail.startswith("results/"):
            session = _session_record(state, username, device_id, session_id)
            session.setdefault("results", {})[tail.removeprefix("results/")] = payload
            return
        if session_id and tail and tail.startswith("events/"):
            session = _session_record(state, username, device_id, session_id)
            events = session.setdefault("events", [])
            events.append(payload)
            if len(events) > MAX_SESSION_EVENTS:
                del events[: len(events) - MAX_SESSION_EVENTS]
            return

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/auth/login")
    def login(req: LoginRequest) -> dict[str, Any]:
        password = settings.users.get(req.username)
        if password is None or not verify_password(req.password, password):
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = mint_token(req.username, settings.token_ttl_seconds)
        state.tokens[str(token["access_token"])] = {"username": req.username, "expires_at": token["expires_at"]}
        return token

    @app.get("/v1/sessions/{username}/{device_id}/{session_id}")
    def read_session(username: str, device_id: str, session_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        caller = _require_token(state, authorization)
        if caller != username:
            raise HTTPException(status_code=403, detail="forbidden")
        key = (username, device_id, session_id)
        session = state.sessions.get(key)
        if session:
            return session
        return {"username": username, "device_id": device_id, "session_id": session_id, "state": "unknown"}

    @app.get("/v1/devices")
    def list_devices(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        username = _require_token(state, authorization)
        devices = []
        for (user, device_id), info in state.devices.items():
            if user != username:
                continue
            devices.append(info)
        return {"items": devices}

    @app.post("/v1/sessions/{username}/{device_id}/{session_id}/commands")
    def send_command(username: str, device_id: str, session_id: str, req: CommandRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        caller = _require_token(state, authorization)
        if caller != username:
            raise HTTPException(status_code=403, detail="forbidden")
        _require_same_target(username, device_id, session_id, req.username, req.device_id, req.session_id)
        payload = {
            "version": "v1",
            "username": username,
            "device_id": device_id,
            "session_id": session_id,
            "cmd_id": f"cmd_{uuid.uuid4().hex}",
            "type": req.type,
            "payload": req.payload,
            "created_at": int(time.time()),
            "timeout_ms": 600000,
            "requires_approval": False,
        }
        _session_record(state, username, device_id, session_id)["last_command"] = payload
        put_json(zenoh, f"u/{username}/fleet/{device_id}/sessions/{session_id}/commands/{payload['cmd_id']}", json.dumps(payload, ensure_ascii=False))
        return payload

    @app.post("/v1/sessions/{username}/{device_id}/{session_id}/control")
    def send_control(username: str, device_id: str, session_id: str, req: ControlRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        caller = _require_token(state, authorization)
        if caller != username:
            raise HTTPException(status_code=403, detail="forbidden")
        _require_same_target(username, device_id, session_id, req.username, req.device_id, req.session_id)
        target_cmd_id = req.payload.get("cmd_id") if isinstance(req.payload, dict) else None
        cmd_id = req.cmd_id or (target_cmd_id if req.type == "approval_response" else None) or f"ctl_{uuid.uuid4().hex}"
        payload = {
            "version": "v1",
            "username": username,
            "device_id": device_id,
            "session_id": session_id,
            "cmd_id": cmd_id,
            "type": req.type,
            "payload": req.payload,
            "timestamp": int(time.time()),
        }
        _session_record(state, username, device_id, session_id)["last_control"] = payload
        put_json(zenoh, f"u/{username}/fleet/{device_id}/sessions/{session_id}/control/{cmd_id}", json.dumps(payload, ensure_ascii=False))
        return payload

    @app.get("/v1/sessions/{username}/{device_id}/{session_id}/events")
    def read_events(username: str, device_id: str, session_id: str, after_seq: int = 0, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        caller = _require_token(state, authorization)
        if caller != username:
            raise HTTPException(status_code=403, detail="forbidden")
        session = state.sessions.get(_session_key(username, device_id, session_id), {})
        raw_events = session.get("events", [])
        events = []
        for event in raw_events if isinstance(raw_events, list) else []:
            if not isinstance(event, dict):
                events.append(event)
                continue
            seq = event.get("seq")
            if isinstance(seq, int) and seq <= after_seq:
                continue
            events.append(event)
        return {
            "username": username,
            "device_id": device_id,
            "session_id": session_id,
            "items": events,
            "results": session.get("results", {}),
        }

    @app.get("/v1/sessions/{username}/{device_id}/{session_id}/directory")
    def read_directory(username: str, device_id: str, session_id: str, path: str = ".", authorization: str | None = Header(default=None)) -> dict[str, Any]:
        caller = _require_token(state, authorization)
        if caller != username:
            raise HTTPException(status_code=403, detail="forbidden")
        replies = zenoh_get(zenoh, f"u/{username}/fleet/{device_id}/directory", payload=json.dumps({"path": path}), timeout=10)
        for reply in replies:
            if reply.ok:
                return json.loads(reply.ok.payload.to_string())
        raise HTTPException(status_code=502, detail="directory query failed")

    web_dir = Path(__file__).resolve().parents[3] / "web"
    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="zenoh-fleet-control HTTP bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--ssl-certfile")
    parser.add_argument("--ssl-keyfile")
    args = parser.parse_args()
    settings = BridgeSettings.from_env()
    settings = BridgeSettings(
        users=settings.users,
        token_ttl_seconds=settings.token_ttl_seconds,
        connect=settings.connect,
        host=args.host,
        port=args.port,
        ssl_certfile=args.ssl_certfile or settings.ssl_certfile,
        ssl_keyfile=args.ssl_keyfile or settings.ssl_keyfile,
    )
    import uvicorn

    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        ssl_certfile=settings.ssl_certfile,
        ssl_keyfile=settings.ssl_keyfile,
    )


if __name__ == "__main__":
    main()
