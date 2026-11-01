"""Run one reboot proof only after saved full-sync qualification, with a deadline margin."""
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sync_validation import Qualification, candidate

ROOT = Path(__file__).resolve().parents[1]
DEADLINE = datetime.fromisoformat('2026-11-01T23:59:00+01:00')


def reboot_allowed(now, deadline, qualified):
    return qualified and now <= deadline - timedelta(hours=1)


def save(value):
    path = ROOT / 'evidence/reboot-verification.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    temporary.replace(path)


def run(read_status):
    path = ROOT / 'evidence/reboot-verification.json'
    state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if state.get('passed'):
        return state
    proof_path = ROOT / 'evidence/first-verified-sync.json'
    proof = json.loads(proof_path.read_text(encoding='utf-8')) if proof_path.exists() else {}
    qualification = Qualification()
    qualified = False
    for sample in proof.get('qualification_samples', []):
        qualified = qualification.observe(sample)
    if not state.get('requested_at') and not reboot_allowed(datetime.now(timezone.utc), DEADLINE, qualified):
        result = {'passed': False, 'stage': 'not_requested',
                  'reason': 'Need saved repeated full-sync proof and at least one hour before the deadline.'}
        save(result)
        return result
    import vps_ssh
    config = vps_ssh.load_env(vps_ssh.ENV_PATH)
    if not state.get('requested_at'):
        client = vps_ssh.connect(config)
        try:
            before = read_status(client)
            if not candidate(before):
                raise RuntimeError('Fresh independent sync check failed; reboot not requested')
            code, boot_id, err = vps_ssh.run_remote(client, 'cat /proc/sys/kernel/random/boot_id')
            if code:
                raise RuntimeError(err)
            state = {'passed': False, 'stage': 'requesting', 'before_boot_id': boot_id.strip(),
                     'requested_at': datetime.now(timezone.utc).isoformat(), 'before_status': before}
            save(state)
            code, out, err = vps_ssh.run_remote(
                client, 'sudo -n systemd-run --unit=ethereum-reboot-proof --on-active=10s /usr/bin/systemctl reboot')
            state.update(stage='requested' if code == 0 else 'request_failed', request_output=out + err)
            save(state)
            if code:
                return state
        finally:
            client.close()
    end = time.monotonic() + 1800
    qualification = Qualification()
    while time.monotonic() < end:
        time.sleep(60)
        client = None
        try:
            client = vps_ssh.connect(config)
            code, boot_id, err = vps_ssh.run_remote(client, 'cat /proc/sys/kernel/random/boot_id')
            if code or boot_id.strip() == state['before_boot_id']:
                continue
            state['after_boot_id'] = boot_id.strip()
            units = ['erigon', 'nginx', 'ethereum-sync-monitor.timer', 'var-lib-erigon_swap.swap']
            results = {}
            for unit in units:
                code, out, err = vps_ssh.run_remote(client, f'systemctl is-active {unit}; systemctl is-enabled {unit}')
                results[unit] = {'exit_code': code, 'output': out.strip(), 'stderr': err}
            state['units'] = results
            status = read_status(client)
            state['latest_status'] = status
            state['stage'] = 'boot_changed_waiting_for_sync'
            enabled = all(item['exit_code'] == 0 and item['output'].splitlines() == ['active', 'enabled']
                          for item in results.values())
            if qualification.observe(status) and enabled:
                state.update(passed=True, stage='verified',
                             verified_at=datetime.now(timezone.utc).isoformat(),
                             qualification_samples=json.loads(json.dumps(qualification.samples)))
                save(state)
                return state
            save(state)
        except Exception as exc:
            qualification = Qualification()
            state['last_check_error'] = f'{type(exc).__name__}: {exc}'
            save(state)
        finally:
            if client:
                client.close()
    state.update(passed=False, stage='verification_timeout')
    save(state)
    return state


if __name__ == '__main__':
    from watch_until_synced import read_status
    print(json.dumps(run(read_status), ensure_ascii=False, indent=2))
