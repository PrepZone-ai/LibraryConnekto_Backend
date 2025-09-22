from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.auth.dependencies import get_current_admin
from app.schemas.subscription import (
    SubscriptionPlanCreate, SubscriptionPlanUpdate, SubscriptionPlanResponse
)
from app.models.subscription import SubscriptionPlan
from app.models.admin import AdminUser, AdminDetails

router = APIRouter()

@router.post("/plans", response_model=SubscriptionPlanResponse)
async def create_subscription_plan(
    plan_data: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Create a new subscription plan"""
    # Get admin's library_id
    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
    if not admin_details:
        raise HTTPException(status_code=404, detail="Admin details not found")
    # Create plan with auto-set library_id
    plan_dict = plan_data.model_dump()
    plan_dict['library_id'] = admin_details.id
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
    db: Session = Depends(get_db)
):
    """Get all subscription plans"""
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
        # Optionally, you can return a more detailed error for debugging (remove in production)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.get("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def get_subscription_plan(
    plan_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific subscription plan"""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    
    return plan

@router.put("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def update_subscription_plan(
    plan_id: str,
    plan_data: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update a subscription plan"""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    
    update_data = plan_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(plan, field, value)
    
    db.commit()
    db.refresh(plan)
    
    return plan

@router.get("/plans/check-duration/{library_id}/{months}")
async def check_duration_exists(
    library_id: str,
    months: int,
    db: Session = Depends(get_db)
):
    """Check if a subscription plan with the given duration exists for a library"""
    try:
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.library_id == library_id,
            SubscriptionPlan.months == months,
            SubscriptionPlan.is_active == True
        ).first()
        
        if plan:
            return plan
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No plan found with this duration"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking duration: {str(e)}"
        )

@router.delete("/plans/{plan_id}")
async def delete_subscription_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Delete a subscription plan (soft delete by setting is_active to False)"""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    
    plan.is_active = False
    db.commit()
    
    return {"message": "Subscription plan deleted successfully"}
