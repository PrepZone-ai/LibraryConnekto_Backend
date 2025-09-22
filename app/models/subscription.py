from sqlalchemy import Column, String, Integer, DateTime, Float, Text, Boolean, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    library_id = Column(UUID(as_uuid=True), ForeignKey("admin_details.id"), nullable=False)
    months = Column(Integer, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    discounted_amount = Column(Numeric(10, 2))
    is_custom = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
