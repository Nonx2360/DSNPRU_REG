from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    classroom = Column(String, nullable=True) # e.g. "ม.1/1"
    sequence = Column(Integer, nullable=True) # e.g. 1, 2, 3 (เลขที่)
    
    registrations = relationship("Registration", back_populates="student", cascade="all, delete-orphan")


class ActivityGroup(Base):
    __tablename__ = "activity_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    quota = Column(Integer, default=3)
    allowed_classrooms = Column(String, nullable=True)  # Comma separated classrooms
    is_visible = Column(Boolean, default=True)

    activities = relationship("Activity", back_populates="group", cascade="all, delete-orphan")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    max_people = Column(Integer, nullable=False)
    status = Column(String, default="open")  # open / close
    allowed_classrooms = Column(String, nullable=True)  # Comma separated classrooms
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    color = Column(String, default="#e11d48") # Default rose-600 hex
    
    # New fields for Team Registration
    type = Column(String, default="individual") # individual / team
    max_team_size = Column(Integer, default=1)
    
    group_id = Column(Integer, ForeignKey("activity_groups.id"), nullable=True)

    group = relationship("ActivityGroup", back_populates="activities")
    registrations = relationship("Registration", back_populates="activity", cascade="all, delete-orphan")


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("student_id", "activity_id", name="uq_student_activity"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=False)
    team_name = Column(String, nullable=True) # New field for Team Registration
    status = Column(String, default="registered") # registered / waitlisted
    timestamp = Column(DateTime, default=datetime.now)

    student = relationship("Student", back_populates="registrations")
    activity = relationship("Activity", back_populates="registrations")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_superuser = Column(Boolean, default=False)



class AdminLog(Base):
    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_username = Column(String, index=True, nullable=False)
    action = Column(String, nullable=False)
    details = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.now)

class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_urgent = Column(Boolean, default=False)
    color = Column(String, default="indigo")
    timestamp = Column(DateTime, default=datetime.now)

class RequestLog(Base):
    __tablename__ = "request_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    method = Column(String, nullable=False)
    path = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=False)

class SystemMetric(Base):
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    metric_type = Column(String, index=True) # e.g. "db_size", "db_health", "api_health"
    value = Column(Integer, nullable=True) # numeric value (e.g. size in bytes)
    status = Column(String, nullable=True) # text status (e.g. "up", "down")
