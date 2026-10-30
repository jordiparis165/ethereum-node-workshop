"""Poll the school VPS; on verified full sync, capture a real terminal screen and publish updated evidence."""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "btc"))
import watch_sync

LOG = ROOT / "sync-watch.log"
STATUS_FILE = ROOT / "sync-status.json"
INTERVAL = 60
REMOTE = r'''python3 - <<'PY'
import json, subprocess, time, urllib.request
def rpc(method):
    body=json.dumps({"jsonrpc":"2.0","method":method,"params":[],"id":1}).encode()
    req=urllib.request.Request("http://127.0.0.1:8545",data=body,headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req,timeout=30).read())["result"]
lines=subprocess.check_output(["journalctl","-u","erigon.service","--since","15 minutes ago","--no-pager"],text=True,stderr=subprocess.DEVNULL).splitlines()
progress=[line.strip() for line in lines if "[Downloader] Syncing" in line or "[OtterSync]" in line or "[4/6 Execution] parallel executed" in line or "head updated" in line]
caplin=[line.strip() for line in lines if "Checkpoint Sync" in line or "Starting caplin" in line or "[Caplin" in line]
body=json.dumps({"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["latest",False],"id":2}).encode()
req=urllib.request.Request("http://127.0.0.1:8545",data=body,headers={"Content-Type":"application/json"})
latest=json.loads(urllib.request.urlopen(req,timeout=30).read())["result"]
age=None if latest is None or int(latest.get("number","0x0"),16)==0 else int(time.time())-int(latest["timestamp"],16)
print(json.dumps({"eth_syncing":rpc("eth_syncing"),"block":rpc("eth_blockNumber"),"head_age_seconds":age,"service":subprocess.check_output(["systemctl","is-active","erigon.service"],text=True).strip(),"progress":progress[-12:],"caplin":caplin[-12:],"disk_free_bytes":__import__("shutil").disk_usage("/data").free}))
PY'''


def log(message):
    line = f"{datetime.now().astimezone().isoformat(timespec='seconds')} {message}"
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line, flush=True)


def read_status(client):
    code, out, err = watch_sync.run_remote(client, REMOTE)
    if code:
        raise RuntimeError(err or f"remote command exited {code}")
    return json.loads(out.strip())


def fully_synced(status):
    return (status["service"] == "active" and status["eth_syncing"] is False and
            int(status["block"], 16) > 0 and
            status["head_age_seconds"] is not None and 0 <= status["head_age_seconds"] <= 300)


def capture_and_publish():
    screenshots = ROOT / "screenshots"
    terminal_script = ROOT / "scripts" / "show-evidence.ps1"
    args = ["-NoLogo", "-NoExit", "-File", str(terminal_script), "-Section", "sync"]
    proc = subprocess.Popen(["powershell.exe", *args], creationflags=subprocess.CREATE_NEW_CONSOLE)
    time.sleep(12)
    focus = f"$ws=New-Object -ComObject WScript.Shell; $ws.AppActivate({proc.pid}) | Out-Null"
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", focus], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    ImageGrab.grab().save(screenshots / "04-synchronisation.png")
    log("Full sync verified remotely; captured the visible Windows terminal.")

    marker = ROOT / ".sync-complete"
    marker.write_text(datetime.now().astimezone().strftime("%d/%m/%Y à %H:%M %Z"), encoding="utf-8")
    evidence = ROOT / "EVIDENCE.md"
    evidence.write_text(
        "# Vérifications et preuves\n\nLes captures de `screenshots/` montrent Windows Terminal et des commandes réellement exécutées par SSH sur le VPS.\n\nLa dernière capture a été prise après vérification que le service Erigon est actif, que `eth_syncing=false`, que le bloc courant est non nul et que son horodatage est à moins de cinq minutes de l’heure du VPS. Erigon intègre Caplin pour le consensus; les journaux de checkpoint et Caplin sont conservés avec le relevé. Le volume `/data` fait environ 984 Go et le client utilise le mode minimal.\n",
        encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_report_pdf.py")], check=True, cwd=ROOT)
    subprocess.run(["git", "add", ".sync-complete", "EVIDENCE.md", "RAPPORT-ETHEREUM.pdf", "screenshots/04-synchronisation.png"], check=True, cwd=ROOT)
    subprocess.run(["git", "commit", "-m", "Update evidence after full Ethereum synchronization"], check=True, cwd=ROOT)
    subprocess.run(["git", "push", "origin", "master"], check=True, cwd=ROOT)
    log("Updated French report, PDF and screenshots pushed to GitHub.")
    proc.terminate()


def main():
    config = watch_sync.load_env(watch_sync.ENV_PATH)
    log(f"Monitoring Ethereum sync on {config['host']} every {INTERVAL}s; credentials loaded from btc/.env.")
    while True:
        client = None
        try:
            client = watch_sync.connect(config)
            status = read_status(client)
            STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
            log(json.dumps(status, ensure_ascii=False))
            if fully_synced(status):
                capture_and_publish()
                return
        except Exception as exc:
            log(f"Check failed: {type(exc).__name__}: {exc}")
        finally:
            if client:
                client.close()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
