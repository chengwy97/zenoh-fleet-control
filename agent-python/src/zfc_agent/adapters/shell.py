from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from zfc_agent.executors.shell import ShellLine, iter_shell

from .base import AdapterContext, ToolEvent


class ShellAdapter:
    name = "shell"
    capabilities = ["non_interactive_run", "stdout", "stderr", "cwd"]

    async def run(self, payload: dict[str, Any], context: AdapterContext) -> AsyncIterator[ToolEvent]:
        command = payload.get("command")
        if not command:
            yield ToolEvent("error", {"code": "empty_command", "message": "payload.command is required", "retryable": False})
            return

        exit_code = 0
        line_count = 0
        async for item in iter_shell(command, context.cwd, context.timeout_ms):
            if isinstance(item, ShellLine):
                line_count += 1
                yield ToolEvent(item.stream, {"text": item.text})
            else:
                exit_code = item
        yield ToolEvent("adapter_result", {"exit_code": exit_code, "line_count": line_count})
