# Vérifications et preuves

Les quatre images du dossier `screenshots/` sont des captures natives de l’écran Windows avec Windows Terminal au premier plan. Les commandes affichées ont interrogé le VPS de l’école par SSH à l’aide des identifiants locaux de `btc/.env` ; aucun secret n’est imprimé dans les captures.

Captures prises le 29 octobre 2026 vers 23 h 39–23 h 40 (heure locale) :

- `01-compilation.png` : versions des exécutables Geth et Lighthouse présents sur la VM.
- `02-services.png` : ressources, stockage et sockets en écoute.
- `03-rpc.png` : appels JSON-RPC et version de l’API Beacon.
- `04-synchronisation.png` : statuts retournés par Lighthouse et Geth et derniers journaux.

Constats visibles dans les preuves :

- `eth_chainId` renvoie `0x1` et Geth a des pairs.
- `eth_blockNumber` renvoie encore `0x0` et `eth_syncing` indique un bloc courant à zéro.
- Lighthouse indique `is_optimistic=true`.
- Le volume `/data` est d’environ 984 Go, inférieur aux 2 To demandés.

Le nœud n’était donc pas complètement synchronisé au moment de ces captures. Les ETA de journaux sont indicatives et ne prouvent pas la fin de la synchronisation.
