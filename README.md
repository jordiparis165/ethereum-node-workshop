# Nœud Ethereum

Pour ce TD, j’ai d’abord installé Geth avec Lighthouse. La synchronisation avançait, mais les estimations de Geth dépassaient le délai du rendu. Après le conseil du prof, j’ai compilé Erigon depuis ses sources et je l’utilise maintenant avec Caplin, son client de consensus intégré. Les anciennes bases Geth et Lighthouse sont gardées sur le VPS, mais leurs services sont arrêtés.

## État du rendu au 1er novembre

<!-- LIVE_STATUS_BEGIN -->
Relevé UTC : **2026-11-01T12:45:19.757947+00:00**. Bloc RPC : **26316998**. Écart avec la référence : **3007 blocs**.

Synchronisation : `not_yet_verified`. Reboot : `not_yet_verified`.
<!-- LIVE_STATUS_END -->

Le dépôt est consultable ici : **https://github.com/jordiparis165/ethereum-node-workshop**. Le rapport est uniquement en PDF : [RAPPORT-ETHEREUM.pdf](RAPPORT-ETHEREUM.pdf).

L'état vérifiable le plus récent est dans [evidence/submission-audit.json](evidence/submission-audit.json), avec les réponses RPC et les contrôles système associés. Ne pas déduire une synchronisation terminée des captures historiques.

- Compilation depuis les sources : Erigon v3.8.1, qui inclut le code de Caplin dans le même binaire. Ce ne sont pas deux téléchargements de binaires précompilés.
- HTTPS/WSS, authentification, TLS, namespaces `eth` et `web3` : testés depuis le PC. Les API `admin`, `debug` et `personal` sont désactivées.
- Services activés au démarrage : configurés. Le résultat du test réel de reboot figure dans `evidence/reboot-verification.json` lorsqu'il est exécuté.
- Synchronisation complète : sa validation exige trois observations espacées, une tête récente et une comparaison avec une référence mainnet indépendante; consulter l'état horodaté ci-dessous et les preuves JSON.
- **Écart au sujet : `--prune.mode=minimal`, pas `--prune.mode=full`.** Je ne présente pas ce mode comme conforme au mode full d'Erigon. La [documentation officielle](https://docs.erigon.tech/fundamentals/pruning-modes) demande une resynchronisation pour changer de mode; je préserve donc la base existante plutôt que de repartir de zéro avant l'échéance.
- Le lien du dépôt était déjà présent dans le tableur, cellule `Feuille 1!F22`, sur la ligne Jordi PARIS / TP-MESIFI590426-07. Lecture de contrôle effectuée le 1er novembre, sans modification : [preuve du contrôle](evidence/spreadsheet-submission.json).

Le nouvel objectif de rendu est le **1er novembre 2026 à 23 h 59, heure de Paris**. Les mesures ci-dessous datant du 31 octobre sont conservées comme historique.

## La VM

Le VPS Debian 13 a 8 vCPU, environ 22 Gio de RAM, un volume système de 197 Gio et un volume `/data` de 984 Gio. Le sujet indique 2 To, mais le prof a précisé le 30 octobre que 1 To devrait suffire. Le volume `/data` a une latence mesurée bien plus élevée que le volume système. Le drapeau virtuel `ROTA=1` ne prouve pas le type de disque physique de l'hébergeur.

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

## Refaire l'installation

Ces chemins correspondent au VPS du TD et au compte Linux `adm-mesifi`; adapter les champs `User`, `Group` et les chemins des unités pour une autre machine. Ne pas lancer une nouvelle installation ou une migration sur la base qui synchronise déjà.

1. Sur une machine vierge, installer les dépendances :

```bash
sudo apt update
sudo apt install git curl ca-certificates build-essential pkg-config cmake clang libssl-dev python3 python3-venv nginx openssl
sudo install -d -o adm-mesifi -g adm-mesifi /data/ethereum-src /data/erigon /data/ethereum-monitor
```

