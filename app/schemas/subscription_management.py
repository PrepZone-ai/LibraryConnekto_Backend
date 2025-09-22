from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class SubscriptionPlanResponse(BaseModel):
    id: UUID
    plan_name: str
    price: float
    duration_days: int
    features: Optional[str] = None
    is_active: bool
    library_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class SubscriptionPurchase(BaseModel):
    plan_id: UUID
    amount: float
    student_id: UUID

class SubscriptionStatus(BaseModel):
    subscription_status: str
    subscription_end: Optional[datetime] = None
    days_left: int
    is_urgent: bool
    is_expired: bool
    library_name: Optional[str] = None

class ExpiringStudent(BaseModel):
    student_id: str
    student_name: str
    email: str
    subscription_end: datetime
    days_left: int
    is_urgent: bool
