from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter()


@router.get("/search_students", response_model=List[schemas.Student])
def search_students(q: str, db: Session = Depends(get_db)):
    if len(q) < 2:
        return []
    students = (
        db.query(models.Student)
        .filter(
            (models.Student.name.contains(q)) | 
            (models.Student.number.contains(q))
        )
        .limit(10)
        .all()
    )
    return students


@router.get("/activities", response_model=List[schemas.Activity])
def list_activities(db: Session = Depends(get_db)):
    activities = db.query(models.Activity).all()
    result = []
    for a in activities:
        registered = len(a.registrations)
        remaining = max(a.max_people - registered, 0)
        result.append(
            schemas.Activity(
                id=a.id,
                title=a.title,
                description=a.description,
                max_people=a.max_people,
                status=a.status,
                registered_count=registered,
                remaining_seats=remaining,
            )
        )
    return result


@router.post("/register", response_model=schemas.MessageResponse)
def register_student(payload: schemas.RegistrationCreate, db: Session = Depends(get_db)):
    # find student (must be imported by admin)
    student = (
        db.query(models.Student)
        .filter(
            (models.Student.number == payload.number) |
            (models.Student.name == payload.name)
        )
        .first()
    )
    if not student:
        return schemas.MessageResponse(
            success=False, message="ไม่พบข้อมูลนักเรียนในระบบ กรุณาติดต่อผู้ดูแลระบบ", remaining_seats=None
        )

    activity = db.query(models.Activity).filter(models.Activity.id == payload.activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="ไม่พบกิจกรรมที่เลือก")

    # business rules
    # 1) duplicate registration
    existing = (
        db.query(models.Registration)
        .filter(
            models.Registration.student_id == student.id,
            models.Registration.activity_id == activity.id,
        )
        .first()
    )
    if existing:
        return schemas.MessageResponse(
            success=False, message="คุณได้ลงทะเบียนกิจกรรมนี้แล้ว", remaining_seats=None
        )

    # 2) 3-activity limit
    count_for_student = (
        db.query(models.Registration)
        .filter(models.Registration.student_id == student.id)
        .count()
    )
    if count_for_student >= 3:
        return schemas.MessageResponse(
            success=False,
            message="คุณลงทะเบียนครบ 3 กิจกรรมแล้ว ไม่สามารถลงเพิ่มได้",
            remaining_seats=None,
        )

    # 3) activity status
    if activity.status != "open":
        return schemas.MessageResponse(
            success=False, message="กิจกรรมนี้ปิดรับสมัครแล้ว", remaining_seats=None
        )

    # 4) capacity
    registered_for_activity = (
        db.query(models.Registration)
        .filter(models.Registration.activity_id == activity.id)
        .count()
    )
    if registered_for_activity >= activity.max_people:
        return schemas.MessageResponse(
            success=False, message="กิจกรรมนี้เต็มแล้ว", remaining_seats=0
        )

    # create registration
    reg = models.Registration(student_id=student.id, activity_id=activity.id)
    db.add(reg)
    db.commit()

    remaining = activity.max_people - (registered_for_activity + 1)
    return schemas.MessageResponse(
        success=True, message="ลงทะเบียนสำเร็จ!", remaining_seats=max(remaining, 0)
    )


