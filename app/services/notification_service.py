from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID
import logging

from app.models.student import Student, StudentTask, StudentExam, StudentNotification
from app.models.admin import AdminUser
from app.schemas.notification import NotificationCreate, TaskReminderCreate, ExamReminderCreate

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_task_reminders(self, task: StudentTask, reminder_times: List[str] = None) -> List[StudentNotification]:
        """Create automatic reminders for a task"""
        if reminder_times is None:
            reminder_times = ["1_hour", "1_day"]
        
        notifications = []
        for reminder_time in reminder_times:
            scheduled_time = self._calculate_reminder_time(task.due_date, reminder_time)
            if scheduled_time and scheduled_time > datetime.now():
                notification = self._create_notification(
                    student_id=task.student_id,
                    admin_id=task.student.admin_id,
                    title=f"Task Reminder: {task.title}",
                    message=f"Your task '{task.title}' is due {self._get_time_description(reminder_time)}.",
                    notification_type="task_reminder",
                    priority=self._get_priority_from_reminder_time(reminder_time),
                    scheduled_for=scheduled_time,
                    related_task_id=task.id
                )
                notifications.append(notification)
        
        return notifications
    
    def create_exam_reminders(self, exam: StudentExam, reminder_times: List[str] = None) -> List[StudentNotification]:
        """Create automatic reminders for an exam"""
        if reminder_times is None:
            reminder_times = ["1_day", "1_week"]
        
        notifications = []
        for reminder_time in reminder_times:
            scheduled_time = self._calculate_reminder_time(exam.exam_date, reminder_time)
            if scheduled_time and scheduled_time > datetime.now():
                notification = self._create_notification(
                    student_id=exam.student_id,
                    admin_id=exam.student.admin_id,
                    title=f"Exam Reminder: {exam.exam_name}",
                    message=f"Your exam '{exam.exam_name}' is scheduled {self._get_time_description(reminder_time)}.",
                    notification_type="exam_reminder",
                    priority=self._get_priority_from_reminder_time(reminder_time),
                    scheduled_for=scheduled_time,
                    related_exam_id=exam.id
                )
                notifications.append(notification)
        
        return notifications
    
    def create_general_notification(
        self, 
        student_id: UUID, 
        admin_id: UUID, 
        title: str, 
        message: str, 
        priority: str = "medium",
        scheduled_for: Optional[datetime] = None
    ) -> StudentNotification:
        """Create a general notification"""
        if scheduled_for is None:
            scheduled_for = datetime.now()
        
        return self._create_notification(
            student_id=student_id,
            admin_id=admin_id,
            title=title,
            message=message,
            notification_type="general",
            priority=priority,
            scheduled_for=scheduled_for
        )
    
    def create_system_notification(
        self, 
        student_id: UUID, 
        admin_id: UUID, 
        title: str, 
        message: str, 
        priority: str = "medium"
    ) -> StudentNotification:
        """Create a system notification (sent immediately)"""
        return self._create_notification(
            student_id=student_id,
            admin_id=admin_id,
            title=title,
            message=message,
            notification_type="system",
            priority=priority,
            scheduled_for=datetime.now()
        )
    
    def get_pending_notifications(self, limit: int = 100) -> List[StudentNotification]:
        """Get notifications that are ready to be sent"""
        return self.db.query(StudentNotification).filter(
            StudentNotification.scheduled_for <= datetime.now(),
            StudentNotification.sent_at.is_(None)
        ).limit(limit).all()
    
    def mark_notification_sent(self, notification_id: UUID) -> bool:
        """Mark a notification as sent"""
        notification = self.db.query(StudentNotification).filter(
            StudentNotification.id == notification_id
        ).first()
        
        if notification:
            notification.sent_at = datetime.now()
            self.db.commit()
            return True
        return False
    
    def get_student_notifications(
        self, 
        student_id: UUID, 
        skip: int = 0, 
        limit: int = 50,
        notification_type: Optional[str] = None,
        unread_only: bool = False
    ) -> List[StudentNotification]:
        """Get notifications for a specific student"""
        query = self.db.query(StudentNotification).filter(
            StudentNotification.student_id == student_id
        )
        
        if notification_type:
            query = query.filter(StudentNotification.notification_type == notification_type)
        
        if unread_only:
            query = query.filter(StudentNotification.read == False)
        
        return query.order_by(StudentNotification.created_at.desc()).offset(skip).limit(limit).all()
    
    def mark_notification_read(self, notification_id: UUID, student_id: UUID) -> bool:
        """Mark a notification as read by a student"""
        notification = self.db.query(StudentNotification).filter(
            StudentNotification.id == notification_id,
            StudentNotification.student_id == student_id
        ).first()
        
        if notification:
            notification.read = True
            self.db.commit()
            return True
        return False
    
    def mark_all_notifications_read(self, student_id: UUID) -> int:
        """Mark all notifications as read for a student"""
        updated = self.db.query(StudentNotification).filter(
            StudentNotification.student_id == student_id,
            StudentNotification.read == False
        ).update({"read": True})
        
        self.db.commit()
        return updated
    
    def get_unread_count(self, student_id: UUID) -> int:
        """Get count of unread notifications for a student"""
        return self.db.query(StudentNotification).filter(
            StudentNotification.student_id == student_id,
            StudentNotification.read == False
        ).count()
    
    def _create_notification(
        self,
        student_id: UUID,
        admin_id: UUID,
        title: str,
        message: str,
        notification_type: str,
        priority: str,
        scheduled_for: datetime,
        related_task_id: Optional[UUID] = None,
        related_exam_id: Optional[UUID] = None
    ) -> StudentNotification:
        """Create a notification record"""
        notification = StudentNotification(
            student_id=student_id,
            admin_id=admin_id,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            scheduled_for=scheduled_for,
            related_task_id=related_task_id,
            related_exam_id=related_exam_id
        )
        
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        
        return notification
    
    def _calculate_reminder_time(self, due_date: datetime, reminder_time: str) -> Optional[datetime]:
        """Calculate when to send a reminder based on the due date and reminder time"""
        if not due_date:
            return None
        
        time_mapping = {
            "1_hour": timedelta(hours=1),
            "6_hours": timedelta(hours=6),
            "1_day": timedelta(days=1),
            "3_days": timedelta(days=3),
            "1_week": timedelta(weeks=1),
            "2_weeks": timedelta(weeks=2)
        }
        
        if reminder_time in time_mapping:
            return due_date - time_mapping[reminder_time]
        
        return None
    
    def _get_time_description(self, reminder_time: str) -> str:
        """Get human-readable description of reminder time"""
        descriptions = {
            "1_hour": "in 1 hour",
            "6_hours": "in 6 hours",
            "1_day": "tomorrow",
            "3_days": "in 3 days",
            "1_week": "in 1 week",
            "2_weeks": "in 2 weeks"
        }
        
        return descriptions.get(reminder_time, f"in {reminder_time}")
    
    def _get_priority_from_reminder_time(self, reminder_time: str) -> str:
        """Get priority based on how close the reminder is to the due date"""
        urgent_times = ["1_hour", "6_hours"]
        high_times = ["1_day"]
        medium_times = ["3_days", "1_week"]
        
        if reminder_time in urgent_times:
            return "urgent"
        elif reminder_time in high_times:
            return "high"
        elif reminder_time in medium_times:
            return "medium"
        else:
            return "low"
