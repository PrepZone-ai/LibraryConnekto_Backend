from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.auth.dependencies import get_current_admin, get_current_student
from app.schemas.messaging import (
    MessageCreate, AdminMessageCreate, StudentMessageCreate, MessageUpdate, 
    MessageResponse, BroadcastMessageCreate
)
from app.models.student import StudentMessage, Student
from app.models.admin import AdminUser, AdminDetails

router = APIRouter()

@router.post("/send-message", response_model=MessageResponse)
async def send_student_message(
    message_data: StudentMessageCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Send a message from student to admin"""
    # Verify admin exists
    admin = db.query(AdminUser).filter(AdminUser.user_id == message_data.admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    message = StudentMessage(
        student_id=current_student.id,
        admin_id=message_data.admin_id,
        message=message_data.message,
        student_name=current_student.name,
        sender_type="student",
        read=False,
        is_broadcast=False,
        image_url=message_data.image_url
    )
    
    db.add(message)
    db.commit()
    db.refresh(message)
    
    return message

@router.post("/admin/send-message", response_model=MessageResponse)
async def send_admin_message(
    message_data: AdminMessageCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Send a message from admin to student or broadcast"""
    # Get admin details for name
    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
    admin_name = admin_details.admin_name if admin_details else "Admin"
    
    if message_data.is_broadcast:
        # Broadcast message to all students
        students = db.query(Student).filter(Student.admin_id == current_admin.user_id).all()
        
        messages = []
        for student in students:
            message = StudentMessage(
                student_id=student.id,
                admin_id=current_admin.user_id,
                message=message_data.message,
                student_name=student.name,
                admin_name=admin_name,
                sender_type="admin",
                read=False,
                is_broadcast=True,
                image_url=message_data.image_url
            )
            messages.append(message)
        
        db.add_all(messages)
        db.commit()
        
        return messages[0] if messages else None
    else:
        # Send to specific student
        if not message_data.student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student ID is required for non-broadcast messages"
            )
        
        student = db.query(Student).filter(
            Student.id == message_data.student_id,
            Student.admin_id == current_admin.user_id
        ).first()
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        message = StudentMessage(
            student_id=student.id,
            admin_id=current_admin.user_id,
            message=message_data.message,
            student_name=student.name,
            admin_name=admin_name,
            sender_type="admin",
            read=False,
            is_broadcast=False,
            image_url=message_data.image_url
        )
        
        db.add(message)
        db.commit()
        db.refresh(message)
        
        return message

@router.post("/admin/broadcast", response_model=MessageResponse)
async def send_broadcast_message(
    message_data: BroadcastMessageCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Send a broadcast message to all students"""
    admin_message = AdminMessageCreate(
        message=message_data.message,
        image_url=message_data.image_url,
        is_broadcast=True
    )
    
    return await send_admin_message(admin_message, db, current_admin)

@router.get("/messages", response_model=List[MessageResponse])
async def get_student_messages(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Get messages for current student (including broadcasts from their library admin only)"""
    messages = db.query(StudentMessage).filter(
        or_(
            # Messages sent directly to this student
            StudentMessage.student_id == current_student.id,
            # Broadcast messages from this student's library admin only
            and_(
                StudentMessage.is_broadcast == True,
                StudentMessage.sender_type == "admin",
                StudentMessage.admin_id == current_student.admin_id
            )
        )
    ).order_by(StudentMessage.created_at.desc()).offset(skip).limit(limit).all()
    
    return messages

@router.get("/admin/messages", response_model=List[MessageResponse])
async def get_admin_messages(
    student_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get messages for current admin"""
    query = db.query(StudentMessage).filter(StudentMessage.admin_id == current_admin.user_id)
    
    if student_id:
        query = query.filter(StudentMessage.student_id == student_id)
    
    messages = query.order_by(StudentMessage.created_at.desc()).offset(skip).limit(limit).all()
    
    return messages

@router.put("/admin/messages/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: str,
    message_data: MessageUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update a message (respond or mark as read)"""
    message = db.query(StudentMessage).filter(
        StudentMessage.id == message_id,
        StudentMessage.admin_id == current_admin.user_id
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    update_data = message_data.model_dump(exclude_unset=True)
    
    if "admin_response" in update_data and update_data["admin_response"]:
        update_data["responded_at"] = datetime.utcnow()
        # Get admin name
        admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
        message.admin_name = admin_details.admin_name if admin_details else "Admin"
    
    for field, value in update_data.items():
        setattr(message, field, value)
    
    db.commit()
    db.refresh(message)
    
    return message

@router.put("/messages/{message_id}/read")
async def mark_message_as_read(
    message_id: str,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Mark a message as read by student"""
    message = db.query(StudentMessage).filter(
        StudentMessage.id == message_id,
        or_(
            StudentMessage.student_id == current_student.id,
            and_(
                StudentMessage.is_broadcast == True,
                StudentMessage.sender_type == "admin"
            )
        )
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    message.read = True
    db.commit()
    
    return {"message": "Message marked as read"}

@router.get("/admin/students", response_model=List[dict])
async def get_students_with_messages(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get students with their latest message for admin chat interface"""
    students = db.query(Student).filter(Student.admin_id == current_admin.user_id).all()
    
    result = []
    
    def _normalize_dt(dt: datetime | None) -> datetime | None:
        """Ensure datetime is naive in UTC for safe comparisons/sorting."""
        if not dt:
            return None
        try:
            if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return dt
    for student in students:
        # Get latest message for this student
        latest_message = db.query(StudentMessage).filter(
            StudentMessage.student_id == student.id,
            StudentMessage.admin_id == current_admin.user_id
        ).order_by(StudentMessage.created_at.desc()).first()
        
        # Count unread messages from this student
        unread_count = db.query(StudentMessage).filter(
            StudentMessage.student_id == student.id,
            StudentMessage.admin_id == current_admin.user_id,
            StudentMessage.sender_type == "student",
            StudentMessage.read == False
        ).count()
        
        result.append({
            "student_id": str(student.id),
            "student_name": student.name,
            "email": student.email,
            "latest_message": latest_message.message if latest_message else None,
            "latest_message_time": _normalize_dt(latest_message.created_at) if latest_message else None,
            "unread_count": unread_count
        })
    
    # Sort by latest message time
    result.sort(key=lambda x: x["latest_message_time"] or datetime.min, reverse=True)
    
    return result
