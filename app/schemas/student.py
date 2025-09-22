from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID

class StudentBase(BaseModel):
    name: str
    email: EmailStr
    mobile_no: str
    address: str
    subscription_start: datetime
    subscription_end: datetime
    is_shift_student: bool = False
    shift_time: Optional[str] = None

class StudentCreate(StudentBase):
    password: str
    admin_id: str

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    mobile_no: Optional[str] = None
    address: Optional[str] = None
    subscription_start: Optional[datetime] = None
    subscription_end: Optional[datetime] = None
    subscription_status: Optional[str] = None
    is_shift_student: Optional[bool] = None
    shift_time: Optional[str] = None
    status: Optional[str] = None

class StudentResponse(StudentBase):
    id: UUID
    student_id: str
    auth_user_id: UUID
    admin_id: UUID
    subscription_status: str
    status: str
    last_visit: Optional[datetime] = None
    profile_image: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    library_name: Optional[str] = None
    library_latitude: Optional[float] = None
    library_longitude: Optional[float] = None
    
    class Config:
        from_attributes = True

class StudentAttendanceCreate(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class StudentAttendanceResponse(BaseModel):
    id: UUID
    student_id: UUID
    admin_id: UUID
    entry_time: datetime
    exit_time: Optional[datetime] = None
    total_duration: Optional[timedelta] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class StudentMessageCreate(BaseModel):
    message: str
    admin_id: str
    image_url: Optional[str] = None

class StudentMessageResponse(BaseModel):
    id: UUID
    student_id: UUID
    admin_id: UUID
    message: str
    student_name: str
    admin_name: Optional[str] = None
    admin_response: Optional[str] = None
    responded_at: Optional[datetime] = None
    read: bool
    sender_type: str
    is_broadcast: bool
    image_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class StudentTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: str = "medium"

class StudentTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

class StudentTaskResponse(BaseModel):
    id: UUID
    student_id: UUID
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    completed: bool
    priority: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class StudentExamCreate(BaseModel):
    exam_name: str
    exam_date: datetime
    notes: Optional[str] = None

class StudentExamUpdate(BaseModel):
    exam_name: Optional[str] = None
    exam_date: Optional[datetime] = None
    notes: Optional[str] = None
    is_completed: Optional[bool] = None

class StudentExamResponse(BaseModel):
    id: UUID
    student_id: UUID
    exam_name: str
    exam_date: datetime
    notes: Optional[str] = None
    is_completed: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
