"""Apply the Go memory target with a clean, unforced service restart."""
import subprocess
from pathlib import Path

guard = Path('/run/systemd/system/erigon.service.d/zz-memory-restart.conf')
try:
    guard.parent.mkdir(parents=True, exist_ok=True)
    guard.write_text('[Service]\nTimeoutStopSec=infinity\n', encoding='ascii')
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'restart', 'erigon.service'], check=True)
    subprocess.run(['systemctl', 'show', 'erigon', '-p', 'MainPID', '-p', 'Environment'], check=True)
finally:
    guard.unlink(missing_ok=True)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
