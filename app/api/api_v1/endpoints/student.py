from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import os
import uuid
from datetime import datetime, timezone
import logging

from app.core.mime_guess import get_mime_from_buffer

from app.database import get_db
from app.auth.dependencies import get_current_student
from app.auth.jwt import get_password_hash
from app.schemas.student import (
    StudentResponse,
    StudentUpdate,
    StudentAttendanceCreate,
    StudentAttendanceResponse,
    StudentTaskCreate,
    StudentTaskUpdate,
    StudentTaskResponse,
    StudentExamCreate,
    StudentExamUpdate,
    StudentExamResponse,
)
from app.schemas.qr_transfer import StudentQRTokenResponse
from app.models.student import (
    Student,
    StudentAttendance,
    StudentTask,
    StudentExam,
    StudentMessage,
)
from app.services.notification_service import NotificationService
from app.services.qr_transfer_service import issue_student_qr_token
from app.core.config import settings
from app.core.cache import (
    admin_location_key,
    attendance_location_rate_limit_key,
    cached,
    get_cached,
    invalidate_admin_caches,
    invalidate_student_dashboard,
    set_cached,
    set_if_absent,
    student_dashboard_key,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _calculate_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c * 1000

@router.get("/test-auth")
async def test_auth(
    current_student: Student = Depends(get_current_student)
):
    """Test authentication endpoint"""
    return {
        "status": "authenticated",
        "student_id": current_student.id,
        "auth_user_id": current_student.auth_user_id,
        "name": current_student.name
    }

@router.get("/set-password")
async def get_set_password_page(token: str, db: Session = Depends(get_db)):
    """Get password setup page - validates token and shows form"""
    # Validate token
    student = db.query(Student).filter(Student.password_reset_token == token).first()
    if not student:
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    
    return {
        "message": "Token valid",
        "student_id": student.student_id,
        "email": student.email,
        "name": student.name
    }

@router.post("/set-password")
async def set_student_password(
    request: dict,
    db: Session = Depends(get_db)
):
    """Set student password using token from email or for first login"""
    token = request.get("token")
    new_password = request.get("new_password")
    student_id = request.get("student_id")  # For first login without token
    
    if not new_password:
        raise HTTPException(status_code=400, detail="new_password is required.")
    
    student = None
    
    # If token provided, find student by token
    if token:
        student = db.query(Student).filter(Student.password_reset_token == token).first()
        if not student:
            raise HTTPException(status_code=404, detail="Invalid or expired token.")
    # If student_id provided (for first login), find student by ID
    elif student_id:
        student = db.query(Student).filter(Student.student_id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found.")
        
        # Check if this is first login (password is still mobile number)
        # Allow password change if it's still the mobile number
        try:
            from app.auth.jwt import verify_password
            is_first_login = verify_password(student.mobile_no, student.hashed_password)

            if not is_first_login:
                # Password has already been changed from mobile number
                # This is not a first login scenario
                raise HTTPException(status_code=400, detail="Password has already been set. Please use your existing password.")
                
        except Exception as e:
            # If verification fails, it's not first login
            print(f"[DEBUG] First login check failed in set-password: {e}")
            raise HTTPException(status_code=400, detail="Password has already been set. Please use your existing password.")
    else:
        raise HTTPException(status_code=400, detail="Either token or student_id is required.")
    
    # Validate password strength
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")
    
    # Set password and clear token
    student.hashed_password = get_password_hash(new_password)
    student.password_reset_token = None
    db.commit()
    
    return {
        "message": f"Password set successfully for {student.name}! You can now log in with your Student ID and password.",
        "student_id": student.student_id,
        "email": student.email,
        "success": True
    }

@router.post("/set-password-manual")
async def set_student_password_manual(
    request: dict,
    db: Session = Depends(get_db)
):
    """Manual password setup for students when email fails (admin use only)"""
    student_id = request.get("student_id")
    new_password = request.get("new_password")
    
    if not student_id or not new_password:
        raise HTTPException(status_code=400, detail="student_id and new_password are required.")
    
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    
    if student.hashed_password:
        raise HTTPException(status_code=400, detail="Student already has a password set.")
    
    # Validate password strength
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")
    
    student.hashed_password = get_password_hash(new_password)
    student.password_reset_token = None
    db.commit()
    return {"message": f"Password set successfully for student {student_id}! They can now log in with their student ID and password."}

@router.get("/profile", response_model=StudentResponse)
async def get_student_profile(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Get current student profile with library information"""
    from app.models.admin import AdminDetails
    
    # Get library details
    admin_details = db.query(AdminDetails).filter(
        AdminDetails.user_id == current_student.admin_id
    ).first()
    
    # Add library information to student response
    student_data = current_student.__dict__.copy()
    if admin_details:
        student_data['library_name'] = admin_details.library_name
        student_data['library_latitude'] = admin_details.latitude
        student_data['library_longitude'] = admin_details.longitude
    else:
        student_data['library_name'] = 'Unknown Library'
        student_data['library_latitude'] = None
        student_data['library_longitude'] = None
    
    return student_data


@router.get("/qr-token", response_model=StudentQRTokenResponse)
async def get_student_qr_token(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Create a short-lived signed QR token for the current student."""
    return issue_student_qr_token(db, current_student)


@router.post("/qr-rotate", response_model=StudentQRTokenResponse)
async def rotate_student_qr_token(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Rotate and return a new short-lived signed QR token."""
    return issue_student_qr_token(db, current_student)

@router.post("/profile/image")
async def upload_profile_image(
    profile_image: UploadFile = File(...),
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Upload profile image for student with validation."""
    content = await profile_image.read()

    max_size = min(settings.MAX_FILE_SIZE, 5 * 1024 * 1024)
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 5MB",
        )

    mime_type = get_mime_from_buffer(content)
    if not mime_type or not mime_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image",
        )

    try:
        upload_dir = "uploads/profile_images"
        os.makedirs(upload_dir, exist_ok=True)

        file_extension = (
            profile_image.filename.split(".")[-1]
            if "." in profile_image.filename
            else "jpg"
        )
        filename = f"{current_student.id}_{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(upload_dir, filename)

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        current_student.profile_image = f"/uploads/profile_images/{filename}"
        db.commit()
        db.refresh(current_student)

        return {
            "message": "Profile image uploaded successfully",
            "profile_image": current_student.profile_image,
            "mime_type": mime_type,
            "size": len(content),
        }

    except Exception as e:
        logger.error(
            "Failed to upload profile image",
            extra={"student_id": str(current_student.id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image",
        )

@router.delete("/profile/image")
async def delete_profile_image(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Delete profile image for student"""
    try:
        if current_student.profile_image:
            # Remove file from filesystem
            file_path = current_student.profile_image.lstrip('/')
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Update student profile
            current_student.profile_image = None
            db.commit()
            db.refresh(current_student)
            
            return {"message": "Profile image deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No profile image found"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete image: {str(e)}"
        )

@router.get("/dashboard/stats")
@cached(ttl=45, key_builder=lambda current_student, db: student_dashboard_key(str(current_student.auth_user_id)))
async def get_student_dashboard_stats(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    """Get comprehensive dashboard statistics for student"""
    from datetime import datetime, date, timedelta
    
    # Check if attendance is marked today
    today = date.today()
    today_attendance = db.query(StudentAttendance).filter(
        StudentAttendance.student_id == current_student.auth_user_id,
        func.date(StudentAttendance.entry_time) == today,
        StudentAttendance.exit_time.is_(None)
    ).first()
    
    # Calculate total study hours from all attendance records
    total_study_hours = 0
    attendance_records = db.query(StudentAttendance).filter(
        StudentAttendance.student_id == current_student.auth_user_id,
        StudentAttendance.total_duration.isnot(None)
    ).all()
    
    for record in attendance_records:
        if record.total_duration:
            # Convert duration to hours
            if hasattr(record.total_duration, 'total_seconds'):
                total_study_hours += record.total_duration.total_seconds() / 3600
            else:
                # Handle string duration format
                try:
                    duration_str = str(record.total_duration)
                    if ':' in duration_str:
                        parts = duration_str.split(':')
                        hours = float(parts[0]) if parts[0] else 0
                        minutes = float(parts[1]) if len(parts) > 1 and parts[1] else 0
                        total_study_hours += hours + (minutes / 60)
                except:
                    pass
    
    # Get task statistics
    total_tasks = db.query(StudentTask).filter(
        StudentTask.student_id == current_student.id
    ).count()
    
    completed_tasks = db.query(StudentTask).filter(
        StudentTask.student_id == current_student.id,
        StudentTask.completed == True
    ).count()
    
    # Get upcoming exams
    from datetime import timezone
    upcoming_exams = db.query(StudentExam).filter(
        StudentExam.student_id == current_student.auth_user_id,
        StudentExam.exam_date > datetime.now(timezone.utc),
        StudentExam.is_completed == False
    ).count()
    
    # Get unread messages (including broadcasts from student's admin)
    from sqlalchemy import or_, and_
    unread_messages = db.query(StudentMessage).filter(
        or_(
            # Messages sent directly to this student
            and_(
                StudentMessage.student_id == current_student.id,
                StudentMessage.read == False
            ),
            # Broadcast messages from this student's library admin only
            and_(
                StudentMessage.is_broadcast == True,
                StudentMessage.sender_type == "admin",
                StudentMessage.admin_id == current_student.admin_id,
                StudentMessage.read == False
            )
        )
    ).count()
    
    # Calculate study streak (consecutive days with attendance)
    study_streak = 0
    current_date = today
    
    # Check if there's attendance today first
    if today_attendance:
        study_streak = 1
        current_date -= timedelta(days=1)
        
        # Continue checking previous days
        while True:
            day_attendance = db.query(StudentAttendance).filter(
                StudentAttendance.student_id == current_student.auth_user_id,
                func.date(StudentAttendance.entry_time) == current_date
            ).first()
            
            if day_attendance:
                study_streak += 1
                current_date -= timedelta(days=1)
            else:
                break
    
    return {
        "attendance_today": bool(today_attendance),
        "total_study_hours": round(total_study_hours, 1),
        "tasks_completed": completed_tasks,
        "total_tasks": total_tasks,
        "upcoming_exams": upcoming_exams,
        "messages_unread": unread_messages,
        "study_streak": study_streak,
        "subscription_status": current_student.subscription_status,
        "subscription_end": current_student.subscription_end.isoformat() if current_student.subscription_end else None
    }

@router.get("/dashboard/messages", response_model=List[dict])
async def get_student_dashboard_messages(
    limit: int = 3,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Get recent messages for student dashboard (from their admin or broadcasts)"""
    from sqlalchemy import or_, and_
    from app.models.student import StudentMessage
    
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
    ).order_by(StudentMessage.created_at.desc()).limit(limit).all()
    
    # Format messages for dashboard display
    formatted_messages = []
    for message in messages:
        formatted_messages.append({
            "id": str(message.id),
            "message": message.message,
            "sender_type": message.sender_type,
            "admin_name": message.admin_name,
            "is_broadcast": message.is_broadcast,
            "read": message.read,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "time_ago": _get_time_ago(message.created_at) if message.created_at else "Unknown"
        })
    
    return formatted_messages

def _get_time_ago(created_at):
    """Helper function to get human-readable time ago"""
    from datetime import datetime, timezone
    if not created_at:
        return "Unknown"
    
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    
    diff = now - created_at
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(seconds // 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"

@router.put("/profile", response_model=StudentResponse)
async def update_student_profile(
    student_data: StudentUpdate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Update student profile"""
    update_data = student_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_student, field, value)
    
    db.commit()
    db.refresh(current_student)
    
    return current_student

@router.post("/attendance/checkin", response_model=StudentAttendanceResponse)
async def checkin_student(
    attendance_data: StudentAttendanceCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Check in student with location validation"""
    from app.models.admin import AdminDetails
    
    # Get admin/library location
    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_student.admin_id).first()
    if not admin_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Library information not found"
        )

    # Calculate distance from library
    if attendance_data.latitude and attendance_data.longitude and admin_details.latitude and admin_details.longitude:
        distance = _calculate_distance_meters(
            admin_details.latitude,
            admin_details.longitude,
            attendance_data.latitude,
            attendance_data.longitude,
        )

        if distance > settings.ATTENDANCE_LOCATION_MAX_DISTANCE_METERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Student is too far from library. Distance: {distance:.1f}m "
                    f"(max: {settings.ATTENDANCE_LOCATION_MAX_DISTANCE_METERS}m)"
                ),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location data required for check-in"
        )
    
    # Check if student is already checked in
    existing_attendance = db.query(StudentAttendance).filter(
        StudentAttendance.student_id == current_student.auth_user_id,
        StudentAttendance.exit_time.is_(None)
    ).first()
    
    if existing_attendance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is already checked in"
        )
    
    # Create new attendance record
    attendance = StudentAttendance(
        student_id=current_student.auth_user_id,
        admin_id=current_student.admin_id,
        latitude=attendance_data.latitude,
        longitude=attendance_data.longitude,
        last_ping_at=datetime.now(timezone.utc),
    )
    
    # Update student status
    current_student.status = "Present"
    current_student.last_visit = attendance.entry_time
    
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    invalidate_student_dashboard(str(current_student.auth_user_id))
    invalidate_admin_caches(str(current_student.admin_id))
    
    return attendance

@router.post("/attendance/checkout")
async def checkout_student(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Check out student"""
    # Find active attendance record
    attendance = db.query(StudentAttendance).filter(
        StudentAttendance.student_id == current_student.auth_user_id,
        StudentAttendance.exit_time.is_(None)
    ).first()
    
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not checked in"
        )
    
    # Update attendance record
    attendance.exit_time = datetime.now(timezone.utc)
    
    # Ensure entry_time is timezone-aware for calculation
    if attendance.entry_time.tzinfo is None:
        # If entry_time is naive, assume it's UTC
        entry_time_aware = attendance.entry_time.replace(tzinfo=timezone.utc)
    else:
        entry_time_aware = attendance.entry_time
    
    attendance.total_duration = attendance.exit_time - entry_time_aware
    
    # Update student status
    current_student.status = "Absent"
    
    db.commit()
    invalidate_student_dashboard(str(current_student.auth_user_id))
    invalidate_admin_caches(str(current_student.admin_id))
    
    return {"message": "Successfully checked out"}

@router.post("/attendance/check-location")
async def check_student_location(
    attendance_data: StudentAttendanceCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Check location with server safeguards and auto-checkout when out of range."""
    from app.models.admin import AdminDetails

    # Server-side safeguard: rate-limit location checks per student
    rate_limit_key = attendance_location_rate_limit_key(str(current_student.auth_user_id))
    allowed = set_if_absent(
        rate_limit_key,
        "1",
        ttl=settings.ATTENDANCE_CHECK_LOCATION_RATE_LIMIT_SECONDS,
    )
    if not allowed:
        return {"ok": True, "skipped": "rate_limited"}

    # Check active attendance first; if not checked in, nothing to do
    active_attendance = db.query(StudentAttendance).filter(
        StudentAttendance.student_id == current_student.auth_user_id,
        StudentAttendance.exit_time.is_(None)
    ).first()
    if not active_attendance:
        return {"ok": True, "active": False}

    # Update ping timestamp even if location is unavailable
    active_attendance.last_ping_at = datetime.now(timezone.utc)
    db.commit()

    if attendance_data.latitude is None or attendance_data.longitude is None:
        return {"ok": True, "active": True, "location": "missing"}

    # Cache admin/library coordinates to avoid DB hits on every ping
    cached_location = get_cached(admin_location_key(str(current_student.admin_id)))
    if cached_location:
        admin_lat = cached_location.get("latitude")
        admin_lon = cached_location.get("longitude")
    else:
        admin_details = db.query(AdminDetails).filter(
            AdminDetails.user_id == current_student.admin_id
        ).first()
        if not admin_details or admin_details.latitude is None or admin_details.longitude is None:
            return {"ok": True, "active": True, "library_location": "missing"}
        admin_lat = admin_details.latitude
        admin_lon = admin_details.longitude
        set_cached(
            admin_location_key(str(current_student.admin_id)),
            {"latitude": admin_lat, "longitude": admin_lon},
            ttl=settings.ATTENDANCE_LIBRARY_LOCATION_CACHE_TTL_SECONDS,
        )

    distance = _calculate_distance_meters(
        admin_lat,
        admin_lon,
        attendance_data.latitude,
        attendance_data.longitude,
    )
    in_range = distance <= settings.ATTENDANCE_LOCATION_MAX_DISTANCE_METERS

    if not in_range:
        # Auto-checkout if outside allowed range
        active_attendance.exit_time = datetime.now(timezone.utc)
        if active_attendance.entry_time.tzinfo is None:
            entry_time_aware = active_attendance.entry_time.replace(tzinfo=timezone.utc)
        else:
            entry_time_aware = active_attendance.entry_time

        active_attendance.total_duration = active_attendance.exit_time - entry_time_aware
        current_student.status = "Absent"
        db.commit()
        invalidate_student_dashboard(str(current_student.auth_user_id))
        invalidate_admin_caches(str(current_student.admin_id))
        return {"ok": True, "auto_checkout": True, "distance_m": round(distance, 1)}

    return {"ok": True, "auto_checkout": False, "distance_m": round(distance, 1)}

@router.get("/attendance", response_model=List[StudentAttendanceResponse])
async def get_student_attendance(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Get student attendance history"""
    attendance_records = db.query(StudentAttendance).filter(
        StudentAttendance.student_id == current_student.auth_user_id
    ).order_by(StudentAttendance.entry_time.desc()).offset(skip).limit(limit).all()
    
    return attendance_records

@router.get("/attendance/history", response_model=List[StudentAttendanceResponse])
async def get_student_attendance_history(
    year: int = None,
    month: int = None,
    date: str = None,
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Get filtered student attendance history with date filtering"""
    query = db.query(StudentAttendance).filter(
        StudentAttendance.student_id == current_student.auth_user_id
    )
    
    # Apply date filters
    if year:
        query = query.filter(func.extract('year', StudentAttendance.entry_time) == year)
    
    if month:
        query = query.filter(func.extract('month', StudentAttendance.entry_time) == month)
    
    if date:
        # Convert date string to datetime for comparison
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            query = query.filter(func.date(StudentAttendance.entry_time) == date_obj)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
    
    attendance_records = query.order_by(StudentAttendance.entry_time.desc()).offset(skip).limit(limit).all()
    
    return attendance_records

@router.post("/tasks", response_model=StudentTaskResponse)
async def create_task(
    task_data: StudentTaskCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Create a new task"""
    task = StudentTask(
        student_id=current_student.id,
        **task_data.model_dump()
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    invalidate_student_dashboard(str(current_student.auth_user_id))
    
    # Create automatic reminders for the task if it has a due date (disabled for now to avoid DB hit on every task create)
    # if task.due_date:
    #     notification_service = NotificationService(db)
    #     # Create default reminders: 1 hour and 1 day before due date
    #     default_reminders = ["1_hour", "1_day"]
    #     notification_service.create_task_reminders(task, default_reminders)
    
    return task

@router.get("/tasks", response_model=List[StudentTaskResponse])
async def get_tasks(
    skip: int = 0,
    limit: int = 100,
    completed: bool = None,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Get student tasks"""
    query = db.query(StudentTask).filter(StudentTask.student_id == current_student.id)
    
    if completed is not None:
        query = query.filter(StudentTask.completed == completed)
    
    tasks = query.order_by(StudentTask.created_at.desc()).offset(skip).limit(limit).all()
    
    return tasks

@router.put("/tasks/{task_id}", response_model=StudentTaskResponse)
async def update_task(
    task_id: str,
    task_data: StudentTaskUpdate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Update a task"""
    task = db.query(StudentTask).filter(
        StudentTask.id == task_id,
        StudentTask.student_id == current_student.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    db.commit()
    db.refresh(task)
    invalidate_student_dashboard(str(current_student.auth_user_id))
    
    return task

@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Delete a task"""
    task = db.query(StudentTask).filter(
        StudentTask.id == task_id,
        StudentTask.student_id == current_student.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    db.delete(task)
    db.commit()
    invalidate_student_dashboard(str(current_student.auth_user_id))
    
    return {"message": "Task deleted successfully"}

@router.post("/exams", response_model=StudentExamResponse)
async def create_exam(
    exam_data: StudentExamCreate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Create a new exam"""
    exam = StudentExam(
        student_id=current_student.auth_user_id,
        **exam_data.model_dump()
    )
    
    db.add(exam)
    db.commit()
    db.refresh(exam)
    
    # Create automatic reminders for the exam
    notification_service = NotificationService(db)
    # Create default reminders: 1 day and 1 week before exam date
    default_reminders = ["1_day", "1_week"]
    notification_service.create_exam_reminders(exam, default_reminders)
    
    return exam

@router.get("/exams", response_model=List[StudentExamResponse])
async def get_exams(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Get student exams"""
    exams = db.query(StudentExam).filter(
        StudentExam.student_id == current_student.auth_user_id
    ).order_by(StudentExam.exam_date.asc()).offset(skip).limit(limit).all()
    
    return exams

@router.put("/exams/{exam_id}", response_model=StudentExamResponse)
async def update_exam(
    exam_id: str,
    exam_data: StudentExamUpdate,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Update an exam"""
    exam = db.query(StudentExam).filter(
        StudentExam.id == exam_id,
        StudentExam.student_id == current_student.auth_user_id
    ).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    update_data = exam_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(exam, field, value)
    
    db.commit()
    db.refresh(exam)
    
    return exam

@router.delete("/exams/{exam_id}")
async def delete_exam(
    exam_id: str,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Delete an exam"""
    exam = db.query(StudentExam).filter(
        StudentExam.id == exam_id,
        StudentExam.student_id == current_student.auth_user_id
    ).first()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    db.delete(exam)
    db.commit()
    
    return {"message": "Exam deleted successfully"}
