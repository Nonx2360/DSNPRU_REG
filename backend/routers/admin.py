from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import openpyxl
import io
import os  # Added for log file reading

from .. import models, schemas
from ..auth import authenticate_admin, create_access_token, get_current_admin, get_current_superuser, get_password_hash, verify_password
from ..database import get_db
from ..utils import log_action
from datetime import datetime, timedelta
from sqlalchemy import func, case
import csv
import io
from fastapi.responses import StreamingResponse


router = APIRouter()


@router.get("/api/logs", response_model=List[schemas.AdminLog])
def read_logs(
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_superuser),
):
    return db.query(models.AdminLog).order_by(models.AdminLog.timestamp.desc()).all()


@router.get("/api/admins", response_model=List[schemas.Admin])
def list_admins(
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_superuser),
):
    return db.query(models.Admin).all()



@router.post("/api/admins", response_model=schemas.Admin)
def create_admin(
    admin_in: schemas.AdminCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_superuser),
):
    existing = db.query(models.Admin).filter(models.Admin.username == admin_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="ชื่อผู้ใช้นี้มีอยู่แล้ว")
    
    new_admin = models.Admin(
        username=admin_in.username,
        password_hash=get_password_hash(admin_in.password),
        is_superuser=admin_in.is_superuser
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    log_action(db, admin.username, "CREATE_ADMIN", f"Created admin: {new_admin.username}", request)
    return new_admin


@router.delete("/api/admins/{admin_id}", status_code=204)
def delete_admin(
    admin_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_superuser),
):
    admin_to_delete = db.query(models.Admin).filter(models.Admin.id == admin_id).first()
    if not admin_to_delete:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้งานนี้")
    
    if admin_to_delete.id == admin.id:
         raise HTTPException(status_code=400, detail="ไม่สามารถลบบัญชีตัวเองได้")

    tgt_username = admin_to_delete.username
    db.delete(admin_to_delete)
    db.commit()
    log_action(db, admin.username, "DELETE_ADMIN", f"Deleted admin: {tgt_username}", request)
    return


@router.post("/login", response_model=schemas.Token)
def admin_login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    admin = authenticate_admin(db, form_data.username, form_data.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง",
        )
    access_token = create_access_token(data={"sub": admin.username})
    log_action(db, admin.username, "LOGIN", "Logged into system", request)
    return schemas.Token(access_token=access_token)


