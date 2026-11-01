import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux domain ownership tests')
class DomainPlacementTests(unittest.TestCase):
    def test_new_writes_use_capacity_volume_and_existing_files_are_unchanged(self):
        spec = importlib.util.spec_from_file_location(
            'placement', Path(__file__).resolve().parents[1] / 'scripts/route-domain-writes.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fast, active, domain = root / 'fast', root / 'active', root / 'domain'
            fast.mkdir()
            (fast / 'accounts.kv').write_bytes(b'original state')
            (fast / 'incomplete.tmp').write_bytes(b'unfinished')
            domain.symlink_to(fast, target_is_directory=True)
            module.switch_domain(domain, fast, active)
            self.assertEqual((domain / 'accounts.kv').read_bytes(), b'original state')
            self.assertTrue((domain / 'accounts.kv').is_symlink())
            (domain / 'new-commitment.kv').write_bytes(b'new data')
            self.assertTrue((active / 'new-commitment.kv').exists())
            self.assertFalse((fast / 'new-commitment.kv').exists())
            self.assertFalse((active / 'incomplete.tmp').exists())
            self.assertTrue((fast / 'incomplete.tmp').exists())
