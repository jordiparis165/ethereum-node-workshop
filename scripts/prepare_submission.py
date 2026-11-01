"""Refresh real evidence and an honest submission checklist without touching node data."""
import json
import os
import subprocess
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

import vps_ssh
from watch_until_synced import read_status
from sync_validation import Qualification

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {
    'source_build': "git -C /data/ethereum-src/erigon-v3.8.1 rev-parse HEAD; /data/ethereum-src/erigon-v3.8.1/build/bin/erigon --version; tail -n 4 /data/ethereum-src/erigon-build-final.log; git -C /data/ethereum-src/erigon-v3.8.1 ls-files cl/phase1/stages | head -3",
    'services': 'systemctl show erigon -p ActiveState -p MainPID -p Environment -p ExecStart; systemctl is-enabled erigon nginx ethereum-sync-monitor.timer var-lib-erigon_swap.swap var-lib-erigon_swap_extra.swap',
    'security': "sudo -n nginx -t; sudo -n stat -c '%a %U %G %n' /etc/nginx/ethereum-rpc/tls.key /etc/nginx/ethereum-rpc/htpasswd; ss -lntup | grep -E ':(9443|8545|8546|8551|6061|5555)\\b'",
    'resources': 'date -Is; free -h; df -h / /data; /usr/sbin/swapon --show; cat /proc/sys/kernel/random/boot_id',
    'recent_chain_events': "journalctl -q -u erigon --since '2 hours ago' --no-pager | grep -E 'head updated|Execution.*DONE|Forward Sync|Checkpoint Sync|Background files build|\\[EROR\\]|\\[CRIT\\]' | tail -18",
}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    evidence = ROOT / 'evidence'
    evidence.mkdir(exist_ok=True)
    previous_path = evidence / 'current-status.json'
    previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {}
    client = None
    checks = {name: {'exit_code': None, 'output': '', 'stderr': 'Not checked'} for name in CHECKS}
    try:
        client = vps_ssh.connect(vps_ssh.load_env(vps_ssh.ENV_PATH))
        status = read_status(client)
        for name, command in CHECKS.items():
            try:
                code, out, err = vps_ssh.run_remote(
                    client, 'timeout 45s sh -c ' + shlex.quote('set -e\n' + command), timeout=55)
                checks[name] = {'exit_code': code, 'output': out, 'stderr': err}
            except Exception as exc:
                checks[name] = {'exit_code': None, 'output': '', 'stderr': f'{type(exc).__name__}: {exc}'}
        sftp = client.open_sftp()
        sftp.get('/data/ethereum-monitor/latest.json', str(evidence / 'current-monitor.json'))
        sftp.close()
    except Exception as exc:
        saved = ROOT / 'sync-status.json'
        if not saved.exists():
            raise
        status = json.loads(saved.read_text(encoding='utf-8'))
        status.update(service='unknown', rpc_error=f'{type(exc).__name__}: {exc}',
                      failed_check_at=datetime.now(timezone.utc).isoformat())
        status['last_known_reference'] = status.pop('reference', None)
        # Keep the last observation's timestamp: this is not a new successful VPS read.
    finally:
        if client:
            client.close()
    write_json(ROOT / 'sync-status.json', status)
    write_json(evidence / 'current-status.json', status)
    write_json(evidence / 'current-system-checks.json', checks)
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    try:
        public = subprocess.run([sys.executable, str(ROOT / 'scripts/test-public-rpc.py')], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=120, env=env)
    except subprocess.TimeoutExpired:
        public = subprocess.CompletedProcess([], 1, '', 'Public RPC test timed out; no success asserted.\n')
    (evidence / 'current-public-rpc.log').write_text(public.stdout + public.stderr, encoding='utf-8', newline='\n')
    reboot_path = evidence / 'reboot-verification.json'
    reboot = json.loads(reboot_path.read_text(encoding='utf-8')) if reboot_path.exists() else {}
    proof_path = evidence / 'first-verified-sync.json'
    proof = json.loads(proof_path.read_text(encoding='utf-8')) if proof_path.exists() else {}
    qualification = Qualification()
    proof_valid = False
    try:
        for sample in proof.get('qualification_samples', []):
            proof_valid = qualification.observe(sample)
    except (ValueError, KeyError, TypeError):
        proof_valid = False
    sheet_path = evidence / 'spreadsheet-submission.json'
    sheet = json.loads(sheet_path.read_text(encoding='utf-8')) if sheet_path.exists() else {}
    now = datetime.now(timezone.utc)
    remaining_time = max(0, (datetime.fromisoformat('2026-11-01T23:59:00+01:00') - now).total_seconds())
    ref, prior = status.get('reference') or {}, previous.get('reference') or {}
    budget = {'seconds_before_deadline': round(remaining_time), 'kind': 'required_rate_not_a_finish_prediction'}
    if ref and remaining_time:
        net_required = max(0, ref['remaining_blocks']) / remaining_time
        budget['minimum_net_catchup_blocks_per_second'] = round(net_required, 5)
        if prior:
            window = (datetime.fromisoformat(ref['observed_at']) - datetime.fromisoformat(prior['observed_at'])).total_seconds()
            if window >= 300 and ref['latest_block'] >= prior['latest_block']:
                network_rate = (ref['latest_block'] - prior['latest_block']) / window
                gross_required = network_rate + net_required
                budget.update(network_sample_seconds=round(window), observed_network_blocks_per_second=round(network_rate, 5),
                              required_average_validated_blocks_per_second=round(gross_required, 5),
                              maximum_seconds_per_1000_validated_blocks=round(1000 / gross_required) if gross_required else None)
    audit = {
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'deadline': '2026-11-01T23:59:00+01:00',
        'repository': 'https://github.com/jordiparis165/ethereum-node-workshop',
        'criteria': {
            'source_build_execution_and_embedded_consensus': 'documented' if checks['source_build']['exit_code'] == 0 else 'check_failed',
            'strict_erigon_full_mode': 'not_met_minimal_mode' if '--prune.mode=minimal' in (
                checks['services']['output'] or (ROOT / 'configs/sync-performance.conf').read_text()) else 'manual_check_required',
            'synchronization': 'verified_in_saved_repeated_observations' if proof_valid else 'not_yet_verified',
            'public_https_wss_eth_web3_auth_tls': 'passed' if public.returncode == 0 else 'failed',
            'systemd_enabled': 'configured' if (checks['services']['exit_code'] == 0
                and checks['services']['output'].splitlines()[-5:] == ['enabled'] * 5) else 'check_failed',
            'actual_reboot_and_automatic_recovery': 'passed' if reboot.get('passed') is True else 'not_yet_verified',
            'screenshots': 'real_terminal_captures_in_screenshots',
            'spreadsheet': 'verified_already_present_in_F22' if sheet.get('value') == 'https://github.com/jordiparis165/ethereum-node-workshop'
                           else 'repository_url_ready_not_verified',
        },
        'reference': status.get('reference'),
        'deadline_budget': budget,
        'limitations': ['Minimal is not Erigon full mode; changing pruning requires resynchronization.',
                        'Peer count or eth_syncing=false alone do not prove synchronization.',
                        'No statistically credible completion probability is available.'],
    }
    write_json(evidence / 'submission-audit.json', audit)
    readme_path = ROOT / 'README.md'
    readme = readme_path.read_text(encoding='utf-8')
    begin, end = '<!-- LIVE_STATUS_BEGIN -->', '<!-- LIVE_STATUS_END -->'
    ref = status.get('reference') or {}
    live = (begin + '\nRelevé UTC : **' + status['observed_at'] + '**. Bloc RPC : **'
            + (str(int(status['block'], 16)) if not status.get('rpc_error') else 'indisponible') + '**. Écart avec la référence : **'
            + str(ref.get('remaining_blocks', 'non mesuré')) + ' blocs**.\n\n'
            + 'Synchronisation : `' + audit['criteria']['synchronization'] + '`. Reboot : `'
            + audit['criteria']['actual_reboot_and_automatic_recovery'] + '`.\n' + end)
    if begin in readme and end in readme:
        left, rest = readme.split(begin, 1)
        _, right = rest.split(end, 1)
        readme = left + live + right
    else:
        heading = '## État du rendu au 1er novembre'
        readme = readme.replace(heading, heading + '\n\n' + live, 1)
    readme_path.write_text(readme, encoding='utf-8', newline='\n')
    subprocess.run([sys.executable, str(ROOT / 'scripts/build_report_pdf.py')], check=True, cwd=ROOT, env=env)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    if public.returncode:
        raise RuntimeError('Public RPC verification failed; inspect evidence/current-public-rpc.log')


if __name__ == '__main__':
    main()
