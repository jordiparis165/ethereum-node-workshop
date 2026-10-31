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

Les outils de suivi sur mon PC utilisent Python : `pip install -r requirements.txt`. Ils lisent un `.env` local au format de [`.env.example`](.env.example); sur mon poste, ils reprennent directement le fichier `btc/.env` déjà présent dans le dossier parent. Les secrets restent hors du dépôt. Les captures automatiques demandent Windows et une session ouverte, mais le suivi systemd sur le VPS fonctionne indépendamment.

Le script [`scripts/check-node.sh`](scripts/check-node.sh) vérifie les services, les ports et quelques requêtes RPC. Sur mainnet, `eth_chainId` doit renvoyer `0x1`. Pour savoir si la synchronisation est finie, il faut aussi vérifier `eth_syncing` et le bloc courant; un endpoint qui répond ne suffit pas à prouver que le nœud est synchronisé.

Le script `scripts/watch_until_synced.py` refait ces contrôles toutes les minutes depuis mon PC. Il ne publiera les preuves de synchronisation terminée que si `eth_syncing` vaut `false`, si le bloc courant est non nul et si son horodatage est récent. Les captures du dossier [`screenshots/`](screenshots/) sont faites depuis un vrai terminal Windows connecté au VPS par SSH, ou depuis ce PC pour les tests publics.

Le timer `ethereum-sync-monitor.timer`, activé sur le VPS, conserve aussi les mesures toutes les deux minutes dans `/data/ethereum-monitor/observations.jsonl`. Il fonctionne même si mon PC est éteint. Un fichier `first-verified-sync.json` est créé seulement quand les contrôles de fin passent; il ne déclenche ni arrêt ni redémarrage d'Erigon. Pour voir le dernier état : `cat /data/ethereum-monitor/latest.json`.

## Accès RPC public

Le 31 octobre, j'ai ajouté un proxy Nginx sans redémarrer Erigon :

- HTTPS : `https://vps-ae86b6b8.vps.ovh.net:9443/rpc`
- WebSocket TLS : `wss://vps-ae86b6b8.vps.ovh.net:9443/ws`

L'accès demande une authentification HTTP Basic. Les identifiants sont dans `rpc-access.secret` sur mon PC, exclu de Git; ils sont à transmettre séparément pour la correction. Le certificat est auto-signé et son certificat public est dans [`configs/rpc-tls.crt`](configs/rpc-tls.crt). Le script de test lui fait explicitement confiance et vérifie le nom du serveur; il ne désactive pas TLS. La configuration limite aussi les requêtes à 5/s, les connexions à 5 par IP et le corps des requêtes à 64 Ko.

Les tests externes du 31 octobre ont confirmé le refus sans identifiants (401), `eth_chainId=0x1` et `web3_clientVersion` en HTTPS et en WSS. Pour les refaire depuis le PC : `python scripts/test-public-rpc.py` (dépendance `websockets`). Le proxy utilise [`configs/ethereum-rpc.nginx.conf`](configs/ethereum-rpc.nginx.conf). Erigon reste sur localhost; seuls Nginx et les ports P2P sont publics. L'API Engine et les métriques restent privées.

## Incident du 31 octobre

Erigon a rejeté le calcul de racine d'état au bloc 26 301 999 à 02 h 25. J'ai d'abord utilisé le commitment séquentiel comme solution de secours, avec des lots de 2 Go et un arrêt propre pouvant durer dix minutes. La configuration est installée comme drop-in dans `/etc/systemd/system/erigon.service.d/`.

À 07 h 09, ce bloc a été validé et l'exécution a repris au-delà. À 09 h 59, le journal indiquait `progress=168.88k/304.52k` pour le calcul d'état courant. Ce compteur continue à bouger même si `blk/s=0` et que le numéro du dernier bloc validé reste fixe. Le code d'Erigon le calcule avec `KeyIndex/UpdateCount` (`execution/stagedsync/exec3_metrics.go`). Il faut donc surveiller les lignes `parallel committed` aussi, pas seulement `parallel executed`.

Le nœud n'est pas encore synchronisé au relevé du matin. La cible de `eth_syncing` est une cible locale qui peut être ancienne; son ratio ne prouve pas une synchronisation à 99,99 %. Le contrôle de fin exige toujours `eth_syncing=false` et une tête récente. Erigon et le timer sont activés au démarrage, mais je n'ai pas redémarré la VM pendant ce calcul pour tester la reprise après reboot. Ce test reste à faire pour compléter le sujet.

