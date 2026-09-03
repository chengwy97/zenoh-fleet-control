from __future__ import annotations

import argparse
import time
import uuid
from pathlib import Path

from zfc_agent.keyspace import Keyspace
from zfc_agent.models import to_json
from zfc_agent.transfer import backend_from_config
from zfc_agent.zenoh_client import open_session, put_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a local file or directory to the current zfc session cwd")
    parser.add_argument("--username", default="eame")
    parser.add_argument("--device-id", default="dev_local")
    parser.add_argument("--session-id", default="sess_local")
    parser.add_argument("--path", required=True)
    parser.add_argument("--target-path", default=".")
    parser.add_argument("--transfer-backend", default="local_spool", choices=["local_spool", "tus", "s3", "minio"])
    parser.add_argument("--transfer-store", default=".zfc/client-transfers")
    parser.add_argument("--file-api-url")
    parser.add_argument("--file-api-token")
    parser.add_argument("--connect")
    args = parser.parse_args()

    backend = backend_from_config(
        args.transfer_backend,
        Path(args.transfer_store),
        username=args.username,
        device_id=args.device_id,
        session_id=args.session_id,
        file_api_url=args.file_api_url,
        file_api_token=args.file_api_token,
    )
    transfer = backend.stage_upload(Path(args.path))
    cmd_id = f"cmd_{uuid.uuid4().hex}"
    session = open_session(args.connect)
    keyspace = Keyspace(args.username, args.device_id, args.session_id)
    put_json(session, keyspace.command(cmd_id), to_json({
        "version": "v1",
        "username": args.username,
        "device_id": args.device_id,
        "session_id": args.session_id,
        "cmd_id": cmd_id,
        "type": "import_transfer",
        "payload": {"transfer": transfer.to_dict(), "target_path": args.target_path},
        "created_at": int(time.time()),
        "timeout_ms": 600000,
        "requires_approval": False,
    }))
    time.sleep(0.2)
    print(cmd_id)
    print(transfer.transfer_id)
    if hasattr(session, "close"):
        session.close()


if __name__ == "__main__":
    main()
