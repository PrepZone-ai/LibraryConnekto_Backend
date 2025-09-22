from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.auth.jwt import verify_token
from app.models.admin import AdminUser
from app.models.student import Student

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> dict:
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = verify_token(token)
    
    user_id: str = payload.get("sub")
    user_type: str = payload.get("user_type")
    
    if user_id is None or user_type is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "user_id": user_id,
        "user_type": user_type,
        "email": payload.get("email")
    }

def get_current_admin(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AdminUser:
    """Get current admin user"""
    if current_user["user_type"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    admin = db.query(AdminUser).filter(AdminUser.user_id == current_user["user_id"]).first()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    return admin

def get_current_student(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Student:
    """Get current student user"""
    if current_user["user_type"] != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    student = db.query(Student).filter(Student.auth_user_id == current_user["user_id"]).first()
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if student has been removed from the library
    # Only block access if student has been explicitly removed (not just inactive or expired)
    if student.subscription_status == "Removed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been removed from the library. Please contact the library administrator."
        )
    
    return student

def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[dict]:
    """Get current user from JWT token (optional)"""
    if not credentials:
        return None
    
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None
