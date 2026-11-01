# Vérifications et preuves

Les images dans `screenshots/` sont des captures réelles de l’écran Windows avec les sorties de commandes SSH exécutées sur le VPS. Aucun mot de passe ni secret JWT n’apparaît.

## Contrôles du 1er novembre

L'état courant est dans `evidence/submission-audit.json`, `current-status.json`, `current-monitor.json` et `current-public-rpc.log`. Ces fichiers sont horodatés : un ancien ratio de téléchargement ne remplace pas la vérification de synchronisation.

- `10-build-source.png` : commit source, fin du journal de build et version du binaire, avec Caplin intégré.
- `11-tests-publics.png` : tests HTTPS/WSS depuis le PC, authentification, TLS et API sensibles désactivées.
- `12-etat-actuel.png` : comparaison entre le RPC du VPS et une référence mainnet indépendante, à l'heure indiquée.
- `13-services-enabled.png` : services actifs et activés, sans prétendre qu'un reboot a déjà été testé.
- `09-securite-memoire.png` : cible mémoire et swap de secours après relance propre.
- `2026-11-01-linux-tests.log` : 38 tests passent sur Linux. Les tests des garde-fous de reboot ne sont pas une preuve de reboot réel.
- `spreadsheet-submission.json` : le lien du dépôt était déjà présent dans la cellule F22 du tableur, vérifiée sans modification.

Le mode reste `minimal`, pas le mode `full` demandé au sens strict d'Erigon. La synchronisation finale et le reboot réel ne doivent pas être considérés comme validés tant que leurs preuves spécifiques ne sont pas présentes.

## Historique

Captures initiales prises le 30 octobre 2026 :

- `01-compilation.png` : versions d’Erigon v3.8.1, Geth et Lighthouse compilés depuis leurs sources.
- `02-services.png` : état des services, ressources, volume, réglages noyau et sockets.
- `03-rpc.png` : tests JSON-RPC sur Ethereum mainnet.

Captures actualisées le 31 octobre 2026 vers 11 h (heure de Paris) :

- `04-synchronisation.png` : le service Erigon est actif et le RPC renvoie le bloc validé 26 302 999, soit 1 000 blocs de plus que lors de la capture précédente. Le journal a confirmé la fin de l'étape Execution à 10 h 46 puis la mise à jour de tête à 10 h 52. L'exécution continue sur le lot suivant. La tête exposée a encore environ 30 heures de retard. Le nœud n'est pas encore synchronisé.
- `05-rpc-public.png` : tests effectués depuis le PC vers les endpoints HTTPS et WSS publics. Le certificat auto-signé est explicitement approuvé, son nom vérifié, et l'accès sans authentification est refusé. Les namespaces `eth` et `web3` répondent sur les deux transports.

Au dernier relevé, `/data` faisait 984 Gio avec environ 151 Gio libres. Erigon reste lié à localhost; le proxy TLS authentifié sur le port 9443 fournit l'accès public. Les identifiants ne sont pas publiés.

Les extraits de journaux et un état JSON horodaté sont conservés dans `evidence/`. Ils montrent l'erreur de racine d'état de 02 h 25, la validation du même bloc à 07 h 09, puis la progression des clés. Sur le VPS, `ethereum-sync-monitor.timer` enregistre aussi les mesures toutes les deux minutes, même si le PC est éteint. Ces preuves attestent une reprise et des endpoints fonctionnels, pas une synchronisation complète ou un reboot testé.

À 11 h 29, `06-optimisation-stockage.png` montre une nouvelle étape : la copie vers le volume système à plus faible latence. Le client a été arrêté proprement vers 11 h 27 pour libérer le disque durant la copie. Les RPC sont temporairement indisponibles. Environ 6,4 Gio sur 136,2 Gio étaient copiés lors de la capture; ce compteur ne mesure pas la synchronisation Ethereum. Le script vérifie les fichiers par SHA-256, garde les originaux et prévoit le redémarrage après bascule. Les tests de copie et de retour arrière ont passé sur Linux. Cette capture ne prouve pas encore le gain de débit après migration.
