import argparse
import runpy
import sys
from pathlib import Path

import vps_ssh as watch_sync


COMMANDS = {
    "build": r"""echo '$ Erigon v3.8.1 (source build)'; /data/ethereum-src/erigon-v3.8.1/build/bin/erigon --version; echo '$ Previous Geth/Lighthouse source builds'; /data/ethereum-src/geth-src/build/bin/geth version | head -3; /home/adm-mesifi/.cargo/bin/lighthouse --version""",
    "services": r"""echo '$ systemctl is-active erigon geth lighthouse'; systemctl is-active erigon.service geth.service lighthouse.service || true; echo '$ systemctl is-enabled erigon geth lighthouse'; systemctl is-enabled erigon.service geth.service lighthouse.service || true; echo '$ CPU, RAM and disk'; nproc; free -h; df -h /data; echo '$ kernel settings'; cat /proc/sys/vm/overcommit_memory /proc/sys/vm/max_map_count; echo '$ RPC listeners'; ss -lntup | grep -E ':(8545|8546|30303|6061)\b' || true""",
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
print('head_age_seconds =',None if head is None or int(head.get('number','0x0'),16)==0 else int(time.time())-int(head['timestamp'],16))
logs=subprocess.check_output(['journalctl','-q','-u','erigon.service','--since','20 minutes ago','--no-pager'],text=True,stderr=subprocess.DEVNULL).splitlines()
execution=next((line for line in reversed(logs) if '[4/6 Execution] parallel executed' in line),None)
if execution:
 match=re.search(r'blk=(\d+).*?blk/s=([\d.]+).*?isApplyingBlocks=(\w+)',execution)
 print('execution_stage =',f'block={match.group(1)} rate={match.group(2)} blk/s applying={match.group(3)}' if match else execution[-180:])
commitment=next((line for line in reversed(logs) if '[4/6 Execution] parallel committed' in line),None)
if commitment:
 match=re.search(r'blk=(\d+).*?progress=([^ ]+)',commitment)
 print('state_commitment =',f'validated_block={match.group(1)} keys={match.group(2)}' if match else commitment[-180:])
 print('The key counter can advance while the validated block stays unchanged.')
errors=[line for line in logs if any(pattern in line for pattern in ('[ERROR]','[EROR]','[CRIT]','Wrong trie root','halting process'))]
print('errors_in_last_20_minutes =',len(errors))
PY
echo '$ Disk and RAM'; df -h /data; free -h""",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=[*COMMANDS, "public"], required=True)
    section = parser.parse_args().section
    if section == "public":
        runpy.run_path(str(Path(__file__).with_name("test-public-rpc.py")), run_name="__main__")
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
