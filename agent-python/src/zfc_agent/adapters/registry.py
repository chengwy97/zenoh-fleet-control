from __future__ import annotations

from .claude import ClaudeAdapter
from .codex import CodexExecAdapter
from .shell import ShellAdapter


class ToolAdapterRegistry:
    def __init__(self) -> None:
        adapters = [ShellAdapter(), CodexExecAdapter(), ClaudeAdapter()]
        self._adapters = {adapter.name: adapter for adapter in adapters}

    def get(self, name: str):
        return self._adapters.get(name)

    def capabilities(self) -> dict[str, list[str]]:
        return {name: adapter.capabilities for name, adapter in self._adapters.items()}
