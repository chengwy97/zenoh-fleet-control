from __future__ import annotations

import hashlib
import hmac
import secrets
import time


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, stored_password: str) -> bool:
    return hmac.compare_digest(hash_password(password), hash_password(stored_password))


def mint_token(username: str, ttl_seconds: int) -> dict[str, str | int]:
    issued_at = int(time.time())
    return {
        "access_token": f"zfc_{username}_{secrets.token_hex(16)}",
        "token_type": "bearer",
        "expires_at": issued_at + ttl_seconds,
    }
