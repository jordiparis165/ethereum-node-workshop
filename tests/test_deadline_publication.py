import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import watch_until_synced


class DeadlinePublicationTests(unittest.TestCase):
    def test_failed_validation_retries_without_marking_deadline_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'evidence').mkdir()
            with (patch.object(watch_until_synced, 'ROOT', root),
                  patch.object(watch_until_synced, 'capture_safely', return_value=False),
                  patch.object(watch_until_synced, 'publish_current', return_value=False)):
                with self.assertRaises(RuntimeError):
                    watch_until_synced.publish_deadline_snapshot({'observed_at': '2026-11-01T22:30:00Z'})
            self.assertTrue((root / 'evidence/deadline-status.json').exists())
            self.assertFalse((root / '.deadline-published.secret').exists())

    def test_success_marks_deadline_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'evidence').mkdir()
            with (patch.object(watch_until_synced, 'ROOT', root),
                  patch.object(watch_until_synced, 'capture_safely', return_value=False),
                  patch.object(watch_until_synced, 'publish_current', return_value=True)):
                watch_until_synced.publish_deadline_snapshot({'observed_at': '2026-11-01T22:30:00Z'})
            self.assertTrue((root / '.deadline-published.secret').exists())


if __name__ == '__main__':
    unittest.main()
