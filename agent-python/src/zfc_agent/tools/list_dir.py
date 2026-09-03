from __future__ import annotations

import argparse
import json

from zfc_agent.keyspace import Keyspace
from zfc_agent.zenoh_client import open_session


def main() -> None:
    parser = argparse.ArgumentParser(description="Query a directory from a zfc agent")
    parser.add_argument("--username", default="eame")
    parser.add_argument("--device-id", default="dev_local")
    parser.add_argument("--path", default=".")
    parser.add_argument("--connect")
    args = parser.parse_args()
    session = open_session(args.connect)
    keyspace = Keyspace(args.username, args.device_id, "directory")
    replies = session.get(keyspace.directory_queryable, payload=json.dumps({"path": args.path}), timeout=10)
    for reply in replies:
        if reply.ok:
            print(reply.ok.payload.to_string())
        elif reply.err:
            print(reply.err.payload.to_string())
    if hasattr(session, "close"):
        session.close()


if __name__ == "__main__":
    main()
