import os
from io import BytesIO
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .. import models
from ..auth import get_current_admin
from ..database import get_db

router = APIRouter()


def _get_registrations(db: Session, activity_id: Optional[int] = None):
    query = db.query(models.Registration).join(models.Student).join(models.Activity)
    if activity_id:
        query = query.filter(models.Registration.activity_id == activity_id)
    return query.all()


@router.get("/excel")
def export_excel(
    activity_id: Optional[int] = None,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    regs = _get_registrations(db, activity_id)
    is_team = False
    if regs and hasattr(regs[0].activity, 'type') and regs[0].activity.type == "team":
        is_team = True
        regs = sorted(regs, key=lambda x: (x.team_name or "", x.student.classroom or "", x.student.sequence or 0))
    else:
        regs = sorted(regs, key=lambda x: (x.student.classroom or "", x.student.sequence or 0))

    wb = Workbook()
    ws = wb.active
    ws.title = "Registrations"
    
    if is_team:
        ws.append(["กิจกรรม", "ทีม", "ชื่อ-สกุล", "ห้อง", "รหัสนักเรียน"])
        for r in regs:
            ws.append([
                r.activity.title,
                r.team_name or "-",
                r.student.name,
                r.student.classroom,
                r.student.number,
            ])
    else:
        ws.append(["กิจกรรม", "ชื่อ-สกุล", "ห้อง", "รหัสนักเรียน"])
        for r in regs:
            ws.append([
                r.activity.title,
                r.student.name,
                r.student.classroom,
                r.student.number,
            ])

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    filename = "registrations.xlsx"
    return Response(
        content=stream.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pdf")
def export_pdf(
    activity_id: Optional[int] = None,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    regs = _get_registrations(db, activity_id)
    stream = BytesIO()

    # Register SukhumvitSet font for Thai text support
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    fonts_dir = os.path.join(base_dir, "frontend", "static", "fonts")
    font_name = "ChakraPetch"
    
    try:
        font_weights = ["Regular", "Medium", "SemiBold", "Bold"]
        font_path = None
        for weight in font_weights:
            test_path = os.path.join(fonts_dir, f"ChakraPetch-{weight}.ttf")
            if os.path.exists(test_path):
                font_path = test_path
                break
        
        if font_path:
            pdfmetrics.registerFont(TTFont("ChakraPetch", font_path))
        else:
            font_name = "Helvetica"
    except Exception:
        font_name = "Helvetica"

    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    thai_style = ParagraphStyle(
        'ThaiStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=16,
        leading=20,
        alignment=1, # Center
    )
    
    title_text = "รายชื่อผู้ลงทะเบียนกิจกรรม DSNPRU_REG"
    if activity_id and regs:
        title_text = f"รายชื่อผู้ลงทะเบียน: {regs[0].activity.title}"
    
    elements.append(Paragraph(title_text, thai_style))
    elements.append(Spacer(1, 20))

    is_team = False
    if regs and hasattr(regs[0].activity, 'type') and regs[0].activity.type == "team":
        is_team = True
        regs = sorted(regs, key=lambda x: (x.team_name or "", x.student.classroom or "", x.student.sequence or 0))
    else:
        regs = sorted(regs, key=lambda x: (x.student.classroom or "", x.student.sequence or 0))

    def get_team_paragraph(name):
        if not name: return "-"
        import hashlib
        h = int(hashlib.md5(name.encode()).hexdigest(), 16)
        r = (h & 0xFF) % 150 # darker colors for white text
        g = ((h >> 8) & 0xFF) % 150
        b = ((h >> 16) & 0xFF) % 150
        bg_color = colors.Color(r/255.0, g/255.0, b/255.0)
        
        style = ParagraphStyle(
            f'Team_{h}',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=11,
            alignment=1,
            textColor=colors.white,
            backColor=bg_color,
            borderPadding=4
        )
        return Paragraph(f"{name}", style)

    if is_team:
        data = [["ลำดับ", "กิจกรรม", "ชื่อทีม", "ชื่อ-สกุล", "ห้อง", "รหัส"]]
        for i, r in enumerate(regs, 1):
            data.append([
                str(i),
                r.activity.title,
                get_team_paragraph(r.team_name),
                r.student.name,
                r.student.classroom or "-",
                r.student.number
            ])
        colWidths = [40, 100, 100, 140, 70, 60]
    else:
        data = [["ลำดับ", "กิจกรรม", "ชื่อ-สกุล", "ห้อง", "รหัสนักเรียน"]]
        for i, r in enumerate(regs, 1):
            data.append([
                str(i),
                r.activity.title,
                r.student.name,
                r.student.classroom or "-",
                r.student.number
            ])
        colWidths = [40, 160, 180, 80, 50]

    t = Table(data, colWidths=colWidths)
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('BACKGROUND', (0, 0), (-1, 0), colors.rose if hasattr(colors, 'rose') else colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(t)
    doc.build(elements)
    
    stream.seek(0)
    filename = f"registrations_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    
    return Response(
        content=stream.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
@router.get("/students/excel")
def export_students_excel(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    students = db.query(models.Student).order_by(models.Student.classroom, models.Student.sequence).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    ws.append(["รหัส", "คำนำหน้า", "ชื่อ", "นามสกุล", "ห้อง", "เลขที่"])

    prefixes = ["เด็กชาย", "เด็กหญิง", "นาย", "นางสาว", "ด.ช.", "ด.ญ."]
    
    for s in students:
        full_name = s.name.strip()
        found_prefix = ""
        rest_of_name = full_name
        
        # Try to extract prefix
        for p in prefixes:
            if full_name.startswith(p):
                found_prefix = p
                rest_of_name = full_name[len(p):].strip()
                break
        
        # Split first and last name
        name_parts = rest_of_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        ws.append([s.number, found_prefix, first_name, last_name, s.classroom or "", s.sequence or ""])

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    filename = f"students_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return Response(
        content=stream.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/students/pdf")
def export_students_pdf(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    students = db.query(models.Student).order_by(models.Student.classroom, models.Student.sequence).all()
    stream = BytesIO()

    # Register SukhumvitSet font for Thai text support
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    fonts_dir = os.path.join(base_dir, "frontend", "static", "fonts")
    font_name = "ChakraPetch"
    
    try:
        font_weights = ["Regular", "Medium", "SemiBold", "Bold"]
        font_path = None
        for weight in font_weights:
            test_path = os.path.join(fonts_dir, f"ChakraPetch-{weight}.ttf")
            if os.path.exists(test_path):
                font_path = test_path
                break
        
        if font_path:
            pdfmetrics.registerFont(TTFont("ChakraPetch", font_path))
        else:
            font_name = "Helvetica"
    except Exception:
        font_name = "Helvetica"

    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    # Custom Thai Paragraph Style
    styles = getSampleStyleSheet()
    thai_style = ParagraphStyle(
        'ThaiStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=16,
        leading=20,
        alignment=1, # Center
    )
    
    elements.append(Paragraph("รายชื่อนักเรียนทั้งหมด - DSNPRU_REG", thai_style))
    elements.append(Spacer(1, 20))

    # Table Data
    data = [["ลำดับ", "รหัสนักเรียน", "ชื่อ-นามสกุล", "ห้อง", "เลขที่"]]
    for i, s in enumerate(students, 1):
        data.append([
            str(i),
            s.number,
            s.name,
            s.classroom or "-",
            str(s.sequence) if s.sequence else "-"
        ])

    # Table Styling
    t = Table(data, colWidths=[40, 90, 240, 90, 50])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('BACKGROUND', (0, 0), (-1, 0), colors.rose if hasattr(colors, 'rose') else colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(t)
    doc.build(elements)
    
    stream.seek(0)
    filename = f"students_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    
    return Response(
        content=stream.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
