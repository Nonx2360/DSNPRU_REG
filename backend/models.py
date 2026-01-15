from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    classroom = Column(String, index=True, nullable=True)  # 'class' reserved in Python
    number = Column(String, nullable=False)

    registrations = relationship("Registration", back_populates="student")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    max_people = Column(Integer, nullable=False)
    status = Column(String, default="open")  # open / close

    registrations = relationship("Registration", back_populates="activity")


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("student_id", "activity_id", name="uq_student_activity"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="registrations")
    activity = relationship("Activity", back_populates="registrations")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_superuser = Column(Boolean, default=False)


