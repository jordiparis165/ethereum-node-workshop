# Rapport de déploiement d’un nœud Ethereum

**Étudiant :** Jordi PARIS  
**VM :** TP-MESIFI590426-07  
**Date du rapport :** 29 octobre 2026  
**Date limite :** 31 octobre 2026

## Objectif

Pour ce travail, je devais déployer un nœud Ethereum sur le VPS de l’école.
Le sujet demandait un client d’exécution, un client de consensus, une
compilation depuis les sources, des RPC HTTP et WebSocket, puis un démarrage
automatique avec systemd.

J’ai choisi Geth pour l’exécution et Lighthouse pour le consensus. Geth est un
client connu qui prend en charge le mode snap. Lighthouse fournit le client de
consensus et le point de contrôle nécessaire pour rejoindre plus rapidement la
chaîne Beacon.

## Préparation de la VM

La VM utilise Debian 13, 8 vCPU et 22 Gio de mémoire vive. Le volume `/data`
fait environ 1 To, alors que le sujet demande 2 To. Cette différence est une
limite réelle de la VM et je l’indique dans le rendu.

J’ai installé les outils nécessaires à la compilation : Git, Go, Rust, un
compilateur C/C++, Clang, CMake, Protobuf et les bibliothèques de développement.
La version de Rust fournie par Debian était trop ancienne pour Lighthouse ;
j’ai donc installé le toolchain stable officiel avec rustup.

## Compilation des clients

J’ai récupéré les sources officielles et compilé les deux programmes sur le VPS,
sans Docker ni binaire client précompilé :

- Geth `v1.17.10`, construit avec `make geth`.
- Lighthouse `v8.3.2`, construit avec `make`.

La compilation de Lighthouse a d’abord échoué parce qu’il manquait CMake et que
Rust était trop ancien. Après installation de CMake et du toolchain stable, la
compilation s’est terminée correctement.

## Configuration

Geth est configuré sur le réseau principal avec le mode snap. Son RPC HTTP
écoute sur le port `8545` et son RPC WebSocket sur `8546`. Les espaces de noms
activés sont `eth`, `net` et `web3`. L’API Engine utilisée par Lighthouse est
limitée à `127.0.0.1:8551` et protégée par un secret JWT commun aux deux clients.

Lighthouse est configuré sur mainnet avec synchronisation par point de contrôle.
Son API Beacon écoute sur le port `5052` et les métriques Prometheus sur `5054`.
Les deux clients utilisent systemd et sont activés au démarrage.

Les fichiers d’unités sont fournis dans le dossier `configs/`. Le secret JWT
n’est pas inclus dans le dépôt.

## Vérifications effectuées le 29 octobre

Les services `geth.service` et `lighthouse.service` étaient actifs et activés
au démarrage. Les fichiers systemd ont passé `systemd-analyze verify`.

J’ai testé les points suivants :

- `eth_chainId` répond `0x1`, ce qui correspond à Ethereum mainnet.
- `web3_clientVersion` renvoie la version de Geth compilée.
- `net_peerCount` renvoie des pairs connectés.
- Le point HTTP Beacon de Lighthouse renvoie sa version.
- Les ports HTTP RPC `8545`, WebSocket `8546` et Beacon API `5052` sont
  accessibles depuis l’extérieur.

Le script `scripts/check-node.sh` regroupe les commandes de contrôle à relancer
avant la remise.

## Synchronisation et délai

Au dernier contrôle, le client Lighthouse recevait les nouveaux slots, mais
signalait encore la tête comme optimiste car Geth n’avait pas fini la
vérification d’exécution. Geth avait environ 43 pairs, mais `eth_blockNumber`
renvoyait encore `0x0` et ses journaux indiquaient le téléchargement des
headers. La synchronisation complète des deux couches n’est donc pas encore
validée.

Il reste deux jours avant la date limite. Les services, les RPC et le dépôt sont
prêts à rendre, mais je ne peux pas garantir que la synchronisation complète
sera finie avant le 31 : la vitesse dépend des pairs, du CPU et du stockage du
VPS. Il faudra refaire les vérifications juste avant la remise et ajouter des
captures réelles de l’état final.

La VM ne possède qu’un volume de 1 To au lieu des 2 To demandés. À la date du
contrôle, environ 965 Go étaient libres, mais cela ne prouve pas que la capacité
respecte la consigne ni que le volume suffira jusqu’à la fin. Ce point devra
être signalé au professeur si le stockage ne peut pas être augmenté.

## Conclusion

J’ai installé et compilé les deux clients depuis leurs sources, configuré les
services systemd et vérifié les RPC mainnet. Le nœud est fonctionnel, mais sa
synchronisation complète et le prérequis de 2 To restent à confirmer. Je ne
présente donc pas le nœud comme entièrement synchronisé tant que les contrôles
finaux ne le démontrent pas.
