from __future__ import annotations

from typing import Callable

import zenoh


def open_session(connect: str | None = None):
    config = zenoh.Config()
    if connect:
        config.insert_json5("connect/endpoints", f'["{connect}"]')
    return zenoh.open(config)


def put_json(session, key: str, payload: str) -> None:
    session.put(key, payload)


def subscribe(session, keyexpr: str, callback: Callable) -> object:
    return session.declare_subscriber(keyexpr, callback)


def get(session, keyexpr: str, payload: str | None = None, timeout: int = 10):
    return session.get(keyexpr, payload=payload, timeout=timeout)
