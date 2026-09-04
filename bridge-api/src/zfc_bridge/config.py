from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeSettings:
    users: dict[str, str]
    token_ttl_seconds: int
    connect: str | None
    host: str
    port: int
    ssl_certfile: str | None
    ssl_keyfile: str | None

    @classmethod
    def from_env(cls) -> "BridgeSettings":
        users_raw = os.getenv("ZFC_BRIDGE_USERS", "{}")
        users_data = json.loads(users_raw)
        if not isinstance(users_data, dict):
            raise ValueError("ZFC_BRIDGE_USERS must be a JSON object")
        return cls(
            users={str(key): str(value) for key, value in users_data.items()},
            token_ttl_seconds=int(os.getenv("ZFC_BRIDGE_TOKEN_TTL_SECONDS", "3600")),
            connect=os.getenv("ZFC_CONNECT"),
            host=os.getenv("ZFC_BRIDGE_HOST", "127.0.0.1"),
            port=int(os.getenv("ZFC_BRIDGE_PORT", "8443")),
            ssl_certfile=os.getenv("ZFC_BRIDGE_SSL_CERTFILE"),
            ssl_keyfile=os.getenv("ZFC_BRIDGE_SSL_KEYFILE"),
        )
