from pydantic import BaseModel, EmailStr
from typing import Optional, Dict
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class SeatBookingBase(BaseModel):
    name: str
    email: EmailStr
    mobile: str
    address: str
    subscription_months: int
    amount: Decimal

class SeatBookingCreate(SeatBookingBase):
    library_id: str

class StudentSeatBookingCreate(BaseModel):
    library_id: str
    seat_id: Optional[str] = None
    subscription_plan_id: Optional[str] = None
    amount: Optional[Decimal] = None
    date: str
    start_time: str
    end_time: str
    purpose: Optional[str] = None

class SeatBookingUpdate(BaseModel):
    status: Optional[str] = None
    seat_number: Optional[str] = None
    approval_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    payment_status: Optional[str] = None
    payment_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None

class PaymentConfirmation(BaseModel):
    booking_id: str
    payment_method: str
    payment_reference: Optional[str] = None
    amount: Optional[Decimal] = None

class RazorpayOrderCreate(BaseModel):
    booking_id: str
    amount: int  # Amount in paise
    currency: str = "INR"
    notes: Optional[Dict[str, str]] = None

class RazorpayOrderResponse(BaseModel):
    id: str
    amount: int
    currency: str
    receipt: str
    status: str
    created_at: int
    notes: Optional[Dict[str, str]] = None

class RazorpayPaymentVerify(BaseModel):
    booking_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class SeatBookingResponse(SeatBookingBase):
    id: UUID
    student_id: Optional[UUID] = None
    library_id: UUID
    admin_id: UUID
    status: str
    seat_number: Optional[str] = None
    approval_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    payment_status: Optional[str] = None
    payment_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    email_sent: Optional[bool] = None  # New field to indicate if email was sent
    email_status: Optional[str] = None  # New field for email status message
    
    class Config:
        from_attributes = True

class LibraryInfo(BaseModel):
    id: UUID
    user_id: str
    library_name: str
    address: str
    total_seats: int
    occupied_seats: int = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance: Optional[float] = None
    
    class Config:
        from_attributes = True
