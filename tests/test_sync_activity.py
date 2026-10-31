import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sync_activity import activity_state


class ActivityTests(unittest.TestCase):
    def sample(self, block='0x10', pid=1, read=100, cpu=10):
        return {'service': 'active', 'block': block,
                'activity': {'process': {'pid': pid, 'read_bytes': read, 'cpu_ticks': cpu}}}

    def test_disk_activity_is_not_declared_deadlock(self):
        self.assertEqual(activity_state(self.sample(read=200), self.sample()),
                         'head_unchanged_process_reading_disk')

    def test_cpu_activity_is_not_declared_deadlock(self):
        self.assertEqual(activity_state(self.sample(cpu=20), self.sample()),
                         'head_unchanged_process_using_cpu')

    def test_validated_head_has_priority(self):
        self.assertEqual(activity_state(self.sample(block='0x11'), self.sample()),
                         'validated_head_advanced')

    def test_restart_resets_baseline(self):
        self.assertEqual(activity_state(self.sample(pid=2), self.sample()),
                         'collecting_activity_samples')

    def test_no_activity_does_not_authorize_restart(self):
        self.assertEqual(activity_state(self.sample(), self.sample()),
                         'no_activity_in_sample_inspect_before_restart')
