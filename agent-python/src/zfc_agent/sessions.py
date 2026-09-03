from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import SessionState, now_ts


@dataclass
class LocalSession:
    username: str
    device_id: str
    session_id: str
    cwd: Path
    created_at: int
    status: str = "idle"
    active_cmd_id: str | None = None
    ended_at: int | None = None

    @classmethod
    def create(cls, username: str, device_id: str, session_id: str, cwd: Path) -> "LocalSession":
        return cls(username=username, device_id=device_id, session_id=session_id, cwd=cwd, created_at=now_ts())

    def state(self) -> SessionState:
        return SessionState(
            username=self.username,
            device_id=self.device_id,
            session_id=self.session_id,
            cwd=str(self.cwd),
            status=self.status,
            active_cmd_id=self.active_cmd_id,
            created_at=self.created_at,
            ended_at=self.ended_at,
        )
