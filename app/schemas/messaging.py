from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class MessageCreate(BaseModel):
    message: str
    image_url: Optional[str] = None

class AdminMessageCreate(MessageCreate):
    student_id: Optional[str] = None  # If None, it's a broadcast message
    is_broadcast: bool = False

class StudentMessageCreate(MessageCreate):
    admin_id: str

class MessageUpdate(BaseModel):
    admin_response: Optional[str] = None
    read: Optional[bool] = None

class MessageResponse(BaseModel):
    id: UUID
    student_id: Optional[UUID] = None
    admin_id: UUID
    message: str
    student_name: Optional[str] = None
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

class BroadcastMessageCreate(BaseModel):
    message: str
    image_url: Optional[str] = None
