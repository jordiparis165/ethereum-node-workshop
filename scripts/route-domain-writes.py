"""Keep existing hot files on root, but route new domain merge files to /data."""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DOMAIN = Path('/data/erigon/snapshots/domain')
FAST = Path('/var/lib/erigon-hot/domain')
ACTIVE = Path('/data/erigon-domain-active')
GUARD = Path('/run/systemd/system/erigon.service.d/zz-domain-placement.conf')
STATE = Path('/data/ethereum-monitor/domain-placement.json')


def switch_domain(domain, fast, active):
    if not domain.is_symlink() or domain.resolve() != fast.resolve():
        raise RuntimeError('Unexpected domain layout; refusing to replace it')
    if active.exists():
        raise RuntimeError('Active target already exists; inspect before retrying')
    files = list(fast.iterdir())
    if any(path.is_dir() for path in files):
        raise RuntimeError('Unexpected nested snapshot directory')
    persistent = [path for path in files if '.tmp' not in path.name]
    targets = {path.name: path.resolve(strict=True) for path in persistent}
    active.mkdir()
    owner = fast.stat()
    os.chown(active, owner.st_uid, owner.st_gid)
    for name, target in targets.items():
        link = active / name
        link.symlink_to(target)
        os.lchown(link, owner.st_uid, owner.st_gid)
    pending = domain.with_name('domain-placement.pending')
    if pending.exists() or pending.is_symlink():
        raise RuntimeError('Pending cutover path occupied')
    pending.symlink_to(active, target_is_directory=True)
    os.lchown(pending, owner.st_uid, owner.st_gid)
    pending.replace(domain)
    return {'existing_files_linked': len(targets), 'new_files_directory': str(active),
            'existing_fast_files_retained': str(fast), 'temporary_files_not_reused': len(files) - len(targets)}


def main():
    if DOMAIN.is_symlink() and DOMAIN.resolve() == ACTIVE:
        print('Domain placement already active; no restart requested')
        return
    if os.geteuid() != 0:
        raise RuntimeError('Run as root')
    GUARD.parent.mkdir(parents=True, exist_ok=True)
    GUARD.write_text('[Service]\nTimeoutStopSec=infinity\n', encoding='ascii')
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    changed = False
    started = False
    try:
        subprocess.run(['systemctl', 'stop', 'erigon'], check=True)
        pid = subprocess.check_output(['systemctl', 'show', 'erigon', '-p', 'MainPID', '--value'], text=True).strip()
        if pid != '0':
            raise RuntimeError('Node is still running; refusing to change domain paths')
        report = switch_domain(DOMAIN, FAST, ACTIVE)
        changed = True
        report.update(observed_at=datetime.now(timezone.utc).isoformat(), phase='paths_switched')
        STATE.write_text(json.dumps(report, indent=2) + '\n')
        subprocess.run(['systemctl', 'start', 'erigon'], check=True)
        started = True
        report.update(phase='activated', observed_at=datetime.now(timezone.utc).isoformat())
        STATE.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report), flush=True)
    except Exception:
        if changed and not started:
            pending = DOMAIN.with_name('domain-rollback.pending')
            pending.symlink_to(FAST, target_is_directory=True)
            pending.replace(DOMAIN)
        if not started:
            subprocess.run(['systemctl', 'start', 'erigon'], check=False)
        raise
    finally:
        GUARD.unlink(missing_ok=True)
        subprocess.run(['systemctl', 'daemon-reload'], check=True)


if __name__ == '__main__':
    main()
