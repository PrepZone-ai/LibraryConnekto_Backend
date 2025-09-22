from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class ReferralCodeBase(BaseModel):
    type: str  # admin, student

class ReferralCodeCreate(ReferralCodeBase):
    name: Optional[str] = None  # For admin referral codes
    library_name: Optional[str] = None  # For admin referral codes

class ReferralCodeResponse(ReferralCodeBase):
    id: UUID
    user_id: UUID
    user_type: str
    code: str
    created_at: datetime

    class Config:
        from_attributes = True

class ReferralBase(BaseModel):
    referred_name: str
    referred_email: Optional[str] = None
    status: str = "pending"  # pending, completed, expired
    points_awarded: str = "0"
    notes: Optional[str] = None

class ReferralCreate(ReferralBase):
    referral_code_id: UUID
    referrer_id: UUID
    referrer_type: str

class ReferralUpdate(BaseModel):
    status: Optional[str] = None
    referred_id: Optional[UUID] = None
    referred_type: Optional[str] = None
    points_awarded: Optional[str] = None
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None

class ReferralResponse(ReferralBase):
    id: UUID
    referral_code_id: UUID
    referrer_id: UUID
    referrer_type: str
    referred_id: Optional[UUID] = None
    referred_type: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ReferralValidationRequest(BaseModel):
    code: str

class ReferralValidationResponse(BaseModel):
    success: bool
    message: str
    referral_code: Optional[ReferralCodeResponse] = None
    referrer_name: Optional[str] = None
    referrer_type: Optional[str] = None