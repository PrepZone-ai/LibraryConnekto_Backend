from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.auth.dependencies import get_current_student, get_current_admin
from app.schemas.notification import (
    NotificationCreate, NotificationUpdate, NotificationResponse,
    TaskReminderCreate, ExamReminderCreate, NotificationSettings, NotificationSettingsUpdate
)
from app.models.student import Student, StudentTask, StudentExam, StudentNotification
from app.models.admin import AdminUser
from app.services.notification_service import NotificationService

router = APIRouter()

@router.get("/", response_model=List[NotificationResponse])
async def get_student_notifications(
    skip: int = 0,
    limit: int = 50,
    notification_type: Optional[str] = Query(None, description="Filter by notification type"),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Get notifications for the current student"""
    notification_service = NotificationService(db)
    notifications = notification_service.get_student_notifications(
        student_id=current_student.id,
        skip=skip,
        limit=limit,
        notification_type=notification_type,
        unread_only=unread_only
    )
    
    return notifications

@router.get("/unread-count")
async def get_unread_notification_count(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Get count of unread notifications for the current student"""
    notification_service = NotificationService(db)
    count = notification_service.get_unread_count(current_student.id)
    
    return {"unread_count": count}

@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Mark a specific notification as read"""
    notification_service = NotificationService(db)
    success = notification_service.mark_notification_read(notification_id, current_student.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"message": "Notification marked as read"}

@router.put("/mark-all-read")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Mark all notifications as read for the current student"""
    notification_service = NotificationService(db)
    updated_count = notification_service.mark_all_notifications_read(current_student.id)
    
    return {"message": f"Marked {updated_count} notifications as read"}

@router.post("/task-reminders", response_model=List[NotificationResponse])
async def create_task_reminders(
    reminder_data: TaskReminderCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Create reminders for a specific task"""
    # Verify task belongs to student
    task = db.query(StudentTask).filter(
        StudentTask.id == reminder_data.task_id,
        StudentTask.student_id == current_student.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    notification_service = NotificationService(db)
    notifications = notification_service.create_task_reminders(task, reminder_data.reminder_times)
    
    return notifications

@router.post("/exam-reminders", response_model=List[NotificationResponse])
async def create_exam_reminders(
    reminder_data: ExamReminderCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Create reminders for a specific exam"""
    # Verify exam belongs to student
    exam = db.query(StudentExam).filter(
        StudentExam.id == reminder_data.exam_id,
        StudentExam.student_id == current_student.auth_user_id
    ).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    notification_service = NotificationService(db)
    notifications = notification_service.create_exam_reminders(exam, reminder_data.reminder_times)
    
    return notifications

# Admin endpoints
@router.post("/admin/send", response_model=NotificationResponse)
async def send_admin_notification(
    notification_data: NotificationCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Send a notification to a specific student (admin only)"""
    # Verify student exists and belongs to admin
    student = db.query(Student).filter(
        Student.id == notification_data.student_id,
        Student.admin_id == current_admin.user_id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found or not under your administration"
        )
    
    notification_service = NotificationService(db)
    notification = notification_service.create_general_notification(
        student_id=notification_data.student_id,
        admin_id=current_admin.user_id,
        title=notification_data.title,
        message=notification_data.message,
        priority=notification_data.priority,
        scheduled_for=notification_data.scheduled_for
    )
    
    return notification

@router.post("/admin/broadcast", response_model=List[NotificationResponse])
async def send_broadcast_notification(
    notification_data: NotificationCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Send a notification to all students under admin (admin only)"""
    # Get all students under this admin
    students = db.query(Student).filter(Student.admin_id == current_admin.user_id).all()
    
    if not students:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No students found under your administration"
        )
    
    notification_service = NotificationService(db)
    notifications = []
    
    for student in students:
        notification = notification_service.create_general_notification(
            student_id=student.id,
            admin_id=current_admin.user_id,
            title=notification_data.title,
            message=notification_data.message,
            priority=notification_data.priority,
            scheduled_for=notification_data.scheduled_for
        )
        notifications.append(notification)
    
    return notifications

@router.get("/admin/pending", response_model=List[NotificationResponse])
async def get_pending_notifications(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get pending notifications that need to be sent (admin only)"""
    notification_service = NotificationService(db)
    notifications = notification_service.get_pending_notifications(limit)
    
    # Filter to only show notifications from this admin's students
    admin_student_ids = [s.id for s in db.query(Student).filter(Student.admin_id == current_admin.user_id).all()]
    filtered_notifications = [n for n in notifications if n.student_id in admin_student_ids]
    
    return filtered_notifications

@router.put("/admin/{notification_id}/sent")
async def mark_notification_sent(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Mark a notification as sent (admin only)"""
    # Verify notification belongs to admin's students
    notification = db.query(StudentNotification).join(Student).filter(
        StudentNotification.id == notification_id,
        Student.admin_id == current_admin.user_id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or not under your administration"
        )
    
    notification_service = NotificationService(db)
    success = notification_service.mark_notification_sent(notification_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as sent"
        )
    
    return {"message": "Notification marked as sent"}
