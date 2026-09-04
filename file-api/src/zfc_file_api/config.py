from __future__ import annotations

import os
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    endpoint_url: str
    access_key: str
    secret_key: str
    bucket: str
    region: str
    public_base_url: str
    auth_token: str
    user_tokens: dict[str, str]
    device_tokens: dict[str, str]
    url_expires_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        def parse_tokens(name: str) -> dict[str, str]:
            raw = os.getenv(name, "")
            if not raw:
                return {}
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError(f"{name} must be a JSON object")
            return {str(key): str(value) for key, value in data.items()}

        return cls(
            endpoint_url=os.getenv("ZFC_S3_ENDPOINT", "http://127.0.0.1:9000"),
            access_key=os.getenv("ZFC_S3_ACCESS_KEY", "zfcadmin"),
            secret_key=os.getenv("ZFC_S3_SECRET_KEY", "zfcadmin123"),
            bucket=os.getenv("ZFC_S3_BUCKET", "zfc-transfers"),
            region=os.getenv("ZFC_S3_REGION", "us-east-1"),
            public_base_url=os.getenv("ZFC_FILE_PUBLIC_BASE_URL", "http://127.0.0.1:9000"),
            auth_token=os.getenv("ZFC_FILE_AUTH_TOKEN", "dev-token-change-me"),
            user_tokens=parse_tokens("ZFC_FILE_USER_TOKENS"),
            device_tokens=parse_tokens("ZFC_FILE_DEVICE_TOKENS"),
            url_expires_seconds=int(os.getenv("ZFC_FILE_URL_EXPIRES_SECONDS", "900")),
        )
