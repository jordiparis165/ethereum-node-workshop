import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "btc"))
import watch_sync


COMMANDS = {
    "build": "printf '$ /data/ethereum-src/geth-src/build/bin/geth version\\n'; /data/ethereum-src/geth-src/build/bin/geth version | head -7; printf '\\n$ lighthouse --version\\n'; /home/adm-mesifi/.cargo/bin/lighthouse --version",
    "services": "printf '$ systemctl is-active geth.service lighthouse.service\\n'; systemctl is-active geth.service lighthouse.service; printf '\\n$ systemctl is-enabled geth.service lighthouse.service\\n'; systemctl is-enabled geth.service lighthouse.service; printf '\\n$ nproc; free -h; df -h /data\\n'; nproc; free -h; df -h /data; printf '\\n$ RPC/API listeners\\n'; ss -lntup | grep -E ':(8545|8546|8551|5052|5054|30303|9000)\\b' || true",
    "rpc": "python3 - <<'PY'\nimport json, urllib.request\nfor method in ('eth_chainId', 'web3_clientVersion', 'net_peerCount', 'eth_blockNumber'):\n data=json.dumps({'jsonrpc':'2.0','method':method,'params':[],'id':1}).encode()\n req=urllib.request.Request('http://127.0.0.1:8545',data=data,headers={'Content-Type':'application/json'})\n print('$',method)\n print(urllib.request.urlopen(req,timeout=30).read().decode())\nprint('$ Lighthouse /eth/v1/node/version')\nprint(urllib.request.urlopen('http://127.0.0.1:5052/eth/v1/node/version',timeout=30).read().decode())\nPY",
    "sync": "printf '$ systemctl is-active geth.service lighthouse.service\\n'; systemctl is-active geth.service lighthouse.service; printf '\\n$ Lighthouse sync status\\n'; curl -fsS http://127.0.0.1:5052/eth/v1/node/syncing; printf '\\n\\n$ Geth eth_syncing\\n'; python3 - <<'PY'\nimport json,urllib.request\ndata=json.dumps({'jsonrpc':'2.0','method':'eth_syncing','params':[],'id':1}).encode()\nreq=urllib.request.Request('http://127.0.0.1:8545',data=data,headers={'Content-Type':'application/json'})\nprint(urllib.request.urlopen(req,timeout=30).read().decode())\nPY\nprintf '\\n$ Latest Geth sync log\\n'; journalctl -u geth.service -n 4 --no-pager | tail -4",
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
