# Nœud Ethereum

Pour ce TD, j’ai installé un nœud Ethereum mainnet sur le VPS de l’école. J’ai utilisé Geth pour l’exécution et Lighthouse pour le consensus. J’ai compilé les deux à partir de leurs dépôts officiels, sans Docker.

## La VM

La machine a 8 vCPU et 22 Gio de mémoire. Le disque `/data` fait environ 1 To. Le sujet en demande 2 To, donc il manque de la place par rapport au prérequis. Je le signale dans le compte rendu.

## Installation et compilation

J’ai installé les outils de compilation avec apt. Pour Geth, il faut Go et les outils C/C++. Lighthouse demande aussi Rust, CMake, Clang et Protobuf. La version de Rust fournie avec Debian était trop vieille ; j’ai installé la version stable avec rustup.

Sur Debian, la base des dépendances était :

```bash
sudo apt-get update
sudo apt-get install -y git golang-go build-essential clang libclang-dev \
  pkg-config libssl-dev protobuf-compiler jq curl cmake ninja-build

curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
source "$HOME/.cargo/env"
```

Les commandes principales que j’ai utilisées :

```bash
git clone --depth 1 --branch v1.17.10 \
  https://github.com/ethereum/go-ethereum.git /data/ethereum-src/geth-src
cd /data/ethereum-src/geth-src
make geth

git clone --depth 1 --branch v8.3.2 \
  https://github.com/sigp/lighthouse.git /data/ethereum-src/lighthouse-src
cd /data/ethereum-src/lighthouse-src
make
```

## Configuration

Geth est sur mainnet en mode snap. Le RPC HTTP utilise le port `8545`, le WebSocket `8546` et l’Engine API `8551`. L’Engine API reste accessible seulement en local et est protégée par le secret JWT partagé avec Lighthouse.

Lighthouse utilise aussi mainnet. Son API Beacon écoute sur `5052` et les métriques sur `5054`. Les deux clients sont lancés par systemd et configurés pour démarrer avec la VM. Les fichiers de service sont dans [`configs/`](configs/). Le secret JWT n’est pas dans ce dépôt.

## Vérifications

J’ai utilisé [`scripts/check-node.sh`](scripts/check-node.sh) pour vérifier les services, le réseau, les ports et les réponses RPC. Pour interroger Geth directement depuis le VPS :

```bash
curl -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' \
  http://127.0.0.1:8545
```

Sur mainnet, `eth_chainId` doit répondre `0x1`. Les captures dans [`screenshots/`](screenshots/) montrent les versions des clients, les ports, les tests RPC et le relevé de synchronisation fait sur la VM.

## Où en est la synchronisation ?

Au dernier relevé, Geth n’avait pas encore de bloc courant et Lighthouse indiquait que sa tête était optimiste. Le nœud n’était donc pas complètement synchronisé à ce moment-là. Le script de surveillance mis à disposition dans `scripts/` refait le contrôle périodiquement et met à jour les preuves si les deux clients finissent par être synchronisés.

Le volume actuel est inférieur aux 2 To demandés. C’est la limite principale de cette VM pour ce TD.

## Compte rendu

Le compte rendu avec les captures est dans [`RAPPORT-ETHEREUM.pdf`](RAPPORT-ETHEREUM.pdf).
