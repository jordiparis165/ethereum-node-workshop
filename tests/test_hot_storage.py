"""Exercise cutover and rollback in temporary directories, without systemd calls."""
import importlib.util
import tempfile
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare-hot-storage.py"


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux storage tests")
class HotStorageTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("migration", SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        module = self.module
        module.DATA = root / "data"
        module.HOT = root / "hot"
        module.DOMAIN = module.DATA / "snapshots/domain"
        module.SLOW_DOMAIN = module.DOMAIN.with_name("domain.slow-backup")
        module.CHAIN = module.DATA / "chaindata"
        module.SLOW_CHAIN = module.CHAIN.with_name("chaindata.slow-backup")
        module.OVERRIDE = root / "runtime/stop.conf"
        module.DOMAIN.mkdir(parents=True)
        module.CHAIN.mkdir()
        (module.DOMAIN / "v1.0-accounts.0-1.kv").write_bytes(b"account state" * 100)
        (module.DOMAIN / "v2.0-commitment.0-1.kv").write_bytes(b"commitment" * 100)
        (module.CHAIN / "mdbx.dat").write_bytes(b"database" * 100)

    def run_migration(self, fail_start=False):
        module = self.module

        def command(args, **kwargs):
            if fail_start and args == ["systemctl", "start", "erigon.service"] and kwargs.get("check"):
                raise RuntimeError("Simulated start failure")

        with patch.object(module.subprocess, "run", side_effect=command) as calls:
            with patch.object(module.subprocess, "check_output", return_value="0\n"), patch.object(
                module.shutil, "disk_usage", return_value=SimpleNamespace(free=1000 * module.GIB)
            ):
                if fail_start:
                    with self.assertRaisesRegex(RuntimeError, "Simulated start failure"):
                        module.main()
                else:
                    module.main()
            return calls.call_args_list

    def test_verified_cutover_keeps_originals(self):
        self.run_migration()
        module = self.module
        self.assertTrue(module.DOMAIN.is_symlink())
        self.assertTrue(module.CHAIN.is_symlink())
        self.assertTrue(module.SLOW_DOMAIN.is_dir())
        self.assertTrue(module.SLOW_CHAIN.is_dir())
        for name in ("v1.0-accounts.0-1.kv", "v2.0-commitment.0-1.kv"):
            self.assertEqual((module.DOMAIN / name).read_bytes(), (module.SLOW_DOMAIN / name).read_bytes())
        self.assertTrue((module.DOMAIN / "v2.0-commitment.0-1.kv").is_symlink())
        self.assertEqual((module.CHAIN / "mdbx.dat").read_bytes(), (module.SLOW_CHAIN / "mdbx.dat").read_bytes())
        self.assertFalse(module.OVERRIDE.exists())

    def test_failure_before_start_restores_original_paths(self):
        self.run_migration(fail_start=True)
        module = self.module
        self.assertFalse(module.DOMAIN.is_symlink())
        self.assertFalse(module.CHAIN.is_symlink())
        self.assertTrue((module.DOMAIN / "v2.0-commitment.0-1.kv").is_file())
        self.assertTrue((module.CHAIN / "mdbx.dat").is_file())
        self.assertFalse(module.SLOW_DOMAIN.exists())
        self.assertFalse(module.SLOW_CHAIN.exists())
        self.assertFalse(module.OVERRIDE.exists())


if __name__ == "__main__":
    unittest.main()
