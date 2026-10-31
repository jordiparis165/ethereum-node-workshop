"""Move small consensus databases while execution migration holds the node stopped."""
import fcntl
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

BASE = Path("/data/erigon/caplin")
HOT = Path("/var/lib/erigon-hot/caplin-preparation")
GUARD = Path("/run/systemd/system/erigon.service.d/zz-caplin-copy.conf")
LOCK = Path("/var/lib/erigon-hot/caplin-switch.lock")


def pid():
    return subprocess.check_output(["systemctl", "show", "erigon", "-p", "MainPID", "--value"], text=True).strip()


def main():
    spec = importlib.util.spec_from_file_location("verified_storage", Path(__file__).with_name("prepare-hot-storage.py"))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.HOT = HOT
    HOT.mkdir(parents=True, exist_ok=True)
    os.chown(HOT, helper.OWNER.pw_uid, helper.OWNER.pw_gid)
    moved = []
    try:
        with LOCK.open("a") as lock:
            os.chown(LOCK, helper.OWNER.pw_uid, helper.OWNER.pw_gid)
            fcntl.flock(lock, fcntl.LOCK_EX)
            if pid() != "0":
                raise RuntimeError("Erigon already running; consensus databases must remain unchanged")
            sources = [BASE / name for name in ("indexing", "latest", "history")]
            for source in sources:
                if source.is_symlink() or source.with_name(source.name + ".slow-backup").exists():
                    raise RuntimeError("Consensus storage paths already occupied")
            helper.total = sum(file.stat().st_size for source in sources for file in source.rglob("*") if file.is_file())
            if shutil.disk_usage(HOT).free < helper.total + 32 * 1024**3:
                raise RuntimeError("Insufficient remaining fast-volume reserve")
            helper.status("preparing_consensus")
            for source in sources:
                target = HOT / source.name
                shutil.copytree(source, target, copy_function=helper.copy_verified)
                for directory, _, _ in os.walk(target):
                    os.chown(directory, helper.OWNER.pw_uid, helper.OWNER.pw_gid)
            if pid() != "0":
                raise RuntimeError("Unexpected node start while copying consensus")
            try:
                for source in sources:
                    backup = source.with_name(source.name + ".slow-backup")
                    source.rename(backup)
                    moved.append((source, backup))
                    source.symlink_to(HOT / source.name, target_is_directory=True)
            except Exception:
                for source, backup in reversed(moved):
                    if source.is_symlink():
                        source.unlink()
                    if not source.exists():
                        backup.rename(source)
                raise
            helper.status("consensus_activated", note="Originals retained; node is still stopped for execution migration")
    except Exception as exc:
        helper.status("failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        GUARD.unlink(missing_ok=True)
        subprocess.run(["systemctl", "daemon-reload"], check=True)


if __name__ == "__main__":
    main()
