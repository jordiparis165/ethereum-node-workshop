import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'memory_safety', Path(__file__).resolve().parents[1] / 'scripts/configure-memory-safety.py'
)
safety = importlib.util.module_from_spec(spec)
spec.loader.exec_module(safety)


class MemorySafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'swap'
        for patcher in (patch.object(safety, 'SWAP', self.path),
                        patch.object(safety, 'SIZE', 1024),
                        patch.object(safety.os, 'geteuid', return_value=0, create=True)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_low_disk_space_refuses_creation(self):
        with patch.object(safety.shutil, 'disk_usage', return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(RuntimeError, 'Insufficient space'):
                safety.main()
        self.assertFalse(self.path.exists())

    def test_unknown_existing_file_is_not_overwritten(self):
        self.path.write_bytes(b'important')
        with self.assertRaisesRegex(RuntimeError, 'unexpected type or size'):
            safety.main()
        self.assertEqual(self.path.read_bytes(), b'important')

    def test_existing_non_swap_file_is_rejected(self):
        self.path.write_bytes(b'x' * 1024)
        with patch.object(safety.subprocess, 'check_output', return_value='ext4\n'):
            with self.assertRaisesRegex(RuntimeError, 'not initialized swap'):
                safety.main()
        self.assertEqual(self.path.read_bytes(), b'x' * 1024)

    def test_initialized_swap_is_reused_without_formatting(self):
        self.path.write_bytes(b'x' * 1024)
        with patch.object(safety.subprocess, 'check_output', return_value='swap\n'), \
                patch.object(safety.subprocess, 'run') as run:
            safety.main()
        commands = [call.args[0][0] for call in run.call_args_list]
        self.assertNotIn('mkswap', commands)
        self.assertNotIn('fallocate', commands)
        self.assertIn('systemctl', commands)
