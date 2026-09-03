from __future__ import annotations

import argparse
import time
import uuid

from zfc_agent.keyspace import Keyspace
from zfc_agent.models import to_json
from zfc_agent.zenoh_client import open_session, put_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a control message to a zfc session")
    parser.add_argument("--username", default="eame")
    parser.add_argument("--device-id", default="dev_local")
    parser.add_argument("--session-id", default="sess_local")
    parser.add_argument("--type", choices=["cancel", "end_session"], required=True)
    parser.add_argument("--cmd-id")
    parser.add_argument("--connect")
    args = parser.parse_args()

    cmd_id = args.cmd_id or f"ctl_{uuid.uuid4().hex}"
    keyspace = Keyspace(args.username, args.device_id, args.session_id)
    session = open_session(args.connect)
    put_json(session, keyspace.control_message(cmd_id), to_json({
        "version": "v1",
        "username": args.username,
        "device_id": args.device_id,
        "session_id": args.session_id,
        "cmd_id": args.cmd_id,
        "type": args.type,
        "timestamp": int(time.time()),
    }))
    # Keep the session alive briefly so the local validation publisher flushes the control sample.
    time.sleep(0.2)
    print(cmd_id)
    if hasattr(session, "close"):
        session.close()


if __name__ == "__main__":
    main()
