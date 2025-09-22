from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class AdminDetailsBase(BaseModel):
    admin_name: str
    library_name: str
    mobile_no: str
    address: str
    total_seats: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    has_shift_system: bool = False
    shift_timings: Optional[List[str]] = None

class AdminDetailsCreate(AdminDetailsBase):
    referral_code: Optional[str] = None
    # user_id will be taken from authentication token

class AdminDetailsUpdate(BaseModel):
    admin_name: Optional[str] = None
    library_name: Optional[str] = None
    mobile_no: Optional[str] = None
    address: Optional[str] = None
    total_seats: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    has_shift_system: Optional[bool] = None
    shift_timings: Optional[List[str]] = None
    referral_code: Optional[str] = None

class AdminDetailsResponse(AdminDetailsBase):
    id: UUID
    user_id: UUID
    referral_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_complete: bool = False

    class Config:
        from_attributes = True

class AdminUserResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    role: str
    status: str
    created_at: datetime
    admin_details: Optional[AdminDetailsResponse] = None

    class Config:
        from_attributes = True

class LibraryStats(BaseModel):
    total_students: int
    present_students: int
    total_seats: int
    available_seats: int
    pending_bookings: int
    total_revenue: float

class DashboardStats(BaseModel):
    library_stats: LibraryStats
    recent_messages: int
    monthly_revenue: float
    growth_percentage: float
