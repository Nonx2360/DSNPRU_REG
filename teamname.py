import os
import re
import sys
import hashlib

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
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "team.pdf")
UNNAMED_TEAM_LABEL = "(ไม่มีชื่อทีม)"

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


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


def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def normalize_team_name(raw):
    if raw is None:
        return None
    name = re.sub(r"\s+", " ", str(raw)).strip()
    if not name or set(name) <= {"-", "."}:
        return None
    return name


def group_teams(regs):
    teams = {}
    for reg in regs:
        name = normalize_team_name(reg.team_name)
        key = name.casefold() if name else UNNAMED_TEAM_LABEL
        if key not in teams:
            teams[key] = {"display": name or UNNAMED_TEAM_LABEL, "unnamed": name is None, "members": []}
        teams[key]["members"].append(reg)
    return sorted(teams.values(), key=lambda t: (1 if t["unnamed"] else 0, t["display"].lower()))


def member_sort_key(reg):
    s = reg.student
    return (s.classroom or "", s.sequence or 0, s.name or "")


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


def build_team_paragraph(team, styles, font_name):
    if team["unnamed"]:
        style = ParagraphStyle("UnnamedTeam", parent=styles["Normal"], fontName=font_name, fontSize=11, alignment=1, textColor=colors.black, backColor=colors.Color(1.0, 0.90, 0.35), borderPadding=4)
    else:
        style = ParagraphStyle(f"Team_{hashlib.md5(team['display'].encode()).hexdigest()}", parent=styles["Normal"], fontName=font_name, fontSize=11, alignment=1, textColor=colors.white, backColor=get_team_color(team["display"], dark=True), borderPadding=4)
    count_line = f'<br/><font size="8">{len(team["members"])} คน</font>'
    return Paragraph(esc(team["display"]) + count_line, style)


def build_members_paragraph(team, styles, font_name):
    style = ParagraphStyle("MemberCell", parent=styles["Normal"], fontName=font_name, fontSize=10, leading=14, alignment=0)
    lines = []
    members = sorted(team["members"], key=member_sort_key)
    for i, reg in enumerate(members, 1):
        s = reg.student
        wait = " (สำรอง)" if reg.status == "waitlisted" else ""
        room = esc(s.classroom) if s.classroom else "-"
        number = esc(s.number) if s.number else "-"
        lines.append(f"{i}. {esc(s.name) or '-'} ({room}, {number}){wait}")
    return Paragraph("<br/>".join(lines), style)


def build_pdf(sections, font_name):
    doc = SimpleDocTemplate(OUTPUT_PATH, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("TitleThai", parent=styles["Normal"], fontName=font_name, fontSize=18, leading=24, alignment=1)
    heading_style = ParagraphStyle("HeadingThai", parent=styles["Normal"], fontName=font_name, fontSize=13, leading=17, spaceBefore=6, textColor=colors.HexColor("#1e1b4b"))
    cell_style = ParagraphStyle("CellCenter", parent=styles["Normal"], fontName=font_name, fontSize=11, leading=14, alignment=1)

    elements.append(Paragraph("รายชื่อทีมทั้งหมด (All Team Names)", title_style))
    elements.append(Spacer(1, 16))

    for act, teams in sections:
        total_members = sum(len(t["members"]) for t in teams)
        elements.append(Paragraph(f"{esc(act.title)}  ({len(teams)} ทีม / {total_members} คน)", heading_style))
        elements.append(Spacer(1, 6))

        data = [["ลำดับ", "ชื่อทีม", "สมาชิก (ชื่อ-สกุล, ห้อง, รหัส)"]]
        for i, team in enumerate(teams, 1):
            data.append([
                str(i),
                build_team_paragraph(team, styles, font_name),
                build_members_paragraph(team, styles, font_name),
            ])

        col_widths = [35, 130, 370]
        table_style_commands = [
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e11d48")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (1, -1), [colors.whitesmoke, colors.white]),
            ("ROWBACKGROUNDS", (2, 1), (2, -1), [colors.whitesmoke, colors.white]),
            ("LEFTPADDING", (2, 1), (2, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]
        for row_index in range(1, len(data)):
            if teams[row_index - 1]["unnamed"]:
                table_style_commands.append(("BACKGROUND", (1, row_index), (1, row_index), colors.Color(1.0, 0.90, 0.35)))

        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle(table_style_commands))
        elements.append(t)
        elements.append(Spacer(1, 18))

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


def main():
    font_name = register_font()
    db = SessionLocal()

    try:
        activities = db.query(Activity).filter(Activity.type == "team").order_by(Activity.id).all()
        if not activities:
            print("No team activities found.")
            return

        print(f"Found {len(activities)} team activities. Building team.pdf...\n")

        sections = []
        for act in activities:
            regs = db.query(Registration).options(
                joinedload(Registration.student),
                joinedload(Registration.activity),
            ).filter(Registration.activity_id == act.id).all()

            teams = group_teams(regs)
            if teams:
                sections.append((act, teams))
                total_members = sum(len(t["members"]) for t in teams)
                print(f"  - {act.title}: {len(teams)} teams, {total_members} members")
            else:
                print(f"  - {act.title}: no registrations, skipped")

        if not sections:
            print("No teams found at all.")
            return

        build_pdf(sections, font_name)
        print(f"\nDone! PDF saved to: {OUTPUT_PATH}")
    finally:
        db.close()


if __name__ == "__main__":
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
