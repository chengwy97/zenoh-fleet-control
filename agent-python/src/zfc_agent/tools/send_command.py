from __future__ import annotations

import argparse
import time
import uuid

from zfc_agent.keyspace import Keyspace
from zfc_agent.models import to_json
from zfc_agent.zenoh_client import open_session, put_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a command to a zfc agent")
    parser.add_argument("--username", default="eame")
    parser.add_argument("--device-id", default="dev_local")
    parser.add_argument("--session-id", default="sess_local")
    parser.add_argument("--cmd", help="shell command for run_shell")
    parser.add_argument("--tool", choices=["shell", "codex", "claude"], default="shell")
    parser.add_argument("--set-cwd", help="set session cwd using an agent-relative path")
    parser.add_argument("--prompt", help="AI prompt for run_ai")
    parser.add_argument("--media", nargs="*", help="asset_id[=description] for uploaded media attachments")
    parser.add_argument("--connect")
    args = parser.parse_args()

    if args.set_cwd and (args.cmd or args.prompt):
        parser.error("--set-cwd cannot be combined with --cmd or --prompt")
    if not args.set_cwd and args.tool == "shell" and not args.cmd:
        parser.error("--cmd is required when --tool=shell")
    if args.tool != "shell" and not args.prompt:
        parser.error("--prompt is required when using an AI tool")

    cmd_id = f"cmd_{uuid.uuid4().hex}"
    keyspace = Keyspace(args.username, args.device_id, args.session_id)
    session = open_session(args.connect)
    if args.set_cwd:
        command_type = "set_cwd"
        command_payload = {"path": args.set_cwd}
    elif args.tool == "shell":
        command_type = "run_shell"
        command_payload = {"command": args.cmd}
    else:
        command_type = "run_ai"
        media = []
        for item in args.media or []:
            asset_id, *rest = item.split("=", 1)
            media.append({"asset_id": asset_id, "description": rest[0] if rest else None})
        command_payload = {
            "tool": args.tool,
            "prompt": args.prompt,
            "mode": "exec",
            "options": {"sandbox": "workspace-write", "approval": "never"},
            "media": media,
        }

    payload = to_json({
        "version": "v1",
        "username": args.username,
        "device_id": args.device_id,
        "session_id": args.session_id,
        "cmd_id": cmd_id,
        "type": command_type,
        "payload": command_payload,
        "created_at": int(time.time()),
        "timeout_ms": 600000,
        "requires_approval": False,
    })
    put_json(session, keyspace.command(cmd_id), payload)
    time.sleep(0.2)
    print(cmd_id)
    if hasattr(session, "close"):
        session.close()


if __name__ == "__main__":
    main()
