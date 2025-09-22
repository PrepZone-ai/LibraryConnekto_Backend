from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import string
import random
import time
import uuid

from app.database import get_db
from app.auth.dependencies import get_current_admin, get_current_student, get_current_user
from app.schemas.referral import (
    ReferralCodeCreate, ReferralCodeResponse, ReferralCreate, ReferralUpdate, 
    ReferralResponse, ReferralValidationRequest, ReferralValidationResponse
)
from app.models.referral import ReferralCode, Referral
from app.models.admin import AdminUser
from app.models.student import Student
from app.services.email_service import EmailService

router = APIRouter()

@router.get("/test")
async def test_referral_endpoint():
    """Test endpoint to verify referral system is working"""
    return {
        "message": "Referral system is working",
        "timestamp": time.time(),
        "status": "ok"
    }

@router.get("/test-auth")
async def test_auth_endpoint():
    """Test endpoint that returns mock user data for development"""
    return {
        "user_id": "550e8400-e29b-41d4-a716-446655440000",  # Mock UUID
        "user_type": "admin",
        "email": "testadmin@library.com"
    }

def generate_referral_code(type: str, name: str, library_name: str = None) -> str:
    """Generate a unique referral code with better uniqueness"""
    if type == "admin":
        prefix = "ADM"
        if library_name:
            # Take first 3 characters of library name, filter out non-alphabetic
            lib_prefix = ''.join(c.upper() for c in library_name if c.isalpha())[:3]
            prefix = lib_prefix if len(lib_prefix) >= 2 else "ADM"
    else:
        prefix = "STU"
    
    # Take first 3 characters of name, filter out non-alphabetic
    name_part = ''.join(c.upper() for c in name if c.isalpha())[:3]
    if len(name_part) < 3:
        name_part = name_part.ljust(3, 'X')
    
    # Generate random 4-digit number
    random_part = ''.join(random.choices(string.digits, k=4))
    
    # Add timestamp component for better uniqueness
    timestamp_part = str(int(time.time()))[-3:]
    
    return f"{prefix}{name_part}{random_part}{timestamp_part}"

