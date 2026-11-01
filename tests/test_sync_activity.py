import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sync_activity import activity_state, activity_rates


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

    def test_resource_rates_use_elapsed_time(self):
        old = self.sample()
        now = self.sample(cpu=110)
        old['observed_at'] = '2026-11-01T12:00:00+00:00'
        now['observed_at'] = '2026-11-01T12:00:10+00:00'
        now['activity']['clock_ticks_per_second'] = 100
        old['activity']['disks'] = {'sdb': dict(reads=0, read_sectors=0, read_ms=0,
                                                writes=0, write_sectors=0, write_ms=0, busy_ms=0)}
        now['activity']['disks'] = {'sdb': dict(reads=20, read_sectors=20480, read_ms=400,
                                                writes=0, write_sectors=0, write_ms=0, busy_ms=5000)}
        result = activity_rates(now, old)
        self.assertEqual(result['process_cpu_percent_one_core'], 10)
        self.assertEqual(result['disks']['sdb']['iops'], 2)
        self.assertEqual(result['disks']['sdb']['average_request_ms'], 20)
        self.assertEqual(result['disks']['sdb']['read_mib_per_second'], 1)
        self.assertEqual(result['disks']['sdb']['busy_percent'], 50)

    def test_counter_reset_is_not_a_negative_disk_rate(self):
        old, now = self.sample(), self.sample()
        old['observed_at'], now['observed_at'] = '2026-11-01T12:00:00+00:00', '2026-11-01T12:01:00+00:00'
        old['activity']['disks'] = {'sda': {'reads': 100}}
        now['activity']['disks'] = {'sda': {'reads': 0}}
        self.assertEqual(activity_rates(now, old)['disks'], {})
