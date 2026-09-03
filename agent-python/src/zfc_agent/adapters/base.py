from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class AdapterContext:
    cwd: Path
    timeout_ms: int | None = None
    native_session_id: str | None = None
    cancel_event: threading.Event | None = None


@dataclass(frozen=True)
class ToolEvent:
    kind: str
    content: dict[str, Any]


class ToolAdapter(Protocol):
    name: str
    capabilities: list[str]

    async def run(self, payload: dict[str, Any], context: AdapterContext) -> AsyncIterator[ToolEvent]:
        ...
