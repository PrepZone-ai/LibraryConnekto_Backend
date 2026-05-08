from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
import math

from app.database import get_db
from app.auth.dependencies import get_current_admin, get_current_student, get_current_user_optional
from app.schemas.booking import SeatBookingCreate, SeatBookingUpdate, SeatBookingResponse, LibraryInfo, StudentSeatBookingCreate, PaymentConfirmation, RazorpayOrderCreate, RazorpayOrderResponse, RazorpayPaymentVerify
from app.schemas.subscription import SubscriptionPlanResponse
from app.models.booking import SeatBooking
from app.models.admin import AdminUser, AdminDetails
from app.models.student import Student
from app.models.subscription import SubscriptionPlan
from app.core.cache import get_cached, set_cached, library_occupied_key, invalidate_library_capacity, invalidate_admin_caches
from app.utils.subscription_plan_scope import apply_plan_shift_filters
from app.utils.razorpay_route import order_transfers_to_library
from app.services.email_queue_service import enqueue_email_job

router = APIRouter()

# Cache TTL for library occupied count (seconds)
LIBRARY_OCCUPIED_TTL = 60


def _get_occupied_seats_cached(db: Session, library_id: str) -> int:
    """Return occupied seat count for a library, from cache or DB."""
    key = library_occupied_key(str(library_id))
    cached_val = get_cached(key)
    if cached_val is not None:
        return int(cached_val)
    count = db.query(SeatBooking).join(Student, SeatBooking.student_id == Student.auth_user_id).filter(
        SeatBooking.library_id == library_id,
        SeatBooking.status == "active",
        Student.is_active == True,
        Student.subscription_status != "Removed"
    ).count()
    set_cached(key, count, LIBRARY_OCCUPIED_TTL)
    return count


@router.get("/libraries", response_model=List[LibraryInfo])
async def get_libraries(
    latitude: Optional[float] = Query(None),
    longitude: Optional[float] = Query(None),
    radius: Optional[float] = Query(50.0),  # Default 50km radius
    db: Session = Depends(get_db)
):
    """Get all libraries with optional location filtering"""
    query = db.query(AdminDetails).filter(AdminDetails.total_seats > 0)
    
    libraries = query.all()
    
    result = []
    for library in libraries:
        occupied_seats = _get_occupied_seats_cached(db, str(library.id))
        
        timings = library.shift_timings or []
        shift_list = [str(t) for t in timings] if timings else None
        library_info = LibraryInfo(
            id=library.id,
            user_id=str(library.user_id),
            library_name=library.library_name,
            address=library.address,
            total_seats=library.total_seats,
            occupied_seats=occupied_seats,
            latitude=library.latitude,
            longitude=library.longitude,
            has_shift_system=bool(library.has_shift_system),
            shift_timings=shift_list,
        )
        
        # Calculate distance if user location is provided
        if latitude and longitude and library.latitude and library.longitude:
            distance = calculate_distance(latitude, longitude, library.latitude, library.longitude)
            library_info.distance = distance
            
            # Filter by radius if specified
            if radius and distance > radius:
                continue
        
        result.append(library_info)
    
    # Sort by distance if location is provided
    if latitude and longitude:
        result.sort(key=lambda x: x.distance or float('inf'))
    
    return result

@router.get("/libraries/{library_id}/subscription-plans", response_model=List[SubscriptionPlanResponse])
async def get_library_subscription_plans(
    library_id: str,
    db: Session = Depends(get_db),
    is_shift_student: Optional[bool] = Query(
        None,
        description="When set, filters plans for non-shift vs shift students (shift libraries).",
    ),
    shift_time: Optional[str] = Query(
        None,
        description="Student's shift slot; used when is_shift_student is true.",
    ),
):
    """Get subscription plans for a specific library (anonymous access)."""
    library = db.query(AdminDetails).filter(AdminDetails.id == library_id).first()
    if not library:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library not found",
        )

    query = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.library_id == library_id,
            SubscriptionPlan.is_active == True,
        )
        .order_by(SubscriptionPlan.months.asc())
    )
    query = apply_plan_shift_filters(
        query,
        library,
        is_shift_student=is_shift_student,
        shift_time=shift_time,
    )
    return query.all()

