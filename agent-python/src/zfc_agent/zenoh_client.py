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


def put_bytes(session, key: str, payload: bytes) -> None:
    session.put(key, payload)


def subscribe(session, keyexpr: str, callback: Callable) -> object:
    return session.declare_subscriber(keyexpr, callback)


def declare_queryable(session, keyexpr: str, callback: Callable) -> object:
    return session.declare_queryable(keyexpr, callback)
