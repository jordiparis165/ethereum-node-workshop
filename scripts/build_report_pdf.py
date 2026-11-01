"""Build the French report from saved measurements and genuine terminal captures."""
import json
from datetime import datetime
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'RAPPORT-ETHEREUM.pdf'


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('ArialUnicode', 8)
    canvas.setFillColor(colors.HexColor('#667085'))
    canvas.drawString(18 * mm, 10 * mm, 'Jordi PARIS | Nœud Ethereum')
    canvas.drawRightString(192 * mm, 10 * mm, f'Page {doc.page}')
    canvas.restoreState()


def add_screenshot(story, filename, caption, styles):
    path = ROOT / 'screenshots' / filename
    if not path.exists():
        return
    shot = Image(str(path))
    scale = min(174 * mm / shot.imageWidth, 105 * mm / shot.imageHeight)
    shot.drawWidth, shot.drawHeight = shot.imageWidth * scale, shot.imageHeight * scale
    story.append(KeepTogether([shot, Spacer(1, 2 * mm), Paragraph(caption, styles['Caption']), Spacer(1, 4 * mm)]))


def main():
    fonts = Path('C:/Windows/Fonts')
    pdfmetrics.registerFont(TTFont('ArialUnicode', str(fonts / 'arial.ttf')))
    pdfmetrics.registerFont(TTFont('ArialUnicode-Bold', str(fonts / 'arialbd.ttf')))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportTitle', fontName='ArialUnicode-Bold', fontSize=22,
                             leading=27, alignment=TA_LEFT, spaceAfter=6 * mm))
    styles.add(ParagraphStyle(name='Section', fontName='ArialUnicode-Bold', fontSize=13,
                             leading=17, spaceBefore=4 * mm, spaceAfter=2 * mm, keepWithNext=True))
    styles.add(ParagraphStyle(name='FR', fontName='ArialUnicode', fontSize=9.5, leading=14, spaceAfter=3 * mm))
    styles.add(ParagraphStyle(name='Caption', fontName='ArialUnicode', fontSize=8,
                             leading=10, textColor=colors.HexColor('#475467')))
    status = read_json(ROOT / 'sync-status.json')
    audit = read_json(ROOT / 'evidence/submission-audit.json')
    monitor = read_json(ROOT / 'evidence/current-monitor.json')
    reboot = read_json(ROOT / 'evidence/reboot-verification.json')
    proof = read_json(ROOT / 'evidence/first-verified-sync.json')
    story = [Paragraph('Déploiement d’un nœud Ethereum', styles['ReportTitle'])]

    def paragraph(text):
        story.append(Paragraph(text, styles['FR']))

    def section(title):
        story.append(Paragraph(title, styles['Section']))

    paragraph('J’ai déployé Erigon v3.8.1 sur le VPS de l’école, avec Caplin pour le consensus. '
              'J’avais commencé avec Geth et Lighthouse, puis changé de client après le conseil du professeur. '
              'Les tests et les captures présentés ici viennent du VPS ou de requêtes envoyées depuis mon PC.')
    section('État vérifié et limites du rendu')
    observed = status.get('observed_at', audit.get('observed_at', 'non disponible'))
    paragraph(f'Dernier relevé UTC : {escape(observed)}. Objectif de rendu : le 1er novembre 2026 à 23 h 59, heure de Paris.')
    if status.get('block') and not status.get('rpc_error'):
        height = int(status['block'], 16)
        age = status.get('head_age_seconds')
        paragraph(f'Le RPC local expose le bloc <b>{height:,}</b>. '
                  + (f'Son horodatage a environ <b>{age / 3600:.2f} heures de retard</b>. ' if age is not None else '')
                  + 'Ce retard n’est pas une durée de synchronisation restante.')
    elif status.get('rpc_error'):
        paragraph('Le RPC ne répond pas lors de ce relevé. Un champ de secours à zéro ne signifie pas une réinitialisation de la chaîne.')
    reference = status.get('reference') or {}
    if reference:
        paragraph(f'La référence indépendante {escape(reference["provider"])} expose le bloc '
                  f'{reference["latest_block"]:,}, soit {reference["remaining_blocks"]:,} blocs d’écart à ce relevé. '
                  f'Comparaison du hash à notre hauteur : {"identique" if reference.get("local_block_hash_matches") else "non confirmée"}. '
                  'La référence ne remplace pas notre nœud : elle sert seulement à contrôler son rattrapage.')
    budget = audit.get('deadline_budget') or {}
    if budget.get('maximum_seconds_per_1000_validated_blocks'):
        paragraph(f'Pour tenir l’échéance, le budget calculé demande en moyenne 1 000 blocs validés en au plus '
                  f'{budget["maximum_seconds_per_1000_validated_blocks"] / 60:.0f} minutes, nouveaux blocs du réseau compris. '
                  'C’est un seuil à atteindre, pas une prévision de fin ni un débit déjà obtenu.')
    criteria = audit.get('criteria', {})
    synchronized = criteria.get('synchronization') == 'verified_in_saved_repeated_observations'
    paragraph('<b>Synchronisation : ' + ('constatée dans les observations répétées sauvegardées.' if synchronized else
              'pas encore confirmée.</b> Un téléchargement terminé ou eth_syncing=false avec une tête ancienne ne suffit pas.')
              + ('</b>' if synchronized else ''))
    if synchronized and 'screenshots/12-etat-actuel.png' not in proof.get('screenshots_refreshed', []):
        paragraph('La confirmation est dans les relevés JSON. La capture de synchronisation reste historique si la session Windows '
                  'ne permettait pas de refaire une vraie capture; aucune image de remplacement n’a été générée.')
    paragraph('<b>Écart au sujet :</b> la base a été créée en mode <b>minimal</b>, pas avec le mode full d’Erigon. '
              'Je ne présente pas ces modes comme équivalents. Changer de mode demande une resynchronisation selon Erigon; '
              'je conserve les données existantes au lieu de supprimer la base à l’approche du rendu.')
    paragraph('Le démarrage automatique est configuré. '
              + ('Le changement de boot ID et le retour automatique des services ont été vérifiés après reboot.'
                 if reboot.get('passed') else 'Le test réel de reboot et de récupération reste à valider.')
              + (' Le lien GitHub était déjà présent dans la cellule F22 du tableur de rendu, vérifiée le 1er novembre sans modification.'
                 if criteria.get('spreadsheet') == 'verified_already_present_in_F22' else ' L’inscription du lien dans le tableur reste à vérifier.'))

    section('Machine et compilation depuis les sources')
    paragraph('La VM utilise Debian 13, 8 vCPU et environ 22 Gio de RAM. Le volume système fait 197 Gio et /data 984 Gio. '
              'Le sujet mentionne 2 To; le professeur a indiqué qu’un VPS de 1 To devait suffire. '
              'Le volume /data présente une latence mesurée élevée; le drapeau virtuel ROTA ne permet pas de conclure au type du disque physique.')
    paragraph('J’ai compilé le tag officiel v3.8.1, commit cf6f14132ff042df33b8ce64b0114daeb0d15145, avec Go 1.26.10 '
              'et make erigon. Le Go système 1.24.4 était trop ancien, donc j’ai utilisé directement le toolchain du cache Go. '
              'Caplin est intégré : le même build compile le client d’exécution et les sources du consensus. '
              'Les avertissements C/MDBX du build n’ont pas empêché la production du binaire. Les commandes de reprise sont dans le README.')
    add_screenshot(story, '10-build-source.png', 'Commit source, fin du journal de compilation et version du binaire réellement installé.', styles)

    section('Configuration et services')
    paragraph('Le service tourne avec le compte non-root adm-mesifi. Les lots sont réglés à 2 Go, la limite de boucle à 10 000 blocs '
              'et le calcul parallèle de commitment reste validé. Erigon et Caplin partagent le processus et le datadir. '
              'Les unités Erigon, Nginx, le timer de suivi et le swap de secours sont activés au démarrage. '
              'Restart=on-failure relance Erigon en cas d’arrêt anormal; cela ne remplace pas un test de reboot.')
    paragraph('Les API HTTP 8545, WebSocket 8546, Engine 8551 et les métriques 6061 restent sur localhost. '
              'Les namespaces activés sont eth, net et web3. L’API Beacon reste désactivée pour éviter sa consommation mémoire supplémentaire; '
              'les logs et métriques Caplin donnent le suivi du consensus sans l’exposer sur Internet.')
    add_screenshot(story, '13-services-enabled.png', 'Services actifs et activés au démarrage, ressources et sockets du VPS. Pas une preuve de reboot.', styles)

    section('RPC publics et sécurité')
    paragraph('Nginx expose HTTPS sur https://vps-ae86b6b8.vps.ovh.net:9443/rpc et WSS sur le même hôte, chemin /ws. '
              'L’accès demande une authentification HTTP Basic sur TLS. Le certificat est auto-signé : le script de test lui fait explicitement confiance '
              'et vérifie le nom du serveur. La clé privée et les mots de passe ne sont pas dans Git. '
              'Les limites du proxy sont 5 requêtes par seconde, 5 connexions par IP et 64 Ko par requête.')
    paragraph('Depuis le PC, j’ai vérifié le refus sans identifiants (401), eth_chainId=0x1 et web3_clientVersion sur les deux transports. '
              'Les méthodes admin_nodeInfo, debug_metrics et personal_listAccounts sont refusées. '
              'L’abonnement et le désabonnement newHeads passent en WebSocket; ce test ne prouve pas la réception d’une notification. '
              'Les réponses brutes sont conservées dans evidence/current-public-rpc.log.')
    add_screenshot(story, '11-tests-publics.png', 'Tests réels depuis le PC vers les endpoints publics, sans afficher les identifiants.', styles)

    section('Synchronisation et mesure du rattrapage')
    paragraph('Le timer enregistre les mesures toutes les deux minutes sur le VPS. Il relève la tête RPC, les logs d’exécution et de commitment, '
              'les événements OOM, la RAM, le swap, les débits et latences disque. Ce suivi fonctionne même quand le PC est éteint. '
              'Le PC ajoute la comparaison avec un endpoint mainnet indépendant, accessible depuis le PC mais refusé depuis ce VPS.')
    paragraph('La confirmation finale demande trois observations sur au moins deux minutes : service actif, eth_syncing=false, tête de moins '
              'de deux minutes, hash identique à la référence et écart de quatre blocs maximum. '
              'Le suivi du VPS seul ne constitue pas cette confirmation indépendante.')
    section('Limites de stockage et débit réel')
    paragraph('Le VPS a un volume /data de 984 Gio, et non les 2 To indiqués dans le sujet. '
              'Le disque système de 197 Gio est plus rapide mais trop petit pour recevoir toutes les données. '
              'Le 1er novembre vers 20 h 30, /data était occupé environ 92 % du temps avec 228 IOPS '
              'et 35 ms par requête, alors que le disque système était occupé moins de 5 %. '
              'La pression I/O observée était proche de 52 %; les lectures du processus Erigon dominaient. '
              'Ces chiffres décrivent une mesure, pas une caractéristique garantie du stockage physique.')
    paragraph('La validation avance par lots. Entre 18 h 24 et 20 h 30, le dernier bloc exposé par notre RPC '
              'est resté à 26 318 998 tandis que la référence mainnet est passée de 26 321 391 à 26 322 024. '
              'Le retard est donc passé de 2 393 à 3 026 blocs pendant ce créneau : le traitement et la '
              'validation ont alors été plus lents que la production de nouveaux blocs. Des index étaient '
              'toujours construits en arrière-plan. Les pourcentages de ces fichiers ne sont pas un '
              'pourcentage de synchronisation globale.')
    paragraph('Vers 20 h 30, il restait environ 1,1 Gio de RAM disponible et le premier swap de 4 Gio '
              'était rempli. Un second swap de secours de 4 Gio a été activé sur le volume système '
              'sans redémarrer Erigon; le même PID est resté actif. Ce secours réduit le risque '
              'd’un nouvel arrêt OOM mais ne rend pas /data plus rapide. La synchronisation reste '
              'non confirmée tant que les contrôles répétés de tête récente et de référence ne passent pas. '
              'La limite du mode minimal reste également présente.')
    paragraph('La date limite concerne le dépôt du rapport, pas l’arrêt du service. Erigon et le timer '
              'continuent après 23 h 59 tant que la VM est disponible. Le PC ne peut publier les '
              'nouvelles preuves sur GitHub que s’il reste allumé et connecté; la VM pourrait être '
              'désactivée par l’école sans préavis.')
    paragraph('Diagnostic du 1er novembre vers 22 h 37 : après plusieurs timeouts du RPC, le processus Erigon '
              'est resté actif et a encore lu environ 80 Mo en quatre secondes. Le journal est passé au bloc '
              '26 319 510 en exécution, mais le bloc validé exposé par RPC restait 26 318 998. '
              'La référence mainnet à 22 h 39 était 26 322 663, soit 3 665 blocs de retard. '
              'Le RPC a fini par répondre de nouveau, sans nouveau bloc validé. Caplin avait encore des pairs. '
              'Cela montre une activité réelle, pas une synchronisation terminée.')
    paragraph('La RAM disponible oscillait autour de 500 à 700 Mio; les deux swaps, 8 Gio au total, '
              'étaient presque pleins. La pression I/O full moyenne sur 60 secondes était proche de 63 %. '
              'Erigon occupait environ 21 Gio de RAM résidente, les autres processus seulement quelques Mio. '
              'Aucun nouvel OOM n\'est apparu dans les journaux accessibles pendant ce contrôle. '
              'Je n\'ai pas vidé le swap ni redémarré le client, car les compteurs avançaient encore et une '
              'interruption risquerait de retarder davantage la synchronisation. Le mode minimal et le reboot '
              'réel non testé restent des limites du rendu.')
    add_screenshot(story, '17-memoire-22h.png', 'Capture reelle du terminal a 22 h 41 : RAM, deux swaps, service actif et compteurs OOM.', styles)
    add_screenshot(story, '16-swap-urgence.png', 'Swap supplémentaire et services vérifiés sur le VPS après activation, sans redémarrer Erigon.', styles)
    forecast = monitor.get('forecast') or {}
    if forecast.get('scenarios'):
        for name, label in [('optimistic', 'optimiste'), ('central', 'centrale'), ('pessimistic', 'pessimiste')]:
            scenario = forecast['scenarios'][name]
            paragraph(f'Estimation {label} UTC : {escape(str(scenario.get("finish_utc")))}. '
                      'Conditionnelle au maintien du rythme; le travail non publié n’est pas crédité.')
    else:
        paragraph('Pas encore d’ETA robuste après la relance mémoire : le calcul attend au moins deux cycles complets de publication '
                  'du même processus. Une fenêtre courte autour d’un saut de 1 000 blocs peut donner une fausse impression de vitesse. '
                  'Je ne donne pas de probabilité chiffrée de finir avant l’échéance avec ces seules mesures.')
    add_screenshot(story, '12-etat-actuel.png', 'État réel de synchronisation à l’heure affichée dans le terminal. Les captures ne sont pas des estimations.', styles)

    section('Incidents et améliorations réalisées')
    paragraph('Les lectures aléatoires de contrôle du 31 octobre donnaient environ 0,22 ms sur le volume système contre 31,82 ms sur /data. '
              'J’ai donc déplacé chaindata, les fichiers d’état qui tenaient sur le volume rapide et les bases récentes de Caplin. '
              'Les copies ont été vérifiées par SHA-256 et les originaux gardés. Les gros fichiers de commitment restent en partie sur /data. '
              'Une fusion de snapshots en arrière-plan partage encore ses accès disque avec l’exécution; je n’interromps pas ce travail sans gain démontré.')
    add_screenshot(story, '07-stockage-active.png', 'Preuve historique de la bascule du 31 octobre. L’espace libre affiché est celui de cette capture.', styles)
    paragraph('Un compteur de blocs est resté fixe pendant un calcul de 383 500 clés qui a duré environ 12 minutes. '
              'Le journal détaillé a ensuite montré la reprise : ce compteur fixe n’était pas la preuve d’un deadlock. '
              'L’erreur de racine du 31 octobre à 02:25 est apparue après une demande d’arrêt; je ne peux pas l’attribuer avec certitude au mode parallèle.')
    paragraph('Le noyau a tué Erigon par manque de RAM le 31 octobre à 22:32 puis le 1er novembre à 07:17. '
              'Le service avait redémarré automatiquement. J’ai installé GOMEMLIMIT=14GiB et un swap de secours de 4 Gio sur le volume rapide. '
              'Cette cible Go est souple et ne couvre pas toute la mémoire du processus. Le swap n’est pas une accélération et peut ralentir s’il est très utilisé. '
              'Une relance propre a appliqué la cible à 12:16. Le verrouillage de 3 Gio d’index en RAM a aussi été retiré après leur déplacement sur le disque rapide.')
    add_screenshot(story, '09-securite-memoire.png', 'Configuration mémoire réellement appliquée et compteurs OOM du nouveau processus.', styles)
    paragraph('Les 38 tests exécutés sur Linux le 1er novembre passent : copie vérifiée et retour arrière, restauration des réglages, '
              'sécurité du swap, diagnostic d’activité, prévisions, qualification de synchronisation et garde-fous des opérations préparées. '
              'Le contrôle ciblé de Git n’a trouvé ni les mots de passe SSH/RPC connus ni de clé privée PEM; ce n’est pas un audit exhaustif de tous les secrets possibles.')
    paragraph('Le 1er novembre après 13 h, la fusion des fichiers de commitment a fait baisser la réserve du disque système. '
              'J’ai réduit sa réserve ext4 de 8 à 4 Gio, conservant environ 4 Gio pour les services privilégiés, et déplacé '
              'les caches de compilation vers /data avec vérification des copies. Les fichiers existants de domain restent '
              'accessibles par liens; les nouveaux snapshots et temporaires sont désormais créés dans /data/erigon-domain-active. '
              'Un arrêt propre puis une relance ont appliqué ce placement vers 13:20. Ce placement réduit le risque de saturation '
              'du volume système, sans prouver un gain immédiat de vitesse. Les fichiers d’état utiles n’ont pas été supprimés.')
    paragraph('Seul le déplacement du cache go-build, environ 3 Gio, a été terminé et vérifié. '
              'La copie secondaire des modules a été interrompue quand la marge est redevenue suffisante : '
              'le cache des modules original est intact et sa copie partielle sur /data n’est pas utilisée.')

    section('Rendu et références')
    paragraph('Dépôt : <link href="https://github.com/jordiparis165/ethereum-node-workshop">github.com/jordiparis165/ethereum-node-workshop</link>. '
              'Le README décrit les dépendances, la compilation, les unités et les commandes de contrôle. '
              'evidence/submission-audit.json distingue les points vérifiés et les manques. '
              'Les identifiants RPC doivent être transmis séparément au correcteur. Aucune note sur 20 n’est déduite automatiquement de ces tests.')
    paragraph('Documentation utilisée : '
              '<link href="https://docs.erigon.tech/fundamentals/caplin">Caplin intégré</link>, '
              '<link href="https://docs.erigon.tech/fundamentals/pruning-modes">modes de pruning</link>, '
              '<link href="https://docs.erigon.tech/fundamentals/performance-tricks">performance</link>, '
              '<link href="https://docs.erigon.tech/fundamentals/optimizing-storage">stockage</link> et '
              '<link href="https://go.dev/doc/gc-guide">limite mémoire Go</link>.')
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                            topMargin=17*mm, bottomMargin=21*mm,
                            title='Déploiement d’un nœud Ethereum', author='Jordi PARIS')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT)


if __name__ == '__main__':
    main()
