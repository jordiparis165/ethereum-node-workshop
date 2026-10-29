#!/usr/bin/env bash
set -euo pipefail

echo '=== services ==='
systemctl is-active geth.service lighthouse.service
systemctl is-enabled geth.service lighthouse.service

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

echo '=== beacon API ==='
curl -fsS http://127.0.0.1:5052/eth/v1/node/version || true
echo

echo '=== listeners ==='
ss -lntup | grep -E ':(8545|8546|8551|5052|5054|30303|9000)\b' || true