Documentation utilisée : [réglages Erigon](https://docs.erigon.tech/fundamentals/performance-tricks), [versions et mode séquentiel](https://github.com/erigontech/erigon/releases).

Mise à jour vers 11 h : l'étape Execution a terminé 1 000 blocs à 10 h 46 en 3 h 36 min. Le RPC expose le bloc 26 302 999 depuis la mise à jour de tête de 10 h 52. L'exécution a commencé le lot suivant, qui vise 26 303 999. La tête validée garde environ 30 heures de retard. Les captures et le PDF sont actualisés; `evidence/2026-10-31-latest-status.json` conserve le relevé brut. La synchronisation complète et le test de reboot restent à confirmer.

## Limites du VPS

Le 31 octobre vers 11 h 15, j'ai comparé 32 petites lectures aléatoires non présentes dans le cache du système : médiane d'environ 0,22 ms sur le disque système contre 31,82 ms sur `/data`. C'est un petit test de latence, pas une mesure de synchronisation complète. Une lecture séquentielle sur `/data` a donné environ 29 Mio/s. Le disque système avait environ 179 Gio disponibles.

La conservation des index `.bt` en RAM est configurée dans [`configs/ethereum-index-cache.service`](configs/ethereum-index-cache.service), avec `vmtouch`, un plafond de 4 Gio et environ 3 Gio d'index à charger. Elle est suspendue pendant la copie pour laisser le disque travailler, puis relancée après la bascule.

À 11 h 23, j'ai lancé [`scripts/prepare-hot-storage.py`](scripts/prepare-hot-storage.py) sur la VM via `ethereum-hot-storage-migration.service`. La préparation copie environ 132 Gio de snapshots et, après un arrêt propre, la base `chaindata` sur `/var/lib/erigon-hot`. Le gros fichier de commitment reste sur `/data`. Chaque copie est vérifiée par SHA-256. Les originaux sont conservés sous `domain.slow-backup` et `chaindata.slow-backup`, et les chemins habituels deviennent des liens vers le volume rapide. Le script garde une marge d'espace libre et rétablit les chemins d'origine si la bascule échoue avant le démarrage.

La copie est encore en cours au moment de cette mise à jour : le gain de débit n'est pas encore mesuré. Après le début de la préparation, j'ai choisi de mettre Erigon en pause proprement pendant la copie pour éviter la concurrence sur le disque lent. Les RPC sont temporairement indisponibles durant cette opération, puis le script relance le client. Le suivi est dans `/var/lib/erigon-hot/migration-status.json` et `journalctl -u ethereum-hot-storage-migration`. Les tests de copie et de retour arrière ont été exécutés sur Linux dans des dossiers temporaires (`tests/test_hot_storage.py`), sans agir sur le vrai nœud. Cette préparation ne prouve pas que la synchronisation sera terminée avant le rendu.

La répartition entre volumes suit le principe décrit dans la [documentation Erigon sur le stockage](https://docs.erigon.tech/fundamentals/optimizing-storage); la conservation des index en RAM vient des [réglages de performance](https://docs.erigon.tech/fundamentals/performance-tricks).

Vers 11 h 45, j'ai aussi ajusté temporairement la copie : plafond de cache passé de 2 à 8 Gio, prélecture du volume de 128 Kio à 4 Mio puis 16 Mio. Les débits observés sont passés d'environ 23 Mio/s avant réglage à 38 Mio/s, puis 65 Mio/s sur une fenêtre d'environ trois minutes. Les fichiers diffèrent selon les fenêtres : ce sont des observations de transfert, pas un benchmark contrôlé ni un délai de synchronisation. Le relevé est dans [`evidence/2026-10-31-copy-speed.json`](evidence/2026-10-31-copy-speed.json).

Le service temporaire `ethereum-copy-tuning` exécute [`scripts/tune-storage-copy.py`](scripts/tune-storage-copy.py). Il remet les paramètres d'origine dès que la copie de la base commence, avant qu'Erigon rouvre les fichiers pour ses lectures aléatoires. Les tests vérifient aussi la restauration après interruption. Les cinq tests de migration et de réglage ont passé sur Linux.

Vers 12 h 06, j'ai aussi déplacé `caplin/indexing`, `caplin/latest` et `caplin/history` sur le volume rapide, soit environ 1,8 Go. Le script [`scripts/prepare-caplin-storage.py`](scripts/prepare-caplin-storage.py) utilise la même copie vérifiée, conserve les répertoires `.slow-backup` et bloque le démarrage pendant la copie avec un verrou temporaire. Cela évite de laisser les bases du consensus sur le volume lent alors que l'exécution a été déplacée.

J'ai ensuite relu les journaux de 02 h 25 : `Got interrupt, shutting down` apparaît à 02:25:21, puis la mauvaise racine à 02:25:22. L'erreur est donc apparue pendant l'arrêt; elle ne prouve pas un défaut du calcul parallèle en fonctionnement normal. Pour la relance après migration, [`configs/sync-performance.conf`](configs/sync-performance.conf) rétablit le mode parallèle par défaut d'Erigon v3.8.1 (`DefaultParallelCommitment=true`). Les validations restent actives. La configuration séquentielle est conservée dans `configs/sync-performance.sequential-backup` si un vrai problème réapparaît.

Le suivi systemd calcule maintenant un champ `forecast` dans `/data/ethereum-monitor/latest.json`, avec l'échéance du rendu fixée au 31 octobre à 23 h 59 (Paris). Pendant la préparation, il ne donne qu'une estimation de transfert, séparée de la fin du nœud. Après la relance, il attend des blocs validés et mesure la diminution du retard de leur horodatage. Il ignore les anciennes mesures prises avant la migration. Son estimation reste conditionnelle au débit observé; seule la vérification RPC confirme la fin. Les douze tests de migration, de restauration et de calcul d'estimation ont passé sur Linux.

Les temps annoncés dans les docs Erigon ont été mesurés sur une machine plus puissante, avec NVMe et beaucoup plus de RAM. Ils ne garantissent pas la même durée sur ce VPS. Le mode minimal économise l’espace, mais garde moins d’historique qu’un nœud complet configuré avec le mode `full`. Je laisse donc le rapport s’appuyer sur l’état réellement retourné par les clients, pas sur une estimation.

Le compte rendu avec les captures est dans [`RAPPORT-ETHEREUM.pdf`](RAPPORT-ETHEREUM.pdf).
