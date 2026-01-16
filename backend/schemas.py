from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StudentBase(BaseModel):
    name: str = Field(..., example="สมชาย ใจดี")
    classroom: Optional[str] = Field(None, example="ม.3/1")
    number: str = Field(..., example="15")


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    classroom: Optional[str] = None
    number: Optional[str] = None


class Student(StudentBase):
    id: int

    model_config = {"from_attributes": True}


class ActivityGroupBase(BaseModel):
    name: str
    quota: int = 3

class ActivityGroupCreate(ActivityGroupBase):
    pass

class ActivityGroup(ActivityGroupBase):
    id: int
    activities: List["Activity"] = []

    model_config = {"from_attributes": True}


class ActivityBase(BaseModel):
    title: str
    description: Optional[str] = None
    max_people: int
    status: str = "open"
    group_id: Optional[int] = None


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    max_people: Optional[int] = None
    status: Optional[str] = None
    group_id: Optional[int] = None


class Activity(ActivityBase):
    id: int
    registered_count: int = 0
    remaining_seats: int = 0
    group_name: Optional[str] = None

    model_config = {"from_attributes": True}


class RegistrationBase(BaseModel):
    student_id: int
    activity_id: int


class RegistrationCreate(BaseModel):
    name: str
    classroom: str
    number: str
    activity_id: int


class Registration(RegistrationBase):
    id: int
    timestamp: datetime
    student: Student

    model_config = {"from_attributes": True}


class AdminBase(BaseModel):
    username: str


class AdminCreate(AdminBase):
    password: str


class Admin(AdminBase):
    id: int
    is_superuser: bool = False

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    success: bool
    message: str
    remaining_seats: Optional[int] = None


class DashboardStats(BaseModel):
    total_students: int
    total_registrations: int
    activities: List[Activity]


class BulkActionIds(BaseModel):
    ids: List[int]


class BulkUpdateClassroom(BaseModel):
    ids: List[int]
    classroom: str


