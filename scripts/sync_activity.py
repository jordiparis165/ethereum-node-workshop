"""Distinguish a stationary RPC head from a process that is still doing I/O."""
import subprocess
from pathlib import Path


def collect_activity():
    result = {}
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemAvailable', 'Mlocked'):
            memory[key] = int(value.split()[0]) * 1024
    result['memory_bytes'] = memory
    events = Path('/sys/fs/cgroup/system.slice/erigon.service/memory.events')
    if events.exists():
        result['cgroup_memory_events'] = {
            key: int(value) for key, value in (line.split() for line in events.read_text().splitlines())
        }
    pid = subprocess.check_output(
        ['systemctl', 'show', 'erigon', '-p', 'MainPID', '--value'], text=True
    ).strip()
    if pid != '0':
        proc = Path('/proc') / pid
        try:
            # The command name can contain spaces, so split after its closing bracket.
            fields = proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()
            result['process'] = {
                'pid': int(pid), 'major_faults': int(fields[9]),
                'cpu_ticks': int(fields[11]) + int(fields[12]),
            }
            result['process'].update({key: int(value) for key, value in
                                     (line.split(':', 1) for line in proc.joinpath('io').read_text().splitlines())})
        except (OSError, ValueError) as exc:
            result['process_check_error'] = str(exc)
    log = Path('/data/erigon/logs/erigon.log')
    if log.exists():
        with log.open('rb') as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - 256 * 1024))
            lines = handle.read().decode('utf-8', errors='replace').splitlines()
        result['last_commitment_calculation'] = next(
            (line for line in reversed(lines) if '[commitment] processed' in line), None
        )
    return result


def activity_state(current, previous):
    if current.get('fully_synced'):
        return 'verified_synced'
    if current.get('service') != 'active':
        return 'service_not_active'
    if not previous:
        return 'collecting_activity_samples'
    if int(current.get('block', '0x0'), 16) > int(previous.get('block', '0x0'), 16):
        return 'validated_head_advanced'
    now = (current.get('activity') or {}).get('process') or {}
    old = (previous.get('activity') or {}).get('process') or {}
    if not now or not old or now.get('pid') != old.get('pid'):
        return 'collecting_activity_samples'
    if now.get('read_bytes', 0) > old.get('read_bytes', 0):
        return 'head_unchanged_process_reading_disk'
    if now.get('cpu_ticks', 0) > old.get('cpu_ticks', 0):
        return 'head_unchanged_process_using_cpu'
    return 'no_activity_in_sample_inspect_before_restart'
