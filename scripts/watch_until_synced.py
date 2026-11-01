"""Poll the school VPS; on verified full sync, capture a real terminal screen and publish updated evidence."""
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from capture_terminal import capture_terminal
from reference_chain import reference_status
from sync_validation import candidate, Qualification

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
monitor_path=Path('/data/ethereum-monitor/latest.json')
forecast=(json.loads(monitor_path.read_text()).get('forecast') if monitor_path.exists() else None)
print(json.dumps({"observed_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"eth_syncing":syncing,"block":block,"head_hash":latest['hash'] if rpc_error is None and latest else None,"head_age_seconds":age,"rpc_error":rpc_error,"service":subprocess.run(["systemctl","is-active","erigon.service"],capture_output=True,text=True).stdout.strip(),"progress":progress[-12:],"caplin":caplin[-12:],"errors":errors[-12:],"storage_migration":migration,"forecast":forecast,"disk_free_bytes":__import__("shutil").disk_usage("/data").free}))
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
    status = json.loads(out.strip())
    if status.get('rpc_error') or int(status.get('block', '0x0'), 16) == 0:
        status['reference_error'] = 'Local RPC head unavailable; no remaining-block count calculated.'
        return status
    try:
        status['reference'] = reference_status(int(status['block'], 16), status.get('head_hash'))
    except Exception as exc:
        status['reference_error'] = f'{type(exc).__name__}: {exc}'
    return status


def fully_synced(status):
    return candidate(status)


def capture_safely(section, filename):
    try:
        capture_terminal(section, ROOT / 'screenshots' / filename)
        return True
    except Exception as exc:
        log(f'Capture unavailable ({section}): {exc}; no replacement image fabricated.')
        return False


def publish_current(message, extras=()):
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/prepare_submission.py')], cwd=ROOT)
    names = ['README.md', 'EVIDENCE.md', 'RAPPORT-ETHEREUM.pdf', 'evidence/current-status.json',
             'evidence/current-monitor.json', 'evidence/current-system-checks.json',
             'evidence/current-public-rpc.log', 'evidence/submission-audit.json', *extras]
    names = [name for name in names if (ROOT / name).exists()]
    subprocess.run(['git', 'add', '--', *names], cwd=ROOT, check=True)
    if subprocess.run(['git', 'diff', '--cached', '--quiet', '--', *names], cwd=ROOT).returncode:
        subprocess.run(['git', 'commit', '--only', '-m', message, '--', *names], cwd=ROOT, check=True)
    subprocess.run(['git', 'push', 'origin', 'master'], check=True, cwd=ROOT)
    return result.returncode == 0


def capture_and_publish(status):
    proof = ROOT / 'evidence/first-verified-sync.json'
    proof.parent.mkdir(exist_ok=True)
    if not proof.exists():
        proof.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    if not (ROOT / '.sync-complete').exists():
        (ROOT / '.sync-complete').write_text(status['observed_at'], encoding='utf-8')
    captures = []
    for section, filename in [('sync', '04-synchronisation.png'), ('reference', '12-etat-actuel.png'),
                              ('public', '11-tests-publics.png'), ('services', '13-services-enabled.png')]:
        if capture_safely(section, filename):
            captures.append('screenshots/' + filename)
    first_proof = json.loads(proof.read_text(encoding='utf-8'))
    first_proof['screenshots_refreshed'] = captures
    first_proof['screenshots_refreshed_at'] = status['observed_at']
    proof.write_text(json.dumps(first_proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    evidence = ROOT / 'EVIDENCE.md'
    note = ('\n\n## Synchronisation constatée\n\nTrois observations sur au moins deux minutes ont confirmé '
            'une tête récente, eth_syncing=false et un hash identique à la référence mainnet, avec au plus '
            'quatre blocs de retard. Les relevés sont dans `evidence/first-verified-sync.json`. '
            'Les captures gardent leur propre horodatage; un échec de capture ne génère jamais une image de remplacement.\n')
    existing = evidence.read_text(encoding='utf-8')
    if '## Synchronisation constatée' not in existing:
        evidence.write_text(existing + note, encoding='utf-8', newline='\n')
    if not publish_current('Publish independently verified synchronization evidence',
                           ['.sync-complete', 'evidence/first-verified-sync.json', *captures]):
        raise RuntimeError('Sync proof published, but public endpoint checks need attention')
    # Preserve and publish synchronization evidence BEFORE the workshop reboot test.
    from verify_reboot import run
    reboot = run(read_status)
    log('Reboot proof stage: ' + reboot['stage'])
    reboot_captures = []
    if reboot.get('passed'):
        for section, filename in [('services', '14-apres-reboot.png'), ('reference', '15-sync-apres-reboot.png')]:
            if capture_safely(section, filename):
                reboot_captures.append('screenshots/' + filename)
    public_ok = publish_current('Update report with guarded reboot verification result',
                                ['evidence/reboot-verification.json', *reboot_captures])
    log('Latest proof, audit and French PDF pushed to GitHub. Inspect remaining compliance gaps.')
    return public_ok and (reboot.get('passed') or reboot['stage'] == 'not_requested')


def publish_deadline_snapshot(status):
    (ROOT / 'evidence/deadline-status.json').write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    captures = []
    for section, filename in [('reference', '12-etat-actuel.png'), ('public', '11-tests-publics.png')]:
        if capture_safely(section, filename):
            captures.append('screenshots/' + filename)
    publish_current('Publish honest pre-deadline submission snapshot', ['evidence/deadline-status.json', *captures])
    (ROOT / '.deadline-published.secret').write_text(datetime.now(timezone.utc).isoformat(), encoding='utf-8')


def main():
    config = watch_sync.load_env(watch_sync.ENV_PATH)
    qualification = Qualification()
    deadline = datetime.fromisoformat('2026-11-01T23:59:00+01:00')
    log(f"Monitoring Ethereum sync on {config['host']} every {INTERVAL}s; credentials loaded from btc/.env.")
    while True:
        client = None
        try:
            client = watch_sync.connect(config)
            status = read_status(client)
            STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
            log(json.dumps(status, ensure_ascii=False))
            if qualification.observe(status):
                status['qualification_samples'] = json.loads(json.dumps(qualification.samples))
                if capture_and_publish(status):
                    return
                qualification = Qualification()
            if (datetime.now(timezone.utc) >= deadline - timedelta(minutes=29)
                    and not (ROOT / '.deadline-published.secret').exists()):
                publish_deadline_snapshot(status)
        except Exception as exc:
            qualification = Qualification()
            log(f"Check failed: {type(exc).__name__}: {exc}")
            if (datetime.now(timezone.utc) >= deadline - timedelta(minutes=29)
                    and not (ROOT / '.deadline-published.secret').exists() and STATUS_FILE.exists()):
                try:
                    saved = json.loads(STATUS_FILE.read_text(encoding='utf-8'))
                    saved['current_check_error'] = f'{type(exc).__name__}: {exc}'
                    publish_deadline_snapshot(saved)
                except Exception as publish_error:
                    log(f'Pre-deadline publication failed: {publish_error}; retry on next check.')
        finally:
            if client:
                client.close()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
