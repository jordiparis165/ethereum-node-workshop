import json
import re
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
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
OUT = ROOT / "RAPPORT-ETHEREUM.pdf"
SYNC_MARKER = ROOT / ".sync-complete"
STATUS_FILE = ROOT / "sync-status.json"


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d8dee8"))
    canvas.line(18 * mm, 15 * mm, 192 * mm, 15 * mm)
    canvas.setFont("ArialUnicode", 8)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(18 * mm, 10 * mm, "Jordi PARIS | Nœud Ethereum")
    canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def add_screenshot(story, filename, caption, styles):
    path = SHOTS / filename
    if not path.exists():
        return
    image = Image(str(path))
    scale = min((174 * mm) / image.imageWidth, (112 * mm) / image.imageHeight)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    story.extend([image, Spacer(1, 2 * mm), Paragraph(caption, styles["Caption"]), Spacer(1, 5 * mm)])


def sync_summary():
    if SYNC_MARKER.exists():
        checked_at = escape(SYNC_MARKER.read_text(encoding="utf-8").strip())
        return ("Le dernier contrôle a confirmé `eth_syncing=false`, un bloc courant non nul "
                "et une tête récente. Caplin est intégré à Erigon; son checkpoint de consensus "
                f"a été chargé avant le suivi de la tête. Vérification faite le {checked_at}.")

    if STATUS_FILE.exists():
        try:
            status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            syncing = status.get("eth_syncing")
            progress = status.get("progress", [])
            snapshot = next((line for line in reversed(progress) if "Syncing snapshots" in line), None)
            execution = next((line for line in reversed(progress) if "[4/6 Execution] parallel executed" in line), None)
            line = execution or snapshot or (progress[-1] if progress else "")
            line = re.sub(r"^.*?\[Downloader\] ", "", line)
            line = re.sub(r"^.*?\[4/6 Execution\] ", "Execution : ", line)
            if isinstance(syncing, dict):
                current = int(syncing.get("currentBlock", "0x0"), 16)
                highest = int(syncing.get("highestBlock", "0x0"), 16)
                rpc_progress = f"Le RPC indique le bloc {current:,} sur la cible {highest:,}."
            else:
                rpc_progress = "Le RPC indique que la synchronisation continue."
            detail = f" Dernier journal Erigon : {escape(line)}." if line else ""
            free = int(status.get("disk_free_bytes", 0))
            free_text = f" Il restait environ {free / (1024**3):.0f} Gio libres sur `/data`." if free else ""
            return ("Au dernier relevé, le nœud n’était pas encore synchronisé. " + rpc_progress +
                    detail + free_text + " Caplin est le client de consensus intégré à Erigon.")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return "La synchronisation est en cours. Je ne la considère terminée que lorsque les RPC et le bloc de tête la confirment."


def main():
    fonts = Path("C:/Windows/Fonts")
    pdfmetrics.registerFont(TTFont("ArialUnicode", str(fonts / "arial.ttf")))
    pdfmetrics.registerFont(TTFont("ArialUnicode-Bold", str(fonts / "arialbd.ttf")))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="ArialUnicode-Bold", fontSize=22, leading=27, textColor=colors.HexColor("#123047"), alignment=TA_LEFT, spaceAfter=7 * mm))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], fontName="ArialUnicode-Bold", fontSize=14, leading=18, textColor=colors.HexColor("#123047"), spaceBefore=4 * mm, spaceAfter=2 * mm))
    styles.add(ParagraphStyle(name="FR", parent=styles["BodyText"], fontName="ArialUnicode", fontSize=9.5, leading=14, spaceAfter=2.5 * mm))
    styles.add(ParagraphStyle(name="Caption", parent=styles["BodyText"], fontName="ArialUnicode", fontSize=8, leading=10, textColor=colors.HexColor("#475467")))

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=17*mm, bottomMargin=21*mm, title="Déploiement d’un nœud Ethereum", author="Jordi PARIS")
    story = [Paragraph("Déploiement d’un nœud Ethereum", styles["ReportTitle"])]
    story.append(Paragraph("J’ai d’abord lancé Geth avec Lighthouse, compilés depuis leurs sources. Comme l’estimation de synchronisation dépassait le temps restant, j’ai suivi le conseil du professeur et compilé Erigon v3.8.1. La configuration active utilise Erigon avec Caplin, son client de consensus intégré.", styles["FR"]))

    story += [Paragraph("Préparation et compilation", styles["Section"]), Paragraph("Le VPS a 8 vCPU, 22 Gio de mémoire et un volume `/data` de 984 Go. Geth et Lighthouse avaient été compilés et testés au début. Erigon v3.8.1 a ensuite été compilé depuis le tag officiel avec Go 1.26.10 et `make erigon`. Le Go système (1.24.4) était trop ancien; son mécanisme de sélection automatique a planté, donc j’ai appelé directement le toolchain téléchargé dans le cache Go. Aucun binaire Erigon précompilé n’a été utilisé.", styles["FR"])]
    add_screenshot(story, "01-compilation.png", "Versions des clients compilés affichées dans le terminal après connexion SSH au VPS.", styles)

    story += [Paragraph("Configuration et services", styles["Section"]), Paragraph("Erigon est sur mainnet, en mode de pruning minimal, avec Caplin intégré. Le service `erigon.service` est activé par systemd. Les API HTTP et WebSocket écoutent sur 8545 et 8546 et n’exposent que `eth`, `net` et `web3`. Les métriques restent locales sur 6061. L’API Engine n’est pas ouverte au réseau. Les services Geth et Lighthouse sont arrêtés mais leurs bases sont conservées pour pouvoir revenir en arrière.", styles["FR"])]
    add_screenshot(story, "02-services.png", "État des services, ressources de la VM, stockage et ports RPC en écoute.", styles)

    story += [Paragraph("Tests", styles["Section"]), Paragraph("Les appels RPC sont faits directement sur la VM. `eth_chainId` doit répondre `0x1` pour Ethereum mainnet; `web3_clientVersion` identifie le client, et `net_peerCount` permet de vérifier les connexions P2P. Une réponse RPC seule ne prouve pas que la synchronisation est terminée, donc j’ai aussi contrôlé `eth_syncing` et le bloc de tête.", styles["FR"])]
    add_screenshot(story, "03-rpc.png", "Résultats réels des requêtes JSON-RPC exécutées sur le VPS.", styles)

    story += [Paragraph("Synchronisation", styles["Section"]), Paragraph(sync_summary(), styles["FR"])]
    add_screenshot(story, "04-synchronisation.png", "État retourné par Erigon et journaux de téléchargement/consensus lors du contrôle.", styles)

    story += [Paragraph("Stockage et bilan", styles["Section"]), Paragraph("Le sujet mentionne 2 To, puis le professeur a indiqué le 30 octobre qu’un VPS de 1 To devait suffire. Le volume `/data` fait 984 Go. Le mode minimal d’Erigon est choisi pour respecter cette contrainte; les données Geth et Lighthouse déjà présentes sont conservées, ce qui réduit l’espace disponible pendant le téléchargement. La doc Erigon recommande un SSD/NVMe, alors que le disque de cette VM apparaît rotatif. Le temps de synchronisation mesuré sur une machine NVMe ne peut donc pas être promis ici. Je m’en tiens aux sorties réelles des RPC et des journaux pour dire si le nœud est prêt.", styles["FR"])]
    story.append(Paragraph(f"Rapport mis à jour le {datetime.now().strftime('%d/%m/%Y')} à partir des contrôles du VPS.", styles["Caption"]))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT)


if __name__ == "__main__":
    main()
