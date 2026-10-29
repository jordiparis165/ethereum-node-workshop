# Verification Evidence

Captured on 29 October 2026 from the school VPS.

## Builds

```text
Geth v1.17.10-stable
Lighthouse v8.3.2-a376def
```

Both binaries were produced by `make` from shallow clones of the official
source repositories.

## Services

```text
geth.service: enabled, active
lighthouse.service: enabled, active
```

`systemd-analyze verify` reported no unit errors.

## RPC

```text
eth_chainId       -> 0x1
web3_clientVersion -> Geth/v1.17.10-stable-1df30b18/linux-amd64/go1.25.0
net_peerCount     -> 0xa
Beacon API        -> Lighthouse/v8.3.2-a376def/x86_64-linux
```

The HTTP endpoint was tested from outside the VPS at port `8545`; the WebSocket
port `8546` and Beacon API port `5052` accepted TCP connections. The Engine API
remained bound to localhost on `8551`.

## Synchronization

At capture time Lighthouse reported:

```json
{
  "is_syncing": true,
  "is_optimistic": true,
  "el_offline": false,
  "sync_distance": "39"
}
```

The node was therefore operational but not yet fully synchronized. The VPS has
1 TB of data storage while the assignment requests 2 TB, so the final storage
and full-sync criteria require a larger volume.