@router.post("/seat-booking", response_model=SeatBookingResponse)
async def create_seat_booking(
    booking_data: SeatBookingCreate,
    db: Session = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Create a new seat booking request (authenticated users)"""
    # Get library details
    library = db.query(AdminDetails).filter(AdminDetails.id == booking_data.library_id).first()
    if not library:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library not found"
        )
    
    # Check if library has available seats
    occupied_seats = db.query(SeatBooking).join(Student, SeatBooking.student_id == Student.auth_user_id).filter(
        SeatBooking.library_id == booking_data.library_id,
        SeatBooking.status.in_(["active", "approved"]),
        Student.is_active == True,
        Student.subscription_status != "Removed"
    ).count()
    
    if occupied_seats >= library.total_seats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No seats available in this library"
        )
    
    # Create booking
    booking = SeatBooking(
        student_id=current_user["user_id"] if current_user and current_user["user_type"] == "student" else None,
        library_id=booking_data.library_id,
        admin_id=library.user_id,
        **booking_data.model_dump(exclude={"library_id"})
    )
    
    db.add(booking)
    db.commit()
    db.refresh(booking)
    
    return booking

@router.post("/student-seat-booking", response_model=SeatBookingResponse)
async def create_student_seat_booking(
    booking_data: StudentSeatBookingCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_student)
):
    """Deprecated: Students must pay Rs.1 token amount before submitting booking.
    Use /booking/student-seat-booking/payment-init and /booking/student-seat-booking/payment-verify instead."""
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Pre-payment required. Please initiate Rs.1 Razorpay token payment and verify before submitting booking."
    )

@router.post("/anonymous-seat-booking", response_model=SeatBookingResponse)
async def create_anonymous_seat_booking(
    booking_data: SeatBookingCreate,
    db: Session = Depends(get_db)
):
    """Deprecated: Anonymous users must pay Rs.1 token amount before submitting booking.
    Use /booking/anonymous-seat-booking/payment-init and /booking/anonymous-seat-booking/payment-verify instead."""
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Pre-payment required. Please initiate Rs.1 Razorpay token payment and verify before submitting booking."
    )

@router.post("/anonymous-seat-booking/payment-init")
async def init_anonymous_booking_token_payment(
    payload: dict,
    db: Session = Depends(get_db)
):
    """Initiate Rs.1 token payment for anonymous booking."""
    from app.services.razorpay_service import razorpay_service
    library_id = payload.get("library_id")
    if not library_id:
        raise HTTPException(status_code=400, detail="library_id is required")
    library = db.query(AdminDetails).filter(AdminDetails.id == library_id).first()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    # Optional plan data
    subscription_plan_id = payload.get("subscription_plan_id")
    if subscription_plan_id:
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == subscription_plan_id,
            SubscriptionPlan.library_id == library_id,
            SubscriptionPlan.is_active == True
        ).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Subscription plan not found or inactive")
    # Razorpay receipt must be <= 40 chars
    lib_short = str(library_id)[:8]
    ts = int(datetime.utcnow().timestamp())
    receipt_id = f"atok_{lib_short}_{ts}"
    notes = {
        "type": "booking_token_anonymous",
        "library_id": str(library_id),
        "subscription_plan_id": str(subscription_plan_id) if subscription_plan_id else "",
        "name": payload.get("name") or "",
        "email": payload.get("email") or "",
        "mobile": payload.get("mobile") or ""
    }
    result = razorpay_service.create_order(amount=100, currency="INR", receipt=receipt_id, notes=notes)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Failed to create token payment order: {result['error']}")
    return result["order"]

@router.post("/anonymous-seat-booking/payment-verify", response_model=SeatBookingResponse)
async def verify_anonymous_booking_token_payment(
    payload: dict,
    db: Session = Depends(get_db)
):
    """Verify Rs.1 token payment and create anonymous pending booking."""
    from app.services.razorpay_service import razorpay_service
    required_fields = ["razorpay_order_id", "razorpay_payment_id", "razorpay_signature", "library_id",
                       "name", "email", "mobile", "address", "subscription_months"]
    missing = [f for f in required_fields if not payload.get(f)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")
    verification = razorpay_service.verify_payment(
        razorpay_order_id=payload["razorpay_order_id"],
        razorpay_payment_id=payload["razorpay_payment_id"],
        razorpay_signature=payload["razorpay_signature"]
    )
    if not verification["success"] or not verification["verified"]:
        raise HTTPException(status_code=400, detail="Token payment verification failed")
    # Capacity check
    library_id = payload["library_id"]
    library = db.query(AdminDetails).filter(AdminDetails.id == library_id).first()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    occupied_seats = db.query(SeatBooking).join(Student, SeatBooking.student_id == Student.auth_user_id).filter(
        SeatBooking.library_id == library_id,
        SeatBooking.status.in_(["active", "approved"]),
        Student.is_active == True,
        Student.subscription_status != "Removed"
    ).count()
    if occupied_seats >= library.total_seats:
        raise HTTPException(status_code=400, detail="No seats available in this library")
    # Create pending anonymous booking
    booking = SeatBooking(
        student_id=None,
        library_id=library_id,
        admin_id=library.user_id,
        name=payload["name"],
        email=payload["email"],
        mobile=payload["mobile"],
        address=payload["address"],
        subscription_months=payload.get("subscription_months"),
        seat_id=payload.get("seat_id"),
        subscription_plan_id=payload.get("subscription_plan_id"),
        amount=payload.get("amount"),
        date=payload.get("date"),
        start_time=payload.get("start_time"),
        end_time=payload.get("end_time"),
        purpose=payload.get("purpose"),
        status="pending",
        payment_status="token_paid",
        payment_method="razorpay",
        payment_reference=payload["razorpay_payment_id"]
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    # Queue submission confirmation email to anonymous user
    if booking.email:
        booking_details = {
            "amount": float(booking.amount) if booking.amount else 0,
            "subscription_months": booking.subscription_months or 1,
            "created_at": booking.created_at,
        }
        enqueue_email_job(
            db=db,
            email_type="booking_submission",
            to_email=booking.email.strip(),
            payload={
                "student_name": booking.name or "User",
                "library_name": library.library_name,
                "booking_details": booking_details,
            },
        )
    return booking

@router.get("/seat-bookings", response_model=List[SeatBookingResponse])
async def get_seat_bookings(
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get seat bookings for current admin"""
    query = db.query(SeatBooking).filter(SeatBooking.admin_id == current_admin.user_id)
    
    if status:
        query = query.filter(SeatBooking.status == status)
    
    bookings = query.order_by(SeatBooking.created_at.desc()).offset(skip).limit(limit).all()
    
    return bookings

@router.put("/seat-bookings/{booking_id}", response_model=SeatBookingResponse)
async def update_seat_booking(
    booking_id: str,
    booking_data: SeatBookingUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update a seat booking (approve/reject)"""
    booking = db.query(SeatBooking).filter(
        SeatBooking.id == booking_id,
        SeatBooking.admin_id == current_admin.user_id
    ).first()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    update_data = booking_data.model_dump(exclude_unset=True)
    
    # If approving, set approval date but don't create student account yet
    if update_data.get("status") == "approved":
        update_data["approval_date"] = datetime.utcnow()
        # Don't set start_date and end_date yet - will be set after payment
        # Don't create student account yet - will be created after payment
    
    for field, value in update_data.items():
        setattr(booking, field, value)
    
    db.commit()
    db.refresh(booking)
    
    if update_data.get("status") == "approved":
        from app.models.admin import AdminDetails
        library_details = db.query(AdminDetails).filter(
            AdminDetails.user_id == current_admin.user_id
        ).first()
        if library_details and booking.email:
            booking_details = {
                "amount": float(booking.amount) if booking.amount else 0,
                "subscription_months": booking.subscription_months or 1,
                "created_at": booking.created_at,
                "seat_number": booking.seat_number or "TBD",
            }
            enqueue_email_job(
                db=db,
                email_type="booking_approval",
                to_email=booking.email,
                payload={
                    "student_name": booking.name,
                    "library_name": library_details.library_name,
                    "booking_details": booking_details,
                },
            )
    
    elif update_data.get("status") == "rejected":
        from app.models.admin import AdminDetails
        library_details = db.query(AdminDetails).filter(
            AdminDetails.user_id == current_admin.user_id
        ).first()
        if library_details and booking.email:
            booking_details = {
                "amount": float(booking.amount) if booking.amount else 0,
                "subscription_months": booking.subscription_months or 1,
                "created_at": booking.created_at,
            }
            enqueue_email_job(
                db=db,
                email_type="booking_rejection",
                to_email=booking.email,
                payload={
                    "student_name": booking.name,
                    "library_name": library_details.library_name,
                    "booking_details": booking_details,
                },
            )
    
    return booking

@router.post("/student-seat-booking/payment-init")
async def init_student_booking_token_payment(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_student)
):
    """Initiate Rs.1 token payment for student seat booking prior to submission."""
    from app.services.razorpay_service import razorpay_service
    # Validate required fields
    library_id = payload.get("library_id")
    if not library_id:
        raise HTTPException(status_code=400, detail="library_id is required")
    # Validate library exists
    library = db.query(AdminDetails).filter(AdminDetails.id == library_id).first()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    # Optional: validate plan if provided
    subscription_plan_id = payload.get("subscription_plan_id")
    if subscription_plan_id:
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == subscription_plan_id,
            SubscriptionPlan.library_id == library_id,
            SubscriptionPlan.is_active == True
        ).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Subscription plan not found or inactive")
    # Create Razorpay order for Rs.1 (100 paise) - keep receipt <= 40 chars
    user_short = str(current_user['user_id'])[:8]
    lib_short = str(library_id)[:8]
    ts = int(datetime.utcnow().timestamp())
    receipt_id = f"tok_{user_short}_{lib_short}_{ts}"
    notes = {
        "type": "booking_token",
        "student_id": str(current_user["user_id"]),
        "library_id": str(library_id),
        "subscription_plan_id": str(subscription_plan_id) if subscription_plan_id else ""
    }
    result = razorpay_service.create_order(amount=100, currency="INR", receipt=receipt_id, notes=notes)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Failed to create token payment order: {result['error']}")
    return result["order"]

@router.post("/student-seat-booking/payment-verify", response_model=SeatBookingResponse)
async def verify_student_booking_token_payment(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_student)
):
    """Verify Rs.1 token payment and create a pending booking request for admin review."""
    from app.services.razorpay_service import razorpay_service
    # Extract verification fields
    required_fields = ["razorpay_order_id", "razorpay_payment_id", "razorpay_signature", "library_id", "date", "start_time", "end_time"]
    missing = [f for f in required_fields if not payload.get(f)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")
    # Verify order signature
    verification = razorpay_service.verify_payment(
        razorpay_order_id=payload["razorpay_order_id"],
        razorpay_payment_id=payload["razorpay_payment_id"],
        razorpay_signature=payload["razorpay_signature"]
    )
    if not verification["success"] or not verification["verified"]:
        raise HTTPException(status_code=400, detail="Token payment verification failed")
    # Validate library capacity
    library_id = payload["library_id"]
    library = db.query(AdminDetails).filter(AdminDetails.id == library_id).first()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    occupied_seats = db.query(SeatBooking).join(Student, SeatBooking.student_id == Student.auth_user_id).filter(
        SeatBooking.library_id == library_id,
        SeatBooking.status.in_(["active", "approved"]),
        Student.is_active == True,
        Student.subscription_status != "Removed"
    ).count()
    if occupied_seats >= library.total_seats:
        raise HTTPException(status_code=400, detail="No seats available in this library")
    # Optional plan validation
    subscription_plan_id = payload.get("subscription_plan_id")
    plan = None
    if subscription_plan_id:
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == subscription_plan_id,
            SubscriptionPlan.library_id == library_id,
            SubscriptionPlan.is_active == True
        ).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Subscription plan not found or inactive")
    # Create pending booking (admin will approve, main payment later)
    booking = SeatBooking(
        student_id=current_user["user_id"],
        library_id=library_id,
        admin_id=library.user_id,
        seat_id=payload.get("seat_id"),
        subscription_plan_id=subscription_plan_id,
        amount=(plan.discounted_amount if plan else payload.get("amount")),
        date=payload["date"],
        start_time=payload["start_time"],
        end_time=payload["end_time"],
        purpose=payload.get("purpose"),
        status="pending",
        payment_status="token_paid",
        payment_method="razorpay",
        payment_reference=payload["razorpay_payment_id"]
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    # Queue submission confirmation email to student
    from app.models.student import Student as StudentModel
    student = db.query(StudentModel).filter(StudentModel.auth_user_id == current_user["user_id"]).first()
    if student and student.email:
        booking_details = {
            "amount": float(booking.amount) if booking.amount else 0,
            "subscription_months": 1,
            "created_at": booking.created_at,
        }
        enqueue_email_job(
            db=db,
            email_type="booking_submission",
            to_email=student.email.strip(),
            payload={
                "student_name": student.name or "Student",
                "library_name": library.library_name,
                "booking_details": booking_details,
            },
        )
    return booking

@router.patch("/seat-bookings/{booking_id}", response_model=SeatBookingResponse)
async def patch_seat_booking(
    booking_id: str,
    booking_data: SeatBookingUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update a seat booking status (approve/reject) - PATCH version"""
    booking = db.query(SeatBooking).filter(
        SeatBooking.id == booking_id,
        SeatBooking.admin_id == current_admin.user_id
    ).first()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    update_data = booking_data.model_dump(exclude_unset=True)
    
    # If approving, set dates and create student account if needed
    if update_data.get("status") == "approved":
        update_data["approval_date"] = datetime.utcnow()
        update_data["start_date"] = datetime.utcnow()
        update_data["end_date"] = datetime.utcnow() + timedelta(days=30 * booking.subscription_months)
        
        # Create student account if student_id is not set
        if not booking.student_id:
            from app.auth.jwt import get_password_hash
            from app.services.student_service import generate_student_id
            
            student_id = await generate_student_id(current_admin.user_id, db)
            
            student = Student(
                auth_user_id=student_id,
                name=booking.name,
                email=booking.email,
                mobile=booking.mobile,
                address=booking.address,
                admin_id=current_admin.user_id,
                is_active=True
            )
            
            db.add(student)
            db.commit()
            db.refresh(student)
            
            update_data["student_id"] = student.auth_user_id
            update_data["status"] = "active"  # Change to active instead of approved
    
    for field, value in update_data.items():
        setattr(booking, field, value)
    
    db.commit()
    db.refresh(booking)
    invalidate_admin_caches(str(current_admin.user_id))
    invalidate_library_capacity(str(booking.library_id))
    
    if update_data.get("status") == "approved":
        from app.models.admin import AdminDetails
        library_details = db.query(AdminDetails).filter(
            AdminDetails.user_id == current_admin.user_id
        ).first()
        if library_details and booking.email:
            booking_details = {
                "amount": float(booking.amount) if booking.amount else 0,
                "subscription_months": booking.subscription_months or 1,
                "created_at": booking.created_at,
                "seat_number": booking.seat_number or "TBD",
            }
            enqueue_email_job(
                db=db,
                email_type="booking_approval",
                to_email=booking.email,
                payload={
                    "student_name": booking.name,
                    "library_name": library_details.library_name,
                    "booking_details": booking_details,
                },
            )
    
    elif update_data.get("status") == "rejected":
        from app.models.admin import AdminDetails
        library_details = db.query(AdminDetails).filter(
            AdminDetails.user_id == current_admin.user_id
        ).first()
        if library_details and booking.email:
            booking_details = {
                "amount": float(booking.amount) if booking.amount else 0,
                "subscription_months": booking.subscription_months or 1,
                "created_at": booking.created_at,
            }
            enqueue_email_job(
                db=db,
                email_type="booking_rejection",
                to_email=booking.email,
                payload={
                    "student_name": booking.name,
                    "library_name": library_details.library_name,
                    "booking_details": booking_details,
                },
            )
    
    return booking

@router.post("/confirm-payment", response_model=SeatBookingResponse)
async def confirm_payment(
    payment_data: PaymentConfirmation,
    db: Session = Depends(get_db)
):
    """Confirm payment for a booking and activate student in library"""
    from app.models.student import Student
    from app.models.admin import AdminDetails
    from datetime import datetime, timedelta
    
    # Find the booking
    booking = db.query(SeatBooking).filter(
        SeatBooking.id == payment_data.booking_id,
        SeatBooking.status == "approved"
    ).first()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or not approved"
        )
    
    # Check if payment is already confirmed
    if booking.payment_status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment already confirmed for this booking"
        )
    
    # Update booking with payment information
    booking.payment_status = "paid"
    booking.payment_date = datetime.utcnow()
    booking.payment_method = payment_data.payment_method
    booking.payment_reference = payment_data.payment_reference
    booking.status = "active"
    
    # Set subscription dates after payment
    booking.start_date = datetime.utcnow()
    booking.end_date = datetime.utcnow() + timedelta(days=30 * (booking.subscription_months or 1))
    
    # If this is an anonymous booking, create or update student record
    if not booking.student_id:
        # Check if student already exists by email
        existing_student = db.query(Student).filter(
            Student.email == booking.email,
            Student.admin_id == booking.admin_id
        ).first()
        
        if existing_student:
            # Update existing student
            student = existing_student
            student.subscription_start = booking.start_date
            student.subscription_end = booking.end_date
            student.subscription_status = "Active"
            student.status = "Absent"  # Default status
        else:
            # Create new student
            from app.services.student_service import generate_student_id
            student_id = await generate_student_id(booking.admin_id, db)
            
            student = Student(
                auth_user_id=student_id,
                name=booking.name,
                email=booking.email,
                mobile_no=booking.mobile,
                address=booking.address,
                admin_id=booking.admin_id,
                subscription_start=booking.start_date,
                subscription_end=booking.end_date,
                subscription_status="Active",
                status="Absent",
                is_active=True
            )
            db.add(student)
            db.flush()  # Get the student ID
        
        # Link booking to student
        booking.student_id = student.auth_user_id
    
    else:
        # Update existing student subscription
        student = db.query(Student).filter(
            Student.auth_user_id == booking.student_id
        ).first()
        
        if student:
            student.subscription_start = booking.start_date
            student.subscription_end = booking.end_date
            student.subscription_status = "Active"
    
    # Commit all changes
    db.commit()
    db.refresh(booking)
    invalidate_admin_caches(str(booking.admin_id))
    invalidate_library_capacity(str(booking.library_id))
    
    # Queue payment confirmation email
    from app.models.admin import AdminDetails
    library_details = db.query(AdminDetails).filter(
        AdminDetails.user_id == booking.admin_id
    ).first()
    if library_details and booking.email:
        enqueue_email_job(
            db=db,
            email_type="payment_confirmation",
            to_email=booking.email,
            payload={
                "student_name": booking.name or "Student",
                "library_name": library_details.library_name,
                "plan_name": f"{booking.subscription_months or 1} Month Plan",
                "amount": float(booking.amount) if booking.amount else 0,
                "payment_id": payment_data.payment_reference or "",
                "subscription_end": booking.end_date.strftime("%d %B %Y") if booking.end_date else "",
                "base_url": "",
            },
        )
    
    return booking

