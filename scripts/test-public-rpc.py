"""Test TLS, authentication and JSON-RPC from outside the VPS."""
import base64
import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]


def main():
    access = json.loads((ROOT / "rpc-access.secret").read_text(encoding="utf-8"))
    authority = f"{access['host']}:{access['port']}"
    context = ssl.create_default_context(cafile=str(ROOT / "configs/rpc-tls.crt"))
    authorization = "Basic " + base64.b64encode(
        f"{access['user']}:{access['password']}".encode()
    ).decode()
    print("Test time (UTC):", datetime.now(timezone.utc).isoformat())
    print("HTTP endpoint:", f"https://{authority}/rpc")
    print("TLS: hostname and certificate verified against configs/rpc-tls.crt")
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []})
    request = urllib.request.Request(
        f"https://{authority}/rpc", data=payload.encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(request, context=context, timeout=20)
    except urllib.error.HTTPError as exc:
        assert exc.code == 401, f"Expected 401, got {exc.code}"
        print("Without authentication: HTTP 401 (expected)")
    else:
        raise AssertionError("RPC unexpectedly accepted unauthenticated access")
    request.add_header("Authorization", authorization)
    for method in ("eth_chainId", "web3_clientVersion", "eth_blockNumber", "eth_syncing"):
        request.data = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": []}).encode()
        with urllib.request.urlopen(request, context=context, timeout=20) as response:
            result = json.load(response)
        assert "result" in result, result
        if method == "eth_chainId":
            assert result["result"] == "0x1", result
        value = result["result"]
        if isinstance(value, dict) and method == "eth_syncing":
            value = {key: value.get(key) for key in ("currentBlock", "highestBlock")}
        print("HTTPS", method, "=", value)
    for method in ('admin_nodeInfo', 'debug_metrics', 'personal_listAccounts'):
        request.data = json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': method, 'params': []}).encode()
        with urllib.request.urlopen(request, context=context, timeout=20) as response:
            result = json.load(response)
        assert result.get('error', {}).get('code') == -32601, result
        print('HTTPS', method, '= disabled (expected)')
    print("WebSocket endpoint:", f"wss://{authority}/ws")
    with connect(f"wss://{authority}/ws", ssl=context,
                 additional_headers={"Authorization": authorization}, open_timeout=20, close_timeout=2) as connection:
        for method in ("eth_chainId", "web3_clientVersion"):
            connection.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": []}))
            result = json.loads(connection.recv(timeout=20))
            assert "result" in result, result
            if method == "eth_chainId":
                assert result["result"] == "0x1", result
            print("WSS", method, "=", result["result"])
        connection.send(json.dumps({'jsonrpc': '2.0', 'id': 3, 'method': 'eth_subscribe', 'params': ['newHeads']}))
        subscription = json.loads(connection.recv(timeout=20))
        assert isinstance(subscription.get('result'), str), subscription
        connection.send(json.dumps({'jsonrpc': '2.0', 'id': 4, 'method': 'eth_unsubscribe',
                                    'params': [subscription['result']]}))
        while True:
            reply = json.loads(connection.recv(timeout=20))
            if reply.get('id') == 4:
                assert reply.get('result') is True, reply
                break
        print('WSS newHeads subscribe/unsubscribe = passed (notification delivery not tested)')
    print("Public HTTPS and WSS tests passed. This does not prove full synchronization.")


if __name__ == "__main__":
    main()
