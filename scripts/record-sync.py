"""Record RPC and commitment progress on the VPS without restarting the client."""
import json
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

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
        logs = subprocess.check_output(
            ["journalctl", "-q", "-u", "erigon.service", "--since", "5 minutes ago", "--no-pager"],
            text=True, stderr=subprocess.DEVNULL,
        ).splitlines()
        for name, pattern in (("commitment", "parallel committed"), ("execution", "parallel executed")):
            status[name] = next((line for line in reversed(logs) if pattern in line), None)
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
