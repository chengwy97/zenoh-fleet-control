from __future__ import annotations

from .config import Settings


def extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    return authorization.removeprefix(prefix).strip() or None


def is_authorized(token: str | None, username: str, device_id: str, settings: Settings) -> bool:
    if not token:
        return False
    if settings.device_tokens.get(f"{username}/{device_id}") == token:
        return True
    if settings.user_tokens.get(username) == token:
        return True
    return token == settings.auth_token
