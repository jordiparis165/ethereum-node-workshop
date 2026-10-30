#!/usr/bin/env bash
set -euo pipefail

echo '=== services ==='
systemctl is-active erigon.service geth.service lighthouse.service || true
systemctl is-enabled erigon.service geth.service lighthouse.service || true

echo '=== resources ==='
nproc
free -h
df -h /data

echo '=== execution RPC ==='
curl -fsS -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' \
  http://127.0.0.1:8545
echo
curl -fsS -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"web3_clientVersion","params":[],"id":2}' \
  http://127.0.0.1:8545
echo
curl -fsS -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":3}' \
  http://127.0.0.1:8545
echo
curl -fsS -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_syncing","params":[],"id":4}' \
  http://127.0.0.1:8545
echo

echo '=== consensus layer ==='
echo 'Caplin is integrated in Erigon; the separate Lighthouse service is retained but disabled.'

echo '=== listeners ==='
ss -lntup | grep -E ':(8545|8546|30303|6061)\b' || true
