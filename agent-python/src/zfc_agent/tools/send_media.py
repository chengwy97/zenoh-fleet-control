from __future__ import annotations

import argparse
import base64
import hashlib
import math
import mimetypes
import os
from pathlib import Path
import time
import uuid

from zfc_agent.keyspace import Keyspace
from zfc_agent.media import MediaManifest
from zfc_agent.models import to_json
from zfc_agent.zenoh_client import open_session, put_bytes, put_json

CHUNK_SIZE = 256 * 1024


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload real binary media to a zfc session")
    parser.add_argument("--username", default="eame")
    parser.add_argument("--device-id", default="dev_local")
    parser.add_argument("--session-id", default="sess_local")
    parser.add_argument("--path", required=True)
    parser.add_argument("--description")
    parser.add_argument("--connect")
    args = parser.parse_args()

    source = Path(args.path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise SystemExit(f"media file not found: {source}")

    asset_id = f"asset_{uuid.uuid4().hex}"
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    chunk_count = math.ceil(len(data) / CHUNK_SIZE) or 1
    keyspace = Keyspace(args.username, args.device_id, args.session_id)
    session = open_session(args.connect)

    for index in range(chunk_count):
        chunk = data[index * CHUNK_SIZE:(index + 1) * CHUNK_SIZE]
        put_bytes(session, keyspace.media_chunk(asset_id, index), chunk)

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
        description=args.description,
        created_at=int(time.time()),
    )
    put_json(session, keyspace.media_manifest(asset_id), to_json(manifest.__dict__))
    time.sleep(0.2)
    print(asset_id)
    if hasattr(session, "close"):
        session.close()


if __name__ == "__main__":
    main()
