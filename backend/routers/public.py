from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..utils import log_action

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
    # Only show activities where group is visible (or no group)
    activities = (
        db.query(models.Activity)
        .outerjoin(models.ActivityGroup)
        .filter(
            models.Activity.status == "open",
            (models.ActivityGroup.is_visible == True) | (models.Activity.group_id == None)
        )
        .all()
    )
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
                allowed_classrooms=a.allowed_classrooms,
                start_time=a.start_time,
                end_time=a.end_time,
                color=a.color,
                group_id=a.group_id,
                group_name=a.group.name if a.group else None,
                registered_count=registered,
                remaining_seats=remaining,
            )
        )
    return result


@router.post("/register", response_model=schemas.MessageResponse)
def register_student(payload: schemas.RegistrationCreate, request: Request, db: Session = Depends(get_db)):
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

    # 2) Restriction checks (Classroom and Time)
    now = datetime.now()

    # Activity restrictions
    if activity.allowed_classrooms:
        allowed = [c.strip() for c in activity.allowed_classrooms.split(",") if c.strip()]
        if student.classroom not in allowed:
            return schemas.MessageResponse(
                success=False, message=f"กิจกรรมนี้เฉพาะนักเรียนห้อง {activity.allowed_classrooms} เท่านั้น", remaining_seats=None
            )
    
    if activity.start_time and now < activity.start_time:
        return schemas.MessageResponse(
            success=False, message=f"กิจกรรมจะเปิดให้ลงทะเบียนในวันที่ {activity.start_time.strftime('%Y-%m-%d %H:%M')}", remaining_seats=None
        )
    
    if activity.end_time and now > activity.end_time:
        return schemas.MessageResponse(
            success=False, message="กิจกรรมนี้หมดเขตการลงทะเบียนแล้ว", remaining_seats=None
        )

    # Group restrictions
    if activity.group_id:
        group = db.query(models.ActivityGroup).filter(models.ActivityGroup.id == activity.group_id).first()
        if group:
            if group.allowed_classrooms:
                allowed = [c.strip() for c in group.allowed_classrooms.split(",") if c.strip()]
                if student.classroom not in allowed:
                    return schemas.MessageResponse(
                        success=False, message=f"กลุ่มกิจกรรม '{group.name}' เฉพาะนักเรียนห้อง {group.allowed_classrooms} เท่านั้น", remaining_seats=None
                    )
            
            # Quota limit check
            # Check how many activities in this group student already has
            count_in_group = (
                db.query(models.Registration)
                .join(models.Activity)
                .filter(
                    models.Registration.student_id == student.id,
                    models.Activity.group_id == activity.group_id
                )
                .count()
            )
            if count_in_group >= group.quota:
                return schemas.MessageResponse(
                    success=False,
                    message=f"คุณลงทะเบียนในกลุ่ม '{group.name}' ครบ {group.quota} กิจกรรมแล้ว",
                    remaining_seats=None,
                )
    else:
        # If NO GROUP, use global 3-activity limit (only counting other ungrouped activities)
        count_ungrouped = (
            db.query(models.Registration)
            .join(models.Activity)
            .filter(
                models.Registration.student_id == student.id,
                models.Activity.group_id == None
            )
            .count()
        )
        if count_ungrouped >= 3:
            return schemas.MessageResponse(
                success=False,
                message="คุณลงทะเบียนครบ 3 กิจกรรมทั่วไปแล้ว ไม่สามารถลงเพิ่มได้",
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

    # Log action
    try:
        log_action(db, f"Student: {student.number}", "REGISTER", f"Registered for '{activity.title}'", request)
    except Exception as e:
        print(f"Public log failed: {e}")

    remaining = activity.max_people - (registered_for_activity + 1)
    return schemas.MessageResponse(
        success=True, message="ลงทะเบียนสำเร็จ!", remaining_seats=max(remaining, 0)
    )


@router.get("/system_info", response_model=schemas.SystemInfo)
def get_system_info(db: Session = Depends(get_db)):
    total_students = db.query(models.Student).count()
    total_activities = db.query(models.Activity).count()
    total_registrations = db.query(models.Registration).count()
    
    return schemas.SystemInfo(
        version="1.0.0",
        environment="Production",
        status="Stable",
        total_students=total_students,
        total_activities=total_activities,
        total_registrations=total_registrations,
        last_updated="Jan 2024"
    )


