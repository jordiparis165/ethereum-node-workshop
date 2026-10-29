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
INTERVAL = 60
REMOTE = r'''python3 - <<'PY'
import json, urllib.request
import subprocess
def rpc(method):
    body=json.dumps({"jsonrpc":"2.0","method":method,"params":[],"id":1}).encode()
    req=urllib.request.Request("http://127.0.0.1:8545",data=body,headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req,timeout=30).read())["result"]
cl=json.loads(urllib.request.urlopen("http://127.0.0.1:5052/eth/v1/node/syncing",timeout=20).read())["data"]
lines=subprocess.check_output("journalctl -u geth.service -n 300 --no-pager",shell=True,text=True,stderr=subprocess.DEVNULL).splitlines()
progress={}
for line in lines:
    if "Syncing: state download in progress" in line: progress["state"] = line.split("Syncing:",1)[1].strip()
    if "Syncing: chain download in progress" in line: progress["chain"] = line.split("Syncing:",1)[1].strip()
print(json.dumps({"eth_syncing":rpc("eth_syncing"),"block":rpc("eth_blockNumber"),"consensus":cl,"geth_progress":progress}))
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
    cl = status["consensus"]
    el = status["eth_syncing"]
    return (el is False and int(status["block"], 16) > 0 and
            cl.get("is_syncing") is False and cl.get("is_optimistic") is False and
            cl.get("el_offline") is False and cl.get("sync_distance") == "0")


def capture_and_publish():
    screenshots = ROOT / "screenshots"
    terminal_script = ROOT / "scripts" / "show-evidence.ps1"
    args = ["-NoLogo", "-NoExit", "-File", str(terminal_script), "-Section", "sync"]
    proc = subprocess.Popen(["powershell.exe", *args], creationflags=subprocess.CREATE_NEW_CONSOLE)
    time.sleep(12)
    ImageGrab.grab().save(screenshots / "04-synchronisation.png")
    log("Full sync verified remotely; captured the visible Windows terminal.")

    marker = ROOT / ".sync-complete"
    marker.write_text(datetime.now().astimezone().strftime("%d/%m/%Y à %H:%M %Z"), encoding="utf-8")
    evidence = ROOT / "EVIDENCE.md"
    evidence.write_text(
        "# Vérifications et preuves\n\nLes captures de `screenshots/` montrent Windows Terminal et des commandes réellement exécutées par SSH sur le VPS.\n\nLa dernière capture de synchronisation a été prise après vérification de `eth_syncing=false`, d’un numéro de bloc non nul, `is_optimistic=false`, `el_offline=false` et `sync_distance=0`. Le volume `/data` de 984 Go reste inférieur aux 2 To demandés.\n",
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
