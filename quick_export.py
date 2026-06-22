import os
import re
import sys
import hashlib
from io import BytesIO

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.database import Base
from backend.models import Activity, Registration, Student

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "sicday.db")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "quick_export")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    return name.strip()[:200] or "unnamed"


def register_font():
    fonts_dir = os.path.join(SCRIPT_DIR, "frontend", "static", "fonts")
    font_name = "ChakraPetch"
    try:
        for weight in ["Regular", "Medium", "SemiBold", "Bold"]:
            path = os.path.join(fonts_dir, f"ChakraPetch-{weight}.ttf")
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont("ChakraPetch", path))
                return font_name
        return "Helvetica"
    except Exception:
        return "Helvetica"


def build_pdf(activity, regs, font_name):
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    thai_style = ParagraphStyle("ThaiStyle", parent=styles["Normal"], fontName=font_name, fontSize=16, leading=20, alignment=1)
    cell_style = ParagraphStyle("CellStyle", parent=styles["Normal"], fontName=font_name, fontSize=11, leading=14, alignment=1)

    elements.append(Paragraph(f"รายชื่อผู้ลงทะเบียน: {activity.title}", thai_style))
    elements.append(Spacer(1, 20))

    is_team = activity.type == "team"
    if is_team:
        regs = sorted(regs, key=lambda x: (x.team_name or "", x.student.classroom or "", x.student.sequence or 0))
    else:
        regs = sorted(regs, key=lambda x: (x.student.classroom or "", x.student.sequence or 0))

    def get_team_color(seed, dark=False):
        h = int(hashlib.md5(str(seed).encode()).hexdigest(), 16)
        if dark:
            r_val = (h & 0xFF) % 150
            g_val = ((h >> 8) & 0xFF) % 150
            b_val = ((h >> 16) & 0xFF) % 150
        else:
            r_val = 180 + ((h & 0xFF) % 65)
            g_val = 180 + (((h >> 8) & 0xFF) % 65)
            b_val = 180 + (((h >> 16) & 0xFF) % 65)
        return colors.Color(r_val / 255.0, g_val / 255.0, b_val / 255.0)

    unnamed_team_color = colors.Color(1.0, 0.90, 0.35)

    def get_team_paragraph(name):
        if not name:
            style = ParagraphStyle("UnnamedTeam", parent=styles["Normal"], fontName=font_name, fontSize=11, alignment=1, textColor=colors.black)
            return Paragraph("-", style)
        h = int(hashlib.md5(name.encode()).hexdigest(), 16)
        bg = get_team_color(name, dark=True)
        style = ParagraphStyle(f"Team_{h}", parent=styles["Normal"], fontName=font_name, fontSize=11, alignment=1, textColor=colors.white, backColor=bg, borderPadding=4)
        return Paragraph(name, style)

    if is_team:
        data = [["ลำดับ", "กิจกรรม", "ชื่อทีม", "ชื่อ-สกุล", "ห้อง", "รหัส"]]
        for i, r in enumerate(regs, 1):
            data.append([str(i), Paragraph(r.activity.title or "-", cell_style), get_team_paragraph(r.team_name), Paragraph(r.student.name or "-", cell_style), r.student.classroom or "-", r.student.number])
        col_widths = [40, 100, 100, 140, 70, 60]
    else:
        data = [["ลำดับ", "กิจกรรม", "ชื่อ-สกุล", "ห้อง", "รหัสนักเรียน"]]
        for i, r in enumerate(regs, 1):
            data.append([str(i), Paragraph(r.activity.title or "-", cell_style), Paragraph(r.student.name or "-", cell_style), r.student.classroom or "-", r.student.number])
        col_widths = [40, 140, 160, 80, 90]

    table_style_commands = [
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, 0), 12),
        ("FONTSIZE", (0, 1), (-1, -1), 11),
        ("BACKGROUND", (0, 0), (-1, 0), colors.rose if hasattr(colors, "rose") else colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]
    if is_team:
        for row_index, reg in enumerate(regs, 1):
            if not reg.team_name:
                table_style_commands.append(("BACKGROUND", (2, row_index), (2, row_index), unnamed_team_color))

    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle(table_style_commands))
    elements.append(t)

    def add_footer(c, doc):
        c.saveState()
        try:
            c.setFont(font_name, 9)
        except Exception:
            c.setFont("Helvetica", 9)
        c.setFillColor(colors.grey)
        c.drawRightString(A4[0] - 30, 15, "Auto Generate Using DSNPRU_REG By ณัฐชนน รอดน้อย 04824")
        c.restoreState()

    doc.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)
    stream.seek(0)
    return stream


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    font_name = register_font()
    db = SessionLocal()

    try:
        activities = db.query(Activity).all()
        if not activities:
            print("No activities found.")
            return

        print(f"Found {len(activities)} activities. Exporting PDFs...\n")

        for act in activities:
            regs = db.query(Registration).options(
                joinedload(Registration.student),
                joinedload(Registration.activity),
            ).filter(Registration.activity_id == act.id).all()

            filename = sanitize_filename(act.title) + ".pdf"
            filepath = os.path.join(OUTPUT_DIR, filename)

            pdf_stream = build_pdf(act, regs, font_name)
            with open(filepath, "wb") as f:
                f.write(pdf_stream.read())

            print(f"  {filename}  ({len(regs)} registrations)")

        print(f"\nDone! PDFs saved to: {OUTPUT_DIR}")
    finally:
        db.close()


if __name__ == "__main__":
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
