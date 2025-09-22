from sqlalchemy import Column, String, Integer, Boolean, DateTime, Float, Text, ForeignKey, Interval
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base

class Student(Base):
    __tablename__ = "students"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(String, unique=True, nullable=False)  # Custom student ID like LIBR25001
    auth_user_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.user_id"), nullable=False)
    name = Column(String, nullable=False)
    first_name = Column(String, nullable=True)  # For removal service compatibility
    last_name = Column(String, nullable=True)   # For removal service compatibility
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)
    password_reset_token = Column(String, nullable=True)
    mobile_no = Column(String(10), nullable=False)
    address = Column(Text, nullable=False)
    subscription_start = Column(DateTime(timezone=True), nullable=False)
    subscription_end = Column(DateTime(timezone=True), nullable=False)
    subscription_status = Column(String, default="Active")  # Active, Expired, Removed
    is_shift_student = Column(Boolean, default=False)
    shift_time = Column(String)
    status = Column(String, default="Absent")  # Present, Absent
    last_visit = Column(DateTime(timezone=True))
    profile_image = Column(String, nullable=True)  # Path to profile image
    is_active = Column(Boolean, default=True)  # For soft delete
    removed_at = Column(DateTime(timezone=True), nullable=True)  # When student was removed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    admin = relationship("AdminUser", back_populates="students")
    attendance_records = relationship("StudentAttendance", back_populates="student")
    messages = relationship("StudentMessage", back_populates="student")
    tasks = relationship("StudentTask", back_populates="student")
    exams = relationship("StudentExam", back_populates="student")
    notifications = relationship("StudentNotification", back_populates="student")
    seat_bookings = relationship("SeatBooking", back_populates="student")
    removal_requests = relationship("StudentRemovalRequest", back_populates="student")

class StudentAttendance(Base):
    __tablename__ = "student_attendance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.auth_user_id"), nullable=False)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.user_id"), nullable=False)
    entry_time = Column(DateTime(timezone=True), server_default=func.now())
    exit_time = Column(DateTime(timezone=True))
    total_duration = Column(Interval)
    latitude = Column(Float)
    longitude = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    student = relationship("Student", back_populates="attendance_records")

class StudentMessage(Base):
    __tablename__ = "student_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.user_id"), nullable=False)
    message = Column(Text, nullable=False)
    student_name = Column(String, nullable=False)
    admin_name = Column(String)
    admin_response = Column(Text)
    responded_at = Column(DateTime(timezone=True))
    read = Column(Boolean, default=False)
    sender_type = Column(String, nullable=False)  # student, admin
    is_broadcast = Column(Boolean, default=False)
    image_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    student = relationship("Student", back_populates="messages")
    admin = relationship("AdminUser", back_populates="student_messages")

class StudentTask(Base):
    __tablename__ = "student_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    due_date = Column(DateTime(timezone=True))
    completed = Column(Boolean, default=False)
    priority = Column(String, default="medium")  # low, medium, high
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    student = relationship("Student", back_populates="tasks")

class StudentExam(Base):
    __tablename__ = "student_exams"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.auth_user_id"), nullable=False)
    exam_name = Column(String, nullable=False)
    exam_date = Column(DateTime(timezone=True), nullable=False)
    notes = Column(Text)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    student = relationship("Student", back_populates="exams")

class StudentNotification(Base):
    __tablename__ = "student_notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.user_id"), nullable=False)
    
    # Notification details
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String, nullable=False)  # task_reminder, exam_reminder, general, system
    priority = Column(String, default="medium")  # low, medium, high, urgent
    
    # Related entities (optional)
    related_task_id = Column(UUID(as_uuid=True), ForeignKey("student_tasks.id"), nullable=True)
    related_exam_id = Column(UUID(as_uuid=True), ForeignKey("student_exams.id"), nullable=True)
    
    # Notification timing
    scheduled_for = Column(DateTime(timezone=True), nullable=False)  # When to send the notification
    sent_at = Column(DateTime(timezone=True), nullable=True)  # When it was actually sent
    read = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    student = relationship("Student", back_populates="notifications")
    admin = relationship("AdminUser", back_populates="student_notifications")
    related_task = relationship("StudentTask")
    related_exam = relationship("StudentExam")
