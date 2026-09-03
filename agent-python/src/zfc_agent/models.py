from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any

PROTOCOL_VERSION = "v1"


def now_ts() -> int:
    return int(time.time())


def to_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def from_payload(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "to_string"):
        raw = payload.to_string()
    elif isinstance(payload, bytes):
        raw = payload.decode("utf-8")
    else:
        raw = str(payload)
    return json.loads(raw)


@dataclass
class DeviceStatus:
    username: str
    device_id: str
    name: str
    platform: str
    status: str
    agent_version: str
    active_session_id: str
    last_seen: int
    capabilities: list[str]
    version: str = PROTOCOL_VERSION

    def json(self) -> str:
        return to_json(asdict(self))


@dataclass
class SessionState:
    username: str
    device_id: str
    session_id: str
    cwd: str
    status: str
    active_cmd_id: str | None
    created_at: int
    ended_at: int | None
    version: str = PROTOCOL_VERSION

    def json(self) -> str:
        return to_json(asdict(self))


@dataclass
class MediaManifest:
    version: str
    username: str
    device_id: str
    session_id: str
    asset_id: str
    name: str
    media_type: str
    size: int
    sha256: str
    chunk_count: int
    description: str | None = None
    created_at: int | None = None

    def json(self) -> str:
        return to_json(asdict(self))
