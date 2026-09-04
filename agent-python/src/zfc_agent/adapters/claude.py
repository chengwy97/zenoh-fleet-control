from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .base import AdapterContext, ToolEvent


class ClaudeAdapter:
    name = "claude"
    capabilities = ["non_interactive_run", "json_output", "cwd", "resume", "cancel"]

    async def run(self, payload: dict[str, Any], context: AdapterContext) -> AsyncIterator[ToolEvent]:
        prompt = payload.get("prompt")
        if not prompt:
            yield ToolEvent("error", {"code": "empty_prompt", "message": "payload.prompt is required", "retryable": False})
            return

        claude = shutil.which("claude")
        if not claude:
            yield ToolEvent("error", {
                "code": "claude_not_installed",
                "message": "claude CLI is not available on this machine",
                "retryable": False,
            })
            yield ToolEvent("adapter_result", {"exit_code": None, "status": "failed"})
            return

        media = payload.get("media") or []
        attachment_notes: list[str] = []
        for item in media:
            media_type = item.get("media_type", "")
            path = item.get("local_path") or item.get("path")
            description = item.get("description") or "no additional instruction"
            if not path:
                continue
            if media_type.startswith("image/"):
                attachment_notes.append(f"[image] path={path}; instruction={description}")
            elif media_type.startswith("video/"):
                attachment_notes.append(f"[video] path={path}; instruction={description}; frame_extraction=agent_decision")
            elif media_type.startswith("audio/"):
                attachment_notes.append(f"[audio] path={path}; instruction={description}; transcription=agent_decision")
            else:
                attachment_notes.append(f"[file] media_type={media_type}; path={path}; instruction={description}")

        full_prompt = prompt
        if attachment_notes:
            full_prompt += "\n\nAttachments available on the agent filesystem:\n" + "\n".join(attachment_notes)

        args = [claude, "-p", full_prompt, "--output-format", "json"]
        if context.native_session_id:
            args += ["--resume", context.native_session_id]

        options = payload.get("options") or {}
        allowed_tools = options.get("allowed_tools") or options.get("allowedTools")
        if allowed_tools:
            if isinstance(allowed_tools, list):
                allowed_tools = ",".join(str(item) for item in allowed_tools)
            args += ["--allowedTools", str(allowed_tools)]

        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(context.cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if stderr_text:
            yield ToolEvent("stderr", {"text": stderr_text})

        if context.cancel_event and context.cancel_event.is_set():
            yield ToolEvent("error", {"code": "cancelled", "message": "claude task cancelled", "retryable": False})
            yield ToolEvent("adapter_result", {"exit_code": None, "status": "cancelled"})
            return

        if proc.returncode != 0:
            yield ToolEvent("error", {
                "code": "claude_failed",
                "message": stderr_text or f"claude exited with {proc.returncode}",
                "retryable": False,
            })
            yield ToolEvent("adapter_result", {"exit_code": proc.returncode, "status": "failed"})
            return

        output = self._parse_output(stdout)
        session_id = output.get("session_id") or output.get("conversation_id")
        if session_id:
            yield ToolEvent("message", {"text": "claude session started", "session_id": session_id, "raw": output})
        message = output.get("result") or output.get("content") or output.get("text")
        if isinstance(message, list):
            message = "\n".join(str(item) for item in message)
        if message:
            yield ToolEvent("message", {"text": str(message), "raw": output})
        else:
            yield ToolEvent("progress", {"text": "claude finished", "raw": output})
        yield ToolEvent("adapter_result", {"exit_code": proc.returncode, "status": "succeeded", "session_id": session_id})

    def _parse_output(self, stdout: bytes) -> dict[str, Any]:
        text = stdout.decode("utf-8", errors="replace").strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
