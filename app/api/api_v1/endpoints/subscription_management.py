from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.database import get_db
from app.auth.dependencies import get_current_student, get_current_admin
from app.schemas.subscription_management import SubscriptionPlanResponse, SubscriptionPurchase
from app.models.student import Student
from app.models.subscription import SubscriptionPlan
from app.services.subscription_notification_service import SubscriptionNotificationService

router = APIRouter()

@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def get_subscription_plans(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Get available subscription plans for the student's library"""
    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.library_id == current_student.admin_id,
        SubscriptionPlan.is_active == True
    ).all()
    
    return plans

@router.post("/purchase")
async def purchase_subscription(
    purchase_data: SubscriptionPurchase,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Purchase a subscription plan"""
    # Verify plan exists and is active
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == purchase_data.plan_id,
        SubscriptionPlan.library_id == current_student.admin_id,
        SubscriptionPlan.is_active == True
    ).first()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    
    # Calculate new subscription end date
    if current_student.subscription_end and current_student.subscription_end > datetime.now():
        # Extend existing subscription
        new_end_date = current_student.subscription_end + timedelta(days=30)
    else:
        # Start new subscription
        new_end_date = datetime.now() + timedelta(days=30)
    
    # Update student subscription
    current_student.subscription_end = new_end_date
    current_student.subscription_status = "Active"
    
    db.commit()
    db.refresh(current_student)
    
    # Send confirmation notification
    notification_service = SubscriptionNotificationService(db)
    notification_service.notification_service.create_system_notification(
        student_id=current_student.id,
        admin_id=current_student.admin_id,
        title="✅ Subscription Renewed Successfully!",
        message=f"Your {plan.plan_name} subscription has been renewed. Thank you for continuing with us!",
        priority="medium"
    )
    
    return {
        "success": True,
        "message": "Subscription purchased successfully",
        "subscription_end": new_end_date.isoformat(),
        "plan_name": plan.plan_name
    }

@router.get("/status")
async def get_subscription_status(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Get current subscription status with detailed information"""
    today = datetime.now()
    days_left = 0
    
    if current_student.subscription_end:
        days_left = (current_student.subscription_end.date() - today.date()).days
    
    is_urgent = days_left <= 5 and days_left > 0
    is_expired = days_left < 0
    
    return {
        "subscription_status": current_student.subscription_status,
        "subscription_end": current_student.subscription_end.isoformat() if current_student.subscription_end else None,
        "days_left": days_left,
        "is_urgent": is_urgent,
        "is_expired": is_expired,
        "library_name": current_student.library_name if hasattr(current_student, 'library_name') else None
    }

@router.post("/admin/send-warning")
async def send_subscription_warning(
    student_id: str,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Send subscription warning to a specific student (admin only)"""
    # Verify student belongs to admin
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.admin_id == current_admin.user_id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found or not under your administration"
        )
    
    # Calculate days left
    today = datetime.now()
    days_left = 0
    if student.subscription_end:
        days_left = (student.subscription_end.date() - today.date()).days
    
    # Send warning
    notification_service = SubscriptionNotificationService(db)
    warning_results = notification_service.check_and_send_subscription_warnings()
    
    # Find the result for this student
    student_result = next((r for r in warning_results if r['student_id'] == str(student.id)), None)
    
    if student_result:
        return {
            "success": True,
            "message": f"Warning sent to {student.name}",
            "days_left": days_left,
            "notification_sent": student_result.get('notification_sent', False),
            "email_sent": student_result.get('email_sent', False)
        }
    else:
        return {
            "success": False,
            "message": "Failed to send warning",
            "days_left": days_left
        }

@router.get("/admin/expiring")
async def get_expiring_subscriptions(
    days: int = 5,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Get students with expiring subscriptions (admin only)"""
    today = datetime.now().date()
    warning_date = today + timedelta(days=days)
    
    students = db.query(Student).filter(
        Student.admin_id == current_admin.user_id,
        Student.subscription_end <= warning_date,
        Student.subscription_end >= today,
        Student.subscription_status == 'Active'
    ).all()
    
    expiring_students = []
    for student in students:
        days_left = (student.subscription_end.date() - today).days
        expiring_students.append({
            "student_id": str(student.id),
            "student_name": student.name,
            "email": student.email,
            "subscription_end": student.subscription_end.isoformat(),
            "days_left": days_left,
            "is_urgent": days_left <= 5
        })
    
    return {
        "expiring_students": expiring_students,
        "total_count": len(expiring_students),
        "urgent_count": len([s for s in expiring_students if s['is_urgent']])
    }
