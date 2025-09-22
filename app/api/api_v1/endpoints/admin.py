from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from fastapi.responses import StreamingResponse, Response
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
        admin_details.admin_name.strip() and
        admin_details.library_name and 
        admin_details.library_name.strip() and
        admin_details.mobile_no and 
        admin_details.mobile_no.strip() and
        admin_details.address and 
        admin_details.address.strip() and
        admin_details.total_seats and 
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
    
    # Calculate total revenue (sum of paid bookings only)
    total_revenue = db.query(SeatBooking).filter(
        SeatBooking.admin_id == current_admin.user_id,
        SeatBooking.payment_status == "paid"
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
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Create a new student and send login credentials email"""
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
    
    # Generate password setup token for email
    import uuid
    password_setup_token = str(uuid.uuid4())
    
    # Create student
    hashed_password = get_password_hash(student_data.password)
    student = Student(
        student_id=student_id,
        admin_id=current_admin.user_id,
        hashed_password=hashed_password,
        password_reset_token=password_setup_token,
        **student_data.model_dump(exclude={"password", "admin_id"})
    )
    
    db.add(student)
    db.commit()
    db.refresh(student)
    
    # Send password setup email to student
    def send_student_password_setup_email(email: str, student_id: str, mobile_no: str, token: str, admin_id: str):
        from app.services.email_service import email_service
        from app.models.admin import AdminDetails
        
        admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == admin_id).first()
        library_name = admin_details.library_name if admin_details else "your library"
        
        result = email_service.send_student_password_setup_email(
            email, student_id, mobile_no, token, library_name, str(request.base_url)
        )
        
        if result["success"]:
            print(f"[EMAIL] Sent password setup email to student {email}")
        else:
            print(f"[EMAIL ERROR] Could not send student password setup email: {result['error']}")
            # Log additional info for debugging
            print(f"[EMAIL DEBUG] Student: {student_id}, Library: {library_name}, Token: {token[:10]}...")
    
    background_tasks.add_task(send_student_password_setup_email, student.email, student.student_id, student.mobile_no, password_setup_token, current_admin.user_id)
    
    return student

@router.get("/students", response_model=List[StudentResponse])
async def get_students(
    skip: int = 0,
    limit: int = 100,
    order: str = None,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get all students for the current admin"""
    try:
        query = db.query(Student).filter(Student.admin_id == current_admin.user_id)
        
        # Handle ordering if provided
        if order:
            if order == "created_at:desc":
                query = query.order_by(Student.created_at.desc())
            elif order == "created_at:asc":
                query = query.order_by(Student.created_at.asc())
            elif order == "name:asc":
                query = query.order_by(Student.name.asc())
            elif order == "name:desc":
                query = query.order_by(Student.name.desc())
        
        students = query.offset(skip).limit(limit).all()
        
        return students
    except Exception as e:
        print(f"Error in get_students: {e}")
        # Return empty list if there's an error
        return []

# Important: This specific route must come BEFORE the dynamic route with {student_id}
@router.get("/students/template")
def download_student_template(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Download CSV template for bulk student upload"""
    csv_content = """Name*,Email*,Mobile Number*,Address*,Subscription Start (YYYY-MM-DD)*,Subscription End (YYYY-MM-DD)*,Is Shift Student (true/false)*,Shift Time (HH:mm - HH:mm)
John Doe,john@example.com,1234567890,123 Main St,2025-03-01,2025-06-01,false,
Jane Smith,jane@example.com,0987654321,456 Oak Ave,2025-03-01,2025-06-01,true,2:00 PM - 6:00 PM"""
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=student_template.csv",
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
    ).order_by(StudentAttendance.entry_time.desc()).offset(skip).limit(limit).all()

    # Format the response to include student information
    formatted_records = []
    for record in attendance_records:
        formatted_records.append({
            "id": str(record.id),
            "student_id": student.student_id,
            "student_name": student.name,
            "email": student.email,
            "entry_time": record.entry_time,
            "exit_time": record.exit_time,
            "total_duration": str(record.total_duration) if record.total_duration else None,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "created_at": record.created_at,
            "student": {
                "student_id": student.student_id,
                "name": student.name,
                "email": student.email
            }
        })

    print(f"Returning {len(formatted_records)} attendance records for student {student.student_id}")
    return formatted_records

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
    try:
        from app.models.student import StudentAttendance, StudentMessage
        from datetime import datetime, timedelta

        # Get basic stats
        total_students = db.query(Student).filter(Student.admin_id == current_admin.user_id).count()

        # Get present students (checked in today) - handle case where table might not exist
        today = datetime.utcnow().date()
        present_students = 0
        try:
            present_students = db.query(StudentAttendance).filter(
                StudentAttendance.admin_id == current_admin.user_id,
                func.date(StudentAttendance.entry_time) == today,
                StudentAttendance.exit_time.is_(None)
            ).count()
        except Exception as e:
            print(f"Warning: Could not query StudentAttendance: {e}")
            present_students = 0

        # Get admin details for total seats
        admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
        total_seats = admin_details.total_seats if admin_details else 0

        # Get pending bookings - handle case where table might not exist
        pending_bookings = 0
        try:
            pending_bookings = db.query(SeatBooking).filter(
                SeatBooking.admin_id == current_admin.user_id,
                SeatBooking.status == "pending"
            ).count()
        except Exception as e:
            print(f"Warning: Could not query SeatBooking: {e}")
            pending_bookings = 0

        # Calculate total revenue (sum of paid bookings only)
        total_revenue = 0
        try:
            total_revenue = db.query(SeatBooking).filter(
                SeatBooking.admin_id == current_admin.user_id,
                SeatBooking.payment_status == "paid"
            ).with_entities(func.sum(SeatBooking.amount)).scalar() or 0
        except Exception as e:
            print(f"Warning: Could not calculate total revenue: {e}")
            total_revenue = 0

        # Get monthly revenue (current month) - only paid bookings
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_revenue = 0
        try:
            monthly_revenue = db.query(SeatBooking).filter(
                SeatBooking.admin_id == current_admin.user_id,
                SeatBooking.payment_status == "paid",
                SeatBooking.payment_date >= current_month_start
            ).with_entities(func.sum(SeatBooking.amount)).scalar() or 0
        except Exception as e:
            print(f"Warning: Could not calculate monthly revenue: {e}")
            monthly_revenue = 0

        # Get recent messages count - handle case where table might not exist
        recent_messages = 0
        try:
            recent_messages = db.query(StudentMessage).filter(
                StudentMessage.admin_id == current_admin.user_id,
                StudentMessage.created_at >= datetime.utcnow() - timedelta(days=7)
            ).count()
        except Exception as e:
            print(f"Warning: Could not query StudentMessage: {e}")
            recent_messages = 0

        # Calculate growth percentage (compare with last month) - only paid bookings
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        last_month_revenue = 0
        try:
            last_month_revenue = db.query(SeatBooking).filter(
                SeatBooking.admin_id == current_admin.user_id,
                SeatBooking.payment_status == "paid",
                SeatBooking.payment_date >= last_month_start,
                SeatBooking.payment_date < current_month_start
            ).with_entities(func.sum(SeatBooking.amount)).scalar() or 0
        except Exception as e:
            print(f"Warning: Could not calculate last month revenue: {e}")
            last_month_revenue = 0

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
    except Exception as e:
        print(f"Error in dashboard analytics: {e}")
        # Return default values if there's an error
        return {
            "library_stats": {
                "total_students": 0,
                "present_students": 0,
                "total_seats": 0,
                "available_seats": 0,
                "pending_bookings": 0,
                "total_revenue": 0.0
            },
            "recent_messages": 0,
            "monthly_revenue": 0.0,
            "growth_percentage": 0.0
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

        # Get revenue for this month - only paid bookings
        monthly_revenue = db.query(SeatBooking).filter(
            SeatBooking.admin_id == current_admin.user_id,
            SeatBooking.payment_status == "paid",
            SeatBooking.payment_date >= month_start,
            SeatBooking.payment_date <= month_end
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

@router.post("/test-email")
async def test_email(
    request: dict,
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Test email functionality"""
    from app.services.email_service import email_service
    
    try:
        email = request.get("email")
        if not email:
            return {
                "success": False,
                "message": "Email address is required",
                "error": "Missing email parameter"
            }
        
        # Test basic email sending
        result = email_service.send_email(
            email,
            "Test Email from Library Management System",
            "This is a test email to verify email functionality is working correctly.",
            "<h2>Test Email</h2><p>This is a test email to verify email functionality is working correctly.</p>"
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "Test email sent successfully",
                "details": result
            }
        else:
            return {
                "success": False,
                "message": "Failed to send test email",
                "error": result["error"],
                "details": result
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": "Error testing email",
            "error": str(e)
        }

@router.get("/attendance")
async def get_admin_attendance(
    date: str = None,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get attendance data for a specific date or today"""
    try:
        from app.models.student import StudentAttendance
        from datetime import datetime, date as date_type
        
        # Parse date or use today
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )
        else:
            target_date = datetime.utcnow().date()
        
        # Get all students for this admin
        students = db.query(Student).filter(Student.admin_id == current_admin.user_id).all()
        print(f"Found {len(students)} students for admin {current_admin.user_id}")
        
        # Debug: Check all attendance records for this date
        all_attendance_for_date = db.query(StudentAttendance).filter(
            func.date(StudentAttendance.entry_time) == target_date
        ).all()
        print(f"Found {len(all_attendance_for_date)} total attendance records for {target_date}")
        
        attendance_data = []
        for student in students:
            # Check if student has attendance record for the target date
            attendance = db.query(StudentAttendance).filter(
                StudentAttendance.student_id == student.auth_user_id,
                func.date(StudentAttendance.entry_time) == target_date
            ).first()
            
            print(f"Student {student.student_id} ({student.name}): {'Has attendance' if attendance else 'No attendance'} for {target_date}")
            if attendance:
                print(f"  - Entry time: {attendance.entry_time}")
                print(f"  - Exit time: {attendance.exit_time}")
                print(f"  - Duration: {attendance.total_duration}")
            
            # Only include students who have attendance records (present or completed)
            if attendance:
                attendance_data.append({
                    "id": str(student.id),
                    "student_id": student.student_id,
                    "student_name": student.name,
                    "email": student.email,
                    "mobile": student.mobile_no,
                    "entry_time": attendance.entry_time,
                    "exit_time": attendance.exit_time,
                    "total_duration": str(attendance.total_duration) if attendance.total_duration else None,
                    "status": "Present" if not attendance.exit_time else "Completed"
                })
        
        # Sort by student_id for consistent ordering
        attendance_data.sort(key=lambda x: x['student_id'])
        
        print(f"Returning {len(attendance_data)} attendance records for {target_date}")
        return attendance_data
        
    except Exception as e:
        print(f"Error fetching attendance data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching attendance data: {str(e)}"
        )

@router.get("/revenue")
async def get_admin_revenue(
    filter: str = "all",
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get revenue/transaction data for admin"""
    try:
        from datetime import datetime, timedelta
        
        # Base query for paid bookings
        base_query = db.query(SeatBooking).filter(
            SeatBooking.admin_id == current_admin.user_id,
            SeatBooking.payment_status == "paid"
        )
        
        # Apply time filter
        now = datetime.utcnow()
        if filter == "today":
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            base_query = base_query.filter(SeatBooking.payment_date >= today_start)
        elif filter == "week":
            week_start = now - timedelta(days=7)
            base_query = base_query.filter(SeatBooking.payment_date >= week_start)
        elif filter == "month":
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            base_query = base_query.filter(SeatBooking.payment_date >= month_start)
        # "all" doesn't add any time filter
        
        # Get transactions
        transactions = base_query.order_by(SeatBooking.payment_date.desc()).all()
        
        revenue_data = []
        for booking in transactions:
            revenue_data.append({
                "id": str(booking.id),
                "student_id": booking.student_id,
                "student_name": booking.name or (booking.student.name if booking.student else "Anonymous"),
                "email": booking.email or (booking.student.email if booking.student else None),
                "mobile": booking.mobile or (booking.student.mobile_no if booking.student else None),
                "amount": float(booking.amount) if booking.amount else 0.0,
                "subscription_months": booking.subscription_months or 1,
                "payment_method": booking.payment_method or "Online",
                "payment_status": booking.payment_status or "paid",
                "transaction_id": booking.transaction_id or f"TXN_{booking.id}",
                "created_at": booking.created_at,
                "payment_date": booking.payment_date or booking.created_at,
                "status": booking.status or "completed"
            })
        
        return revenue_data
        
    except Exception as e:
        print(f"Error fetching revenue data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching revenue data: {str(e)}"
        )

@router.get("/recent-activities")
async def get_recent_activities(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get recent activities for admin dashboard"""
    try:
        from app.models.student import StudentAttendance, StudentMessage
        from datetime import datetime, timedelta
        
        activities = []
        
        # Get recent student registrations
        recent_students = db.query(Student).filter(
            Student.admin_id == current_admin.user_id,
            Student.created_at >= datetime.utcnow() - timedelta(days=7)
        ).order_by(Student.created_at.desc()).limit(5).all()
        
        for student in recent_students:
            activities.append({
                "id": f"student_{student.id}",
                "type": "student_registration",
                "title": "New student registration",
                "description": f"{student.name} registered",
                "timestamp": student.created_at,
                "icon": "👨‍🎓",
                "color": "emerald"
            })
        
        # Get recent bookings
        recent_bookings = db.query(SeatBooking).filter(
            SeatBooking.admin_id == current_admin.user_id,
            SeatBooking.created_at >= datetime.utcnow() - timedelta(days=7)
        ).order_by(SeatBooking.created_at.desc()).limit(5).all()
        
        for booking in recent_bookings:
            student_name = booking.name or (booking.student.name if booking.student else "Anonymous")
            activities.append({
                "id": f"booking_{booking.id}",
                "type": "booking_request",
                "title": "Seat booking request",
                "description": f"{student_name} requested a seat",
                "timestamp": booking.created_at,
                "icon": "🪑",
                "color": "blue"
            })
        
        # Get recent messages
        try:
            recent_messages = db.query(StudentMessage).filter(
                StudentMessage.admin_id == current_admin.user_id,
                StudentMessage.created_at >= datetime.utcnow() - timedelta(days=7),
                StudentMessage.sender_type == "student"
            ).order_by(StudentMessage.created_at.desc()).limit(5).all()
            
            for message in recent_messages:
                activities.append({
                    "id": f"message_{message.id}",
                    "type": "student_message",
                    "title": "Message from student",
                    "description": f"{message.student_name} sent a message",
                    "timestamp": message.created_at,
                    "icon": "💬",
                    "color": "purple"
                })
        except Exception as e:
            print(f"Warning: Could not query StudentMessage: {e}")
        
        # Get recent attendance (check-ins)
        try:
            recent_attendance = db.query(StudentAttendance).filter(
                StudentAttendance.admin_id == current_admin.user_id,
                StudentAttendance.entry_time >= datetime.utcnow() - timedelta(days=7)
            ).order_by(StudentAttendance.entry_time.desc()).limit(5).all()
            
            for attendance in recent_attendance:
                activities.append({
                    "id": f"attendance_{attendance.id}",
                    "type": "student_checkin",
                    "title": "Student checked in",
                    "description": f"{attendance.student.name} checked in",
                    "timestamp": attendance.entry_time,
                    "icon": "✅",
                    "color": "green"
                })
        except Exception as e:
            print(f"Warning: Could not query StudentAttendance: {e}")
        
        # Get recent booking approvals/rejections
        recent_booking_updates = db.query(SeatBooking).filter(
            SeatBooking.admin_id == current_admin.user_id,
            SeatBooking.updated_at >= datetime.utcnow() - timedelta(days=7),
            SeatBooking.status.in_(["approved", "rejected"])
        ).order_by(SeatBooking.updated_at.desc()).limit(5).all()
        
        for booking in recent_booking_updates:
            student_name = booking.name or (booking.student.name if booking.student else "Anonymous")
            status_text = "approved" if booking.status == "approved" else "rejected"
            activities.append({
                "id": f"booking_update_{booking.id}",
                "type": "booking_update",
                "title": f"Booking {status_text}",
                "description": f"{student_name}'s booking was {status_text}",
                "timestamp": booking.updated_at,
                "icon": "✅" if booking.status == "approved" else "❌",
                "color": "green" if booking.status == "approved" else "red"
            })
        
        # Sort all activities by timestamp (most recent first)
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Return only the requested number of activities
        return activities[:limit]
        
    except Exception as e:
        print(f"Error fetching recent activities: {e}")
        return []