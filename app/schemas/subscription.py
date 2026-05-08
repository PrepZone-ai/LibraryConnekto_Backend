from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal
from uuid import UUID


class SubscriptionPlanMutable(BaseModel):
    months: int
    amount: Decimal
    discounted_amount: Optional[Decimal] = None
    is_custom: bool = False
    is_active: bool = True
    is_shift_plan: bool = False
    shift_time: Optional[str] = None


class SubscriptionPlanCreate(SubscriptionPlanMutable):
    """library_id is set by the server from the authenticated admin's library."""


class SubscriptionPlanUpdate(BaseModel):
    months: Optional[int] = None
    amount: Optional[Decimal] = None
    discounted_amount: Optional[Decimal] = None
    is_custom: Optional[bool] = None
    is_active: Optional[bool] = None
    is_shift_plan: Optional[bool] = None
    shift_time: Optional[str] = None


class SubscriptionPlanResponse(SubscriptionPlanMutable):
    id: UUID
    library_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