@router.post("/codes", response_model=ReferralCodeResponse)
async def create_referral_code(
    referral_data: ReferralCodeCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new referral code"""
    user_id = current_user["user_id"]
    user_type = current_user["user_type"]

    # Check if user already has a referral code of this type
    # Handle backward compatibility - check if user_type column exists
    try:
        existing_code = db.query(ReferralCode).filter(
            ReferralCode.user_id == user_id,
            ReferralCode.type == referral_data.type
        ).first()
    except Exception as e:
        # If user_type column doesn't exist, fall back to old query
        existing_code = db.query(ReferralCode).filter(
            ReferralCode.user_id == user_id,
            ReferralCode.type == referral_data.type
        ).first()

    if existing_code:
        return existing_code

    # Generate unique code with retry logic
    attempts = 0
    max_attempts = 20
    code = None
    
    while attempts < max_attempts:
        try:
            if user_type == "admin":
                # Try to get admin details from database first
                admin = db.query(AdminUser).filter(AdminUser.user_id == user_id).first()
                admin_details = admin.admin_details if admin else None
                
                # Use provided name and library name from request, fallback to database, then defaults
                user_name = referral_data.name if hasattr(referral_data, 'name') and referral_data.name else (
                    admin_details.admin_name if admin_details else "Admin"
                )
                library_name = referral_data.library_name if hasattr(referral_data, 'library_name') and referral_data.library_name else (
                    admin_details.library_name if admin_details else None
                )
                
                code = generate_referral_code(referral_data.type, user_name, library_name)
            else:
                student = db.query(Student).filter(Student.auth_user_id == user_id).first()
                user_name = student.name if student else "Student"
                code = generate_referral_code(referral_data.type, user_name)

            # Check if code already exists
            existing = db.query(ReferralCode).filter(ReferralCode.code == code).first()
            if not existing:
                break
                
            attempts += 1
            # Small delay to ensure different timestamp
            time.sleep(0.1)
            
        except Exception as e:
            attempts += 1
            continue

    if attempts >= max_attempts or not code:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate unique referral code after multiple attempts"
        )

    # Create the referral code
    try:
        referral_code = ReferralCode(
            user_id=user_id,
            user_type=user_type,
            code=code,
            type=referral_data.type
        )
    except Exception as e:
        # Fallback for backward compatibility
        referral_code = ReferralCode(
            user_id=user_id,
            code=code,
            type=referral_data.type
        )

    db.add(referral_code)
    db.commit()
    db.refresh(referral_code)

    return referral_code

@router.get("/codes", response_model=List[ReferralCodeResponse])
async def get_referral_codes(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get referral codes for current user"""
    codes = db.query(ReferralCode).filter(
        ReferralCode.user_id == current_user["user_id"]
    ).all()
    
    return codes

@router.post("/validate", response_model=ReferralValidationResponse)
async def validate_referral_code(
    validation_request: ReferralValidationRequest,
    db: Session = Depends(get_db)
):
    """Validate a referral code"""
    referral_code = db.query(ReferralCode).filter(
        ReferralCode.code == validation_request.code
    ).first()
    
    if not referral_code:
        return ReferralValidationResponse(
            success=False,
            message="Invalid referral code"
        )
    
    # Get referrer details
    referrer_name = "Unknown"
    referrer_type = "unknown"
    
    try:
        if hasattr(referral_code, 'user_type') and referral_code.user_type:
            referrer_type = referral_code.user_type
        else:
            # Fallback - try to determine type from user_id
            admin = db.query(AdminUser).filter(AdminUser.user_id == referral_code.user_id).first()
            if admin:
                referrer_type = "admin"
            else:
                student = db.query(Student).filter(Student.auth_user_id == referral_code.user_id).first()
                if student:
                    referrer_type = "student"
    except Exception:
        referrer_type = "unknown"
    
    if referrer_type == "admin":
        admin = db.query(AdminUser).filter(AdminUser.user_id == referral_code.user_id).first()
        if admin and admin.admin_details:
            referrer_name = admin.admin_details.admin_name
    elif referrer_type == "student":
        student = db.query(Student).filter(Student.auth_user_id == referral_code.user_id).first()
        if student:
            referrer_name = student.name
    
    return ReferralValidationResponse(
        success=True,
        message="Valid referral code",
        referral_code=referral_code,
        referrer_name=referrer_name,
        referrer_type=referrer_type
    )

@router.post("/referrals", response_model=ReferralResponse)
async def create_referral(
    referral_data: ReferralCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new referral"""
    # Verify referral code exists
    referral_code = db.query(ReferralCode).filter(
        ReferralCode.id == referral_data.referral_code_id
    ).first()
    
    if not referral_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral code not found"
        )
    
    # Check if referral already exists for this referrer and referral code
    existing_referral = db.query(Referral).filter(
        Referral.referral_code_id == referral_data.referral_code_id,
        Referral.referrer_id == referral_data.referrer_id
    ).first()
    
    if existing_referral:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Referral already exists for this code"
        )
    
    try:
        referral = Referral(**referral_data.model_dump())
    except Exception as e:
        # Fallback for backward compatibility
        referral_data_dict = referral_data.model_dump()
        # Remove fields that might not exist in old schema
        referral_data_dict.pop('referrer_type', None)
        referral_data_dict.pop('referred_type', None)
        referral_data_dict.pop('referred_email', None)
        referral_data_dict.pop('points_awarded', None)
        referral_data_dict.pop('notes', None)
        referral_data_dict.pop('completed_at', None)
        referral = Referral(**referral_data_dict)
    
    db.add(referral)
    db.commit()
    db.refresh(referral)
    
    # Send invitation email if email provided; don't fail the API if email fails
    if referral.referred_email:
      try:
        # Determine referrer name
        referrer_name = ""
        if referral.referrer_type == "admin":
            admin = db.query(AdminUser).filter(AdminUser.user_id == referral.referrer_id).first()
            referrer_name = admin.admin_details.admin_name if admin and admin.admin_details else "An admin"
            library_name = admin.admin_details.library_name if admin and admin.admin_details else ""
        else:
            student = db.query(Student).filter(Student.auth_user_id == referral.referrer_id).first()
            referrer_name = student.name if student else "A student"
            library_name = ""

        # Fetch referral code string
        code = db.query(ReferralCode).filter(ReferralCode.id == referral.referral_code_id).first()
        code_str = code.code if code else ""

        EmailService().send_referral_invitation_email(
            email=referral.referred_email,
            referrer_name=referrer_name or "Your friend",
            referral_code=code_str,
            library_name=library_name,
            invite_url=""
        )
      except Exception as e:
        # Log-only failure; do not raise
        import logging
        logging.getLogger(__name__).error(f"Referral invite email failed: {e}")

    return referral

@router.get("/referrals", response_model=List[ReferralResponse])
async def get_referrals(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get referrals for current user"""
    referrals = db.query(Referral).filter(
        Referral.referrer_id == current_user["user_id"]
    ).offset(skip).limit(limit).all()
    
    return referrals

@router.get("/summary")
async def get_referrals_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get referral summary (total points, counts) for current user"""
    user_id = current_user["user_id"]
    user_referrals = db.query(Referral).filter(Referral.referrer_id == user_id).all()
    total_points = 0
    completed = 0
    pending = 0
    for r in user_referrals:
        try:
            pts = int(r.points_awarded or "0")
        except Exception:
            pts = 0
        total_points += pts
        status = (r.status or "").lower()
        if status == "completed":
            completed += 1
        else:
            pending += 1
    return {
        "total_points": total_points,
        "completed": completed,
        "pending": pending,
        "total_referrals": len(user_referrals)
    }

@router.put("/referrals/{referral_id}", response_model=ReferralResponse)
async def update_referral(
    referral_id: str,
    referral_data: ReferralUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a referral"""
    referral = db.query(Referral).filter(
        Referral.id == referral_id,
        Referral.referrer_id == current_user["user_id"]
    ).first()
    
    if not referral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral not found"
        )
    
    update_data = referral_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(referral, field):
            setattr(referral, field, value)
    
    db.commit()
    db.refresh(referral)
    
    return referral
