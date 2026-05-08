from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.database import get_db
from app.auth.dependencies import get_current_student, get_current_admin
from app.schemas.subscription_management import SubscriptionPurchase
from app.schemas.subscription import SubscriptionPlanResponse
from app.models.student import Student
from app.models.subscription import SubscriptionPlan
from app.models.admin import AdminDetails
from app.services.subscription_notification_service import SubscriptionNotificationService
from app.utils.subscription_plan_scope import (
    admin_details_id_for_user,
    apply_plan_shift_filters,
)

router = APIRouter()


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def get_subscription_plans(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    """Get subscription plans for the student's library (respects shift vs non-shift)."""
    lib_id = admin_details_id_for_user(db, current_student.admin_id)
    if not lib_id:
        raise HTTPException(status_code=404, detail="Library not found for this account")

    library = db.query(AdminDetails).filter(AdminDetails.id == lib_id).first()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    query = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.library_id == lib_id,
        SubscriptionPlan.is_active == True,
    )
    query = apply_plan_shift_filters(
        query,
        library,
        is_shift_student=current_student.is_shift_student,
        shift_time=current_student.shift_time,
    )
    return query.all()


@router.post("/purchase")
async def purchase_subscription(
    purchase_data: SubscriptionPurchase,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    """Purchase a subscription plan"""
    lib_id = admin_details_id_for_user(db, current_student.admin_id)
    if not lib_id:
        raise HTTPException(status_code=404, detail="Library not found for this account")

    library = db.query(AdminDetails).filter(AdminDetails.id == lib_id).first()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    plan = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.id == purchase_data.plan_id,
            SubscriptionPlan.library_id == lib_id,
            SubscriptionPlan.is_active == True,
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found",
        )

    visible = apply_plan_shift_filters(
        db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan.id),
        library,
        is_shift_student=current_student.is_shift_student,
        shift_time=current_student.shift_time,
    ).first()
    if not visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This plan is not available for your shift enrollment type",
        )

    if current_student.subscription_end and current_student.subscription_end > datetime.now():
        new_end_date = current_student.subscription_end + timedelta(days=30)
    else:
        new_end_date = datetime.now() + timedelta(days=30)

    current_student.subscription_end = new_end_date
    current_student.subscription_status = "Active"

    db.commit()
    db.refresh(current_student)

    notification_service = SubscriptionNotificationService(db)
    notification_service.notification_service.create_system_notification(
        student_id=current_student.id,
        admin_id=current_student.admin_id,
        title="✅ Subscription Renewed Successfully!",
        message=f"Your {plan.months}-month subscription has been renewed. Thank you for continuing with us!",
        priority="medium",
    )

    return {
        "success": True,
        "message": "Subscription purchased successfully",
        "subscription_end": new_end_date.isoformat(),
        "plan_name": f"{plan.months} month(s)",
    }


@router.get("/status")
async def get_subscription_status(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
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
        "subscription_end": current_student.subscription_end.isoformat()
        if current_student.subscription_end
        else None,
        "days_left": days_left,
        "is_urgent": is_urgent,
        "is_expired": is_expired,
        "library_name": current_student.library_name
        if hasattr(current_student, "library_name")
        else None,
    }


@router.post("/admin/send-warning")
async def send_subscription_warning(
    student_id: str,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """Send subscription warning to a specific student (admin only)"""
    student = (
        db.query(Student)
        .filter(
            Student.id == student_id,
            Student.admin_id == current_admin.user_id,
        )
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found or not under your administration",
        )

    today = datetime.now()
    days_left = 0
    if student.subscription_end:
        days_left = (student.subscription_end.date() - today.date()).days

    notification_service = SubscriptionNotificationService(db)
    warning_results = notification_service.check_and_send_subscription_warnings()

    student_result = next(
        (r for r in warning_results if r["student_id"] == str(student.id)), None
    )

    if student_result:
        return {
            "success": True,
            "message": f"Warning sent to {student.name}",
            "days_left": days_left,
            "notification_sent": student_result.get("notification_sent", False),
            "email_sent": student_result.get("email_sent", False),
        }
    else:
        return {
            "success": False,
            "message": "Failed to send warning",
            "days_left": days_left,
        }


@router.get("/admin/expiring")
async def get_expiring_subscriptions(
    days: int = 5,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """Get students with expiring subscriptions (admin only)"""
    today = datetime.now().date()
    warning_date = today + timedelta(days=days)

    students = (
        db.query(Student)
        .filter(
            Student.admin_id == current_admin.user_id,
            Student.subscription_end <= warning_date,
            Student.subscription_end >= today,
            Student.subscription_status == "Active",
        )
        .all()
    )

    expiring_students = []
    for student in students:
        days_left = (student.subscription_end.date() - today).days
        expiring_students.append(
            {
                "student_id": str(student.id),
                "student_name": student.name,
                "email": student.email,
                "subscription_end": student.subscription_end.isoformat(),
                "days_left": days_left,
                "is_urgent": days_left <= 5,
            }
        )

    return {
        "expiring_students": expiring_students,
        "total_count": len(expiring_students),
        "urgent_count": len([s for s in expiring_students if s["is_urgent"]]),
    }
