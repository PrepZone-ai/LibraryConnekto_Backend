from app.database import Base

# Import all models here to ensure they are registered with SQLAlchemy
from .admin import AdminUser, AdminDetails
from .student import Student, StudentAttendance, StudentMessage, StudentTask, StudentExam
from .booking import SeatBooking
from .referral import ReferralCode, Referral
from .subscription import SubscriptionPlan
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
    "ReferralCode",
    "Referral",
    "SubscriptionPlan"
]
