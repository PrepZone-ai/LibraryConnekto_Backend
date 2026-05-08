from app.database import Base

# Import all models here to ensure they are registered with SQLAlchemy
from .admin import AdminUser, AdminDetails
from .student import Student, StudentAttendance, StudentMessage, StudentTask, StudentExam
from .booking import SeatBooking
from .library_freed_seat import LibraryFreedSeat
from .referral import ReferralCode, Referral
from .subscription import SubscriptionPlan
from .email_delivery_log import EmailDeliveryLog
from .qr_transfer import StudentQRToken, StudentTransferRequest
from app.database import Base

__all__ = [
    "Base",
    "AdminUser",
    "AdminDetails", 
    "Student",
    "StudentAttendance",
    "StudentMessage",
    "StudentTask",
    "StudentExam",
    "SeatBooking",
    "LibraryFreedSeat",
    "ReferralCode",
    "Referral",
    "SubscriptionPlan",
    "EmailDeliveryLog",
    "StudentQRToken",
    "StudentTransferRequest",
]
