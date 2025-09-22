from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class NotificationCreate(BaseModel):
    title: str
    message: str
    notification_type: str  # task_reminder, exam_reminder, general, system
    priority: str = "medium"  # low, medium, high, urgent
    scheduled_for: datetime
    related_task_id: Optional[UUID] = None
    related_exam_id: Optional[UUID] = None

class NotificationUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    priority: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    read: Optional[bool] = None

class NotificationResponse(BaseModel):
    id: UUID
    student_id: UUID
    admin_id: UUID
    title: str
    message: str
    notification_type: str
    priority: str
    related_task_id: Optional[UUID] = None
    related_exam_id: Optional[UUID] = None
    scheduled_for: datetime
    sent_at: Optional[datetime] = None
    read: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class TaskReminderCreate(BaseModel):
    """Schema for creating task reminders with automatic scheduling"""
    task_id: UUID
    reminder_times: list[str] = ["1_hour", "1_day"]  # 1_hour, 6_hours, 1_day, 3_days, 1_week

class ExamReminderCreate(BaseModel):
    """Schema for creating exam reminders with automatic scheduling"""
    exam_id: UUID
    reminder_times: list[str] = ["1_day", "1_week"]  # 1_hour, 6_hours, 1_day, 3_days, 1_week, 2_weeks

class NotificationSettings(BaseModel):
    """Schema for student notification preferences"""
    task_reminders_enabled: bool = True
    exam_reminders_enabled: bool = True
    task_reminder_times: list[str] = ["1_hour", "1_day"]
    exam_reminder_times: list[str] = ["1_day", "1_week"]
    general_notifications_enabled: bool = True
    system_notifications_enabled: bool = True

class NotificationSettingsUpdate(BaseModel):
    task_reminders_enabled: Optional[bool] = None
    exam_reminders_enabled: Optional[bool] = None
    task_reminder_times: Optional[list[str]] = None
    exam_reminder_times: Optional[list[str]] = None
    general_notifications_enabled: Optional[bool] = None
    system_notifications_enabled: Optional[bool] = None
