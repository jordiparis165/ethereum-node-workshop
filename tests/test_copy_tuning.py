import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class CopyTuningTests(unittest.TestCase):
    def setUp(self):
        script = Path(__file__).resolve().parents[1] / "scripts/tune-storage-copy.py"
        spec = importlib.util.spec_from_file_location("tuning", script)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.module.QUEUE = Path(temporary.name) / "read_ahead_kb"
        self.module.QUEUE.write_text("128\n")
        self.module.STATUS = Path(temporary.name) / "status.json"
        self.module.FAST_CHAIN = Path(temporary.name) / "chaindata"

    def test_restores_read_ahead_after_migration_finishes(self):
        m = self.module
        with patch.object(m, "active", side_effect=[True, False, False]), patch.object(
            m.subprocess, "check_output", return_value="2147483648\n"
        ), patch.object(m.subprocess, "run"), patch.object(m.signal, "signal"):
            m.main()
        self.assertEqual(m.QUEUE.read_text().strip(), "128")
        self.assertEqual(json.loads(m.STATUS.read_text())["phase"], "restored")

    def test_interruption_also_restores_cache_limit(self):
        m = self.module
        with patch.object(m, "active", return_value=True), patch.object(
            m.subprocess, "check_output", return_value="2147483648\n"
        ), patch.object(m.subprocess, "run") as commands, patch.object(
            m.signal, "signal"
        ), patch.object(m.time, "sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                m.main()
        self.assertEqual(m.QUEUE.read_text().strip(), "128")
        self.assertEqual(commands.call_args.args[0][-1], "MemoryMax=2147483648")

    def test_restores_before_node_reopens_database(self):
        m = self.module
        m.FAST_CHAIN.mkdir()
        with patch.object(m, "active", return_value=True), patch.object(
            m.subprocess, "check_output", return_value="2147483648\n"
        ), patch.object(m.subprocess, "run") as commands, patch.object(m.signal, "signal"):
            m.main()
        self.assertEqual(m.QUEUE.read_text().strip(), "128")
        self.assertEqual(commands.call_args.args[0][-1], "MemoryMax=2147483648")


if __name__ == "__main__":
    unittest.main()
