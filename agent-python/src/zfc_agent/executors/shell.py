from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ShellLine:
    stream: str
    text: str


async def stream_shell(command: str, cwd: Path, timeout_ms: int | None = None) -> tuple[int, AsyncIterator[ShellLine]]:
    raise NotImplementedError("use iter_shell instead")


async def iter_shell(command: str, cwd: Path, timeout_ms: int | None = None) -> AsyncIterator[ShellLine | int]:
    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    queue: asyncio.Queue[ShellLine | int | BaseException | None] = asyncio.Queue()

    async def collect(stream, name: str) -> None:
        while True:
            raw = await stream.readline()
            if not raw:
                break
            await queue.put(ShellLine(name, raw.decode("utf-8", errors="replace").rstrip("\n")))

    async def wait_process() -> None:
        try:
            if timeout_ms:
                await asyncio.wait_for(proc.wait(), timeout_ms / 1000)
            else:
                await proc.wait()
            await queue.put(proc.returncode or 0)
        except TimeoutError as exc:
            proc.kill()
            await proc.wait()
            await queue.put(exc)

    tasks = [
        asyncio.create_task(collect(proc.stdout, "stdout")),
        asyncio.create_task(collect(proc.stderr, "stderr")),
        asyncio.create_task(wait_process()),
    ]
    try:
        while True:
            item = await queue.get()
            if isinstance(item, BaseException):
                raise item
            yield item
            if isinstance(item, int):
                break
    finally:
        await asyncio.gather(*tasks, return_exceptions=True)
