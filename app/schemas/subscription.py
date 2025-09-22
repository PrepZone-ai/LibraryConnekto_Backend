from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal
from uuid import UUID

class SubscriptionPlanBase(BaseModel):
    library_id: UUID
    months: int
    amount: Decimal
    discounted_amount: Optional[Decimal] = None
    is_custom: bool = False
    is_active: bool = True

class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass

class SubscriptionPlanUpdate(BaseModel):
    library_id: Optional[UUID] = None
    months: Optional[int] = None
    amount: Optional[Decimal] = None
    discounted_amount: Optional[Decimal] = None
    is_custom: Optional[bool] = None
    is_active: Optional[bool] = None

class SubscriptionPlanResponse(SubscriptionPlanBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