@router.get("/my-bookings", response_model=List[SeatBookingResponse])
async def get_my_bookings(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Get bookings for current student"""
    bookings = db.query(SeatBooking).filter(
        SeatBooking.student_id == current_student.auth_user_id
    ).order_by(SeatBooking.created_at.desc()).all()
    
    return bookings

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using Haversine formula"""
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    
    return c * r

@router.post("/create-razorpay-order", response_model=RazorpayOrderResponse)
async def create_razorpay_order(
    order_data: RazorpayOrderCreate,
    db: Session = Depends(get_db)
):
    """Create a Razorpay order for booking payment"""
    from app.services.razorpay_service import razorpay_service
    
    # Find the booking
    booking = db.query(SeatBooking).filter(SeatBooking.id == order_data.booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Check if booking is approved
    if booking.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking must be approved before payment"
        )
    
    # Check if payment already exists
    if booking.payment_status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment already completed for this booking"
        )
    
    # Create Razorpay order (full amount → library linked account when Route is enabled; not Rs.1 token)
    library = db.query(AdminDetails).filter(AdminDetails.id == booking.library_id).first()
    receipt_id = f"bk{str(booking.id).replace('-', '')[:10]}_{int(datetime.utcnow().timestamp())}"
    if len(receipt_id) > 40:
        receipt_id = receipt_id[:40]
    notes = {
        "booking_id": str(booking.id),
        "student_name": booking.name or "Anonymous",
        "library_id": str(booking.library_id)
    }
    
    if order_data.notes:
        notes.update(order_data.notes)

    transfers = order_transfers_to_library(
        library,
        amount_paise=order_data.amount,
        currency=order_data.currency,
        notes=notes,
    )
    
    result = razorpay_service.create_order(
        amount=order_data.amount,
        currency=order_data.currency,
        receipt=receipt_id,
        notes=notes,
        transfers=transfers,
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment order: {result['error']}"
        )
    
    return result["order"]

