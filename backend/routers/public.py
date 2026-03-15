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
                type=a.type,
                max_team_size=a.max_team_size,
            )
        )
    return result


@router.post("/register", response_model=schemas.MessageResponse)
def register_student(payload: schemas.RegistrationCreate, request: Request, db: Session = Depends(get_db)):
    # 1. Find main student
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

    # 2. Activity Status Checks (Global)
    if activity.status != "open":
         return schemas.MessageResponse(success=False, message="กิจกรรมนี้ปิดรับสมัครแล้ว", remaining_seats=None)

    now = datetime.now()
    if activity.start_time and now < activity.start_time:
        return schemas.MessageResponse(
            success=False, message=f"กิจกรรมจะเปิดให้ลงทะเบียนในวันที่ {activity.start_time.strftime('%Y-%m-%d %H:%M')}", remaining_seats=None
        )
    
    if activity.end_time and now > activity.end_time:
        return schemas.MessageResponse(
            success=False, message="กิจกรรมนี้หมดเขตการลงทะเบียนแล้ว", remaining_seats=None
        )

    # 3. Identify all members (Main + Partners)
    members = [student]
    
    if activity.type == "team" and payload.partner_numbers:
        # Team Size check
        if len(payload.partner_numbers) + 1 > activity.max_team_size:
             return schemas.MessageResponse(
                 success=False, message=f"กิจกรรมนี้จำกัดทีมละไม่เกิน {activity.max_team_size} คน", remaining_seats=None
             )
        
        # Verify partners
        for p_num in payload.partner_numbers:
            if not p_num: continue
            clean_num = str(p_num).strip()
            if clean_num == str(student.number): continue # Skip self if entered
            
            # Check for duplicate partners in the payload itself
            # (handled by logic if user inputs same number twice? No, need to be careful)
            # Logic below handles DB duplicates, but payload duplicates?
            # Let's trust the set logic or simple check:
            
            partner = db.query(models.Student).filter(models.Student.number == clean_num).first()
            if not partner:
                return schemas.MessageResponse(success=False, message=f"ไม่พบรหัสนักเรียน {clean_num} ในระบบ", remaining_seats=None)
            
            # Avoid adding same partner object twice
            if partner.id not in [m.id for m in members]:
                members.append(partner)

    # 4. Capacity Check
    registered_count = (
        db.query(models.Registration)
        .filter(models.Registration.activity_id == activity.id)
        .count()
    )
    if registered_count + len(members) > activity.max_people:
         return schemas.MessageResponse(
             success=False, message="ที่นั่งไม่พอสำหรับจำนวนสมาชิกในทีม", remaining_seats=max(activity.max_people - registered_count, 0)
         )

    # 5. Validation Loop for ALL members
    for member in members:
        # Duplicate registration
        existing = (
            db.query(models.Registration)
            .filter(
                models.Registration.student_id == member.id,
                models.Registration.activity_id == activity.id,
            )
            .first()
        )
        if existing:
            return schemas.MessageResponse(
                success=False, message=f"นักเรียน {member.name} ({member.number}) ลงทะเบียนกิจกรรมนี้ไปแล้ว", remaining_seats=None
            )

        # Classroom Restrictions (Activity Level)
        if activity.allowed_classrooms:
            allowed = [c.strip() for c in activity.allowed_classrooms.split(",") if c.strip()]
            if member.classroom not in allowed:
                return schemas.MessageResponse(
                    success=False, message=f"นักเรียน {member.name} ({member.classroom}) ไม่อยู่ในห้องที่ได้รับอนุญาต ({activity.allowed_classrooms})", remaining_seats=None
                )

        # Group Restrictions
        if activity.group_id:
            group = db.query(models.ActivityGroup).filter(models.ActivityGroup.id == activity.group_id).first()
            if group:
                if group.allowed_classrooms:
                    allowed = [c.strip() for c in group.allowed_classrooms.split(",") if c.strip()]
                    if member.classroom not in allowed:
                        return schemas.MessageResponse(
                            success=False, message=f"กลุ่มกิจกรรม '{group.name}' เฉพาะนักเรียนห้อง {group.allowed_classrooms} เท่านั้น", remaining_seats=None
                        )
                
                # Quota Check
                count_in_group = (
                    db.query(models.Registration)
                    .join(models.Activity)
                    .filter(
                        models.Registration.student_id == member.id,
                        models.Activity.group_id == activity.group_id
                    )
                    .count()
                )
                if count_in_group >= group.quota:
                    return schemas.MessageResponse(
                        success=False,
                        message=f"นักเรียน {member.name} ลงทะเบียนในกลุ่ม '{group.name}' ครบ {group.quota} กิจกรรมแล้ว",
                        remaining_seats=None,
                    )
        else:
            # Ungrouped Limit (3)
            count_ungrouped = (
                db.query(models.Registration)
                .join(models.Activity)
                .filter(
                    models.Registration.student_id == member.id,
                    models.Activity.group_id == None
                )
                .count()
            )
            if count_ungrouped >= 3:
                return schemas.MessageResponse(
                    success=False,
                    message=f"นักเรียน {member.name} ลงทะเบียนครบ 3 กิจกรรมทั่วไปแล้ว",
                    remaining_seats=None,
                )

    # 6. Commit Registrations
    team_name_val = payload.team_name if (activity.type == "team" and payload.team_name) else None
    
    for member in members:
        reg = models.Registration(student_id=member.id, activity_id=activity.id, team_name=team_name_val)
        db.add(reg)

    db.commit()

    # Log action
    try:
        details = f"Registered for '{activity.title}'"
        if len(members) > 1:
            details += f" with {len(members)-1} partners (Team: {team_name_val})"
        log_action(db, f"Student: {student.number}", "REGISTER", details, request)
    except Exception as e:
        print(f"Public log failed: {e}")

    remaining = activity.max_people - (registered_count + len(members))
    return schemas.MessageResponse(
        success=True, message="ลงทะเบียนสำเร็จ!", remaining_seats=max(remaining, 0)
    )


