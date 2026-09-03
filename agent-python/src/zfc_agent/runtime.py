from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field


@dataclass
class PendingMessage:
    command: dict


@dataclass
class SessionRuntime:
    lock: threading.Lock = field(default_factory=threading.Lock)
    running_cmd_id: str | None = None
    active_tool: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    pending: deque[PendingMessage] = field(default_factory=deque)
    ending: bool = False
