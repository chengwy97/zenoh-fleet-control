from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent-python" / "src"))

from zfc_agent.storage import PendingCommand, PersistedSession, SessionStore, ToolSession


class PendingQueuePersistenceTest(unittest.TestCase):
    def test_session_store_round_trip_includes_pending_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            session = PersistedSession(
                session_id="sess_test",
                cwd="/home/eame",
                tools={"codex": ToolSession(native_session_id="thread_123", updated_at=123)},
                pending_commands=[
                    PendingCommand(command={"cmd_id": "cmd_1", "type": "run_ai"}, queued_at=111),
                    PendingCommand(command={"cmd_id": "cmd_2", "type": "run_ai"}, queued_at=222),
                ],
            )
            store.save(session)

            loaded = store.load("sess_test", Path("/fallback"))

            self.assertEqual(loaded.session_id, "sess_test")
            self.assertEqual(loaded.cwd, "/home/eame")
            self.assertEqual(loaded.tools["codex"].native_session_id, "thread_123")
            self.assertEqual([item.command["cmd_id"] for item in loaded.pending_commands], ["cmd_1", "cmd_2"])


if __name__ == "__main__":
    unittest.main()
