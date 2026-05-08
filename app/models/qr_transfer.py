from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class StudentQRToken(Base):
    __tablename__ = "student_qr_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    issued_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_scanned_at = Column(DateTime(timezone=True), nullable=True)

    student = relationship("Student", back_populates="qr_tokens")


class StudentTransferRequest(Base):
    __tablename__ = "student_transfer_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    source_admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.user_id"), nullable=False, index=True)
    target_admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.user_id"), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, nullable=False, default="initiated", index=True)
    payment_reference = Column(String, nullable=True)
    payment_link = Column(Text, nullable=True)
    razorpay_order_id = Column(String, nullable=True, index=True)
    razorpay_payment_id = Column(String, nullable=True, index=True)
    payment_verified_at = Column(DateTime(timezone=True), nullable=True)
    initiated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    student = relationship("Student", back_populates="transfer_requests")
