from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "file-api" / "src"))

from zfc_file_api.auth import extract_bearer, is_authorized
from zfc_file_api.config import Settings


class FileApiAuthTest(unittest.TestCase):
    def test_scoped_tokens_and_legacy_token(self) -> None:
        settings = Settings(
            endpoint_url="http://127.0.0.1:9000",
            access_key="zfcadmin",
            secret_key="zfcadmin123",
            bucket="zfc-transfers",
            region="us-east-1",
            public_base_url="http://127.0.0.1:9000",
            auth_token="legacy-token",
            user_tokens={"eame": "user-token-eame"},
            device_tokens={"eame/dev1": "device-token-dev1"},
            url_expires_seconds=900,
        )

        self.assertEqual(extract_bearer("Bearer abc"), "abc")
        self.assertIsNone(extract_bearer(None))
        self.assertTrue(is_authorized("device-token-dev1", "eame", "dev1", settings))
        self.assertTrue(is_authorized("user-token-eame", "eame", "dev2", settings))
        self.assertTrue(is_authorized("legacy-token", "other", "devX", settings))
        self.assertFalse(is_authorized("wrong-token", "eame", "dev1", settings))


if __name__ == "__main__":
    unittest.main()
