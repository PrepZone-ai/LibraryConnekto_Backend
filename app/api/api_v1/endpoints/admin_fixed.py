from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from fastapi.responses import StreamingResponse
import io
import openpyxl

from app.database import get_db
from app.auth.dependencies import get_current_admin
from app.schemas.admin import AdminDetailsCreate, AdminDetailsUpdate, AdminDetailsResponse, LibraryStats
from app.schemas.student import StudentResponse, StudentCreate, StudentUpdate
from app.schemas.subscription import SubscriptionPlanResponse
from app.models.admin import AdminUser, AdminDetails
from app.models.student import Student
from app.models.booking import SeatBooking
from app.models.subscription import SubscriptionPlan
from app.auth.jwt import get_password_hash

router = APIRouter()

@router.post("/details", response_model=AdminDetailsResponse)
async def create_admin_details(
    details: AdminDetailsCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Create or update admin details"""
    # Check if details already exist
    existing_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
    if existing_details:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin details already exist"
        )
    
    admin_details = AdminDetails(
        user_id=current_admin.user_id,
        **details.model_dump(exclude={"user_id"})
    )
    
    db.add(admin_details)
    db.commit()
    db.refresh(admin_details)
    
    return admin_details

@router.get("/details", response_model=AdminDetailsResponse)
async def get_admin_details(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get admin details"""
    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
    if not admin_details:
        # Create empty admin details if they don't exist
        admin_details = AdminDetails(
            user_id=current_admin.user_id,
            admin_name="",
            library_name="",
            mobile_no="",
            address="",
            total_seats=0
        )
        db.add(admin_details)
        db.commit()
        db.refresh(admin_details)
    
    # Check if admin details are complete (not empty)
    is_complete = (
        admin_details.admin_name and 
        admin_details.library_name and 
        admin_details.mobile_no and 
        admin_details.address and 
        admin_details.total_seats > 0
    )
    
    # Create a proper response object with is_complete field
    return AdminDetailsResponse(
        id=admin_details.id,
        user_id=admin_details.user_id,
        admin_name=admin_details.admin_name,
        library_name=admin_details.library_name,
        mobile_no=admin_details.mobile_no,
        address=admin_details.address,
        total_seats=admin_details.total_seats,
        latitude=admin_details.latitude,
        longitude=admin_details.longitude,
        has_shift_system=admin_details.has_shift_system,
        shift_timings=admin_details.shift_timings,
        referral_code=admin_details.referral_code,
        created_at=admin_details.created_at,
        updated_at=admin_details.updated_at,
        is_complete=is_complete
    )

@router.put("/details", response_model=AdminDetailsResponse)
async def update_admin_details(
    details: AdminDetailsUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update admin details"""
    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
    if not admin_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin details not found"
        )
    
    update_data = details.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(admin_details, field, value)
    
    db.commit()
    db.refresh(admin_details)
    
    # Check if admin details are complete (not empty)
    is_complete = (
        admin_details.admin_name and 
        admin_details.library_name and 
        admin_details.mobile_no and 
        admin_details.address and 
        admin_details.total_seats > 0
    )
    
    # Create a proper response object with is_complete field
    return AdminDetailsResponse(
        id=admin_details.id,
        user_id=admin_details.user_id,
        admin_name=admin_details.admin_name,
        library_name=admin_details.library_name,
        mobile_no=admin_details.mobile_no,
        address=admin_details.address,
        total_seats=admin_details.total_seats,
        latitude=admin_details.latitude,
        longitude=admin_details.longitude,
        has_shift_system=admin_details.has_shift_system,
        shift_timings=admin_details.shift_timings,
        referral_code=admin_details.referral_code,
        created_at=admin_details.created_at,
        updated_at=admin_details.updated_at,
        is_complete=is_complete
    )

@router.get("/stats", response_model=LibraryStats)
async def get_library_stats(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get library statistics"""
    # Get total students
    total_students = db.query(Student).filter(Student.admin_id == current_admin.user_id).count()
    
    # Get present students
    present_students = db.query(Student).filter(
        Student.admin_id == current_admin.user_id,
        Student.status == "Present"
    ).count()
    
    # Get admin details for total seats
    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
    total_seats = admin_details.total_seats if admin_details else 0
    
    # Get pending bookings
    pending_bookings = db.query(SeatBooking).filter(
        SeatBooking.admin_id == current_admin.user_id,
        SeatBooking.status == "pending"
    ).count()
    
    # Calculate total revenue (sum of approved bookings)
    total_revenue = db.query(SeatBooking).filter(
        SeatBooking.admin_id == current_admin.user_id,
        SeatBooking.status.in_(["approved", "active"])
    ).with_entities(func.sum(SeatBooking.amount)).scalar() or 0
    
    return LibraryStats(
        total_students=total_students,
        present_students=present_students,
        total_seats=total_seats,
        available_seats=total_seats - present_students,
        pending_bookings=pending_bookings,
        total_revenue=float(total_revenue)
    )

@router.post("/students", response_model=StudentResponse)
async def create_student(
    student_data: StudentCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Create a new student"""
    # Check if student already exists
    existing_student = db.query(Student).filter(Student.email == student_data.email.lower()).first()
    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student with this email already exists"
        )
    
    # Generate student ID
    from app.services.student_service import generate_student_id
    student_id = await generate_student_id(current_admin.user_id, db)
    
    # Create student
    hashed_password = get_password_hash(student_data.password)
    student = Student(
        student_id=student_id,
        admin_id=current_admin.user_id,
        hashed_password=hashed_password,
        **student_data.model_dump(exclude={"password", "admin_id"})
    )
    
    db.add(student)
    db.commit()
    db.refresh(student)
    
    return student

@router.get("/students", response_model=List[StudentResponse])
async def get_students(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get all students for the current admin"""
    students = db.query(Student).filter(
        Student.admin_id == current_admin.user_id
    ).offset(skip).limit(limit).all()
    
    return students

# Important: This specific route must come BEFORE the dynamic route with {student_id}
@router.get("/students/template")
def download_student_template(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Download Excel template for bulk student upload"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Students"
    columns = [
        "Name*",
        "Email*",
        "Mobile Number*",
        "Address*",
        "Subscription Start (YYYY-MM-DD)*",
        "Subscription End (YYYY-MM-DD)*",
        "Is Shift Student (true/false)*",
        "Shift Time (HH:mm - HH:mm)",
    ]
    ws.append(columns)
    # Add a sample row
    ws.append([
        "John Doe",
        "john@example.com",
        "1234567890",
        "123 Main St",
        "2025-03-01",
        "2025-06-01",
        "false",
        "",
    ])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=student_template.xlsx",
            "Access-Control-Allow-Origin": "http://localhost:8081",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Expose-Headers": "Content-Disposition"
        },
    )

@router.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get a specific student"""
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.admin_id == current_admin.user_id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    return student

@router.put("/students/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: str,
    student_data: StudentUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update a student"""
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.admin_id == current_admin.user_id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    update_data = student_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(student, field, value)
    
    db.commit()
    db.refresh(student)

    return student

@router.delete("/students/{student_id}")
async def delete_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Delete a student"""
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.admin_id == current_admin.user_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    # Soft delete by setting status to inactive
    student.status = "inactive"
    db.commit()

    return {"message": "Student deleted successfully"}

@router.get("/students/{student_id}/attendance")
async def get_student_attendance(
    student_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get attendance records for a specific student"""
    from app.models.student import StudentAttendance

    # Verify student belongs to current admin
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.admin_id == current_admin.user_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    attendance_records = db.query(StudentAttendance).filter(
        StudentAttendance.student_id == student.auth_user_id
    ).order_by(StudentAttendance.created_at.desc()).offset(skip).limit(limit).all()

    return attendance_records

@router.get("/attendance/today")
async def get_today_attendance(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get today's attendance for all students"""
    from app.models.student import StudentAttendance
    from datetime import date

    today = date.today()

    # Get all students for this admin
    students = db.query(Student).filter(Student.admin_id == current_admin.user_id).all()

    attendance_data = []
    for student in students:
        # Check if student has attendance record for today
        attendance = db.query(StudentAttendance).filter(
            StudentAttendance.student_id == student.auth_user_id,
            func.date(StudentAttendance.entry_time) == today
        ).first()

        attendance_data.append({
            "student_id": str(student.id),
            "student_name": student.name,
            "auth_user_id": str(student.auth_user_id),
            "status": "Present" if attendance and not attendance.exit_time else "Absent",
            "entry_time": attendance.entry_time if attendance else None,
            "exit_time": attendance.exit_time if attendance else None,
            "total_duration": str(attendance.total_duration) if attendance and attendance.total_duration else None
        })

    return attendance_data

@router.get("/students/{student_id}/tasks")
async def get_student_tasks(
    student_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get tasks for a specific student"""
    from app.models.student import StudentTask

    # Verify student belongs to current admin
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.admin_id == current_admin.user_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    tasks = db.query(StudentTask).filter(
        StudentTask.student_id == student.id
    ).order_by(StudentTask.created_at.desc()).offset(skip).limit(limit).all()

    return tasks

@router.post("/students/{student_id}/tasks")
async def create_student_task(
    student_id: str,
    task_data: dict,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Create a task for a specific student"""
    from app.models.student import StudentTask

    # Verify student belongs to current admin
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.admin_id == current_admin.user_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    task = StudentTask(
        student_id=student.id,
        **task_data
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task

@router.get("/analytics/dashboard")
async def get_dashboard_analytics(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get comprehensive dashboard analytics"""
    from app.models.student import StudentAttendance, StudentMessage
    from datetime import datetime, timedelta

    # Get basic stats
    total_students = db.query(Student).filter(Student.admin_id == current_admin.user_id).count()

    # Get present students (checked in today)
    today = datetime.utcnow().date()
    present_students = db.query(StudentAttendance).filter(
        StudentAttendance.admin_id == current_admin.user_id,
        func.date(StudentAttendance.entry_time) == today,
        StudentAttendance.exit_time.is_(None)
    ).count()

    # Get admin details for total seats
    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
    total_seats = admin_details.total_seats if admin_details else 0

    # Get pending bookings
    pending_bookings = db.query(SeatBooking).filter(
        SeatBooking.admin_id == current_admin.user_id,
        SeatBooking.status == "pending"
    ).count()

    # Calculate total revenue (sum of approved bookings)
    total_revenue = db.query(SeatBooking).filter(
        SeatBooking.admin_id == current_admin.user_id,
        SeatBooking.status.in_(["approved", "active"])
    ).with_entities(func.sum(SeatBooking.amount)).scalar() or 0

    # Get monthly revenue (current month)
    current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue = db.query(SeatBooking).filter(
        SeatBooking.admin_id == current_admin.user_id,
        SeatBooking.status.in_(["approved", "active"]),
        SeatBooking.created_at >= current_month_start
    ).with_entities(func.sum(SeatBooking.amount)).scalar() or 0

    # Get recent messages count
    recent_messages = db.query(StudentMessage).filter(
        StudentMessage.admin_id == current_admin.user_id,
        StudentMessage.created_at >= datetime.utcnow() - timedelta(days=7)
    ).count()

    # Calculate growth percentage (compare with last month)
    last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
    last_month_revenue = db.query(SeatBooking).filter(
        SeatBooking.admin_id == current_admin.user_id,
        SeatBooking.status.in_(["approved", "active"]),
        SeatBooking.created_at >= last_month_start,
        SeatBooking.created_at < current_month_start
    ).with_entities(func.sum(SeatBooking.amount)).scalar() or 0

    growth_percentage = 0
    if last_month_revenue > 0:
        growth_percentage = ((float(monthly_revenue) - float(last_month_revenue)) / float(last_month_revenue)) * 100

    return {
        "library_stats": {
            "total_students": total_students,
            "present_students": present_students,
            "total_seats": total_seats,
            "available_seats": total_seats - present_students,
            "pending_bookings": pending_bookings,
            "total_revenue": float(total_revenue)
        },
        "recent_messages": recent_messages,
        "monthly_revenue": float(monthly_revenue),
        "growth_percentage": round(growth_percentage, 2)
    }

@router.get("/analytics/attendance-trends")
async def get_attendance_trends(
    days: int = 30,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get attendance trends for the last N days"""
    from app.models.student import StudentAttendance
    from datetime import datetime, timedelta

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)

    # Get daily attendance counts
    attendance_data = []
    current_date = start_date

    while current_date <= end_date:
        daily_count = db.query(StudentAttendance).filter(
            StudentAttendance.admin_id == current_admin.user_id,
            func.date(StudentAttendance.entry_time) == current_date
        ).count()

        attendance_data.append({
            "date": current_date.isoformat(),
            "count": daily_count
        })

        current_date += timedelta(days=1)

    return attendance_data

@router.get("/analytics/revenue-trends")
async def get_revenue_trends(
    months: int = 12,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get revenue trends for the last N months"""
    from datetime import datetime, timedelta
    import calendar

    revenue_data = []
    current_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    for i in range(months):
        # Calculate month start and end
        month_start = current_date - timedelta(days=30 * i)
        month_start = month_start.replace(day=1)

        # Get last day of month
        last_day = calendar.monthrange(month_start.year, month_start.month)[1]
        month_end = month_start.replace(day=last_day, hour=23, minute=59, second=59)

        # Get revenue for this month
        monthly_revenue = db.query(SeatBooking).filter(
            SeatBooking.admin_id == current_admin.user_id,
            SeatBooking.status.in_(["approved", "active"]),
            SeatBooking.created_at >= month_start,
            SeatBooking.created_at <= month_end
        ).with_entities(func.sum(SeatBooking.amount)).scalar() or 0

        revenue_data.append({
            "month": month_start.strftime("%Y-%m"),
            "revenue": float(monthly_revenue)
        })

    return list(reversed(revenue_data))

@router.get("/subscription-plans", response_model=List[SubscriptionPlanResponse])
async def get_admin_subscription_plans(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get all subscription plans for the current admin's library"""
    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
    if not admin_details:
        raise HTTPException(status_code=404, detail="Admin details not found")
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.library_id == admin_details.id).all()
    return plans