# Nœud Ethereum

Pour ce TD, j’ai d’abord installé Geth avec Lighthouse. La synchronisation avançait, mais les estimations de Geth dépassaient le délai du rendu. Après le conseil du prof, j’ai compilé Erigon depuis ses sources et je l’utilise maintenant avec Caplin, son client de consensus intégré. Les anciennes bases Geth et Lighthouse sont gardées sur le VPS, mais leurs services sont arrêtés.

## La VM

Le VPS a 8 vCPU, 22 Gio de RAM et un volume `/data` de 984 Go. Le sujet indique 2 To, mais le prof a précisé le 30 octobre que 1 To devrait suffire. Erigon tourne en mode minimal, prévu pour tenir dans cette capacité. La machine a assez de mémoire pour démarrer, mais son disque est rotatif et plus lent que le NVMe utilisé dans les mesures officielles d’Erigon.

## Compilation

J’ai gardé les builds Geth et Lighthouse faits au début, puis j’ai compilé Erigon v3.8.1 depuis le tag officiel. Erigon demande Go 1.26 ou plus récent; la version système était 1.24.4. Le lanceur automatique de Go a planté au début, alors j’ai utilisé directement le toolchain Go 1.26.10 téléchargé dans le cache Go.

```bash
git clone --depth 1 --branch v3.8.1 \
  https://github.com/erigontech/erigon.git /data/ethereum-src/erigon-v3.8.1
cd /data/ethereum-src/erigon-v3.8.1

GOROOT="$HOME/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.10.linux-amd64"
export GOROOT
export PATH="$GOROOT/bin:$PATH"
export GOTOOLCHAIN=local
GOMAXPROCS=6 make erigon
```

Le binaire compilé est `build/bin/erigon`. Erigon lance Caplin dans le même processus, donc il n’y a pas de service Lighthouse séparé dans la configuration finale. Caplin télécharge son checkpoint de consensus puis suit la chaîne avec Erigon.

## Configuration

Le service [`configs/erigon.service`](configs/erigon.service) démarre Erigon sur mainnet en mode `minimal`. Il est activé avec systemd. Les endpoints RPC HTTP et WebSocket utilisent les ports `8545` et `8546`, avec seulement les namespaces `eth`, `net` et `web3`. Les métriques restent locales sur `6061`. Le port Engine API ne sert pas à une connexion externe; Caplin est intégré.

Le fichier [`configs/99-erigon.conf`](configs/99-erigon.conf) règle `vm.overcommit_memory` et `vm.max_map_count`, comme recommandé au démarrage par Erigon. Le dossier Geth reste dans `/data/ethereum/geth` et celui de Lighthouse dans `/data/ethereum/lighthouse`, en cas de retour arrière.

## Vérifications

Le script [`scripts/check-node.sh`](scripts/check-node.sh) vérifie les services, les ports et quelques requêtes RPC. Sur mainnet, `eth_chainId` doit renvoyer `0x1`. Pour savoir si la synchronisation est finie, il faut aussi vérifier `eth_syncing` et le bloc courant; un endpoint qui répond ne suffit pas à prouver que le nœud est synchronisé.

Le script `scripts/watch_until_synced.py` refait ces contrôles toutes les minutes. Il ne publiera les preuves de synchronisation terminée que si `eth_syncing` vaut `false`, si le bloc courant est non nul et si son horodatage est récent. Les captures du dossier [`screenshots/`](screenshots/) sont faites depuis un vrai terminal Windows connecté au VPS par SSH.

## Limites

Les temps annoncés dans les docs Erigon ont été mesurés sur une machine plus puissante, avec NVMe et beaucoup plus de RAM. Ils ne garantissent pas la même durée sur ce VPS. Le mode minimal économise l’espace, mais garde moins d’historique qu’un nœud complet configuré avec le mode `full`. Je laisse donc le rapport s’appuyer sur l’état réellement retourné par les clients, pas sur une estimation.

Le compte rendu avec les captures est dans [`RAPPORT-ETHEREUM.pdf`](RAPPORT-ETHEREUM.pdf).
