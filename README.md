# Ethereum Node Deployment Workshop

Mainnet Ethereum node deployment using Geth v1.17.10 for the execution layer
and Lighthouse v8.3.2 for the consensus layer. Both clients are compiled from
their official source repositories; Docker and pre-built client binaries are
not used.

Le compte rendu rédigé pour le rendu est disponible dans
[`RAPPORT.md`](RAPPORT.md).

## Hardware and Constraint

The VPS has 8 vCPUs, 22 GiB RAM and a 1 TB `/data` volume. The assignment
requires 2 TB, so the current VPS allocation does not meet the storage
requirement. This must be resolved before claiming a fully synchronized node.

## Build

```bash
sudo apt-get update
sudo apt-get install -y git golang-go build-essential clang libclang-dev \
  pkg-config libssl-dev protobuf-compiler jq curl cmake ninja-build

git clone --depth 1 --branch v1.17.10 \
  https://github.com/ethereum/go-ethereum.git /data/ethereum-src/geth-src
cd /data/ethereum-src/geth-src
make geth

git clone --depth 1 --branch v8.3.2 \
  https://github.com/sigp/lighthouse.git /data/ethereum-src/lighthouse-src
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
source "$HOME/.cargo/env"
cd /data/ethereum-src/lighthouse-src
make
```

The Debian Rust compiler was too old for Lighthouse v8.3.2, so the official
Rust stable toolchain was installed with rustup. CMake was also required by a
native Lighthouse dependency.

## Configuration

Geth uses mainnet snap sync, HTTP RPC on `8545`, WebSocket RPC on `8546`, and
only the `eth`, `net` and `web3` namespaces on public RPC. The Engine API is
bound to `127.0.0.1:8551` and protected by a 32-byte JWT secret. P2P uses
TCP/UDP `30303`.

Lighthouse uses mainnet, the local Engine API and JWT secret, checkpoint sync,
the beacon API on `5052`, Prometheus metrics on `5054`, and consensus P2P on
TCP/UDP `9000`.

Secrets are stored only on the VPS and are excluded from this repository.

## Services

The systemd templates are in [`configs/`](configs/). Both services are enabled
at boot and restart after failures:

```bash
sudo systemctl enable --now geth.service lighthouse.service
systemctl status geth.service lighthouse.service
```

## Verification

Run [`scripts/check-node.sh`](scripts/check-node.sh) on the VPS. It checks
service state, mainnet chain ID, execution RPC, WebSocket listeners, beacon API,
peer counts and resource usage. Expected mainnet chain ID is `0x1`.

Example RPC checks:

```bash
curl -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' \
  http://127.0.0.1:8545

curl -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"web3_clientVersion","params":[],"id":2}' \
  http://127.0.0.1:8545
```

The Engine API is intentionally local-only. Public RPC exposes only read/query
namespaces; production deployment should add firewall rules or a reverse
proxy/rate limiter before allowing arbitrary internet clients.

## Evidence Checklist

Capture screenshots for source build completion, `systemctl status`, RPC
responses, beacon API response, resource usage, and `systemctl is-enabled`.

The current VPS has 1 TB instead of the required 2 TB. A fully synchronized
Ethereum mainnet node cannot be certified until a larger volume is attached or
the assignment accepts the current allocation.
