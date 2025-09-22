from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base

class ReferralCode(Base):
    __tablename__ = "referral_codes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)  # Can be admin or student user_id
    user_type = Column(String, nullable=False)  # admin, student
    code = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)  # admin, student
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    referrals = relationship("Referral", back_populates="referral_code")

class Referral(Base):
    __tablename__ = "referrals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referral_code_id = Column(UUID(as_uuid=True), ForeignKey("referral_codes.id"), nullable=False)
    referrer_id = Column(UUID(as_uuid=True), nullable=False)  # Can be admin or student user_id
    referrer_type = Column(String, nullable=False)  # admin, student
    referred_id = Column(UUID(as_uuid=True), nullable=True)  # Will be set when referred user registers
    referred_type = Column(String, nullable=True)  # admin, student
    referred_name = Column(String, nullable=False)
    referred_email = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, completed, expired
    points_awarded = Column(String, default="0")  # Points awarded to referrer
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    referral_code = relationship("ReferralCode", back_populates="referrals")
