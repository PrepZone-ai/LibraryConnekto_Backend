from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base

class RemovalRequestStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class StudentRemovalRequest(Base):
    __tablename__ = "student_removal_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False)
    
    # Request details
    reason = Column(Text, nullable=False, default="Subscription expired and payment not received within 2 days")
    status = Column(Enum(RemovalRequestStatus), default=RemovalRequestStatus.PENDING, nullable=False)
    
    # Subscription details at time of request
    subscription_end_date = Column(DateTime, nullable=False)
    days_overdue = Column(String(50), nullable=False)  # e.g., "3 days overdue"
    
    # Admin action details
    admin_notes = Column(Text, nullable=True)
    processed_by = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    student = relationship("Student", back_populates="removal_requests")
    admin = relationship("AdminUser", foreign_keys=[admin_id], back_populates="student_removal_requests")
    processed_by_admin = relationship("AdminUser", foreign_keys=[processed_by])

# Note: Student and AdminUser relationships are added to existing models
# in their respective files to avoid duplicate class definitions
