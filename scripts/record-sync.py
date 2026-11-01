"""Record RPC and commitment progress on the VPS without restarting the client."""
import json
import os
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from sync_forecast import forecast
from sync_activity import collect_activity, activity_state, activity_rates

ROOT = Path(__file__).resolve().parent


def rpc(method, params=None):
    request = urllib.request.Request(
        "http://127.0.0.1:8545",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                         "params": params or []}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.load(response)
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result["result"]


def record():
    status = {"observed_at": datetime.now(timezone.utc).isoformat(), "fully_synced": False}
    try:
        previous = json.loads((ROOT / 'latest.json').read_text())
    except (OSError, ValueError):
        previous = None
    try:
        status['activity'] = collect_activity()
    except Exception as exc:
        status['activity_check_error'] = f'{type(exc).__name__}: {exc}'
    try:
        migration = Path("/var/lib/erigon-hot/migration-status.json")
        if migration.exists():
            status["storage_migration"] = json.loads(migration.read_text(encoding="utf-8"))
            status["storage_migration_service"] = subprocess.run(
                ["systemctl", "is-active", "ethereum-hot-storage-migration.service"],
                capture_output=True, text=True,
            ).stdout.strip()
            status["fast_disk_free_bytes"] = shutil.disk_usage(migration.parent).free
        placement = ROOT / 'domain-placement.json'
        if placement.exists():
            status['domain_placement'] = json.loads(placement.read_text())
        status["service"] = subprocess.run(
            ["systemctl", "is-active", "erigon.service"], capture_output=True, text=True
        ).stdout.strip()
        status["eth_syncing"] = rpc("eth_syncing")
        status["block"] = rpc("eth_blockNumber")
        head = rpc("eth_getBlockByNumber", ["latest", False])
        status["head_age_seconds"] = (
            int(time.time()) - int(head["timestamp"], 16)
            if head and int(head["number"], 16) > 0 else None
        )
        status["disk_free_bytes"] = shutil.disk_usage("/data").free
        status["io_pressure"] = Path("/proc/pressure/io").read_text().strip()
        same_head = previous and status.get('block') == previous.get('block')
        same_pid = previous and ((status.get('activity') or {}).get('process') or {}).get('pid') == (
            (previous.get('activity') or {}).get('process') or {}).get('pid')
        status['last_head_advance_at'] = (previous.get('last_head_advance_at', previous['observed_at'])
                                         if same_head and same_pid else status['observed_at'])
        logs = subprocess.check_output(
            ["journalctl", "-q", "-u", "erigon.service", "--since", "5 minutes ago", "--no-pager"],
            text=True, stderr=subprocess.DEVNULL,
        ).splitlines()
        for name, pattern in (("commitment", "parallel committed"), ("execution", "parallel executed")):
            status[name] = next((line for line in reversed(logs) if pattern in line), None)
        status['consensus_log'] = next((line for line in reversed(logs)
                                        if 'Forward Sync' in line or 'Caplin P2P' in line), None)
        status["errors"] = [line for line in logs if any(
            pattern in line for pattern in ("[ERROR]", "[EROR]", "[CRIT]", "Wrong trie root", "halting process")
        )][-10:]
        age = status["head_age_seconds"]
        status["fully_synced"] = (
            status["service"] == "active" and status["eth_syncing"] is False
            and int(status["block"], 16) > 0 and age is not None and 0 <= age <= 300
        )
    except Exception as exc:
        status["check_error"] = f"{type(exc).__name__}: {exc}"
    status['activity_state'] = activity_state(status, previous)
    status['resource_rates'] = activity_rates(status, previous)
    status['warnings'] = []
    for field in ('fast_disk_free_bytes', 'disk_free_bytes'):
        if field in status and status[field] < 15 * 1024**3:
            status['warnings'].append(f'Low disk reserve: {field}')
    available = ((status.get('activity') or {}).get('memory_bytes') or {}).get('MemAvailable')
    if available is not None and available < 1024**3:
        status['warnings'].append('Less than 1 GiB available RAM')
    events = (status.get('activity') or {}).get('cgroup_memory_events') or {}
    if events.get('oom_kill', 0):
        status['warnings'].append('OOM kill recorded in the current service cgroup; inspect kernel logs')
    if status.get('last_head_advance_at') and not status['fully_synced']:
        unchanged = (datetime.fromisoformat(status['observed_at'])
                     - datetime.fromisoformat(status['last_head_advance_at'])).total_seconds()
        status['seconds_without_validated_head_advance'] = round(unchanged)
        if unchanged >= 3 * 3600:
            status['warnings'].append('No validated head advance for 3 hours; inspect I/O and commitment before restarting')
    deadline = os.environ.get("ETHEREUM_DEADLINE")
    if deadline:
        history = []
        log = ROOT / "observations.jsonl"
        if log.exists():
            for line in log.read_text(encoding="utf-8").splitlines()[-360:]:
                try:
                    history.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        status["forecast"] = forecast(status, history, deadline)
    payload = json.dumps(status, ensure_ascii=False)
    with (ROOT / "observations.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")
    temporary = ROOT / "latest.json.tmp"
    temporary.write_text(payload + "\n", encoding="utf-8")
    temporary.replace(ROOT / "latest.json")
    marker = ROOT / "first-verified-sync.json"
    if status["fully_synced"] and not marker.exists():
        marker.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    record()
