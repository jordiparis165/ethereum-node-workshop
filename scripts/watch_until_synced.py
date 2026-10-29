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
INTERVAL = 300
REMOTE = r'''python3 - <<'PY'
import json, urllib.request
def rpc(method):
    body=json.dumps({"jsonrpc":"2.0","method":method,"params":[],"id":1}).encode()
    req=urllib.request.Request("http://127.0.0.1:8545",data=body,headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req,timeout=30).read())["result"]
cl=json.loads(urllib.request.urlopen("http://127.0.0.1:5052/eth/v1/node/syncing",timeout=20).read())["data"]
print(json.dumps({"eth_syncing":rpc("eth_syncing"),"block":rpc("eth_blockNumber"),"consensus":cl}))
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

    report = ROOT / "RAPPORT.md"
    content = report.read_text(encoding="utf-8")
    content = content.replace(
        "La couche de consensus avançait, mais la couche d’exécution n’était pas synchronisée. Je ne présente donc pas le nœud comme entièrement synchronisé.",
        "Un contrôle ultérieur a confirmé eth_syncing=false, un numéro de bloc non nul, is_optimistic=false, el_offline=false et sync_distance=0. Les deux couches étaient synchronisées à la date de la capture actualisée."
    )
    content = content.replace(
        "La synchronisation complète avant le 31 octobre n’est pas garantie : l’ETA des journaux varie selon les pairs et les ressources disponibles.",
        "La synchronisation complète a été confirmée par les API des deux clients ; la date et l’état détaillé figurent dans la capture actualisée."
    )
    content = content.replace(
        "Elles prouvent l’état relevé à leur horodatage ; elles ne prétendent pas prouver une synchronisation achevée.",
        "La capture de synchronisation actualisée montre l’état retourné par les clients lors de sa prise."
    )
    report.write_text(content, encoding="utf-8")
    evidence = ROOT / "EVIDENCE.md"
    evidence.write_text(
        "# Vérifications et preuves\n\nLes images du dossier `screenshots/` sont des captures natives de l’écran Windows avec Windows Terminal au premier plan. Les commandes affichées interrogent le VPS de l’école par SSH ; aucun secret n’est imprimé.\n\nLa capture de synchronisation a été actualisée après confirmation simultanée de `eth_syncing=false`, d’un numéro de bloc non nul, `is_optimistic=false`, `el_offline=false` et `sync_distance=0`. Consultez `04-synchronisation.png` pour les valeurs et l’heure du relevé. Le volume `/data` de 984 Go reste inférieur aux 2 To demandés.\n",
        encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_report_pdf.py")], check=True, cwd=ROOT)
    subprocess.run(["git", "add", "RAPPORT.md", "EVIDENCE.md", "RAPPORT-ETHEREUM.pdf", "screenshots/04-synchronisation.png"], check=True, cwd=ROOT)
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
