import sys
import unittest
import tempfile
from unittest.mock import patch
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_reboot import reboot_allowed
import verify_reboot


class RebootGuardTests(unittest.TestCase):
    def test_sync_proof_is_mandatory(self):
        now = datetime.fromisoformat('2026-11-01T15:00:00+01:00')
        end = datetime.fromisoformat('2026-11-01T23:59:00+01:00')
        self.assertFalse(reboot_allowed(now, end, False))

    def test_late_reboot_is_not_allowed(self):
        now = datetime.fromisoformat('2026-11-01T23:00:00+01:00')
        end = datetime.fromisoformat('2026-11-01T23:59:00+01:00')
        self.assertFalse(reboot_allowed(now, end, True))

    def test_qualified_node_with_margin_can_be_tested(self):
        now = datetime.fromisoformat('2026-11-01T20:00:00+01:00')
        end = datetime.fromisoformat('2026-11-01T23:59:00+01:00')
        self.assertTrue(reboot_allowed(now, end, True))

    def test_without_saved_proof_no_ssh_or_reboot_is_attempted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'evidence').mkdir()
            with patch.object(verify_reboot, 'ROOT', root):
                result = verify_reboot.run(lambda client: self.fail('Must not read the server without proof'))
            self.assertEqual(result['stage'], 'not_requested')
            self.assertFalse(result['passed'])
