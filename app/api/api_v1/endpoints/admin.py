from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from sqlalchemy.exc import IntegrityError
from typing import List
from fastapi.responses import StreamingResponse, Response
import io
import openpyxl

from app.database import get_db
from app.auth.dependencies import get_current_admin
from app.schemas.admin import (
    AdminDetailsCreate,
    AdminDetailsUpdate,
    AdminDetailsResponse,
    LibraryStats,
    DashboardStats,
    AttendanceTrendDay,
    RevenueTrendMonth,
    AdminAttendanceRecord,
    AdminRevenueItem,
    AdminActivityItem,
    AdminStudentAttendanceRecord,
    StudentAttendanceRecordDetail,
    AdminStudentSubscriptionExtend,
)
from app.schemas.student import StudentResponse, StudentCreate, StudentUpdate, StudentTaskResponse
from app.schemas.subscription import SubscriptionPlanResponse
from app.schemas.common import PaginatedResponse
from app.models.admin import AdminUser, AdminDetails
from app.models.student import Student
from app.models.booking import SeatBooking
from app.models.subscription import SubscriptionPlan
from app.auth.jwt import get_password_hash
from app.core.cache import (
    cached,
    admin_dashboard_key,
    admin_attendance_trends_key,
    admin_revenue_trends_key,
    invalidate_student_dashboard,
    invalidate_admin_caches,
)
import logging
from app.services.email_queue_service import enqueue_email_job, enqueue_generic_email_job
from app.schemas.qr_transfer import (
    AdminScanRequest,
    TransferInitiateRequest,
    TransferPaymentConfirmRequest,
)
from app.services.qr_transfer_service import (
    resolve_student_from_qr_token,
    build_student_scan_summary,
    initiate_transfer,
    complete_transfer_payment,
    list_transfer_requests,
    deactivate_qr_token,
)
from decimal import Decimal

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_referral_code(value):
    """Store blank referral codes as NULL to avoid unique collisions on empty string."""
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return value

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
    
    create_data = details.model_dump(exclude={"user_id"})
    create_data["referral_code"] = _normalize_referral_code(create_data.get("referral_code"))

    admin_details = AdminDetails(
        user_id=current_admin.user_id,
        **create_data
    )
    
    db.add(admin_details)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "admin_details_referral_code_key" in str(exc.orig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Referral code already exists. Please use a different code."
            ) from exc
        raise
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
        bank_account_holder_name=admin_details.bank_account_holder_name,
        bank_account_number=admin_details.bank_account_number,
        bank_ifsc_code=admin_details.bank_ifsc_code,
        bank_name=admin_details.bank_name,
        bank_branch_name=admin_details.bank_branch_name,
        razorpay_linked_account_id=admin_details.razorpay_linked_account_id,
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
    if "referral_code" in update_data:
        update_data["referral_code"] = _normalize_referral_code(update_data.get("referral_code"))
    for field, value in update_data.items():
        setattr(admin_details, field, value)
    
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "admin_details_referral_code_key" in str(exc.orig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Referral code already exists. Please use a different code."
            ) from exc
        raise
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
        bank_account_holder_name=admin_details.bank_account_holder_name,
        bank_account_number=admin_details.bank_account_number,
        bank_ifsc_code=admin_details.bank_ifsc_code,
        bank_name=admin_details.bank_name,
        bank_branch_name=admin_details.bank_branch_name,
        razorpay_linked_account_id=admin_details.razorpay_linked_account_id,
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

    from app.services.library_seat_reuse_service import (
        assign_next_freed_seat_to_student,
        invalidate_seat_caches,
    )

    if assign_next_freed_seat_to_student(db, student):
        db.commit()
        db.refresh(student)
    invalidate_seat_caches(db, student)
    
    from app.models.admin import AdminDetails
    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
    library_name = admin_details.library_name if admin_details else "your library"
    enqueue_email_job(
        db=db,
        email_type="student_password_setup",
        to_email=student.email,
        payload={
            "student_id": student.student_id,
            "mobile_no": student.mobile_no,
            "token": password_setup_token,
            "library_name": library_name,
            "base_url": str(request.base_url),
        },
    )
    
    return student