@router.post("/logout", status_code=204)
def admin_logout(
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    log_action(db, admin.username, "LOGOUT", "Logged out of system", request)
    return


@router.put("/change-password", status_code=204)
def change_password(
    password_in: schemas.ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    if not verify_password(password_in.old_password, admin.password_hash):
        raise HTTPException(status_code=400, detail="รหัสผ่านเดิมไม่ถูกต้อง")
    
    admin.password_hash = get_password_hash(password_in.new_password)
    db.commit()
    log_action(db, admin.username, "CHANGE_PASSWORD", "Changed own password", request)
    return


@router.post("/api/activity_groups", response_model=schemas.ActivityGroup)
def create_activity_group(
    group_in: schemas.ActivityGroupCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    group = models.ActivityGroup(
        name=group_in.name, 
        quota=group_in.quota,
        allowed_classrooms=group_in.allowed_classrooms,
        is_visible=group_in.is_visible
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    log_action(db, admin.username, "CREATE_ACTIVITY_GROUP", f"Created group: {group.name}", request)
    return group


@router.get("/api/activity_groups", response_model=List[schemas.ActivityGroup])
def list_activity_groups(
    db: Session = Depends(get_db), admin: models.Admin = Depends(get_current_admin)
):
    return db.query(models.ActivityGroup).all()


@router.put("/api/activity_groups/{group_id}", response_model=schemas.ActivityGroup)
def update_activity_group(
    group_id: int,
    group_in: schemas.ActivityGroupCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    group = db.query(models.ActivityGroup).filter(models.ActivityGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="ไม่พบกลุ่มกิจกรรม")
    group.name = group_in.name
    group.quota = group_in.quota
    db.commit()
    db.refresh(group)
    log_action(db, admin.username, "UPDATE_ACTIVITY_GROUP", f"Updated group: {group.name}", request)
    return group


@router.delete("/api/activity_groups/{group_id}", status_code=204)
def delete_activity_group(
    group_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    group = db.query(models.ActivityGroup).filter(models.ActivityGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="ไม่พบกลุ่มกิจกรรม")
    name = group.name
    db.delete(group)
    db.commit()
    log_action(db, admin.username, "DELETE_ACTIVITY_GROUP", f"Deleted group: {name}", request)
    return


@router.post("/create_activity", response_model=schemas.Activity)
def create_activity(
    activity_in: schemas.ActivityCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    activity = models.Activity(
        title=activity_in.title,
        description=activity_in.description,
        max_people=activity_in.max_people,
        status=activity_in.status,
        allowed_classrooms=activity_in.allowed_classrooms,
        start_time=activity_in.start_time,
        end_time=activity_in.end_time,
        color=activity_in.color,
        group_id=activity_in.group_id,
        # New fields for V3
        type=activity_in.type or "individual",
        max_team_size=activity_in.max_team_size or 1,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    log_action(db, admin.username, "CREATE_ACTIVITY", f"Created activity: {activity.title}", request)

    return schemas.Activity(
        id=activity.id,
        title=activity.title,
        description=activity.description,
        max_people=activity.max_people,
        status=activity.status,
        allowed_classrooms=activity.allowed_classrooms,
        start_time=activity.start_time,
        end_time=activity.end_time,
        color=activity.color,
        group_id=activity.group_id,
        group_name=activity.group.name if activity.group else None,
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


@router.put("/activities/{activity_id}", response_model=schemas.Activity)
def update_activity(
    activity_id: int,
    activity_in: schemas.ActivityUpdate,
    request: Request,
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
    log_action(db, admin.username, "UPDATE_ACTIVITY", f"Updated activity: {activity.title}", request)

    registered = len(activity.registrations)
    remaining = max(activity.max_people - registered, 0)
    return schemas.Activity(
        id=activity.id,
        title=activity.title,
        description=activity.description,
        max_people=activity.max_people,
        status=activity.status,
        allowed_classrooms=activity.allowed_classrooms,
        start_time=activity.start_time,
        end_time=activity.end_time,
        color=activity.color,
        group_id=activity.group_id,
        group_name=activity.group.name if activity.group else None,
        registered_count=registered,
        remaining_seats=remaining,
        type=activity.type,
        max_team_size=activity.max_team_size,
    )


@router.post("/activities/{activity_id}/toggle", response_model=schemas.Activity)
def toggle_activity_status(
    activity_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    activity = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="ไม่พบกิจกรรม")

    activity.status = "close" if activity.status == "open" else "open"
    db.commit()
    db.refresh(activity)
    log_action(db, admin.username, "TOGGLE_ACTIVITY", f"Toggled status of '{activity.title}' to {activity.status}", request)

    registered = len(activity.registrations)
    remaining = max(activity.max_people - registered, 0)
    return schemas.Activity(
        id=activity.id,
        title=activity.title,
        description=activity.description,
        max_people=activity.max_people,
        status=activity.status,
        allowed_classrooms=activity.allowed_classrooms,
        start_time=activity.start_time,
        end_time=activity.end_time,
        color=activity.color,
        group_id=activity.group_id,
        group_name=activity.group.name if activity.group else None,
        registered_count=registered,
        remaining_seats=remaining,
        type=activity.type,
        max_team_size=activity.max_team_size,
    )


@router.delete("/activities/{activity_id}", status_code=204)
def delete_activity(
    activity_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    activity = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="ไม่พบกิจกรรม")

    title = activity.title
    db.delete(activity)
    db.commit()
    log_action(db, admin.username, "DELETE_ACTIVITY", f"Deleted activity: {title}", request)
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


@router.delete("/registrations/{reg_id}", status_code=204)
def delete_registration(
    reg_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    reg = db.query(models.Registration).filter(models.Registration.id == reg_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลการลงทะเบียน")
    
    was_registered = (reg.status == "registered")
    activity = reg.activity

    details = f"Removed Student {reg.student.number} ({reg.student.name}) from activity ID {reg.activity_id} ({reg.activity.title})"
    db.delete(reg)
    db.commit()

    if was_registered:
        # Promote next in line if any
        next_in_line = (
             db.query(models.Registration)
             .filter(
                 models.Registration.activity_id == activity.id,
                 models.Registration.status == "waitlisted"
             )
             .order_by(models.Registration.timestamp.asc())
             .first()
        )
        if next_in_line:
            next_in_line.status = "registered"
            db.commit()
            try:
                log_action(db, "SYSTEM", "PROMOTE", f"Promoted student.id={next_in_line.student_id} to registered for '{activity.title}' via ADMIN removal", request)
            except:
                pass

    log_action(db, admin.username, "DELETE_REGISTRATION", details, request)
    return


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
                group_id=a.group_id,
                group_name=a.group.name if a.group else None,
                registered_count=registered,
                remaining_seats=remaining,
                type=a.type,
                max_team_size=a.max_team_size,
            )
        )
    return schemas.DashboardStats(
        total_students=total_students,
        total_registrations=total_registrations,
        activities=stats_activities,
    )


@router.get("/api/analytics", response_model=schemas.AnalyticsData)
def analytics_data(
    db: Session = Depends(get_db), admin: models.Admin = Depends(get_current_admin)
):
    from sqlalchemy import func
    
    # 1. Trend: Registrations per day (last 14 days)
    # Note: SQLite date() function for grouping
    trend_query = (
        db.query(func.date(models.Registration.timestamp).label("date"), func.count(models.Registration.id).label("count"))
        .group_by("date")
        .order_by("date")
        .limit(14)
        .all()
    )
    trend = [schemas.TrendPoint(date=r.date, count=r.count) for r in trend_query]

    # 2. Popularity by Group
    group_query = (
        db.query(models.ActivityGroup.name, func.count(models.Registration.id).label("count"))
        .join(models.Activity, models.Activity.group_id == models.ActivityGroup.id)
        .join(models.Registration, models.Registration.activity_id == models.Activity.id)
        .group_by(models.ActivityGroup.name)
        .all()
    )
    # Also count activities with NO group
    ungrouped_count = (
        db.query(func.count(models.Registration.id))
        .join(models.Activity, models.Registration.activity_id == models.Activity.id)
        .filter(models.Activity.group_id == None)
        .scalar()
    )
    groups = [schemas.GroupStat(name=r.name, count=r.count) for r in group_query]
    if ungrouped_count:
        groups.append(schemas.GroupStat(name="General", count=ungrouped_count))

    # 3. Classroom Stats (Registered count per class)
    class_query = (
        db.query(models.Student.classroom, func.count(models.Registration.id).label("count"))
        .join(models.Registration, models.Registration.student_id == models.Student.id)
        .group_by(models.Student.classroom)
        .order_by(func.count(models.Registration.id).desc())
        .limit(10)
        .all()
    )
    classrooms = [schemas.ClassStat(classroom=r.classroom or "N/A", count=r.count) for r in class_query]

    return schemas.AnalyticsData(trend=trend, groups=groups, classrooms=classrooms)


@router.post("/api/import_students", response_model=schemas.MessageResponse)
def import_students(
    request: Request,
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

        # Assume header is in row 1: Code, Prefix, Name, Surname, Classroom, Sequence
        # รหัส, คำนำหน้า, ชื่อ, สกุล, ห้อง, เลขที่
        imported_count = 0
        for row in sheet.iter_rows(min_row=2, values_only=True):
            # Format: รหัส(0), คำนำหน้า(1), ชื่อ(2), นามสกุล(3), ห้อง(4), เลขที่(5)
            if not row or len(row) < 1:
                continue
            
            # Use safe padding to handle rows with fewer columns
            data = (list(row) + [None] * 6)[:6]
            code, prefix, first_name, last_name, classroom, sequence_val = data
            
            if not code or not first_name:
                continue
            
            # Combine name for storage: [Prefix][First Name] [Last Name]
            full_name = f"{prefix or ''}{first_name} {last_name or ''}".strip()
            student_number = str(code).strip()
            classroom_name = str(classroom).strip() if classroom else ""
            
            # Parse Sequence
            sequence_num = None
            if sequence_val:
                try:
                    sequence_num = int(float(str(sequence_val).strip()))
                except ValueError:
                    pass

            # Check if student exists
            existing = db.query(models.Student).filter(models.Student.number == student_number).first()
            if existing:
                existing.name = full_name
                existing.classroom = classroom_name
                existing.sequence = sequence_num
            else:
                new_student = models.Student(
                    number=student_number,
                    name=full_name,
                    classroom=classroom_name,
                    sequence=sequence_num
                )
                db.add(new_student)
            
            imported_count += 1

        db.commit()
        log_action(db, admin.username, "IMPORT_STUDENTS", f"Imported {imported_count} students", request)
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
    request: Request,
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
    log_action(db, admin.username, "UPDATE_STUDENT", f"Updated student: {student.name}", request)
    return student


@router.delete("/api/students/{student_id}", status_code=204)
def delete_student(
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลนักเรียน")

    name = student.name
    db.delete(student)
    db.commit()
    log_action(db, admin.username, "DELETE_STUDENT", f"Deleted student: {name}", request)
    return


@router.post("/api/students/bulk-delete", response_model=schemas.MessageResponse)
def bulk_delete_students(
    payload: schemas.BulkActionIds,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    students = db.query(models.Student).filter(models.Student.id.in_(payload.ids)).all()
    count = len(students)
    for student in students:
        db.delete(student)
    db.commit()
    log_action(db, admin.username, "BULK_DELETE_STUDENTS", f"Deleted {count} students", request)
    return schemas.MessageResponse(success=True, message=f"ลบข้อมูลนักเรียนสำเร็จ {count} รายการ")


@router.post("/api/students/bulk-update-class", response_model=schemas.MessageResponse)
def bulk_update_classroom(
    payload: schemas.BulkUpdateClassroom,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    db.query(models.Student).filter(models.Student.id.in_(payload.ids)).update(
        {models.Student.classroom: payload.classroom}, synchronize_session=False
    )
    db.commit()
    log_action(db, admin.username, "BULK_UPDATE_CLASS", f"Updated {len(payload.ids)} students to {payload.classroom}", request)
    return schemas.MessageResponse(success=True, message=f"อัปเดตห้องเรียนสำเร็จ {len(payload.ids)} รายการ")


@router.get("/api/classrooms", response_model=List[str])
def list_classrooms(
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    classrooms = db.query(models.Student.classroom).distinct().all()
    return sorted([c[0] for c in classrooms if c[0]])


@router.get("/api/announcements", response_model=List[schemas.Announcement])
def admin_list_announcements(
    db: Session = Depends(get_db), admin: models.Admin = Depends(get_current_admin)
):
    return db.query(models.Announcement).order_by(models.Announcement.timestamp.desc()).all()


@router.post("/api/announcements", response_model=schemas.Announcement)
def create_announcement(
    ann_in: schemas.AnnouncementCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    ann = models.Announcement(
        message=ann_in.message,
        is_active=ann_in.is_active,
        color=ann_in.color
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    log_action(db, admin.username, "CREATE_ANNOUNCEMENT", f"Created announcement", request)
    return ann


@router.put("/api/announcements/{ann_id}", response_model=schemas.Announcement)
def update_announcement(
    ann_id: int,
    ann_in: schemas.AnnouncementUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    ann = db.query(models.Announcement).filter(models.Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="ไม่พบประกาศ")

    for field, value in ann_in.dict(exclude_unset=True).items():
        setattr(ann, field, value)

    db.commit()
    db.refresh(ann)
    log_action(db, admin.username, "UPDATE_ANNOUNCEMENT", f"Updated announcement ID {ann.id}", request)
    return ann


@router.delete("/api/announcements/{ann_id}", status_code=204)
def delete_announcement(
    ann_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin),
):
    ann = db.query(models.Announcement).filter(models.Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="ไม่พบประกาศ")

    db.delete(ann)
    db.commit()
    log_action(db, admin.username, "DELETE_ANNOUNCEMENT", f"Deleted announcement ID {ann_id}", request)
    return

# --- Platform Status Endpoints ---

@router.get("/api/platform/status", response_model=schemas.PlatformStatus)
def get_platform_status(
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin)
):
    now = datetime.now()
    day_ago = now - timedelta(days=1)
    
    # DB Size
    db_size = 0
    if os.path.exists("sicday.db"):
        db_size = os.path.getsize("sicday.db")
        
    # Stats for last 24h
    logs_count = db.query(models.RequestLog).filter(models.RequestLog.timestamp >= day_ago).count()
    avg_resp = db.query(func.avg(models.RequestLog.response_time_ms)).filter(models.RequestLog.timestamp >= day_ago).scalar() or 0.0
    error_count = db.query(models.RequestLog).filter(
        models.RequestLog.timestamp >= day_ago,
        models.RequestLog.status_code >= 400
    ).count()
    error_rate = (error_count / logs_count * 100) if logs_count > 0 else 0.0
    
    # Uptime % (Based on 5-min metrics in last 24h)
    expected_metrics = (24 * 60) // 5
    healthy_metrics = db.query(models.SystemMetric).filter(
        models.SystemMetric.metric_type == "db_health",
        models.SystemMetric.status == "healthy",
        models.SystemMetric.timestamp >= day_ago
    ).count()
    # If no metrics yet, assume 100%
    uptime = (healthy_metrics / expected_metrics * 100) if expected_metrics > 0 and healthy_metrics > 0 else 100.0
    if healthy_metrics == 0 and db.query(models.SystemMetric).filter(models.SystemMetric.timestamp >= day_ago).count() > 0:
        uptime = 0.0 # Had metrics but none healthy

    return schemas.PlatformStatus(
        api_health="healthy",
        db_health="healthy", # If we can query, it's healthy
        db_size_bytes=db_size,
        uptime_percent=min(round(uptime, 2), 100.0),
        total_requests_24h=logs_count,
        avg_response_time_24h=round(avg_resp, 2),
        error_rate_24h=round(error_rate, 2)
    )

@router.get("/api/platform/metrics", response_model=schemas.DetailedMetrics)
def get_platform_metrics(
    days: int = 7,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin)
):
    now = datetime.now()
    start_date = now - timedelta(days=days)
    
    # Determine grouping (by hour if <= 2 days, by day if more)
    if days <= 2:
        group_func = func.strftime('%Y-%m-%d %H:00', models.RequestLog.timestamp)
        metric_group_func = func.strftime('%Y-%m-%d %H:00', models.SystemMetric.timestamp)
    else:
        group_func = func.date(models.RequestLog.timestamp)
        metric_group_func = func.date(models.SystemMetric.timestamp)

    # Request Trend
    req_trend = (
        db.query(group_func.label("label"), func.count(models.RequestLog.id).label("value"))
        .filter(models.RequestLog.timestamp >= start_date)
        .group_by("label")
        .order_by("label")
        .all()
    )
    
    # Response Time Trend
    resp_trend = (
        db.query(group_func.label("label"), func.avg(models.RequestLog.response_time_ms).label("value"))
        .filter(models.RequestLog.timestamp >= start_date)
        .group_by("label")
        .order_by("label")
        .all()
    )
    
    # Error Rate Trend
    error_trend_raw = (
        db.query(
            group_func.label("label"), 
            func.count(models.RequestLog.id).label("total"),
            func.sum(case((models.RequestLog.status_code >= 400, 1), else_=0)).label("errors")
        )
        .filter(models.RequestLog.timestamp >= start_date)
        .group_by("label")
        .order_by("label")
        .all()
    )
    error_trend = []
    for r in error_trend_raw:
        rate = (r.errors / r.total * 100) if r.total > 0 else 0
        error_trend.append(schemas.GenericTrendPoint(label=r.label, value=round(rate, 2)))

    # DB Size Trend
    db_size_trend = (
        db.query(metric_group_func.label("label"), func.avg(models.SystemMetric.value).label("value"))
        .filter(models.SystemMetric.metric_type == "db_size", models.SystemMetric.timestamp >= start_date)
        .group_by("label")
        .order_by("label")
        .all()
    )

    # Endpoint Breakdown
    endpoint_stats = (
        db.query(
            models.RequestLog.path,
            models.RequestLog.method,
            func.count(models.RequestLog.id).label("count"),
            func.avg(models.RequestLog.response_time_ms).label("avg_resp"),
            func.sum(case((models.RequestLog.status_code >= 400, 1), else_=0)).label("errors")
        )
        .filter(models.RequestLog.timestamp >= start_date)
        .group_by(models.RequestLog.path, models.RequestLog.method)
        .order_by(func.count(models.RequestLog.id).desc())
        .limit(20)
        .all()
    )
    
    breakdown = []
    for e in endpoint_stats:
        rate = (e.errors / e.count * 100) if e.count > 0 else 0
        breakdown.append(schemas.EndpointMetric(
            path=e.path,
            method=e.method,
            count=e.count,
            avg_response_time=round(e.avg_resp, 2),
            error_rate=round(rate, 2)
        ))

    return schemas.DetailedMetrics(
        request_trend=[schemas.GenericTrendPoint(label=r.label, value=float(r.value)) for r in req_trend],
        response_time_trend=[schemas.GenericTrendPoint(label=r.label, value=float(r.value)) for r in resp_trend],
        error_rate_trend=error_trend,
        db_size_trend=[schemas.GenericTrendPoint(label=r.label, value=float(r.value or 0)) for r in db_size_trend],
        endpoint_breakdown=breakdown
    )

@router.get("/api/platform/export")
def export_platform_status(
    days: int = 30,
    db: Session = Depends(get_db),
    admin: models.Admin = Depends(get_current_admin)
):
    start_date = datetime.now() - timedelta(days=days)
    logs = db.query(models.RequestLog).filter(models.RequestLog.timestamp >= start_date).order_by(models.RequestLog.timestamp.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Method", "Path", "Status Code", "Response Time (ms)"])
    
    for log in logs:
        writer.writerow([log.timestamp.isoformat(), log.method, log.path, log.status_code, log.response_time_ms])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=platform_status_report_{datetime.now().strftime('%Y%m%d')}.csv"}
    )