2. Installer Go 1.26 ou plus récent depuis [go.dev/doc/install](https://go.dev/doc/install), puis compiler le tag avec `GOMAXPROCS=6 make erigon`. Les commandes de la section Compilation montrent le toolchain effectivement utilisé sur cette VM. Le commit source observé est `cf6f14132ff042df33b8ce64b0114daeb0d15145`; le journal de build et l'identité du binaire sont conservés dans les preuves.

3. Depuis une copie de ce dépôt sur la VM, installer les unités et réglages :

```bash
sudo install -m 644 configs/99-erigon.conf /etc/sysctl.d/99-erigon.conf
sudo sysctl --system
sudo install -m 644 configs/erigon.service /etc/systemd/system/erigon.service
sudo install -d /etc/systemd/system/erigon.service.d
sudo install -m 644 configs/sync-performance.conf configs/memory-safety.conf /etc/systemd/system/erigon.service.d/
sudo install -m 644 configs/var-lib-erigon_swap.swap /etc/systemd/system/
sudo python3 scripts/configure-memory-safety.py
sudo systemctl daemon-reload
sudo systemctl enable --now erigon.service
```

`GOMEMLIMIT=14GiB` laisse une marge au système et au cache disque. C'est une cible Go souple, pas un plafond strict. Le swap de 4 Gio est un secours pour les pointes mémoire. Les symlinks de stockage de cette VM résultent d'une migration séparée et vérifiée; ils ne sont pas nécessaires pour une première installation sur un volume rapide suffisamment grand.

4. Installer le monitoring :

```bash
sudo install -o adm-mesifi -g adm-mesifi -m 644 scripts/record-sync.py scripts/sync_activity.py scripts/sync_forecast.py /data/ethereum-monitor/
sudo install -m 644 configs/ethereum-sync-monitor.service configs/ethereum-sync-monitor.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ethereum-sync-monitor.timer
```

5. Sur le PC, installer `requirements.txt`, renseigner le `.env` local à partir de `.env.example`, puis lancer `python scripts/deploy-rpc-proxy.py`. Ce script installe le certificat, l'authentification et la configuration Nginx par SSH; ses identifiants restent dans `rpc-access.secret`, jamais dans Git. Tester avec `python scripts/test-public-rpc.py`. Le certificat auto-signé public du dépôt doit être explicitement approuvé par le client de test.

6. Actualiser les preuves avec `python scripts/prepare_submission.py`, puis générer de vraies captures avec `python scripts/capture_terminal.py --section sync --output screenshots/04-synchronisation.png`. Les captures exigent une session Windows ouverte; le script refuse de capturer si le terminal n'est pas au premier plan.

## Configuration

Le service [`configs/erigon.service`](configs/erigon.service) démarre Erigon sur mainnet en mode `minimal`. Il est activé avec systemd. Les endpoints RPC HTTP et WebSocket utilisent les ports `8545` et `8546`, avec seulement les namespaces `eth`, `net` et `web3`. Les métriques restent locales sur `6061`. Le port Engine API ne sert pas à une connexion externe; Caplin est intégré.

Le fichier [`configs/99-erigon.conf`](configs/99-erigon.conf) règle `vm.overcommit_memory` et `vm.max_map_count`, comme recommandé au démarrage par Erigon. Le dossier Geth reste dans `/data/ethereum/geth` et celui de Lighthouse dans `/data/ethereum/lighthouse`, en cas de retour arrière.

## Vérifications

Le script de finition est `python scripts/watch_until_synced.py`. Il utilise le `.env` existant, sans mot de passe dans la commande. Il compare le hash de notre bloc avec une référence mainnet indépendante, puis attend trois observations cohérentes sur au moins deux minutes avant de sauvegarder une preuve de synchronisation. Une tête ancienne avec `eth_syncing=false` ne passe pas ce contrôle.

Après publication de ces preuves, le test de reboot préparé ne se déclenche qu'avec au moins une heure de marge avant le 1er novembre à 23 h 59. Il doit constater un boot ID différent, des services actifs et activés, puis une nouvelle qualification de synchronisation. Ses garde-fous ont été testés; cela ne signifie pas que le reboot réel a déjà eu lieu. Une photographie du résultat sera ajoutée seulement si une vraie capture est possible.

Si le nœud n'est pas prêt à 23 h 30, le script prépare et publie un état honnête avant l'échéance, puis continue son suivi. Le PC doit rester allumé et connecté pour les tests publics, les captures et GitHub. Le timer du VPS continue ses relevés indépendamment, mais il ne dispose pas des identifiants GitHub et ne peut pas publier à la place du PC. Une VM devenue inaccessible est signalée comme telle; les anciennes mesures ne sont pas présentées comme nouvelles.

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

La bascule a terminé à 12 h 15 : Erigon et le cache d'index sont actifs sur les nouveaux chemins. La prélecture du volume lent est revenue à 128 Kio. Il reste environ 41 Gio sur le disque système et 153 Gio sur `/data`. Le redémarrage du client ne signifie pas que le rattrapage est terminé; le suivi attend les nouvelles têtes validées pour estimer la suite.

Les temps annoncés dans les docs Erigon ont été mesurés sur une machine plus puissante, avec NVMe et beaucoup plus de RAM. Ils ne garantissent pas la même durée sur ce VPS. Le mode minimal économise l’espace, mais garde moins d’historique qu’un nœud complet configuré avec le mode `full`. Je laisse donc le rapport s’appuyer sur l’état réellement retourné par les clients, pas sur une estimation.

Le compte rendu avec les captures est dans [`RAPPORT-ETHEREUM.pdf`](RAPPORT-ETHEREUM.pdf).

## Attente du calcul d'état vers 14 h 30

Le compteur est resté au bloc 26 304 908 pendant plusieurs minutes. Le journal détaillé explique cette attente : à 14:30:31, `[commitment] processed` indique 383 500 clés traitées en 12 min 08 s. L'exécution a ensuite repris, avant le réglage mémoire ci-dessous. Les lectures du processus et les attentes `filemap_fault` montrent une forte activité disque, pas la preuve d'un deadlock. Le suivi ne redémarre donc pas le client simplement parce que son numéro de bloc reste fixe.

À 14 h 31, j'ai arrêté puis désactivé le service optionnel `ethereum-index-cache`, sans arrêter Erigon. Les index sont maintenant sur le disque rapide : les garder verrouillés occupait environ 3 Gio qui ne pouvaient pas servir au cache des données du disque lent. La RAM disponible est passée d'environ 5 à 8 Go au moment du changement. Les index ne sont ni supprimés ni désactivés dans Erigon; seul leur verrouillage en RAM est retiré. Cela ne démontre pas encore une accélération de la synchronisation complète.

Le module `scripts/sync_activity.py`, appelé par le timer existant, enregistre aussi les lectures du processus, son activité CPU, la RAM disponible et le dernier calcul de commitment détaillé. Il distingue une tête RPC inchangée avec des lectures disque d'un échantillon sans activité. Les réserves disque inférieures à 15 Gio et la RAM disponible inférieure à 1 Gio sont signalées dans `warnings`. Ce sont des diagnostics, pas un régulateur qui garantit une vitesse maximale ou un redémarrage automatique. Les cinq nouveaux tests passent sur la VM. Le PC passe 15 tests et en ignore deux réservés à Linux.

## Manque de RAM pendant la nuit

Le 1er novembre vers midi, la vérification des journaux du noyau a révélé deux arrêts OOM : le 31 octobre à 22:32 et le 1er novembre à 07:17. Le noyau avait tué Erigon avec environ 21 Gio de mémoire anonyme. Le service avait redémarré automatiquement. L'absence d'erreurs dans un relevé récent ne permettait donc pas de conclure qu'il n'y avait eu aucun incident pendant la nuit.

J'ai installé `configs/memory-safety.conf` dans les drop-ins du service : `GOMEMLIMIT=14GiB`, au lieu de laisser la cible automatique. Cette limite Go est souple et ne couvre pas toute la mémoire du processus : ce n'est pas un plafond strict de RAM. Le [guide Go](https://go.dev/doc/gc-guide) et la [documentation Erigon](https://docs.erigon.tech/help-center/common-errors-and-solutions) expliquent ce réglage.

Le script `scripts/configure-memory-safety.py` crée aussi un fichier de swap de secours de 4 Gio sur le volume système rapide, avec une réserve disque vérifiée et des permissions 600. Il refuse d'écraser un fichier inconnu. L'unité `configs/var-lib-erigon_swap.swap` l'active au démarrage, sans modifier `/etc/fstab`. Ce swap sert à absorber des pointes, pas à accélérer les lectures; un usage prolongé pourrait ralentir le nœud. Quatre tests vérifient les refus et la réutilisation sans reformatage.

Une relance propre a été demandée vers 12 h 12 pour appliquer la cible Go. Le script `scripts/restart-memory-safety.py` retire temporairement la limite de temps d'arrêt, puis restaure la configuration après la relance; il n'envoie pas de SIGKILL. Le suivi relève désormais aussi les événements OOM du cgroup courant. Juste avant l'intervention, la tête RPC avait atteint 26 316 998, avec environ 8 h 27 de retard. Ce changement vise à réduire les incidents mémoire, sans garantie de délai de synchronisation.

L'arrêt a terminé normalement à 12:16:05, puis le journal confirme `GOMEMLIMIT already set` avec la nouvelle valeur. Le swap utilisé est redescendu à environ 10 Mio après la fermeture de l'ancien processus. Cela confirme l'application de la configuration, pas encore l'absence de futures pointes. Les événements du noyau et les contrôles restent dans `evidence/2026-11-01-memory-safety.log`.

## Protection de l'espace le 1er novembre

Après 13 h, une fusion de commitment avec environ 24 Gio d'entrées a créé un temporaire de plus de 13 Gio sur le volume système. J'ai ramené la réserve ext4 de 8 à 4 Gio, en conservant environ 4 Gio réservés aux services privilégiés. La preuve avant/après et le nombre original de blocs réservés sont dans `evidence/2026-11-01-root-reserve.log`. Ce n'est ni un formatage ni un redimensionnement.

Le cache de compilation `~/.cache/go-build`, environ 3 Gio, a été copié vers `/data/ethereum-build-cache/go-build`, vérifié par SHA-256 puis remplacé par un lien au chemin initial. La copie secondaire des modules Go a été interrompue quand elle n'était plus nécessaire; le cache des modules original reste intact. Sa copie partielle est conservée sur `/data` et n'est pas utilisée. Je ne compte donc pas ces 2,5 Gio comme libérés.

`scripts/route-domain-writes.py` a ensuite appliqué un placement distinct pour les nouvelles écritures : `/data/erigon/snapshots/domain` pointe maintenant vers `/data/erigon-domain-active`, répertoire sur le grand volume. Il contient des liens vers les fichiers existants, dont ceux restés sur le disque rapide. Les futurs snapshots et fichiers temporaires sont créés sur `/data`, pour ne plus faire grossir les gros temporaires de fusion sur le volume système. Les originaux restent présents. La bascule a terminé vers 13:20 après un arrêt propre, sans resynchronisation complète.

Le volume système est revenu à environ 29 Gio disponibles, en combinant la libération des temporaires par Erigon, le réglage de réserve et le déplacement vérifié du cache. Je n'attribue pas toute cette libération à un seul réglage, et ce placement ne prouve pas une accélération. Le but est d'éviter une saturation du disque système. Les 38 tests passent sur Linux; le module de placement est testé dans un répertoire temporaire, sans modifier la vraie base pendant les tests.
