from __future__ import annotations

import argparse
import hashlib
import math
import mimetypes
from pathlib import Path
import time
import uuid

from zfc_agent.keyspace import Keyspace
from zfc_agent.media import MediaManifest
from zfc_agent.models import to_json
from zfc_agent.transfer import backend_from_config
from zfc_agent.zenoh_client import open_session, put_bytes, put_json

CHUNK_SIZE = 256 * 1024


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload real binary media to a zfc session and return an asset_id for chat attachments")
    parser.add_argument("--username", default="eame")
    parser.add_argument("--device-id", default="dev_local")
    parser.add_argument("--session-id", default="sess_local")
    parser.add_argument("--path", required=True)
    parser.add_argument("--description")
    parser.add_argument("--transfer-backend", default="zenoh_chunks", choices=["zenoh_chunks", "local_spool", "s3", "minio"] )
    parser.add_argument("--transfer-store", default=".zfc/client-transfers")
    parser.add_argument("--file-api-url")
    parser.add_argument("--file-api-token")
    parser.add_argument("--connect")
    args = parser.parse_args()

    source = Path(args.path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise SystemExit(f"media file not found: {source}")

    asset_id = f"asset_{uuid.uuid4().hex}"
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    keyspace = Keyspace(args.username, args.device_id, args.session_id)
    session = open_session(args.connect)

    transfer = None
    chunk_count = 0
    if args.transfer_backend == "zenoh_chunks":
        chunk_count = math.ceil(len(data) / CHUNK_SIZE) or 1
        for index in range(chunk_count):
            chunk = data[index * CHUNK_SIZE:(index + 1) * CHUNK_SIZE]
            put_bytes(session, keyspace.media_chunk(asset_id, index), chunk)
    else:
        backend = backend_from_config(
            args.transfer_backend,
            Path(args.transfer_store),
            username=args.username,
            device_id=args.device_id,
            session_id=args.session_id,
            file_api_url=args.file_api_url,
            file_api_token=args.file_api_token,
        )
        transfer = backend.stage_upload(source).to_dict()

    manifest = MediaManifest(
        version="v1",
        username=args.username,
        device_id=args.device_id,
        session_id=args.session_id,
        asset_id=asset_id,
        name=source.name,
        media_type=media_type,
        size=len(data),
        sha256=digest,
        chunk_count=chunk_count,
        transfer=transfer,
        description=args.description,
        created_at=int(time.time()),
    )
    put_json(session, keyspace.media_manifest(asset_id), to_json(manifest.to_dict()))
    time.sleep(0.2)
    print(asset_id)
    if hasattr(session, "close"):
        session.close()


if __name__ == "__main__":
    main()
