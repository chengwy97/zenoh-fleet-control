from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .base import AdapterContext, ToolEvent


class ClaudeAdapter:
    name = "claude"
    capabilities = ["planned", "non_interactive_run", "json_stream", "cwd"]

    async def run(self, payload: dict[str, Any], context: AdapterContext) -> AsyncIterator[ToolEvent]:
        yield ToolEvent("error", {
            "code": "adapter_not_implemented",
            "message": "Claude adapter is reserved but not implemented in the first prototype",
            "retryable": False,
        })
