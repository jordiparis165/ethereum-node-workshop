import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sync_validation import candidate, Qualification


def sample(minute=0, height=100):
    return {'observed_at': f'2026-11-01T12:{minute:02}:00+00:00', 'service': 'active',
            'eth_syncing': False, 'block': hex(height), 'head_age_seconds': 20, 'errors': [],
            'reference': {'head_age_seconds': 10, 'remaining_blocks': 1, 'local_block_hash_matches': True}}


class ValidationTests(unittest.TestCase):
    def test_stale_head_with_false_syncing_is_not_complete(self):
        status = sample()
        status['head_age_seconds'] = 3600
        self.assertFalse(candidate(status))

    def test_unknown_reference_does_not_prove_sync(self):
        status = sample()
        del status['reference']
        self.assertFalse(candidate(status))

    def test_different_hash_rejected(self):
        status = sample()
        status['reference']['local_block_hash_matches'] = False
        self.assertFalse(candidate(status))

    def test_three_advancing_samples_required(self):
        check = Qualification()
        self.assertFalse(check.observe(sample(0, 100)))
        self.assertFalse(check.observe(sample(1, 105)))
        self.assertTrue(check.observe(sample(2, 110)))

    def test_stagnant_head_rejected(self):
        check = Qualification()
        for minute in range(3):
            self.assertFalse(check.observe(sample(minute)))

    def test_failed_sample_resets_confirmation(self):
        check = Qualification()
        check.observe(sample())
        status = sample(1, 105)
        status['eth_syncing'] = {'currentBlock': '0x69'}
        self.assertFalse(check.observe(status))
        self.assertFalse(check.observe(sample(2, 110)))
