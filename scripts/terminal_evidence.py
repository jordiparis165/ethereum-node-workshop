import argparse
import runpy
import sys
from pathlib import Path

import vps_ssh as watch_sync


COMMANDS = {
    "memory": r"""date -Is
systemctl show erigon -p ActiveState -p MainPID -p Environment
free -h; /usr/sbin/swapon --show
echo '$ swap units active / enabled'; systemctl is-active var-lib-erigon_swap.swap var-lib-erigon_swap_extra.swap; systemctl is-enabled var-lib-erigon_swap.swap var-lib-erigon_swap_extra.swap
echo '$ OOM events'; grep -E '^oom( |_)' /sys/fs/cgroup/system.slice/erigon.service/memory.events""",
    "storage": r"""python3 - <<'PY'
import json, shutil, subprocess
from datetime import datetime
from pathlib import Path
print('VPS time =', datetime.now().astimezone().isoformat(timespec='seconds'))
for unit in ('erigon', 'ethereum-hot-storage-migration'):
 print(unit, '=', subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True).stdout.strip())
s=json.loads(Path('/var/lib/erigon-hot/migration-status.json').read_text())
print('migration phase =', s['phase'])
print('status recorded UTC =', s['observed_at'])
print('copy progress GiB =', round(s['copied_bytes']/1024**3,2), '/', round(s['total_bytes']/1024**3,2))
print('current file =', s.get('current_file','-'))
print('Copy progress is NOT Ethereum synchronization progress.')
print('Node restarted on fast storage; originals retained.' if s['phase']=='activated' else 'Erigon is paused cleanly during staging; originals are retained.')
for name in ('chaindata', 'snapshots/domain', 'caplin/indexing'):
 print(name, '->', Path('/data/erigon',name).resolve())
print('Fast-volume free GiB =', round(shutil.disk_usage('/var/lib/erigon-hot').free/1024**3,2))
PY""",
    "build": r"""date -Is
echo '$ source tag and commit'; git -C /data/ethereum-src/erigon-v3.8.1 describe --tags --always; git -C /data/ethereum-src/erigon-v3.8.1 rev-parse HEAD
echo '$ completion of actual build log'; tail -n 4 /data/ethereum-src/erigon-build-final.log
echo '$ installed binary'; /data/ethereum-src/erigon-v3.8.1/build/bin/erigon --version
echo '$ Go build metadata'; go version -m /data/ethereum-src/erigon-v3.8.1/build/bin/erigon | head -3
echo '$ consensus sources included in this source tree'; git -C /data/ethereum-src/erigon-v3.8.1 ls-files cl/phase1/stages | head -3
echo 'Caplin is compiled into the Erigon binary; no external consensus binary is used.'""",
    "services": r"""date -Is
python3 - <<'PY'
import subprocess
for unit in ('erigon','nginx','ethereum-sync-monitor.timer','var-lib-erigon_swap.swap','var-lib-erigon_swap_extra.swap'):
 def state(action):return subprocess.run(['systemctl',action,unit],text=True,capture_output=True).stdout.strip()
 print(unit,':',state('is-active'),'; boot =',state('is-enabled'))
PY
echo '$ RAM and storage'; free -h; df -h / /data
echo '$ RPC listeners'; ss -lnt | grep -E ':(9443|8545|8546|8551|6061)\b'
echo 'Enabled units do not prove a completed reboot test.'""",
    "rpc": r"""python3 - <<'PY'
import json, urllib.request
for method in ('eth_chainId', 'web3_clientVersion', 'net_peerCount', 'eth_blockNumber', 'eth_syncing'):
 data=json.dumps({'jsonrpc':'2.0','method':method,'params':[],'id':1}).encode()
 req=urllib.request.Request('http://127.0.0.1:8545',data=data,headers={'Content-Type':'application/json'})
 print('$',method)
 print(urllib.request.urlopen(req,timeout=30).read().decode())
print('Consensus layer: Caplin integrated in Erigon (Beacon API kept disabled to save RAM).')
PY""",
    "sync": r"""echo '$ Erigon service'; systemctl is-active erigon.service; python3 - <<'PY'
import json, time, urllib.request
from datetime import datetime
import re, subprocess
def rpc(method,params=[]):
 data=json.dumps({'jsonrpc':'2.0','method':method,'params':params,'id':1}).encode()
 req=urllib.request.Request('http://127.0.0.1:8545',data=data,headers={'Content-Type':'application/json'})
 return json.loads(urllib.request.urlopen(req,timeout=30).read())['result']
print('VPS time =',datetime.now().astimezone().isoformat(timespec='seconds'))
print('eth_chainId =',rpc('eth_chainId'))
print('eth_blockNumber =',rpc('eth_blockNumber'))
sync=rpc('eth_syncing')
print('eth_syncing =',sync if not isinstance(sync,dict) else {key:sync.get(key) for key in ('currentBlock','highestBlock')})
if isinstance(sync,dict):
 target=sync.get('highestBlock')
 if target:
  block=rpc('eth_getBlockByNumber',[target,False])
  print('snapshot target block available =',None if block is None else block.get('number'))
head=rpc('eth_getBlockByNumber',['latest',False])
print('validated_head_decimal =',None if head is None else int(head['number'],16))
print('head_age_seconds =',None if head is None or int(head.get('number','0x0'),16)==0 else int(time.time())-int(head['timestamp'],16))
logs=subprocess.check_output(['journalctl','-q','-u','erigon.service','--since','20 minutes ago','--no-pager'],text=True,stderr=subprocess.DEVNULL).splitlines()
execution=next((line for line in reversed(logs) if '[4/6 Execution] parallel executed' in line),None)
if execution:
 match=re.search(r'blk=(\d+).*?blk/s=([\d.]+).*?isApplyingBlocks=(\w+)',execution)
 print('execution_stage =',f'block={match.group(1)} rate={match.group(2)} blk/s applying={match.group(3)}' if match else execution[-180:])
commitment=next((line for line in reversed(logs) if '[4/6 Execution] parallel committed' in line),None)
if commitment:
 match=re.search(r'blk=(\d+).*?progress=([^ ]+)',commitment)
 if match and head and int(match.group(1)) < int(head['number'],16):
  print('state_commitment = last logged counter belongs to an earlier batch')
 else:
  print('state_commitment =',f'last_logged_block={match.group(1)} keys={match.group(2)}' if match else commitment[-180:])
  print('The key counter can advance while the validated block stays unchanged.')
errors=[line for line in logs if any(pattern in line for pattern in ('[ERROR]','[EROR]','[CRIT]','Wrong trie root','halting process'))]
print('errors_in_last_20_minutes =',len(errors))
PY
echo '$ Disk and RAM'; df -h /data; free -h""",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=[*COMMANDS, "public", "reference"], required=True)
    section = parser.parse_args().section
    if section == "public":
        runpy.run_path(str(Path(__file__).with_name("test-public-rpc.py")), run_name="__main__")
        return
    if section == 'reference':
        import json
        from watch_until_synced import read_status
        client = watch_sync.connect(watch_sync.load_env(watch_sync.ENV_PATH))
        try:
            status = read_status(client)
        finally:
            client.close()
        print('Observation UTC =', status['observed_at'])
        print('Erigon service =', status['service'])
        print('Local validated RPC head =', int(status['block'], 16) if not status.get('rpc_error') else 'unavailable')
        print('Local head age seconds =', status['head_age_seconds'])
        print('eth_syncing =', status['eth_syncing'] if not isinstance(status['eth_syncing'],dict) else 'in progress')
        print('Independent mainnet reference:')
        print(json.dumps(status.get('reference', {'error':status.get('reference_error')}), indent=2))
        print('A local batch target is NOT the current mainnet head.')
        print('Full confirmation requires 3 advancing observations over at least 2 minutes.')
        return
    config = watch_sync.load_env(watch_sync.ENV_PATH)
    client = watch_sync.connect(config)
    try:
        _, output, error = watch_sync.run_remote(client, COMMANDS[section])
    finally:
        client.close()
    print(output.rstrip())
    if error.strip():
        print(error.rstrip(), file=sys.stderr)


if __name__ == "__main__":
    main()
