# Vérifications et preuves

Les images dans `screenshots/` sont des captures natives de l’écran Windows avec un terminal ouvert sur les sorties SSH du VPS. Aucun mot de passe ni secret JWT n’apparaît.

Captures prises le 30 octobre 2026 :

- `01-compilation.png` : versions d’Erigon v3.8.1, Geth et Lighthouse compilés depuis leurs sources.
- `02-services.png` : Erigon actif et activé avec systemd; Geth et Lighthouse arrêtés et désactivés; RAM, volume, réglages noyau et sockets.
- `03-rpc.png` : `eth_chainId=0x1`, version Erigon, pairs et réponse de `eth_syncing`.
- `04-synchronisation.png` : journaux réels d’Erigon et Caplin pendant le téléchargement des snapshots.

Au relevé visible dans la dernière capture, Erigon téléchargeait les snapshots (environ 7,63 %, soit 43,2 Go sur 566,1 Go). Caplin avait démarré et annoncé 127 pairs. `eth_blockNumber` était encore à `0x0` et `eth_syncing` continuait à renvoyer un objet de progression : le nœud n’était donc pas synchronisé.

Le volume `/data` fait 984 Go et il restait environ 679 Go libres à ce relevé. Les anciennes données Geth et Lighthouse sont gardées sur le disque. Le suivi local interroge Erigon chaque minute et ne marque la synchronisation comme terminée qu’après `eth_syncing=false`, un bloc non nul et un horodatage de tête récent.
