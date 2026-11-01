"""Read an independent mainnet head; never use it as this node's RPC endpoint."""
import json
import time
import urllib.request
from datetime import datetime, timezone

PROVIDER = 'https://ethereum-rpc.publicnode.com'


def rpc(method, params):
    request = urllib.request.Request(
        PROVIDER, data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(),
        headers={'Content-Type': 'application/json', 'User-Agent': 'EthereumWorkshopVerification/1.0'},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        value = json.load(response)
    if 'error' in value:
        raise RuntimeError(value['error'])
    return value['result']


def reference_status(local_height, local_hash):
    if rpc('eth_chainId', []) != '0x1':
        raise RuntimeError('Reference provider is not on mainnet')
    head = rpc('eth_getBlockByNumber', ['latest', False])
    number = int(head['number'], 16)
    same_height = head if number == local_height else rpc('eth_getBlockByNumber', [hex(local_height), False])
    return {'provider': PROVIDER, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'latest_block': number, 'head_timestamp': int(head['timestamp'], 16),
            'head_age_seconds': int(time.time()) - int(head['timestamp'], 16),
            'remaining_blocks': number - local_height,
            'local_block_hash_matches': bool(same_height and same_height['hash'] == local_hash)}
