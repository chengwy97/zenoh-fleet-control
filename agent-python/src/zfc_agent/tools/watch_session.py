from __future__ import annotations

import argparse
import time

from zfc_agent.keyspace import Keyspace
from zfc_agent.zenoh_client import open_session, subscribe


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch zfc session events and results")
    parser.add_argument("--username", default="eame")
    parser.add_argument("--device-id", default="dev_local")
    parser.add_argument("--session-id", default="sess_local")
    parser.add_argument("--connect")
    args = parser.parse_args()

    keyspace = Keyspace(args.username, args.device_id, args.session_id)
    session = open_session(args.connect)

    def on_sample(sample) -> None:
        print(f"{sample.key_expr}: {sample.payload}", flush=True)

    subs = [
        subscribe(session, f"{keyspace.session_prefix}/events/*", on_sample),
        subscribe(session, f"{keyspace.session_prefix}/results/*", on_sample),
        subscribe(session, keyspace.session_state, on_sample),
    ]
    print(f"watching {keyspace.session_prefix}", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for sub in subs:
            if hasattr(sub, "undeclare"):
                sub.undeclare()
        if hasattr(session, "close"):
            session.close()


if __name__ == "__main__":
    main()
