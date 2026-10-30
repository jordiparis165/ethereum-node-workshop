# Vérifications et preuves

Les images dans `screenshots/` sont des captures réelles de l’écran Windows avec les sorties de commandes SSH exécutées sur le VPS. Aucun mot de passe ni secret JWT n’apparaît.

Captures initiales prises le 30 octobre 2026 :

- `01-compilation.png` : versions d’Erigon v3.8.1, Geth et Lighthouse compilés depuis leurs sources.
- `02-services.png` : état des services, ressources, volume, réglages noyau et sockets.
- `03-rpc.png` : tests JSON-RPC sur Ethereum mainnet.

Capture actualisée le 31 octobre 2026 vers 00 h 26 :

- `04-synchronisation.png` : le service Erigon est actif. Le bloc cible des snapshots répond, mais `eth_blockNumber` renvoie encore `0x0`. Le journal indique que l’étape `4/6 Execution` applique les blocs autour de 26 301 656. Le nœud n’est pas encore synchronisé.

Au relevé de la capture, `/data` faisait 984 Gio avec environ 156 Gio libres. Le RPC HTTP/WS est temporairement limité à localhost pendant le traitement initial ; il faudra rétablir l’accès public et le tester après la synchronisation.
