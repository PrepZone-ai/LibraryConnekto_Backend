"""FIFO queue of physical seat numbers freed when students leave a library."""
import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class LibraryFreedSeat(Base):
    __tablename__ = "library_freed_seats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    library_id = Column(UUID(as_uuid=True), ForeignKey("admin_details.id"), nullable=False, index=True)
    seat_number = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    library = relationship("AdminDetails", foreign_keys=[library_id])
