from sqlalchemy import Column, String, Integer, Boolean, DateTime, Float, Text, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base

class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=True)  # For removal service compatibility
    role = Column(String, default="admin")
    status = Column(String, default="pending")  # pending, active
    email_verification_token = Column(String, nullable=True)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    admin_details = relationship("AdminDetails", back_populates="admin_user", uselist=False)
    students = relationship("Student", back_populates="admin")
    seat_bookings = relationship("SeatBooking", back_populates="admin")
    student_messages = relationship("StudentMessage", back_populates="admin")
    student_notifications = relationship("StudentNotification", back_populates="admin")
    student_removal_requests = relationship("StudentRemovalRequest", foreign_keys="StudentRemovalRequest.admin_id", back_populates="admin")

class AdminDetails(Base):
    __tablename__ = "admin_details"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.user_id"), nullable=False)
    admin_name = Column(String, nullable=False)
    library_name = Column(String, nullable=False)
    mobile_no = Column(String(10), nullable=False)
    address = Column(Text, nullable=False)
    total_seats = Column(Integer, nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    has_shift_system = Column(Boolean, default=False)
    shift_timings = Column(ARRAY(String))
    referral_code = Column(String, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    admin_user = relationship("AdminUser", back_populates="admin_details")
