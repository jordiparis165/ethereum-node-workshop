# Rapport de déploiement d’un nœud Ethereum

**Étudiant :** Jordi PARIS  
**VM :** TP-MESIFI590426-07  
**Date :** 29 octobre 2026  
**Rendu prévu :** 31 octobre 2026

## Objectif et choix des clients

Pour ce travail, j’ai déployé un nœud Ethereum composé d’un client d’exécution et d’un client de consensus. J’ai choisi Geth pour l’exécution, car il prend en charge le mode snap, et Lighthouse pour le consensus, car il fournit le client Beacon et la synchronisation par point de contrôle. Les deux clients ont été compilés sur le VPS depuis leurs sources, sans Docker ni binaire client précompilé.

## Préparation et compilation

La VM utilise Debian 13, 8 vCPU et 22 Gio de mémoire. J’ai installé Git, Go, Rust, les compilateurs C/C++, Clang, CMake, Protobuf et les bibliothèques de développement nécessaires. La version de Rust fournie par Debian était trop ancienne pour Lighthouse ; le toolchain stable a été installé avec rustup.

- Geth `v1.17.10`, compilé avec `make geth`.
- Lighthouse `v8.3.2`, compilé avec `make`.

## Configuration

Geth est configuré sur Ethereum mainnet en mode snap. Les API HTTP et WebSocket utilisent respectivement les ports 8545 et 8546 et exposent les espaces de noms `eth`, `net` et `web3`. L’Engine API utilise le port 8551 sur localhost avec un secret JWT partagé avec Lighthouse. L’API Beacon de Lighthouse écoute sur le port 5052. Les deux clients sont gérés par systemd et configurés pour démarrer automatiquement.

## Vérifications et état observé

Les services `geth.service` et `lighthouse.service` étaient actifs. Les appels RPC ont renvoyé `eth_chainId = 0x1`, une version Geth et un nombre de pairs non nul ; l’API Beacon renvoyait la version Lighthouse. Les ports HTTP, WebSocket et Beacon étaient en écoute.

Au relevé illustré par les captures, Lighthouse indiquait `is_syncing=false`, mais `is_optimistic=true` et `sync_distance=1`. Geth renvoyait `eth_blockNumber = 0x0` et `eth_syncing` montrait encore un bloc courant à zéro. Ses journaux indiquaient le téléchargement des headers. La couche de consensus avançait, mais la couche d’exécution n’était pas synchronisée. Je ne présente donc pas le nœud comme entièrement synchronisé.

## Stockage et délai

Le sujet demande 2 To de stockage. La VM dispose d’un volume `/data` d’environ 984 Go, dont environ 961 Go étaient libres à l’heure de la capture. Cette capacité ne respecte pas le prérequis et constitue une limite du VPS. La synchronisation complète avant le 31 octobre n’est pas garantie : l’ETA des journaux varie selon les pairs et les ressources disponibles.

## Conclusion

J’ai compilé et lancé Geth et Lighthouse, configuré les services systemd et vérifié les endpoints mainnet. Les captures jointes proviennent de Windows Terminal et montrent les sorties de commandes exécutées par SSH sur la VM. Elles prouvent l’état relevé à leur horodatage ; elles ne prétendent pas prouver une synchronisation achevée.

Les fichiers de configuration et les commandes de contrôle sont dans le dépôt. Le secret JWT et les identifiants SSH ne sont pas inclus.
