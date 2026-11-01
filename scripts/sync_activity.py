"""Distinguish a stationary RPC head from a process that is still doing I/O."""
import subprocess
import os
from datetime import datetime
from pathlib import Path


def collect_activity():
    result = {}
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable', 'Mlocked', 'SwapTotal', 'SwapFree'):
            memory[key] = int(value.split()[0]) * 1024
    result['memory_bytes'] = memory
    result['clock_ticks_per_second'] = os.sysconf('SC_CLK_TCK')
    result['page_size'] = os.sysconf('SC_PAGE_SIZE')
    vm = dict(line.split() for line in Path('/proc/vmstat').read_text().splitlines())
    result['swap_pages'] = {key: int(vm[key]) for key in ('pswpin', 'pswpout')}
    result['disks'] = {}
    for line in Path('/proc/diskstats').read_text().splitlines():
        fields = line.split()
        if fields[2] in ('sda', 'sdb'):
            values = list(map(int, fields[3:]))
            result['disks'][fields[2]] = dict(reads=values[0], read_sectors=values[2], read_ms=values[3],
                                             writes=values[4], write_sectors=values[6], write_ms=values[7],
                                             busy_ms=values[9])
    result['network'] = {'rx_bytes': 0, 'tx_bytes': 0}
    for line in Path('/proc/net/dev').read_text().splitlines()[2:]:
        name, counters = line.split(':', 1)
        if name.strip() != 'lo':
            fields = counters.split()
            result['network']['rx_bytes'] += int(fields[0])
            result['network']['tx_bytes'] += int(fields[8])
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


def activity_rates(current, previous):
    if not previous:
        return {}
    seconds = (datetime.fromisoformat(current['observed_at'])
               - datetime.fromisoformat(previous['observed_at'])).total_seconds()
    if seconds <= 0:
        return {}
    now, old = current.get('activity') or {}, previous.get('activity') or {}
    result = {'window_seconds': round(seconds, 2), 'disks': {}}
    for name, disk in now.get('disks', {}).items():
        prior = old.get('disks', {}).get(name)
        if not prior:
            continue
        delta = {key: disk[key] - prior[key] for key in disk}
        if any(value < 0 for value in delta.values()):
            continue
        operations = delta['reads'] + delta['writes']
        result['disks'][name] = {
            'iops': round(operations / seconds, 2),
            'read_mib_per_second': round(delta['read_sectors'] * 512 / seconds / 1024**2, 2),
            'write_mib_per_second': round(delta['write_sectors'] * 512 / seconds / 1024**2, 2),
            'average_request_ms': round((delta['read_ms'] + delta['write_ms']) / operations, 2) if operations else None,
            'busy_percent': round(min(100, delta['busy_ms'] / seconds / 10), 2),
        }
    a, b = now.get('process') or {}, old.get('process') or {}
    if a and b and a.get('pid') == b.get('pid'):
        result['process_cpu_percent_one_core'] = round(
            100 * (a['cpu_ticks'] - b['cpu_ticks']) / seconds / now.get('clock_ticks_per_second', 100), 2)
    if now.get('network') and old.get('network'):
        result['network_bytes_per_second'] = {
            key: round(max(0, value - old['network'][key]) / seconds)
            for key, value in now['network'].items()
        }
    if now.get('swap_pages') and old.get('swap_pages'):
        result['swap_mib_per_second'] = {
            key: round(max(0, value - old['swap_pages'][key]) * now.get('page_size', 4096) / seconds / 1024**2, 3)
            for key, value in now['swap_pages'].items()
        }
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
