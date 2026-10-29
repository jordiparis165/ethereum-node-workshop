from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
OUT = ROOT / "RAPPORT-ETHEREUM.pdf"


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d8dee8"))
    canvas.line(18 * mm, 15 * mm, 192 * mm, 15 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(18 * mm, 10 * mm, "Jordi PARIS | Atelier nœud Ethereum")
    canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def add_screenshot(story, filename, caption, styles):
    path = SHOTS / filename
    if path.exists():
        image = Image(str(path))
        scale = min((174 * mm) / image.imageWidth, (112 * mm) / image.imageHeight)
        image.drawWidth = image.imageWidth * scale
        image.drawHeight = image.imageHeight * scale
        story.extend([image, Spacer(1, 2 * mm), Paragraph(caption, styles["Caption"]), Spacer(1, 5 * mm)])


def main():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=23, leading=28, textColor=colors.HexColor("#123047"), alignment=TA_LEFT, spaceAfter=5 * mm))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], fontSize=15, leading=19, textColor=colors.HexColor("#123047"), spaceBefore=4 * mm, spaceAfter=3 * mm))
    styles.add(ParagraphStyle(name="Sub", parent=styles["Heading2"], fontSize=11, leading=14, textColor=colors.HexColor("#007c78"), spaceBefore=3 * mm, spaceAfter=2 * mm))
    styles.add(ParagraphStyle(name="FR", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13.5, spaceAfter=2.5 * mm))
    styles.add(ParagraphStyle(name="Caption", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#475467")))
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=17*mm, bottomMargin=21*mm, title="Déploiement d’un nœud Ethereum", author="Jordi PARIS")
    story = [Paragraph("Déploiement d’un nœud Ethereum", styles["ReportTitle"]),
             Paragraph("Rapport de l’atelier · rendu du 31 octobre 2026", styles["Sub"]), Spacer(1, 4*mm)]
    details = [["Étudiant", "Jordi PARIS"], ["VM", "TP-MESIFI590426-07"], ["Réseau", "Ethereum mainnet"], ["Clients", "Geth v1.17.10 et Lighthouse v8.3.2"], ["Captures prises", datetime.now().strftime("%d/%m/%Y %H:%M")]]
    table = Table(details, colWidths=[38*mm, 130*mm])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (0,-1), colors.HexColor("#eaf1f5")), ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#123047")), ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 9), ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#d8dee8")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 7), ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
    story += [table, Spacer(1, 6*mm), Paragraph("1. Objectif et choix des clients", styles["Section"]), Paragraph("Pour ce travail, j’ai déployé un nœud Ethereum composé d’un client d’exécution et d’un client de consensus. J’ai choisi Geth pour l’exécution, qui prend en charge le mode snap, et Lighthouse pour le consensus, qui fournit le client Beacon et la synchronisation par point de contrôle. Les deux logiciels ont été compilés sur le VPS depuis leurs sources, sans Docker ni binaire client précompilé.", styles["FR"]), Paragraph("2. Préparation et compilation", styles["Section"]), Paragraph("La VM utilise Debian 13, 8 vCPU et 22 Gio de mémoire. J’ai installé Git, Go, Rust, les compilateurs C/C++, Clang, CMake, Protobuf et les bibliothèques nécessaires. Rust fourni par Debian était trop ancien pour Lighthouse v8.3.2 ; le toolchain stable a donc été installé avec rustup. Geth v1.17.10 a été construit avec make geth et Lighthouse v8.3.2 avec make.", styles["FR"])]
    add_screenshot(story, "01-compilation.png", "Capture 1 — Versions des clients compilés, affichées dans Windows Terminal après interrogation SSH du VPS.", styles)
    story += [Paragraph("3. Configuration et services", styles["Section"]), Paragraph("Geth est configuré sur mainnet en mode snap. Les RPC HTTP et WebSocket écoutent sur 8545 et 8546 avec les espaces de noms eth, net et web3. L’Engine API est limitée à localhost sur 8551 et utilise un secret JWT partagé avec Lighthouse. L’API Beacon écoute sur 5052 et les deux services systemd sont activés au démarrage.", styles["FR"])]
    add_screenshot(story, "02-services.png", "Capture 2 — Ressources, stockage, services et ports constatés sur le VPS.", styles)
    story += [Paragraph("4. Vérification des endpoints", styles["Section"]), Paragraph("Les requêtes RPC exécutées sur le VPS confirment eth_chainId à 0x1 (mainnet), la version Geth, la présence de pairs et la version de l’API Beacon. Au moment de la capture, eth_blockNumber répond encore 0x0 : Geth n’a donc pas terminé la synchronisation d’exécution.", styles["FR"])]
    add_screenshot(story, "03-rpc.png", "Capture 3 — Requêtes JSON-RPC et réponse de l’API Beacon depuis les clients actifs.", styles)
    story += [Paragraph("5. État de synchronisation", styles["Section"]), Paragraph("Au moment du relevé, les deux services étaient actifs. Lighthouse indiquait is_syncing=false, mais aussi is_optimistic=true et sync_distance=1. Geth renvoyait encore un bloc courant à 0x0 et ses journaux montraient le téléchargement des headers avec un retard important. La chaîne de consensus avançait, mais l’exécution n’était pas synchronisée ; je ne peux donc pas présenter le nœud comme complètement synchronisé.", styles["FR"])]
    add_screenshot(story, "04-synchronisation.png", "Capture 4 — État réel retourné par Lighthouse et Geth ; synchronisation incomplète au relevé.", styles)
    story += [Paragraph("6. Limite de stockage et conclusion", styles["Section"]), Paragraph("Le sujet demande 2 To de stockage disponible. Le volume /data de cette VM fait environ 984 Go, avec environ 961 Go libres au relevé. La contrainte matérielle n’est donc pas satisfaite et peut empêcher de conserver les données nécessaires à long terme. Les clients sont compilés et démarrés, les services systemd sont actifs et les endpoints répondent, mais la synchronisation complète n’est pas démontrée. Une ETA de journal est une estimation variable et ne permet pas de promettre une fin avant la remise du 31 octobre.", styles["FR"]), Paragraph("Les images de ce rapport sont des captures natives de l’écran Windows montrant Windows Terminal et la sortie de commandes exécutées par SSH sur la VM. Elles documentent l’état observé à l’heure de la capture et ne simulent pas une synchronisation achevée.", styles["FR"]), PageBreak(), Paragraph("Annexe — Captures du terminal", styles["Section"])]
    for filename, caption in [("01-compilation.png", "Clients compilés"), ("02-services.png", "Services et ressources"), ("03-rpc.png", "RPC et API Beacon"), ("04-synchronisation.png", "Synchronisation au relevé")]:
        add_screenshot(story, filename, caption, styles)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT)


if __name__ == "__main__":
    main()
