from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge-api" / "src"))

from zfc_bridge.config import BridgeSettings
from zfc_bridge.main import create_app


class FakeZenohSession:
    def __init__(self) -> None:
        self.callbacks: dict[str, object] = {}
        self.put_calls: list[tuple[str, str]] = []
        self.closed = False

    def declare_subscriber(self, keyexpr, callback):
        self.callbacks[keyexpr] = callback
        return SimpleNamespace(undeclare=lambda: None)

    def put(self, key, payload):
        self.put_calls.append((key, payload))

    def get(self, keyexpr, payload=None, timeout=10):
        return []

    def close(self):
        self.closed = True


class BridgeApiTest(unittest.TestCase):
    def test_login_device_and_command_flow(self) -> None:
        fake_zenoh = FakeZenohSession()
        app = create_app(
            settings=BridgeSettings(
                users={"eame": "password"},
                token_ttl_seconds=3600,
                connect=None,
                host="127.0.0.1",
                port=8443,
                ssl_certfile=None,
                ssl_keyfile=None,
            ),
            zenoh_session=fake_zenoh,
        )
        client = TestClient(app)

        with client:
            login = client.post("/v1/auth/login", json={"username": "eame", "password": "password"})
            self.assertEqual(login.status_code, 200)
            token = login.json()["access_token"]

            status_cb = fake_zenoh.callbacks["u/*/fleet/*/status"]
            status_cb(SimpleNamespace(key_expr="u/eame/fleet/dev1/status", payload='{"status":"online","cwd":"/home/eame"}'))

            devices = client.get("/v1/devices", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(devices.status_code, 200)
            self.assertEqual(devices.json()["items"][0]["device_id"], "dev1")

            session_cb = fake_zenoh.callbacks["u/*/fleet/*/sessions/*/state"]
            session_cb(SimpleNamespace(key_expr="u/eame/fleet/dev1/sessions/sess1/state", payload='{"state":"running","cwd":"/home/eame"}'))

            session = client.get("/v1/sessions/eame/dev1/sess1", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(session.status_code, 200)
            self.assertEqual(session.json()["session_id"], "sess1")

            event_cb = fake_zenoh.callbacks["u/*/fleet/*/sessions/*/events/*"]
            event_cb(SimpleNamespace(
                key_expr="u/eame/fleet/dev1/sessions/sess1/events/evt1",
                payload='{"seq":1,"kind":"stdout","content":{"text":"hello"}}',
            ))
            events = client.get(
                "/v1/sessions/eame/dev1/sess1/events?after_seq=0",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(events.status_code, 200)
            self.assertEqual(events.json()["items"][0]["content"]["text"], "hello")
            self.assertEqual(
                client.get(
                    "/v1/sessions/eame/dev1/sess1/events?after_seq=1",
                    headers={"Authorization": f"Bearer {token}"},
                ).json()["items"],
                [],
            )
            session_cb(SimpleNamespace(key_expr="u/eame/fleet/dev1/sessions/sess1/state", payload='{"state":"waiting_approval"}'))
            preserved = client.get("/v1/sessions/eame/dev1/sess1/events", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(len(preserved.json()["items"]), 1)

            command = client.post(
                "/v1/sessions/eame/dev1/sess1/commands",
                headers={"Authorization": f"Bearer {token}"},
                json={"username": "eame", "device_id": "dev1", "session_id": "sess1", "type": "run_shell", "payload": {"command": "pwd"}},
            )
            self.assertEqual(command.status_code, 200)
            self.assertTrue(fake_zenoh.put_calls)
            self.assertIn("/commands/", fake_zenoh.put_calls[0][0])

            mismatch = client.post(
                "/v1/sessions/eame/dev1/sess1/commands",
                headers={"Authorization": f"Bearer {token}"},
                json={"username": "other", "device_id": "dev1", "session_id": "sess1", "type": "run_shell"},
            )
            self.assertEqual(mismatch.status_code, 400)

            approval = client.post(
                "/v1/sessions/eame/dev1/sess1/control",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "username": "eame",
                    "device_id": "dev1",
                    "session_id": "sess1",
                    "type": "approval_response",
                    "payload": {"approval_id": "approval_1", "cmd_id": "approval_1", "decision": "approve"},
                },
            )
            self.assertEqual(approval.status_code, 200)
            self.assertEqual(approval.json()["payload"]["decision"], "approve")
            self.assertEqual(approval.json()["cmd_id"], "approval_1")

            web = client.get("/")
            self.assertEqual(web.status_code, 200)
            self.assertIn("Zenoh Fleet Control", web.text)


if __name__ == "__main__":
    unittest.main()
