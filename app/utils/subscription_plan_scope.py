"""Helpers for resolving admin library PK and filtering subscription plans by shift scope."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query, Session

from app.models.admin import AdminDetails
from app.models.subscription import SubscriptionPlan


def admin_details_id_for_user(db: Session, admin_user_id: UUID) -> Optional[UUID]:
    row = db.query(AdminDetails).filter(AdminDetails.user_id == admin_user_id).first()
    return row.id if row else None


def apply_plan_shift_filters(
    query: Query,
    library: AdminDetails,
    *,
    is_shift_student: Optional[bool] = None,
    shift_time: Optional[str] = None,
) -> Query:
    """
    Non-shift libraries only expose non-shift plans.
    Shift libraries:
      - Non-shift students: plans with is_shift_plan == False.
      - Shift students: non-shift plans OR plans tied to their shift_time.
      - No student hint (None): non-shift plans only (safe default for public listing).
    """
    if not library.has_shift_system:
        return query.filter(SubscriptionPlan.is_shift_plan.is_(False))

    if is_shift_student is None:
        return query.filter(SubscriptionPlan.is_shift_plan.is_(False))

    if is_shift_student is False:
        return query.filter(SubscriptionPlan.is_shift_plan.is_(False))

    st = (shift_time or "").strip()
    if not st:
        return query.filter(SubscriptionPlan.is_shift_plan.is_(False))

    return query.filter(
        or_(
            SubscriptionPlan.is_shift_plan.is_(False),
            and_(SubscriptionPlan.is_shift_plan.is_(True), SubscriptionPlan.shift_time == st),
        )
    )


def validate_plan_shift_fields(
    library: AdminDetails,
    is_shift_plan: bool,
    shift_time: Optional[str],
) -> None:
    from fastapi import HTTPException, status

    st = (shift_time or "").strip() or None
    if not library.has_shift_system:
        if is_shift_plan or st:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shift-specific plans require the library to have shift system enabled.",
            )
        return

    if is_shift_plan:
        if not st:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="shift_time is required for shift-specific subscription plans.",
            )
        timings = library.shift_timings or []
        if st not in timings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="shift_time must match one of the library's configured shift timings.",
            )
    elif st:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="shift_time must be empty for non-shift subscription plans.",
        )