@router.get("/my_registrations", response_model=List[schemas.Registration])
def get_my_registrations(number: str, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.number == number).first()
    if not student:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลนักเรียน")
    
    return student.registrations


@router.post("/cancel_registration", response_model=schemas.MessageResponse)
def cancel_registration(payload: schemas.CancelRequest, request: Request, db: Session = Depends(get_db)):
    # 1. Verify Student
    student = db.query(models.Student).filter(models.Student.number == payload.number).first()
    if not student:
        return schemas.MessageResponse(success=False, message="ไม่พบข้อมูลนักเรียน", remaining_seats=None)

    # 2. Find Registration
    reg = (
        db.query(models.Registration)
        .filter(
            models.Registration.student_id == student.id,
            models.Registration.activity_id == payload.activity_id
        )
        .first()
    )
    if not reg:
        return schemas.MessageResponse(success=False, message="ไม่พบข้อมูลการลงทะเบียนรายการนี้", remaining_seats=None)

    # 3. Check Activity Status (Can only cancel if open?)
    # Valid question: Should they be able to cancel if closed? 
    # Usually NO, because replacements can't register.
    # But usually YES if it's far in advance. 
    # For now, let's allow cancellation ONLY if activity is still OPEN or it's not yet started.
    # Simple rule: If activity status is 'close', cannot cancel.
    
    activity = reg.activity
    if activity.status == "close":
         return schemas.MessageResponse(success=False, message="กิจกรรมปิดแล้ว ไม่สามารถยกเลิกได้", remaining_seats=None)
    
    # 4. Delete
    db.delete(reg)
    db.commit()
    
    # Log
    try:
        log_action(db, f"Student: {student.number}", "CANCEL", f"Cancelled '{activity.title}'", request)
    except:
        pass
        
    # Get remaining seats
    count = db.query(models.Registration).filter(models.Registration.activity_id == activity.id).count()
    remaining = max(activity.max_people - count, 0)
    
    return schemas.MessageResponse(
        success=True, message="ยกเลิกการลงทะเบียนสำเร็จ", remaining_seats=remaining
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


