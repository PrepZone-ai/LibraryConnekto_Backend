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
    bank_account_holder_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    bank_branch_name: Optional[str] = None
    razorpay_linked_account_id: Optional[str] = None

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
    bank_account_holder_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    bank_branch_name: Optional[str] = None
    razorpay_linked_account_id: Optional[str] = None

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
    """Stable response shape for GET /admin/analytics/dashboard."""

    library_stats: LibraryStats
    recent_messages: int
    monthly_revenue: float
    growth_percentage: float


# --- Analytics trends (stable response shapes for frontend caching) ---


class AttendanceTrendDay(BaseModel):
    """Single day in attendance trends."""

    date: str  # ISO date YYYY-MM-DD
    count: int


class RevenueTrendMonth(BaseModel):
    """Single month in revenue trends."""

    month: str  # YYYY-MM
    revenue: float


# --- List endpoint response models ---


class AdminAttendanceRecord(BaseModel):
    """Single attendance record in admin attendance list."""

    id: str
    student_id: str
    student_name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    total_duration: Optional[str] = None
    status: str  # "Present" | "Completed"


class StudentAttendanceRecordDetail(BaseModel):
    """Nested student summary in attendance record detail."""

    student_id: str
    name: str
    email: str


class AdminStudentAttendanceRecord(BaseModel):
    """Single record for GET /admin/students/{student_id}/attendance."""

    id: str
    student_id: str
    student_name: str
    email: str
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    total_duration: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: Optional[datetime] = None
    student: StudentAttendanceRecordDetail


class AdminRevenueItem(BaseModel):
    """Single revenue/transaction item for GET /admin/revenue."""

    id: str
    student_id: Optional[str] = None
    student_name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    amount: float
    subscription_months: int = 1
    payment_method: str = "Online"
    payment_status: str = "paid"
    transaction_id: str
    created_at: Optional[datetime] = None
    payment_date: Optional[datetime] = None
    status: str
    revenue_source: Optional[str] = None
    purpose: Optional[str] = None


class AdminActivityItem(BaseModel):
    """Single activity item for GET /admin/recent-activities."""

    id: str
    type: str
    title: str
    description: str
    timestamp: datetime
    icon: Optional[str] = None
    color: Optional[str] = None


class AdminStudentSubscriptionExtend(BaseModel):
    """Admin extends a student subscription (e.g. cash at desk); records paid SeatBooking for revenue."""

    plan_id: UUID
    amount: Optional[float] = None
