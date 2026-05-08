from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.auth.dependencies import get_current_admin
from app.schemas.subscription import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    SubscriptionPlanResponse,
)
from app.models.subscription import SubscriptionPlan
from app.models.admin import AdminUser, AdminDetails
from app.utils.subscription_plan_scope import validate_plan_shift_fields

router = APIRouter()


def _admin_library(db: Session, current_admin: AdminUser) -> AdminDetails:
    admin_details = (
        db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
    )
    if not admin_details:
        raise HTTPException(status_code=404, detail="Admin details not found")
    return admin_details


def _normalized_shift_time(shift_time: Optional[str]) -> Optional[str]:
    cleaned = (shift_time or "").strip()
    return cleaned or None


def _validate_unique_plan_scope(
    db: Session,
    *,
    library_id,
    months: int,
    is_shift_plan: bool,
    shift_time: Optional[str],
    exclude_plan_id=None,
) -> None:
    """Ensure one active plan per library+months+scope combination."""
    normalized_shift = _normalized_shift_time(shift_time)
    query = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.library_id == library_id,
        SubscriptionPlan.months == months,
        SubscriptionPlan.is_shift_plan == is_shift_plan,
        SubscriptionPlan.is_active == True,
    )
    if is_shift_plan:
        query = query.filter(SubscriptionPlan.shift_time == normalized_shift)
    else:
        query = query.filter(SubscriptionPlan.shift_time.is_(None))

    if exclude_plan_id:
        query = query.filter(SubscriptionPlan.id != exclude_plan_id)

    existing = query.first()
    if existing:
        if is_shift_plan:
            detail = (
                f"A {months}-month shift plan already exists for shift '{normalized_shift}'."
            )
        else:
            detail = f"A {months}-month non-shift plan already exists."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.post("/plans", response_model=SubscriptionPlanResponse)
async def create_subscription_plan(
    plan_data: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Create a new subscription plan for the current admin's library."""
    admin_details = _admin_library(db, current_admin)
    validate_plan_shift_fields(
        admin_details,
        plan_data.is_shift_plan,
        plan_data.shift_time,
    )
    _validate_unique_plan_scope(
        db,
        library_id=admin_details.id,
        months=plan_data.months,
        is_shift_plan=plan_data.is_shift_plan,
        shift_time=plan_data.shift_time,
    )
    plan_dict = plan_data.model_dump()
    plan_dict["shift_time"] = _normalized_shift_time(plan_dict.get("shift_time"))
    plan_dict["library_id"] = admin_details.id
    plan = SubscriptionPlan(**plan_dict)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def get_subscription_plans(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """Get all subscription plans (public listing)."""
    try:
        query = db.query(SubscriptionPlan)

        if active_only:
            query = query.filter(SubscriptionPlan.is_active == True)

        plans = query.offset(skip).limit(limit).all()

        return plans
    except Exception as e:
        import traceback

        print("Error in get_subscription_plans:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def get_subscription_plan(
    plan_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific subscription plan"""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found",
        )

    return plan


@router.put("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def update_subscription_plan(
    plan_id: str,
    plan_data: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Update a subscription plan owned by the current admin's library."""
    admin_details = _admin_library(db, current_admin)
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found",
        )
    if plan.library_id != admin_details.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update plans for your own library.",
        )

    update_data = plan_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(plan, field, value)

    validate_plan_shift_fields(
        admin_details,
        plan.is_shift_plan,
        plan.shift_time,
    )
    _validate_unique_plan_scope(
        db,
        library_id=admin_details.id,
        months=plan.months,
        is_shift_plan=plan.is_shift_plan,
        shift_time=plan.shift_time,
        exclude_plan_id=plan.id,
    )
    plan.shift_time = _normalized_shift_time(plan.shift_time)

    db.commit()
    db.refresh(plan)

    return plan


@router.get("/plans/check-duration/{library_id}/{months}")
async def check_duration_exists(
    library_id: str,
    months: int,
    db: Session = Depends(get_db),
):
    """Check if a subscription plan with the given duration exists for a library"""
    try:
        plan = (
            db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.library_id == library_id,
                SubscriptionPlan.months == months,
                SubscriptionPlan.is_active == True,
            )
            .first()
        )

        if plan:
            return plan
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No plan found with this duration",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking duration: {str(e)}",
        )


@router.delete("/plans/{plan_id}")
async def delete_subscription_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Soft-delete a subscription plan (sets is_active to False)."""
    admin_details = _admin_library(db, current_admin)
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found",
        )
    if plan.library_id != admin_details.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete plans for your own library.",
        )

    plan.is_active = False
    db.commit()

    return {"message": "Subscription plan deleted successfully"}