@router.post("/verify-razorpay-payment", response_model=SeatBookingResponse)
async def verify_razorpay_payment(
    payment_data: RazorpayPaymentVerify,
    db: Session = Depends(get_db)
):
    """Verify Razorpay payment and activate booking"""
    from app.services.razorpay_service import razorpay_service
    from app.models.student import Student
    from app.models.admin import AdminDetails
    from datetime import datetime, timedelta
    
    # Find the booking
    booking = db.query(SeatBooking).filter(SeatBooking.id == payment_data.booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Check if booking is approved
    if booking.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking must be approved before payment"
        )
    
    # Check if payment already exists
    if booking.payment_status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment already completed for this booking"
        )
    
    # Verify payment with Razorpay
    verification_result = razorpay_service.verify_payment(
        razorpay_order_id=payment_data.razorpay_order_id,
        razorpay_payment_id=payment_data.razorpay_payment_id,
        razorpay_signature=payment_data.razorpay_signature
    )
    
    if not verification_result["success"] or not verification_result["verified"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment verification failed: {verification_result.get('message', 'Invalid signature')}"
        )
    
    # Get payment details from Razorpay
    payment_details = razorpay_service.get_payment_details(payment_data.razorpay_payment_id)
    if not payment_details["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch payment details"
        )
    
    razorpay_payment = payment_details["payment"]
    
    # Update booking with payment information
    booking.payment_status = "paid"
    booking.payment_date = datetime.utcnow()
    booking.payment_method = "razorpay"
    booking.payment_reference = payment_data.razorpay_payment_id
    booking.status = "active"
    
    # Set subscription dates after payment
    booking.start_date = datetime.utcnow()
    booking.end_date = datetime.utcnow() + timedelta(days=30 * (booking.subscription_months or 1))
    
    # If this is an anonymous booking, create or update student record
    if not booking.student_id:
        # Check if student already exists by email
        existing_student = db.query(Student).filter(
            Student.email == booking.email,
            Student.admin_id == booking.admin_id
        ).first()
        
        if existing_student:
            # Update existing student
            student = existing_student
            student.subscription_start = booking.start_date
            student.subscription_end = booking.end_date
            student.subscription_status = "Active"
            student.status = "Absent"  # Default status
        else:
            # Create new student
            from app.services.student_service import generate_student_id
            student_id = await generate_student_id(booking.admin_id, db)
            
            student = Student(
                auth_user_id=student_id,
                name=booking.name,
                email=booking.email,
                mobile_no=booking.mobile,
                address=booking.address,
                admin_id=booking.admin_id,
                subscription_start=booking.start_date,
                subscription_end=booking.end_date,
                subscription_status="Active",
                status="Absent",
                is_active=True
            )
            db.add(student)
            db.flush()  # Get the student ID
        
        # Link booking to student
        booking.student_id = student.auth_user_id
    
    else:
        # Update existing student subscription
        student = db.query(Student).filter(
            Student.auth_user_id == booking.student_id
        ).first()
        
        if student:
            student.subscription_start = booking.start_date
            student.subscription_end = booking.end_date
            student.subscription_status = "Active"
    
    # Commit all changes
    db.commit()
    db.refresh(booking)
    invalidate_admin_caches(str(booking.admin_id))
    invalidate_library_capacity(str(booking.library_id))
    
    # Queue payment confirmation email
    from app.models.admin import AdminDetails
    library = db.query(AdminDetails).filter(AdminDetails.id == booking.library_id).first()
    if library and booking.email:
        enqueue_email_job(
            db=db,
            email_type="payment_confirmation",
            to_email=booking.email,
            payload={
                "student_name": booking.name or "Student",
                "library_name": library.library_name,
                "plan_name": f"{booking.subscription_months or 1} Month Plan",
                "amount": float(booking.amount) if booking.amount else 0,
                "payment_id": payment_data.razorpay_payment_id,
                "subscription_end": booking.end_date.strftime("%d %B %Y") if booking.end_date else "",
                "base_url": "",
            },
        )
    
    return booking