@router.get(
    "/students",
    response_model=PaginatedResponse[StudentResponse],
    summary="List students (paginated)",
)
async def get_students(
    skip: int = 0,
    limit: int = 20,
    order: str = None,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get paginated list of students for the current admin. Use skip/limit for pagination (max page_size 100)."""
    limit = min(max(1, limit), 100)
    try:
        base_query = db.query(Student).filter(Student.admin_id == current_admin.user_id)
        total = base_query.count()

        if order == "created_at:desc":
            base_query = base_query.order_by(Student.created_at.desc())
        elif order == "created_at:asc":
            base_query = base_query.order_by(Student.created_at.asc())
        elif order == "name:asc":
            base_query = base_query.order_by(Student.name.asc())
        elif order == "name:desc":
            base_query = base_query.order_by(Student.name.desc())

        students = base_query.offset(skip).limit(limit).all()
        page = (skip // limit) + 1 if limit else 1
        return PaginatedResponse(
            items=students,
            total=total,
            page=page,
            page_size=limit,
        )
    except Exception as e:
        logger.exception("Error in get_students")
        return PaginatedResponse(items=[], total=0, page=1, page_size=limit)

# Important: This specific route must come BEFORE the dynamic route with {student_id}
@router.get("/students/template")
def download_student_template(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Download CSV template for bulk student upload"""
    csv_content = """Name*,Email*,Mobile Number*,Address*,Subscription Start (YYYY-MM-DD)*,Subscription End (YYYY-MM-DD)*,Is Shift Student (true/false)*,Shift Time (HH:mm - HH:mm)
Sandeep Kumar,sandeep@example.com,1234567890,123 Main St,2025-03-01,2025-06-01,false,
Anshul Kumar,anshul@example.com,0987654321,456 Oak Ave,2025-03-01,2025-06-01,true,2:00 PM - 6:00 PM"""
    
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


@router.post("/students/{student_id}/extend-subscription")
async def extend_student_subscription_admin(
    student_id: str,
    body: AdminStudentSubscriptionExtend,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Extend subscription after cash (or manual) payment; amount is recorded as paid SeatBooking revenue."""
    from decimal import Decimal
    from app.services.subscription_cash_revenue_service import apply_cash_subscription_extension

    student = (
        db.query(Student)
        .filter(Student.id == student_id, Student.admin_id == current_admin.user_id)
        .first()
    )
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    library = (
        db.query(AdminDetails)
        .filter(AdminDetails.user_id == current_admin.user_id)
        .first()
    )
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library details not found")

    try:
        amt = Decimal(str(body.amount)) if body.amount is not None else None
        _, _, new_end = apply_cash_subscription_extension(
            db,
            student=student,
            library=library,
            plan_id=body.plan_id,
            amount_override=amt,
        )
        db.commit()
        db.refresh(student)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    invalidate_student_dashboard(str(student.auth_user_id))
    invalidate_admin_caches(str(current_admin.user_id))

    return {
        "success": True,
        "subscription_end": new_end.isoformat(),
        "message": "Subscription extended and revenue recorded.",
    }


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

@router.get(
    "/students/{student_id}/attendance",
    response_model=PaginatedResponse[AdminStudentAttendanceRecord],
    summary="List student attendance (paginated)",
)
async def get_student_attendance(
    student_id: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get paginated attendance records for a specific student."""
    from app.models.student import StudentAttendance

    student = db.query(Student).filter(
        Student.id == student_id,
        Student.admin_id == current_admin.user_id,
    ).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    base = db.query(StudentAttendance).filter(
        StudentAttendance.student_id == student.auth_user_id
    ).order_by(StudentAttendance.entry_time.desc())
    total = base.count()
    limit = min(max(1, limit), 100)
    records = base.offset(skip).limit(limit).all()

    items = [
        AdminStudentAttendanceRecord(
            id=str(r.id),
            student_id=student.student_id,
            student_name=student.name,
            email=student.email,
            entry_time=r.entry_time,
            exit_time=r.exit_time,
            total_duration=str(r.total_duration) if r.total_duration else None,
            latitude=r.latitude,
            longitude=r.longitude,
            created_at=r.created_at,
            student=StudentAttendanceRecordDetail(
                student_id=student.student_id,
                name=student.name,
                email=student.email,
            ),
        )
        for r in records
    ]
    page = (skip // limit) + 1 if limit else 1
    return PaginatedResponse(items=items, total=total, page=page, page_size=limit)

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

@router.get(
    "/students/{student_id}/tasks",
    response_model=PaginatedResponse[StudentTaskResponse],
    summary="List student tasks (paginated)",
)
async def get_student_tasks(
    student_id: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get paginated tasks for a specific student."""
    from app.models.student import StudentTask

    student = db.query(Student).filter(
        Student.id == student_id,
        Student.admin_id == current_admin.user_id,
    ).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    base = db.query(StudentTask).filter(StudentTask.student_id == student.id).order_by(
        StudentTask.created_at.desc()
    )
    total = base.count()
    limit = min(max(1, limit), 100)
    tasks = base.offset(skip).limit(limit).all()
    page = (skip // limit) + 1 if limit else 1
    return PaginatedResponse(items=tasks, total=total, page=page, page_size=limit)

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
    invalidate_student_dashboard(str(student.auth_user_id))

    return task

@router.get(
    "/analytics/dashboard",
    response_model=DashboardStats,
    summary="Dashboard analytics (cached)",
)
@cached(ttl=60, key_builder=lambda db, current_admin: admin_dashboard_key(str(current_admin.user_id)))
async def get_dashboard_analytics(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get comprehensive dashboard analytics. Stable response shape for frontend caching."""
    from app.models.student import StudentAttendance, StudentMessage
    from datetime import datetime, timedelta

    try:
        today = datetime.utcnow().date()
        current_month_start = datetime.utcnow().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

        result = (
            db.query(
                func.count(Student.id).label("total_students"),
                func.count(
                    case(
                        (func.date(StudentAttendance.entry_time) == today, 1),
                        else_=None,
                    )
                ).label("present_students"),
                func.sum(
                    case(
                        (
                            (SeatBooking.payment_status == "paid")
                            & (SeatBooking.admin_id == current_admin.user_id),
                            SeatBooking.amount,
                        ),
                        else_=0,
                    )
                ).label("total_revenue"),
                func.sum(
                    case(
                        (
                            (SeatBooking.payment_status == "paid")
                            & (SeatBooking.payment_date >= current_month_start)
                            & (SeatBooking.admin_id == current_admin.user_id),
                            SeatBooking.amount,
                        ),
                        else_=0,
                    )
                ).label("monthly_revenue"),
                func.sum(
                    case(
                        (
                            (SeatBooking.payment_status == "paid")
                            & (SeatBooking.payment_date >= last_month_start)
                            & (SeatBooking.payment_date < current_month_start)
                            & (SeatBooking.admin_id == current_admin.user_id),
                            SeatBooking.amount,
                        ),
                        else_=0,
                    )
                ).label("last_month_revenue"),
                func.count(
                    case(
                        (
                            (SeatBooking.status == "pending")
                            & (SeatBooking.admin_id == current_admin.user_id),
                            1,
                        ),
                        else_=None,
                    )
                ).label("pending_bookings"),
            )
            .outerjoin(
                StudentAttendance,
                (StudentAttendance.student_id == Student.id)
                & (func.date(StudentAttendance.entry_time) == today)
                & (StudentAttendance.exit_time.is_(None)),
            )
            .outerjoin(
                SeatBooking,
                SeatBooking.admin_id == current_admin.user_id,
            )
            .filter(Student.admin_id == current_admin.user_id)
            .first()
        )

        admin_details = (
            db.query(AdminDetails)
            .filter(AdminDetails.user_id == current_admin.user_id)
            .first()
        )

        monthly_revenue = float(result.monthly_revenue or 0)
        last_month_revenue = float(result.last_month_revenue or 0)
        growth_percentage = 0.0
        if last_month_revenue > 0:
            growth_percentage = (
                (monthly_revenue - last_month_revenue) / last_month_revenue
            ) * 100

        recent_messages = (
            db.query(StudentMessage)
            .filter(
                StudentMessage.admin_id == current_admin.user_id,
                StudentMessage.created_at >= datetime.utcnow() - timedelta(days=7),
            )
            .count()
        )

        total_students = result.total_students or 0
        present_students = result.present_students or 0
        total_seats = admin_details.total_seats if admin_details else 0

        return DashboardStats(
            library_stats=LibraryStats(
                total_students=total_students,
                present_students=present_students,
                total_seats=total_seats,
                available_seats=total_seats - present_students,
                pending_bookings=result.pending_bookings or 0,
                total_revenue=float(result.total_revenue or 0),
            ),
            recent_messages=recent_messages,
            monthly_revenue=monthly_revenue,
            growth_percentage=round(growth_percentage, 2),
        )
    except Exception as e:
        logger.error("Error in dashboard analytics", extra={"error": str(e)})
        return DashboardStats(
            library_stats=LibraryStats(
                total_students=0,
                present_students=0,
                total_seats=0,
                available_seats=0,
                pending_bookings=0,
                total_revenue=0.0,
            ),
            recent_messages=0,
            monthly_revenue=0.0,
            growth_percentage=0.0,
        )

@router.get(
    "/analytics/attendance-trends",
    response_model=List[AttendanceTrendDay],
    summary="Attendance trends by day (cached)",
)
@cached(ttl=60, key_builder=lambda days, db, current_admin: admin_attendance_trends_key(str(current_admin.user_id), days))
async def get_attendance_trends(
    days: int = 30,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get attendance trends for the last N days. Stable response shape: list of {date, count}."""
    from app.models.student import StudentAttendance
    from datetime import datetime, timedelta

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)
    attendance_data: List[AttendanceTrendDay] = []
    current_date = start_date

    while current_date <= end_date:
        daily_count = db.query(StudentAttendance).filter(
            StudentAttendance.admin_id == current_admin.user_id,
            func.date(StudentAttendance.entry_time) == current_date,
        ).count()
        attendance_data.append(
            AttendanceTrendDay(date=current_date.isoformat(), count=daily_count)
        )
        current_date += timedelta(days=1)

    return attendance_data

@router.get(
    "/analytics/revenue-trends",
    response_model=List[RevenueTrendMonth],
    summary="Revenue trends by month (cached)",
)
@cached(ttl=60, key_builder=lambda months, db, current_admin: admin_revenue_trends_key(str(current_admin.user_id), months))
async def get_revenue_trends(
    months: int = 12,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get revenue trends for the last N months. Stable response shape: list of {month, revenue}."""
    from datetime import datetime, timedelta
    import calendar

    revenue_data: List[RevenueTrendMonth] = []
    current_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    for i in range(months):
        month_start = current_date - timedelta(days=30 * i)
        month_start = month_start.replace(day=1)
        last_day = calendar.monthrange(month_start.year, month_start.month)[1]
        month_end = month_start.replace(day=last_day, hour=23, minute=59, second=59)

        monthly_revenue = db.query(SeatBooking).filter(
            SeatBooking.admin_id == current_admin.user_id,
            SeatBooking.payment_status == "paid",
            SeatBooking.payment_date >= month_start,
            SeatBooking.payment_date <= month_end,
        ).with_entities(func.sum(SeatBooking.amount)).scalar() or 0

        revenue_data.append(
            RevenueTrendMonth(month=month_start.strftime("%Y-%m"), revenue=float(monthly_revenue))
        )

    return list(reversed(revenue_data))

@router.get(
    "/subscription-plans",
    response_model=PaginatedResponse[SubscriptionPlanResponse],
    summary="List subscription plans (paginated)",
)
async def get_admin_subscription_plans(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get paginated subscription plans for the current admin's library."""
    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == current_admin.user_id).first()
    if not admin_details:
        raise HTTPException(status_code=404, detail="Admin details not found")
    # Keep list consistent with soft-delete behavior in subscription endpoints.
    # Deleted plans are marked is_active=False, so exclude them from admin listing.
    base = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.library_id == admin_details.id,
        SubscriptionPlan.is_active == True,
    )
    total = base.count()
    limit = min(max(1, limit), 100)
    plans = base.offset(skip).limit(limit).all()
    page = (skip // limit) + 1 if limit else 1
    return PaginatedResponse(items=plans, total=total, page=page, page_size=limit)

@router.post("/test-email")
async def test_email(
    request: dict,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Test email functionality"""
    try:
        email = request.get("email")
        if not email:
            return {
                "success": False,
                "message": "Email address is required",
                "error": "Missing email parameter"
            }
        
        # Test basic email sending
        delivery_id = enqueue_generic_email_job(
            db=db,
            to_email=email,
            subject="Test Email from Library Management System",
            body="This is a test email to verify email functionality is working correctly.",
            html_body="<h2>Test Email</h2><p>This is a test email to verify email functionality is working correctly.</p>",
        )
        return {
            "success": True,
            "message": "Test email queued successfully",
            "delivery_id": str(delivery_id),
        }
            
    except Exception as e:
        return {
            "success": False,
            "message": "Error testing email",
            "error": str(e)
        }

@router.get(
    "/attendance",
    response_model=PaginatedResponse[AdminAttendanceRecord],
    summary="List attendance for a date (paginated)",
)
async def get_admin_attendance(
    date: str = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get paginated attendance data for a specific date or today."""
    from app.models.student import StudentAttendance
    from datetime import datetime

    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD",
            )
    else:
        target_date = datetime.utcnow().date()

    students = db.query(Student).filter(Student.admin_id == current_admin.user_id).all()
    all_records: List[AdminAttendanceRecord] = []
    for student in students:
        attendance = db.query(StudentAttendance).filter(
            StudentAttendance.student_id == student.auth_user_id,
            func.date(StudentAttendance.entry_time) == target_date,
        ).first()
        if attendance:
            all_records.append(
                AdminAttendanceRecord(
                    id=str(student.id),
                    student_id=student.student_id,
                    student_name=student.name,
                    email=student.email,
                    mobile=student.mobile_no,
                    entry_time=attendance.entry_time,
                    exit_time=attendance.exit_time,
                    total_duration=str(attendance.total_duration) if attendance.total_duration else None,
                    status="Present" if not attendance.exit_time else "Completed",
                )
            )
    all_records.sort(key=lambda x: x.student_id)
    total = len(all_records)
    limit = min(max(1, limit), 100)
    page = (skip // limit) + 1 if limit else 1
    items = all_records[skip : skip + limit]
    return PaginatedResponse(items=items, total=total, page=page, page_size=limit)

@router.get(
    "/revenue",
    response_model=PaginatedResponse[AdminRevenueItem],
    summary="List revenue/transactions (paginated)",
)
async def get_admin_revenue(
    filter: str = "all",
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get paginated revenue/transaction data. Use filter: today|week|month|all."""
    from datetime import datetime, timedelta
    import re

    base_query = db.query(SeatBooking).filter(
        SeatBooking.admin_id == current_admin.user_id,
        SeatBooking.payment_status == "paid",
    )
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

    base_query = base_query.order_by(SeatBooking.payment_date.desc())
    total = base_query.count()
    limit = min(max(1, limit), 100)
    transactions = base_query.offset(skip).limit(limit).all()

    def _revenue_source(booking: SeatBooking) -> str:
        pm = (booking.payment_method or "").strip().lower()
        pref = (booking.payment_reference or "").strip().lower()
        purpose = (booking.purpose or "").strip().lower()
        if pm == "cash":
            if pref == "cash_subscription_renewal_removal_request" or "removal request" in purpose:
                return "cash_removal_request"
            if pref == "cash_subscription_renewal" or "renewal" in purpose:
                return "cash_extension"
            return "cash_other"
        if pm in {"razorpay", "online", "upi", "card", "netbanking"}:
            return "online"
        return "other"

    def _student_display_id(booking: SeatBooking) -> str | None:
        if booking.student and booking.student.student_id:
            return booking.student.student_id
        if booking.student_id:
            return str(booking.student_id)
        text = (booking.payment_reference or "")
        m = re.search(r"[A-Za-z]+[0-9]+", text)
        return m.group(0) if m else None

    items = [
        AdminRevenueItem(
            id=str(b.id),
            student_id=_student_display_id(b),
            student_name=b.name or (b.student.name if b.student else "Anonymous"),
            email=b.email or (b.student.email if b.student else None),
            mobile=b.mobile or (b.student.mobile_no if b.student else None),
            amount=float(b.amount) if b.amount else 0.0,
            subscription_months=b.subscription_months or 1,
            payment_method=b.payment_method or "Online",
            payment_status=b.payment_status or "paid",
            transaction_id=getattr(b, "transaction_id", None) or b.payment_reference or f"TXN_{b.id}",
            created_at=b.created_at,
            payment_date=b.payment_date or b.created_at,
            status=b.status or "completed",
            revenue_source=_revenue_source(b),
            purpose=b.purpose,
        )
        for b in transactions
    ]
    page = (skip // limit) + 1 if limit else 1
    return PaginatedResponse(items=items, total=total, page=page, page_size=limit)

@router.get(
    "/recent-activities",
    response_model=PaginatedResponse[AdminActivityItem],
    summary="List recent activities (paginated)",
)
async def get_recent_activities(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get paginated recent activities for admin dashboard (last 7 days)."""
    from app.models.student import StudentAttendance, StudentMessage
    from datetime import datetime, timedelta

    activities: List[AdminActivityItem] = []
    try:
        recent_students = db.query(Student).filter(
            Student.admin_id == current_admin.user_id,
            Student.created_at >= datetime.utcnow() - timedelta(days=7),
        ).order_by(Student.created_at.desc()).limit(50).all()
        for student in recent_students:
            activities.append(
                AdminActivityItem(
                    id=f"student_{student.id}",
                    type="student_registration",
                    title="New student registration",
                    description=f"{student.name} registered",
                    timestamp=student.created_at,
                    icon="👨‍🎓",
                    color="emerald",
                )
            )

        recent_bookings = db.query(SeatBooking).filter(
            SeatBooking.admin_id == current_admin.user_id,
            SeatBooking.created_at >= datetime.utcnow() - timedelta(days=7),
        ).order_by(SeatBooking.created_at.desc()).limit(50).all()
        for booking in recent_bookings:
            student_name = booking.name or (booking.student.name if booking.student else "Anonymous")
            activities.append(
                AdminActivityItem(
                    id=f"booking_{booking.id}",
                    type="booking_request",
                    title="Seat booking request",
                    description=f"{student_name} requested a seat",
                    timestamp=booking.created_at,
                    icon="🪑",
                    color="blue",
                )
            )

        try:
            recent_messages = db.query(StudentMessage).filter(
                StudentMessage.admin_id == current_admin.user_id,
                StudentMessage.created_at >= datetime.utcnow() - timedelta(days=7),
                StudentMessage.sender_type == "student",
            ).order_by(StudentMessage.created_at.desc()).limit(50).all()
            for message in recent_messages:
                activities.append(
                    AdminActivityItem(
                        id=f"message_{message.id}",
                        type="student_message",
                        title="Message from student",
                        description=f"{message.student_name} sent a message",
                        timestamp=message.created_at,
                        icon="💬",
                        color="purple",
                    )
                )
        except Exception as e:
            logger.warning("Could not query StudentMessage: %s", e)

        try:
            recent_attendance = db.query(StudentAttendance).filter(
                StudentAttendance.admin_id == current_admin.user_id,
                StudentAttendance.entry_time >= datetime.utcnow() - timedelta(days=7),
            ).order_by(StudentAttendance.entry_time.desc()).limit(50).all()
            for attendance in recent_attendance:
                name = attendance.student.name if attendance.student else "Student"
                activities.append(
                    AdminActivityItem(
                        id=f"attendance_{attendance.id}",
                        type="student_checkin",
                        title="Student checked in",
                        description=f"{name} checked in",
                        timestamp=attendance.entry_time,
                        icon="✅",
                        color="green",
                    )
                )
        except Exception as e:
            logger.warning("Could not query StudentAttendance: %s", e)

        recent_booking_updates = db.query(SeatBooking).filter(
            SeatBooking.admin_id == current_admin.user_id,
            SeatBooking.updated_at >= datetime.utcnow() - timedelta(days=7),
            SeatBooking.status.in_(["approved", "rejected"]),
        ).order_by(SeatBooking.updated_at.desc()).limit(50).all()
        for booking in recent_booking_updates:
            student_name = booking.name or (booking.student.name if booking.student else "Anonymous")
            status_text = "approved" if booking.status == "approved" else "rejected"
            activities.append(
                AdminActivityItem(
                    id=f"booking_update_{booking.id}",
                    type="booking_update",
                    title=f"Booking {status_text}",
                    description=f"{student_name}'s booking was {status_text}",
                    timestamp=booking.updated_at,
                    icon="✅" if booking.status == "approved" else "❌",
                    color="green" if booking.status == "approved" else "red",
                )
            )

        activities.sort(key=lambda x: x.timestamp, reverse=True)
        total = len(activities)
        limit = min(max(1, limit), 100)
        page = (skip // limit) + 1 if limit else 1
        items = activities[skip : skip + limit]
        return PaginatedResponse(items=items, total=total, page=page, page_size=limit)
    except Exception as e:
        logger.exception("Error fetching recent activities")
        return PaginatedResponse(items=[], total=0, page=1, page_size=min(max(1, limit), 100))


@router.post("/scan-student-qr")
async def scan_student_qr(
    body: AdminScanRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Scan and resolve a student QR token into common student details."""
    student = resolve_student_from_qr_token(db, body.qr_token)
    summary = build_student_scan_summary(db, student)
    summary["can_transfer"] = str(student.admin_id) != str(current_admin.user_id)
    return summary


@router.post("/transfers/initiate")
async def initiate_student_transfer(
    body: TransferInitiateRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Initiate transfer and send payment link email to student."""
    if body.student_uuid:
        student = db.query(Student).filter(Student.id == body.student_uuid).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    elif body.qr_token:
        student = resolve_student_from_qr_token(db, body.qr_token)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="qr_token or student_uuid is required")
    if str(student.admin_id) == str(current_admin.user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student already belongs to your library")

    transfer = initiate_transfer(
        db,
        target_admin=current_admin,
        student=student,
        amount=Decimal(str(body.amount)),
        plan_id=body.plan_id,
    )
    if body.qr_token:
        deactivate_qr_token(db, body.qr_token)
    return {
        "transfer_id": str(transfer.id),
        "status": transfer.status,
        "payment_reference": transfer.payment_reference,
        "payment_link": transfer.payment_link,
        "message": "Transfer initiated and payment link sent to student email.",
    }


@router.post("/transfers/confirm-payment")
async def confirm_student_transfer_payment(
    body: TransferPaymentConfirmRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Complete transfer after payment confirmation."""
    transfer = complete_transfer_payment(db, body.payment_reference)
    if str(transfer.target_admin_id) != str(current_admin.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to complete this transfer")
    return {
        "transfer_id": str(transfer.id),
        "status": transfer.status,
        "student_id": str(transfer.student_id),
        "source_admin_id": str(transfer.source_admin_id),
        "target_admin_id": str(transfer.target_admin_id),
        "amount": float(transfer.amount),
    }


@router.get("/transfers")
async def get_admin_transfer_requests(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """List transfers targeted to current admin."""
    transfers = list_transfer_requests(db, current_admin.user_id)
    return [
        {
            "transfer_id": str(item.id),
            "student_id": str(item.student_id),
            "source_admin_id": str(item.source_admin_id),
            "target_admin_id": str(item.target_admin_id),
            "status": item.status,
            "amount": float(item.amount),
            "payment_reference": item.payment_reference,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in transfers
    ]