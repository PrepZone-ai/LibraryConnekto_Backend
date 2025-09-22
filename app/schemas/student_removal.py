from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum

class RemovalRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class StudentRemovalRequestCreate(BaseModel):
    student_id: UUID
    admin_id: UUID
    reason: str = "Subscription expired and payment not received within 2 days"
    subscription_end_date: datetime
    days_overdue: str

class StudentRemovalRequestResponse(BaseModel):
    id: UUID
    student_id: UUID
    admin_id: UUID
    reason: str
    status: RemovalRequestStatus
    subscription_end_date: datetime
    days_overdue: str
    admin_notes: Optional[str] = None
    processed_by: Optional[UUID] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Student details
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    student_phone: Optional[str] = None
    
    # Admin details
    admin_name: Optional[str] = None
    library_name: Optional[str] = None

class StudentRemovalRequestUpdate(BaseModel):
    status: RemovalRequestStatus
    admin_notes: Optional[str] = None

class StudentRemovalRequestList(BaseModel):
    requests: List[StudentRemovalRequestResponse]
    total: int
    pending_count: int
    approved_count: int
    rejected_count: int

class StudentRemovalStats(BaseModel):
    total_requests: int
    pending_requests: int
    approved_requests: int
    rejected_requests: int
    overdue_students: int
