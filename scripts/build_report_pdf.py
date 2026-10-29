from datetime import datetime
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
    story += [Paragraph("Pour ce TD, j’ai installé un nœud Ethereum mainnet sur le VPS de l’école. J’ai choisi Geth pour l’exécution et Lighthouse pour le consensus. J’ai compilé les deux clients depuis leurs dépôts officiels, sans Docker ni binaires précompilés.", styles["FR"]), Paragraph("Préparation et compilation", styles["Section"]), Paragraph("La VM tourne sous Debian 13, avec 8 vCPU et 22 Gio de mémoire. J’ai installé Git, Go, Rust, les compilateurs C/C++, Clang, CMake, Protobuf et les bibliothèques nécessaires. La version de Rust fournie par Debian ne convenait pas à Lighthouse v8.3.2 ; j’ai donc installé le toolchain stable avec rustup. Geth v1.17.10 a été compilé avec make geth et Lighthouse v8.3.2 avec make.", styles["FR"])]
    add_screenshot(story, "01-compilation.png", "Versions des deux clients compilés, affichées dans le terminal après une connexion SSH au VPS.", styles)

    story += [Paragraph("Configuration et services", styles["Section"]), Paragraph("Geth est configuré sur mainnet en mode snap. Les API HTTP et WebSocket utilisent les ports 8545 et 8546, avec les espaces de noms eth, net et web3. L’Engine API écoute seulement en local sur 8551 et utilise un secret JWT partagé avec Lighthouse. L’API Beacon de Lighthouse écoute sur 5052. Les deux services systemd sont activés au démarrage.", styles["FR"])]
    add_screenshot(story, "02-services.png", "Ressources de la VM, espace disque et ports en écoute au moment du contrôle.", styles)

    story += [Paragraph("Tests", styles["Section"]), Paragraph("J’ai interrogé les RPC directement sur le VPS. eth_chainId répond 0x1, ce qui confirme le réseau mainnet. Geth répond aussi avec sa version et un nombre de pairs non nul. L’API Beacon renvoie la version de Lighthouse. Par contre, le numéro de bloc était encore à 0x0 au moment de la capture.", styles["FR"])]
    add_screenshot(story, "03-rpc.png", "Quelques appels RPC et la réponse de l’API Beacon.", styles)

    story += [Paragraph("Synchronisation", styles["Section"])]
    if SYNC_MARKER.exists():
        checked_at = SYNC_MARKER.read_text(encoding="utf-8").strip()
        story.append(Paragraph(f"Un contrôle ultérieur a confirmé que Geth ne synchronisait plus, que son numéro de bloc était non nul et que Lighthouse n’était plus en mode optimiste. Les deux clients étaient synchronisés lors de la capture du {checked_at}.", styles["FR"]))
    else:
        story.append(Paragraph("Au dernier relevé, la synchronisation n’était pas finie. Lighthouse indiquait encore une tête optimiste et Geth renvoyait un numéro de bloc à 0x0, tout en téléchargeant des headers. Le fait que Lighthouse ne soit plus en train de synchroniser ses slots ne suffit pas à dire que tout le nœud est prêt.", styles["FR"]))
    add_screenshot(story, "04-synchronisation.png", "État retourné par les clients au moment du relevé. La date et l’heure de la capture apparaissent dans la barre des tâches.", styles)

    story += [Paragraph("Stockage et bilan", styles["Section"]), Paragraph("Le sujet demande 2 To de stockage, mais le volume /data de cette VM fait environ 984 Go. Au dernier contrôle, il restait environ 961 Go libres. C’est une limite importante de la machine et je ne peux pas la corriger depuis la configuration du nœud. Les deux clients sont installés, compilés et lancés, et les endpoints ont répondu aux tests. Pour la synchronisation complète, je m’en tiens à ce que montrent les réponses réelles des clients.", styles["FR"])]
    story.append(Paragraph(f"Relevés et captures préparés le {datetime.now().strftime('%d/%m/%Y')}.", styles["Caption"]))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT)


if __name__ == "__main__":
    main()
