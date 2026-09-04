from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent-python" / "src"))

from zfc_agent.transfer import LocalSpoolTransferBackend


class TransferProgressTest(unittest.TestCase):
    def test_local_spool_emits_archive_and_extract_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "a.txt").write_text("a", encoding="utf-8")
            (source / "b.txt").write_text("b", encoding="utf-8")

            backend = LocalSpoolTransferBackend(root / "spool")
            events: list[tuple[str, dict]] = []
            ref = backend.stage_upload(source, progress=lambda phase, content: events.append((phase, dict(content))))

            self.assertTrue(any(phase == "archive_started" for phase, _ in events))
            self.assertTrue(any(phase == "archive_progress" for phase, _ in events))
            self.assertTrue(any(phase == "archive_completed" for phase, _ in events))

            events.clear()
            destination = backend.import_to_cwd(ref, root / "cwd", "imported", progress=lambda phase, content: events.append((phase, dict(content))))

            self.assertEqual(destination, (root / "cwd" / "imported").resolve())
            self.assertTrue(any(phase == "download_started" for phase, _ in events))
            self.assertTrue(any(phase == "extract_started" for phase, _ in events))
            self.assertTrue(any(phase == "extract_progress" for phase, _ in events))
            self.assertTrue(any(phase == "extract_completed" for phase, _ in events))


if __name__ == "__main__":
    unittest.main()
