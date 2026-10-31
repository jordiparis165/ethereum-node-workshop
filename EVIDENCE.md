# Vérifications et preuves

Les images dans `screenshots/` sont des captures réelles de l’écran Windows avec les sorties de commandes SSH exécutées sur le VPS. Aucun mot de passe ni secret JWT n’apparaît.

Captures initiales prises le 30 octobre 2026 :

- `01-compilation.png` : versions d’Erigon v3.8.1, Geth et Lighthouse compilés depuis leurs sources.
- `02-services.png` : état des services, ressources, volume, réglages noyau et sockets.
- `03-rpc.png` : tests JSON-RPC sur Ethereum mainnet.

Captures actualisées le 31 octobre 2026 vers 10 h 04 et 10 h 05 (heure de Paris) :

- `04-synchronisation.png` : le service Erigon est actif, le RPC renvoie le bloc validé 26 301 999 et le calcul de commitment indique `183.52k/304.52k` clés. L'exécution a atteint 26 302 909, mais ce lot n'est pas encore validé. La tête exposée a plus de 32 heures de retard. Le nœud n'est pas encore synchronisé.
- `05-rpc-public.png` : tests effectués depuis le PC vers les endpoints HTTPS et WSS publics. Le certificat auto-signé est explicitement approuvé, son nom vérifié, et l'accès sans authentification est refusé. Les namespaces `eth` et `web3` répondent sur les deux transports.

Au relevé de la capture, `/data` faisait 984 Gio avec environ 154 Gio libres. Erigon reste lié à localhost; le proxy TLS authentifié sur le port 9443 fournit l'accès public. Les identifiants ne sont pas publiés.

Les extraits de journaux et un état JSON horodaté sont conservés dans `evidence/`. Ils montrent l'erreur de racine d'état de 02 h 25, la validation du même bloc à 07 h 09, puis la progression des clés. Sur le VPS, `ethereum-sync-monitor.timer` enregistre aussi les mesures toutes les deux minutes, même si le PC est éteint. Ces preuves attestent une reprise et des endpoints fonctionnels, pas une synchronisation complète ou un reboot testé.
