import os
from io import BytesIO
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

    wb = Workbook()
    ws = wb.active
    ws.title = "Registrations"
    ws.append(["กิจกรรม", "ชื่อ-สกุล", "ห้อง", "เลขที่"])

    for r in regs:
        ws.append(
            [
                r.activity.title,
                r.student.name,
                r.student.classroom,
                r.student.number,
            ]
        )

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
    regs = _get_registrations(db, activity_id)
    stream = BytesIO()

    # Register SukhumvitSet font for Thai text support
    # Get absolute path to fonts directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    fonts_dir = os.path.join(base_dir, "frontend", "static", "fonts")
    font_name = "SukhumvitSet"
    
    try:
        # Try Medium first, then fallback to other weights
        font_weights = ["Medium", "Text", "Regular", "SemiBold", "Bold"]
        font_path = None
        
        for weight in font_weights:
            test_path = os.path.join(fonts_dir, f"SukhumvitSet-{weight}.ttf")
            if os.path.exists(test_path):
                font_path = test_path
                break
        
        if font_path:
            pdfmetrics.registerFont(TTFont("SukhumvitSet", font_path))
        else:
            raise FileNotFoundError(f"Could not find any SukhumvitSet font in {fonts_dir}")
    except Exception as e:
        # If font registration fails, use Helvetica (will show squares for Thai)
        font_name = "Helvetica"
        import logging
        logging.warning(f"Could not load Thai font: {e}. Using Helvetica (Thai text may display as squares).")

    c = canvas.Canvas(stream, pagesize=A4)
    width, height = A4
    c.setFont(font_name, 14)

    y = height - 40
    c.drawString(40, y, "รายชื่อผู้ลงทะเบียนกิจกรรม")
    y -= 30

    for r in regs:
        line = f"{r.activity.title} - {r.student.name} ({r.student.classroom} เลขที่ {r.student.number})"
        c.drawString(40, y, line)
        y -= 22
        if y < 40:
            c.showPage()
            c.setFont(font_name, 14)
            y = height - 40

    c.showPage()
    c.save()
    stream.seek(0)

    return Response(
        content=stream.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="registrations.pdf"'},
    )


