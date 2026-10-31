"""Poll the school VPS; on verified full sync, capture a real terminal screen and publish updated evidence."""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from capture_terminal import capture_terminal

ROOT = Path(__file__).resolve().parents[1]
import vps_ssh as watch_sync

LOG = ROOT / "sync-watch.log"
STATUS_FILE = ROOT / "sync-status.json"
INTERVAL = 60
REMOTE = r'''python3 - <<'PY'
import json, subprocess, time, urllib.request
from pathlib import Path
def rpc(method):
    body=json.dumps({"jsonrpc":"2.0","method":method,"params":[],"id":1}).encode()
    req=urllib.request.Request("http://127.0.0.1:8545",data=body,headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req,timeout=30).read())["result"]
lines=subprocess.check_output(["journalctl","-u","erigon.service","--since","15 minutes ago","--no-pager"],text=True,stderr=subprocess.DEVNULL).splitlines()
progress=[line.strip() for line in lines if "[Downloader] Syncing" in line or "[OtterSync]" in line or "[4/6 Execution] parallel executed" in line or "[4/6 Execution] parallel committed" in line or "head updated" in line]
caplin=[line.strip() for line in lines if "Checkpoint Sync" in line or "Starting caplin" in line or "[Caplin" in line]
body=json.dumps({"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["latest",False],"id":2}).encode()
req=urllib.request.Request("http://127.0.0.1:8545",data=body,headers={"Content-Type":"application/json"})
rpc_error=None
try:
    latest=json.loads(urllib.request.urlopen(req,timeout=30).read())["result"]
    age=None if latest is None or int(latest.get("number","0x0"),16)==0 else int(time.time())-int(latest["timestamp"],16)
    syncing=rpc("eth_syncing")
    block=rpc("eth_blockNumber")
except Exception as exc:
    age=None
    syncing=None
    block="0x0"
    rpc_error=f"{type(exc).__name__}: {exc}"
errors=[line.strip() for line in lines if any(pattern in line for pattern in ("[ERROR]", "[EROR]", "[CRIT]", "Wrong trie root", "halting process"))]
migration_path=Path('/var/lib/erigon-hot/migration-status.json')
migration=json.loads(migration_path.read_text()) if migration_path.exists() else None
print(json.dumps({"observed_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"eth_syncing":syncing,"block":block,"head_age_seconds":age,"rpc_error":rpc_error,"service":subprocess.run(["systemctl","is-active","erigon.service"],capture_output=True,text=True).stdout.strip(),"progress":progress[-12:],"caplin":caplin[-12:],"errors":errors[-12:],"storage_migration":migration,"disk_free_bytes":__import__("shutil").disk_usage("/data").free}))
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


def capture_and_publish(status):
    screenshots = ROOT / "screenshots"
    capture_terminal("sync", screenshots / "04-synchronisation.png")
    log("Full sync verified remotely; captured the visible Windows terminal.")

    marker = ROOT / ".sync-complete"
    marker.write_text(datetime.now().astimezone().strftime("%d/%m/%Y à %H:%M %Z"), encoding="utf-8")
    evidence = ROOT / "EVIDENCE.md"
    evidence.write_text(
        "# Vérifications et preuves\n\nLes captures de `screenshots/` montrent de vrais terminaux Windows. "
        "Les contrôles du nœud sont exécutés par SSH; les tests RPC publics partent du PC vers le VPS.\n\n"
        "La dernière capture `04-synchronisation.png` a été prise après vérification que le service Erigon "
        "est actif, que `eth_syncing=false`, que le bloc courant est non nul et que son horodatage "
        "est à moins de cinq minutes de l'heure du VPS. Erigon intègre Caplin pour le consensus. "
        "Le relevé JSON correspondant est dans `evidence/first-verified-sync.json`.\n\n"
        "`05-rpc-public.png` prouve les tests HTTPS/WSS avec authentification et vérification TLS. "
        "Les extraits de l'incident et des premières mesures restent dans `evidence/`. "
        "Le timer sur la VM garde également ses propres mesures. Le reboot complet reste à tester; "
        "le démarrage automatique est configuré mais cela ne remplace pas un test de redémarrage.\n",
        encoding="utf-8")
    verified = ROOT / "evidence" / "first-verified-sync.json"
    verified.parent.mkdir(exist_ok=True)
    verified.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_report_pdf.py")], check=True, cwd=ROOT)
    subprocess.run(["git", "add", ".sync-complete", "EVIDENCE.md", "RAPPORT-ETHEREUM.pdf", "screenshots/04-synchronisation.png", "evidence/first-verified-sync.json"], check=True, cwd=ROOT)
    subprocess.run(["git", "commit", "-m", "Update evidence after full Ethereum synchronization"], check=True, cwd=ROOT)
    subprocess.run(["git", "push", "origin", "master"], check=True, cwd=ROOT)
    log("Updated French report, PDF and screenshots pushed to GitHub.")


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
                capture_and_publish(status)
                return
        except Exception as exc:
            log(f"Check failed: {type(exc).__name__}: {exc}")
        finally:
            if client:
                client.close()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
