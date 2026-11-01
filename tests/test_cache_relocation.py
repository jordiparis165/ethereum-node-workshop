import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux cache ownership tests')
class CacheRelocationTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            'cache_move', Path(__file__).resolve().parents[1] / 'scripts/relocate-build-caches.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / 'source'
        self.target = Path(self.directory.name) / 'target'
        self.source.mkdir()
        (self.source / 'file').write_bytes(b'preserve this content')
        self.patcher = patch.object(self.module.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024**4))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_verified_move_preserves_original_path_and_content(self):
        self.module.relocate(self.source, self.target)
        self.assertTrue(self.source.is_symlink())
        self.assertEqual((self.source / 'file').read_bytes(), b'preserve this content')
        self.assertEqual((self.target / 'file').read_bytes(), b'preserve this content')

    def test_mismatched_copy_never_replaces_source(self):
        with patch.object(self.module, 'digest', side_effect=['original', 'different']):
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                self.module.relocate(self.source, self.target)
        self.assertFalse(self.source.is_symlink())
        self.assertEqual((self.source / 'file').read_bytes(), b'preserve this content')
