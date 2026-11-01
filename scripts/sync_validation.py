"""Qualify final synchronization with independent, repeated observations."""
from datetime import datetime


def candidate(status):
    reference = status.get('reference') or {}
    age = status.get('head_age_seconds')
    ref_age = reference.get('head_age_seconds')
    gap = reference.get('remaining_blocks')
    return (status.get('service') == 'active' and status.get('eth_syncing') is False
            and int(status.get('block', '0x0'), 16) > 0
            and isinstance(age, (int, float)) and 0 <= age <= 120
            and isinstance(ref_age, (int, float)) and 0 <= ref_age <= 90
            and isinstance(gap, int) and 0 <= gap <= 4
            and reference.get('local_block_hash_matches') is True and not status.get('errors'))


class Qualification:
    def __init__(self):
        self.samples = []

    def observe(self, status):
        if not candidate(status):
            self.samples.clear()
            return False
        self.samples.append({key: value for key, value in status.items() if key != 'qualification_samples'})
        self.samples = self.samples[-3:]
        if len(self.samples) < 3:
            return False
        elapsed = (datetime.fromisoformat(self.samples[-1]['observed_at'])
                   - datetime.fromisoformat(self.samples[0]['observed_at'])).total_seconds()
        heights = [int(sample['block'], 16) for sample in self.samples]
        return elapsed >= 120 and heights == sorted(heights) and heights[-1] > heights[0]
