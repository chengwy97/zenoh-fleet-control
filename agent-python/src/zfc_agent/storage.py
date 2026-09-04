from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ToolSession:
    native_session_id: str
    updated_at: int


@dataclass
class PendingCommand:
    command: dict
    queued_at: int


@dataclass
class PersistedSession:
    session_id: str
    cwd: str
    tools: dict[str, ToolSession] = field(default_factory=dict)
    pending_commands: list[PendingCommand] = field(default_factory=list)


class SessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = threading.Lock()

    def load(self, session_id: str, cwd: Path) -> PersistedSession:
        path = self._path(session_id)
        with self._lock:
            if not path.exists():
                return PersistedSession(session_id=session_id, cwd=str(cwd))
            data = json.loads(path.read_text(encoding="utf-8"))
        return PersistedSession(
            session_id=data["session_id"],
            cwd=data["cwd"],
            tools={name: ToolSession(**value) for name, value in data.get("tools", {}).items()},
            pending_commands=[PendingCommand(**item) for item in data.get("pending_commands", [])],
        )

    def save(self, session: PersistedSession) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._path(session.session_id).write_text(
                json.dumps(asdict(session), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._path(session_id).unlink(missing_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.json"
