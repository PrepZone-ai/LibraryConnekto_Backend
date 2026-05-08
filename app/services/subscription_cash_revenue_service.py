"""Cash subscription extension + SeatBooking revenue for admin flows."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.admin import AdminDetails
from app.models.booking import SeatBooking
from app.models.student import Student
from app.models.subscription import SubscriptionPlan
from app.utils.subscription_plan_scope import apply_plan_shift_filters


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_new_subscription_end(student: Student, plan: SubscriptionPlan) -> datetime:
    """Extend from current end if still valid, else from now. Uses 30 days per plan month."""
    now = _now_utc()
    end = student.subscription_end
    if end is not None:
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        base = end if end > now else now
    else:
        base = now
    return base + timedelta(days=30 * int(plan.months or 1))


def plan_amount(plan: SubscriptionPlan) -> Decimal:
    if plan.discounted_amount is not None:
        return Decimal(str(plan.discounted_amount))
    return Decimal(str(plan.amount))


def create_cash_subscription_booking(
    db: Session,
    *,
    student: Student,
    library: AdminDetails,
    plan: SubscriptionPlan,
    amount: Decimal,
    purpose: str = "Subscription renewal (cash)",
    payment_reference: str = "cash_subscription_renewal",
) -> SeatBooking:
    """Paid SeatBooking for revenue (cash subscription renewal)."""
    booking = SeatBooking(
        student_id=student.auth_user_id,
        library_id=library.id,
        admin_id=student.admin_id,
        name=student.name,
        email=student.email,
        mobile=student.mobile_no,
        address=student.address or "",
        subscription_months=int(plan.months or 1),
        subscription_plan_id=plan.id,
        amount=amount,
        date="",
        start_time="",
        end_time="",
        purpose=purpose,
        status="active",
        payment_status="paid",
        payment_date=_now_utc(),
        payment_method="cash",
        payment_reference=payment_reference,
    )
    db.add(booking)
    return booking


def validate_plan_for_student(
    db: Session,
    *,
    student: Student,
    library: AdminDetails,
    plan_id: UUID,
) -> SubscriptionPlan:
    q = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == plan_id,
        SubscriptionPlan.library_id == library.id,
        SubscriptionPlan.is_active == True,
    )
    q = apply_plan_shift_filters(
        q,
        library,
        is_shift_student=student.is_shift_student,
        shift_time=student.shift_time,
    )
    plan = q.first()
    if not plan:
        raise ValueError("Subscription plan not found or not available for this student")
    return plan


def apply_cash_subscription_extension(
    db: Session,
    *,
    student: Student,
    library: AdminDetails,
    plan_id: UUID,
    amount_override: Optional[Decimal] = None,
    purpose: str = "Subscription renewal (cash)",
    payment_reference: str = "cash_subscription_renewal",
) -> Tuple[Student, SeatBooking, datetime]:
    """
    Extend student subscription from plan duration and record paid cash booking for revenue.
    """
    plan = validate_plan_for_student(db, student=student, library=library, plan_id=plan_id)
    amount = amount_override if amount_override is not None else plan_amount(plan)
    new_end = compute_new_subscription_end(student, plan)
    student.subscription_end = new_end
    student.subscription_status = "Active"
    student.is_active = True
    student.removed_at = None
    now = _now_utc()
    if not student.subscription_start or student.subscription_start > now:
        student.subscription_start = now
    booking = create_cash_subscription_booking(
        db,
        student=student,
        library=library,
        plan=plan,
        amount=amount,
        purpose=purpose,
        payment_reference=payment_reference,
    )
    return student, booking, new_end
