"""Temporarily enlarge sequential read-ahead and the migration's page cache."""
import json
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

UNIT = "ethereum-hot-storage-migration.service"
QUEUE = Path("/sys/block/sdb/queue/read_ahead_kb")
STATUS = Path("/var/lib/erigon-hot/copy-tuning.json")
FAST_CHAIN = Path("/var/lib/erigon-hot/chaindata")


def active():
    result = subprocess.run(["systemctl", "is-active", UNIT], capture_output=True, text=True)
    return result.stdout.strip() in ("active", "activating", "deactivating")


def report(phase, original):
    temporary = STATUS.with_suffix(".tmp")
    temporary.write_text(json.dumps({
        "observed_at": datetime.now(timezone.utc).isoformat(), "phase": phase,
        "original_read_ahead_kb": original, "read_ahead_kb": int(QUEUE.read_text()),
    }, indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATUS)


def stop(signum, frame):
    raise SystemExit(0)


def main():
    if not active():
        raise RuntimeError("No active migration to tune")
    original = int(QUEUE.read_text())
    before = subprocess.check_output(
        ["systemctl", "show", UNIT, "-p", "MemoryMax", "--value"], text=True
    ).strip()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        subprocess.run(["systemctl", "set-property", "--runtime", UNIT, "MemoryMax=8G"], check=True)
        QUEUE.write_text("16384\n", encoding="ascii")
        if int(QUEUE.read_text()) != 16384:
            raise RuntimeError("Read-ahead change not applied")
        report("temporary_tuning_active", original)
        while active():
            # Restore before Erigon reopens files for random state reads.
            if FAST_CHAIN.exists():
                break
            time.sleep(1)
    finally:
        QUEUE.write_text(str(original) + "\n", encoding="ascii")
        if active():
            subprocess.run(["systemctl", "set-property", "--runtime", UNIT, f"MemoryMax={before}"], check=False)
        report("restored", original)


if __name__ == "__main__":
    main()
