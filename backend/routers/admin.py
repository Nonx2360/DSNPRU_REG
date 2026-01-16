from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import openpyxl
import io

from .. import models, schemas
from ..auth import authenticate_admin, create_access_token, get_current_admin, get_password_hash
from ..database import get_db

router = APIRouter()


@router.post("/login", response_model=schemas.Token)
def admin_login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    admin = authenticate_admin(db, form_data.username, form_data.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง",
        )
    access_token = create_access_token(data={"sub": admin.username})
    return schemas.Token(access_token=access_token)


@router.post("/create_activity", response_model=schemas.Activity)
def create_activity(
    activity_in: schemas.ActivityCreate,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    activity = models.Activity(
        title=activity_in.title,
        description=activity_in.description,
        max_people=activity_in.max_people,
        status=activity_in.status,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)

    return schemas.Activity(
        id=activity.id,
        title=activity.title,
        description=activity.description,
        max_people=activity.max_people,
        status=activity.status,
        registered_count=0,
        remaining_seats=activity.max_people,
    )


@router.get("/api/activities", response_model=List[schemas.Activity])
def admin_list_activities(
    db: Session = Depends(get_db), admin: models.Admin = Depends(get_current_admin)
):
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


@router.put("/activities/{activity_id}", response_model=schemas.Activity)
def update_activity(
    activity_id: int,
    activity_in: schemas.ActivityUpdate,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    activity = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="ไม่พบกิจกรรม")

    for field, value in activity_in.dict(exclude_unset=True).items():
        setattr(activity, field, value)

    db.commit()
    db.refresh(activity)

    registered = len(activity.registrations)
    remaining = max(activity.max_people - registered, 0)
    return schemas.Activity(
        id=activity.id,
        title=activity.title,
        description=activity.description,
        max_people=activity.max_people,
        status=activity.status,
        registered_count=registered,
        remaining_seats=remaining,
    )


@router.post("/activities/{activity_id}/toggle", response_model=schemas.Activity)
def toggle_activity_status(
    activity_id: int,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    activity = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="ไม่พบกิจกรรม")

    activity.status = "close" if activity.status == "open" else "open"
    db.commit()
    db.refresh(activity)

    registered = len(activity.registrations)
    remaining = max(activity.max_people - registered, 0)
    return schemas.Activity(
        id=activity.id,
        title=activity.title,
        description=activity.description,
        max_people=activity.max_people,
        status=activity.status,
        registered_count=registered,
        remaining_seats=remaining,
    )


@router.delete("/activities/{activity_id}", status_code=204)
def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    activity = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="ไม่พบกิจกรรม")

    db.delete(activity)
    db.commit()
    return


@router.get("/registrations/{activity_id}", response_model=List[schemas.Registration])
def get_registrations_for_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    regs = (
        db.query(models.Registration)
        .filter(models.Registration.activity_id == activity_id)
        .all()
    )
    return regs


@router.get("/search_students", response_model=List[schemas.Student])
def search_students(
    q: str,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    students = (
        db.query(models.Student)
        .filter(
            (models.Student.name.contains(q))
            | (models.Student.classroom.contains(q))
        )
        .all()
    )
    return students


@router.get("/api/dashboard", response_model=schemas.DashboardStats)
def dashboard_stats(
    db: Session = Depends(get_db), admin: models.Admin = Depends(get_current_admin)
):
    total_students = db.query(models.Student).count()
    total_registrations = db.query(models.Registration).count()
    activities = db.query(models.Activity).all()
    stats_activities = []
    for a in activities:
        registered = len(a.registrations)
        remaining = max(a.max_people - registered, 0)
        stats_activities.append(
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
    return schemas.DashboardStats(
        total_students=total_students,
        total_registrations=total_registrations,
        activities=stats_activities,
    )


@router.post("/api/import_students", response_model=schemas.MessageResponse)
def import_students(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ Excel (.xlsx หรือ .xls)")

    try:
        contents = file.file.read()
        wb = openpyxl.load_workbook(io.BytesIO(contents))
        sheet = wb.active

        # Assume header is in row 1: Code, Prefix, Name, Surname
        # รหัส, คำนำหน้า, ชื่อ, สกุล
        imported_count = 0
        for row in sheet.iter_rows(min_row=2, values_only=True):
            # Format: รหัส(0), คำนำหน้า(1), ชื่อ(2), นามสกุล(3), ห้อง(4)
            if not row or len(row) < 1:
                continue
            
            # Use safe padding to handle rows with fewer columns
            data = (list(row) + [None] * 5)[:5]
            code, prefix, first_name, last_name, classroom = data
            
            if not code or not first_name:
                continue
            
            # Combine name for storage: [Prefix][First Name] [Last Name]
            full_name = f"{prefix or ''}{first_name} {last_name or ''}".strip()
            student_number = str(code).strip()
            classroom_name = str(classroom).strip() if classroom else ""

            # Check if student exists
            existing = db.query(models.Student).filter(models.Student.number == student_number).first()
            if existing:
                existing.name = full_name
                existing.classroom = classroom_name
            else:
                new_student = models.Student(
                    number=student_number,
                    name=full_name,
                    classroom=classroom_name
                )
                db.add(new_student)
            
            imported_count += 1

        db.commit()
        return schemas.MessageResponse(
            success=True, message=f"นำเข้าข้อมูลนักเรียนสำเร็จ {imported_count} คน"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการนำเข้าข้อมูล: {str(e)}")


@router.get("/api/students", response_model=List[schemas.Student])
def admin_list_students(
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    return db.query(models.Student).all()


@router.put("/api/students/{student_id}", response_model=schemas.Student)
def update_student(
    student_id: int,
    student_in: schemas.StudentUpdate,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลนักเรียน")

    for field, value in student_in.dict(exclude_unset=True).items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)
    return student


@router.delete("/api/students/{student_id}", status_code=204)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลนักเรียน")

    db.delete(student)
    db.commit()
    return


@router.post("/api/students/bulk-delete", response_model=schemas.MessageResponse)
def bulk_delete_students(
    payload: schemas.BulkActionIds,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    students = db.query(models.Student).filter(models.Student.id.in_(payload.ids)).all()
    count = len(students)
    for student in students:
        db.delete(student)
    db.commit()
    return schemas.MessageResponse(success=True, message=f"ลบข้อมูลนักเรียนสำเร็จ {count} รายการ")


@router.post("/api/students/bulk-update-class", response_model=schemas.MessageResponse)
def bulk_update_classroom(
    payload: schemas.BulkUpdateClassroom,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    db.query(models.Student).filter(models.Student.id.in_(payload.ids)).update(
        {models.Student.classroom: payload.classroom}, synchronize_session=False
    )
    db.commit()
    return schemas.MessageResponse(success=True, message=f"อัปเดตห้องเรียนสำเร็จ {len(payload.ids)} รายการ")
