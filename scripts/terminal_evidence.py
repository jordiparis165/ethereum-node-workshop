import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "btc"))
import watch_sync


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
def rpc(method,params=[]):
 data=json.dumps({'jsonrpc':'2.0','method':method,'params':params,'id':1}).encode()
 req=urllib.request.Request('http://127.0.0.1:8545',data=data,headers={'Content-Type':'application/json'})
 return json.loads(urllib.request.urlopen(req,timeout=30).read())['result']
print('eth_chainId =',rpc('eth_chainId'))
print('eth_blockNumber =',rpc('eth_blockNumber'))
print('eth_syncing =',rpc('eth_syncing'))
head=rpc('eth_getBlockByNumber',['latest',False])
print('head_age_seconds =',None if head is None else int(time.time())-int(head['timestamp'],16))
PY
echo '$ Recent snapshot and Caplin logs'; journalctl -u erigon.service -n 18 --no-pager | grep -E 'Downloader|Caplin|Checkpoint Sync|Starting caplin' | tail -10; echo '$ Disk and RAM'; df -h /data; free -h""",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=COMMANDS, required=True)
    section = parser.parse_args().section
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
