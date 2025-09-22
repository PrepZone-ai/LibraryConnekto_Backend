from sqlalchemy import Column, String, Integer, DateTime, Float, Text, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base

class SeatBooking(Base):
    __tablename__ = "seat_bookings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.auth_user_id"))
    library_id = Column(UUID(as_uuid=True), ForeignKey("admin_details.id"))
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.user_id"), nullable=False)
    # Anonymous booking fields
    name = Column(String)
    email = Column(String)
    mobile = Column(String)
    address = Column(Text)
    subscription_months = Column(Integer)
    # Student booking fields
    seat_id = Column(String)
    subscription_plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"))
    amount = Column(Numeric(10, 2))
    date = Column(String)
    start_time = Column(String)
    end_time = Column(String)
    purpose = Column(Text)
    # Common fields
    status = Column(String, default="pending")  # pending, approved, rejected, active, paid
    seat_number = Column(String)
    approval_date = Column(DateTime(timezone=True))
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    # Payment fields
    payment_status = Column(String, default="pending")  # pending, paid, failed, refunded
    payment_date = Column(DateTime(timezone=True))
    payment_method = Column(String)  # online, cash, bank_transfer
    payment_reference = Column(String)  # transaction ID or reference
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    student = relationship("Student", back_populates="seat_bookings")
    admin = relationship("AdminUser", back_populates="seat_bookings")
    subscription_plan = relationship("SubscriptionPlan")
