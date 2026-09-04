from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent-python" / "src"))

from zfc_agent.adapters.claude import ClaudeAdapter


class ClaudeAdapterTest(unittest.TestCase):
    def test_parse_output(self) -> None:
        adapter = ClaudeAdapter()
        parsed = adapter._parse_output(b'{"session_id":"sess_123","result":"hello"}')
        self.assertEqual(parsed["session_id"], "sess_123")
        self.assertEqual(parsed["result"], "hello")


if __name__ == "__main__":
    unittest.main()
