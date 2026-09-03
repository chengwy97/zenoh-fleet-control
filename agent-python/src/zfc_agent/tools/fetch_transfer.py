from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

from zfc_agent.keyspace import Keyspace
from zfc_agent.models import from_payload, to_json
from zfc_agent.transfer import backend_from_config, ref_from_dict
from zfc_agent.zenoh_client import open_session, put_json, subscribe


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a file or directory from a zfc agent and unpack it locally")
    parser.add_argument("--username", default="eame")
    parser.add_argument("--device-id", default="dev_local")
    parser.add_argument("--session-id", default="sess_local")
    parser.add_argument("--path", default=".")
    parser.add_argument("--output-dir", required=True)
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
    cmd_id = f"cmd_{uuid.uuid4().hex}"
    keyspace = Keyspace(args.username, args.device_id, args.session_id)
    session = open_session(args.connect)
    result_holder: dict[str, dict] = {}

    def on_result(sample) -> None:
        data = from_payload(sample.payload)
        if data.get("cmd_id") == cmd_id:
            result_holder["result"] = data

    sub = subscribe(session, keyspace.result(cmd_id), on_result)
    put_json(session, keyspace.command(cmd_id), to_json({
        "version": "v1",
        "username": args.username,
        "device_id": args.device_id,
        "session_id": args.session_id,
        "cmd_id": cmd_id,
        "type": "export_transfer",
        "payload": {"path": args.path},
        "created_at": int(time.time()),
        "timeout_ms": 600000,
        "requires_approval": False,
    }))

    deadline = time.time() + 30
    while time.time() < deadline and "result" not in result_holder:
        time.sleep(0.1)
    if hasattr(sub, "undeclare"):
        sub.undeclare()
    if hasattr(session, "close"):
        session.close()
    result = result_holder.get("result")
    if not result:
        raise SystemExit("timed out waiting for export result")
    if result.get("status") != "succeeded":
        raise SystemExit(json.dumps(result, ensure_ascii=False))
    transfer = ref_from_dict(result["output"]["transfer"])
    output = backend.materialize(transfer, Path(args.output_dir))
    print(cmd_id)
    print(transfer.transfer_id)
    print(output)


if __name__ == "__main__":
    main()
