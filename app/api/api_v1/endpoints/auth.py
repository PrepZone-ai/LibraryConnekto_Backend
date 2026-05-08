from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.schemas.auth import (
    AdminSignUp,
    AdminSignIn,
    AdminResendVerificationRequest,
    AdminResetPasswordConfirm,
    PasswordReset,
    StudentSignUp,
    StudentSignUpByAdmin,
    StudentSignIn,
    StudentForgotPasswordRequest,
    Token,
    UserResponse,
    StudentRegistrationResponse,
    StudentSetPassword,
)
from app.models.admin import AdminUser, AdminDetails
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.student import Student
from app.auth.jwt import create_access_token, verify_password, get_password_hash
from app.auth.dependencies import get_current_admin
from app.core.config import settings
from app.services.email_queue_service import enqueue_email_job
import uuid

router = APIRouter()
ADMIN_VERIFICATION_RESEND_COOLDOWN_SECONDS = 60
PASSWORD_RESET_EMAIL_COOLDOWN_SECONDS = 60


def _password_reset_cooldown_response(
    db: Session,
    *,
    email_type: str,
    to_email: str,
) -> None:
    latest_delivery = (
        db.query(EmailDeliveryLog)
        .filter(
            EmailDeliveryLog.email_type == email_type,
            EmailDeliveryLog.to_email == to_email,
        )
        .order_by(EmailDeliveryLog.created_at.desc())
        .first()
    )
    if latest_delivery and latest_delivery.created_at:
        last_created_at = latest_delivery.created_at
        if last_created_at.tzinfo is None:
            last_created_at = last_created_at.replace(tzinfo=timezone.utc)
        elapsed_seconds = int((datetime.now(timezone.utc) - last_created_at).total_seconds())
        if elapsed_seconds < PASSWORD_RESET_EMAIL_COOLDOWN_SECONDS:
            retry_after_seconds = PASSWORD_RESET_EMAIL_COOLDOWN_SECONDS - elapsed_seconds
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "password_reset_cooldown",
                    "message": f"Please wait {retry_after_seconds} seconds before requesting another reset email.",
                    "retry_after_seconds": retry_after_seconds,
                },
            )

@router.post("/admin/signup", response_model=UserResponse)
async def admin_signup(admin_data: AdminSignUp, request: Request, db: Session = Depends(get_db)):
    """Register a new admin with email verification"""
    existing_admin = db.query(AdminUser).filter(AdminUser.email == admin_data.email.lower()).first()
    if existing_admin:
        # If account is active and verified, suggest signing in instead
        if existing_admin.status == "active" and existing_admin.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin with this email already exists. Please sign in instead."
            )
        # If account is pending, allow re-signup by updating the existing account
        elif existing_admin.status == "pending":
            # Update existing pending account with new password and token
            verification_token = str(uuid.uuid4())
            existing_admin.hashed_password = get_password_hash(admin_data.password)
            existing_admin.email_verification_token = verification_token
            existing_admin.email_verified = False
            db.commit()
            db.refresh(existing_admin)
            
            # Update admin details if provided
            if any([admin_data.library_name, admin_data.mobile_no, admin_data.address, admin_data.total_seats]):
                admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == existing_admin.user_id).first()
                if admin_details:
                    admin_details.library_name = admin_data.library_name or admin_details.library_name
                    admin_details.mobile_no = admin_data.mobile_no or admin_details.mobile_no
                    admin_details.address = admin_data.address or admin_details.address
                    admin_details.total_seats = admin_data.total_seats or admin_details.total_seats
                else:
                    admin_details = AdminDetails(
                        user_id=existing_admin.user_id,
                        admin_name="",
                        library_name=admin_data.library_name or "",
                        mobile_no=admin_data.mobile_no or "",
                        address=admin_data.address or "",
                        total_seats=admin_data.total_seats or 0
                    )
                    db.add(admin_details)
                db.commit()
            
            delivery_id = enqueue_email_job(
                db=db,
                email_type="admin_verification",
                to_email=existing_admin.email,
                payload={"token": verification_token, "base_url": str(request.base_url)},
            )
            
            return UserResponse(
                user_id=str(existing_admin.user_id),
                email=existing_admin.email,
                user_type="admin",
                is_first_login=True,
                email_verified=False,
                email_delivery_status="queued",
                email_delivery_id=str(delivery_id),
                message="Signup successful. Verification email has been queued for delivery. If you do not receive it within a few minutes, check spam and use resend.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin with this email already exists. Please contact support."
            )
    # Generate verification token
    verification_token = str(uuid.uuid4())
    # Create admin user with status 'pending'
    hashed_password = get_password_hash(admin_data.password)
    admin_user = AdminUser(
        email=admin_data.email.lower(),
        hashed_password=hashed_password,
        role="admin",
        status="pending",
        email_verification_token=verification_token,
        email_verified=False
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    # Create admin details if provided
    if any([admin_data.library_name, admin_data.mobile_no, admin_data.address, admin_data.total_seats]):
        admin_details = AdminDetails(
            user_id=admin_user.user_id,
            admin_name="",  # Will be updated later
            library_name=admin_data.library_name or "",
            mobile_no=admin_data.mobile_no or "",
            address=admin_data.address or "",
            total_seats=admin_data.total_seats or 0
        )
        db.add(admin_details)
        db.commit()
    delivery_id = enqueue_email_job(
        db=db,
        email_type="admin_verification",
        to_email=admin_user.email,
        payload={"token": verification_token, "base_url": str(request.base_url)},
    )
    return UserResponse(
        user_id=str(admin_user.user_id),
        email=admin_user.email,
        user_type="admin",
        is_first_login=True,
        email_verified=False,
        email_delivery_status="queued",
        email_delivery_id=str(delivery_id),
        message="Signup successful. Verification email has been queued for delivery. If you do not receive it within a few minutes, check spam and use resend.",
    )

@router.get("/admin/verify-email")
async def verify_admin_email(token: str, db: Session = Depends(get_db)):
    """Verify admin email using the token from the email link"""
    admin = db.query(AdminUser).filter(AdminUser.email_verification_token == token).first()
    if not admin:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token.")
    if admin.email_verified:
        return {"message": "Email already verified. You can sign in."}
    admin.email_verified = True
    admin.status = "active"
    admin.email_verification_token = None
    db.commit()
    return {"message": "Email verified successfully! You can now sign in."}


@router.post("/admin/resend-verification")
async def resend_admin_verification(
    request_data: AdminResendVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Resend admin verification email with a short cooldown to avoid abuse."""
    admin = db.query(AdminUser).filter(AdminUser.email == request_data.email.lower()).first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    if admin.email_verified or admin.status == "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is already verified.")

    latest_delivery = (
        db.query(EmailDeliveryLog)
        .filter(
            EmailDeliveryLog.email_type == "admin_verification",
            EmailDeliveryLog.to_email == admin.email,
        )
        .order_by(EmailDeliveryLog.created_at.desc())
        .first()
    )
    if latest_delivery and latest_delivery.created_at:
        last_created_at = latest_delivery.created_at
        if last_created_at.tzinfo is None:
            last_created_at = last_created_at.replace(tzinfo=timezone.utc)
        elapsed_seconds = int((datetime.now(timezone.utc) - last_created_at).total_seconds())
        if elapsed_seconds < ADMIN_VERIFICATION_RESEND_COOLDOWN_SECONDS:
            retry_after_seconds = ADMIN_VERIFICATION_RESEND_COOLDOWN_SECONDS - elapsed_seconds
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "resend_verification_cooldown",
                    "message": f"Please wait {retry_after_seconds} seconds before requesting another verification email.",
                    "retry_after_seconds": retry_after_seconds,
                },
            )

    verification_token = str(uuid.uuid4())
    admin.email_verification_token = verification_token
    admin.email_verified = False
    db.commit()
    db.refresh(admin)

    delivery_id = enqueue_email_job(
        db=db,
        email_type="admin_verification",
        to_email=admin.email,
        payload={"token": verification_token, "base_url": str(request.base_url)},
    )
    return {
        "success": True,
        "message": "Verification email re-queued. Please check your inbox and spam folder.",
        "email_delivery_status": "queued",
        "email_delivery_id": str(delivery_id),
        "cooldown_seconds": ADMIN_VERIFICATION_RESEND_COOLDOWN_SECONDS,
    }

@router.post("/admin/signin", response_model=Token)
async def admin_signin(admin_data: AdminSignIn, db: Session = Depends(get_db)):
    """Admin login"""
    admin = db.query(AdminUser).filter(AdminUser.email == admin_data.email.lower()).first()
    
    if not admin or not verify_password(admin_data.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if admin.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is not active"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(admin.user_id), "email": admin.email, "user_type": "admin"},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/admin/forgot-password")
async def admin_forgot_password(
    request_data: PasswordReset,
    db: Session = Depends(get_db),
):
    """Email a password reset link to verified, active admins (uniform response)."""
    ok_message = {
        "success": True,
        "message": "If an account exists for this email, you will receive password reset instructions shortly.",
    }
    admin = db.query(AdminUser).filter(AdminUser.email == request_data.email.lower()).first()
    if not admin or admin.status != "active" or not admin.email_verified:
        return ok_message

    _password_reset_cooldown_response(db, email_type="admin_password_reset", to_email=admin.email)

    reset_token = str(uuid.uuid4())
    admin.password_reset_token = reset_token
    db.commit()
    db.refresh(admin)

    reset_url = f"{settings.FRONTEND_BASE_URL}/admin/reset-password?token={reset_token}"
    enqueue_email_job(
        db=db,
        email_type="admin_password_reset",
        to_email=admin.email,
        payload={"reset_url": reset_url},
    )
    return ok_message


@router.post("/admin/reset-password")
async def admin_reset_password(request_data: AdminResetPasswordConfirm, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.password_reset_token == request_data.token).first()
    if not admin:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset link.")
    if len(request_data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")
    admin.hashed_password = get_password_hash(request_data.new_password)
    admin.password_reset_token = None
    db.commit()
    return {"success": True, "message": "Password updated. You can sign in with your new password."}


@router.post("/student/forgot-password")
async def student_forgot_password(
    request_data: StudentForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """Email a reset link to the student's registered address (uniform response)."""
    ok_message = {
        "success": True,
        "message": "If we found your account, password reset instructions were sent to your registered email.",
    }
    student = None
    sid = (request_data.student_id or "").strip().upper()
    email_val = None
    if request_data.email is not None:
        email_val = str(request_data.email).strip().lower()
    if sid:
        student = db.query(Student).filter(Student.student_id == sid).first()
    if not student and email_val:
        student = db.query(Student).filter(Student.email == email_val).first()

    if not student or not student.hashed_password:
        return ok_message

    _password_reset_cooldown_response(db, email_type="student_password_reset", to_email=student.email)

    reset_token = str(uuid.uuid4())
    student.password_reset_token = reset_token
    db.commit()

    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == student.admin_id).first()
    library_name = admin_details.library_name if admin_details else "your library"
    reset_url = f"{settings.FRONTEND_BASE_URL}/student/set-password?token={reset_token}"

    enqueue_email_job(
        db=db,
        email_type="student_password_reset",
        to_email=student.email,
        payload={
            "student_id": student.student_id,
            "library_name": library_name,
            "reset_url": reset_url,
        },
    )
    return ok_message


# Remove or comment out the /student/signup endpoint
defunct = True  # This disables the endpoint for self-signup

@router.post("/admin/student/signup", response_model=StudentRegistrationResponse)
async def admin_student_signup(
    student_data: StudentSignUpByAdmin, 
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
    request: Request = None
):
    """Register a new student by admin"""
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
    
    # Generate password setup token
    password_setup_token = str(uuid.uuid4())
    try:
        # Create student with no password yet
        # Set mobile number as initial password
        initial_password = student_data.mobile_no
        hashed_initial_password = get_password_hash(initial_password)
        
        student = Student(
            student_id=student_id,
            admin_id=current_admin.user_id,
            name=student_data.name,
            email=student_data.email.lower(),
            hashed_password=hashed_initial_password,  # Mobile number as initial password
            password_reset_token=password_setup_token,
            mobile_no=student_data.mobile_no,
            address=student_data.address,
            subscription_start=student_data.subscription_start,
            subscription_end=student_data.subscription_end,
            subscription_status="Active",
            is_shift_student=student_data.is_shift_student,
            shift_time=student_data.shift_time
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
        
        print(f"✓ Student created successfully: {student.email} with ID: {student.student_id}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating student: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create student: {str(e)}"
        )

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

    return StudentRegistrationResponse(
        user_id=str(student.auth_user_id),
        email=student.email,
        user_type="student",
        is_first_login=True,
        student_id=student.student_id
    )

@router.post("/student/set-password")
async def set_student_password(request_data: StudentSetPassword, db: Session = Depends(get_db)):
    """Set student password - supports both token-based and first-time login"""
    # Handle both token-based and student_id-based password setup
    if request_data.token:
        # Token-based password setup (from email link)
        student = db.query(Student).filter(Student.password_reset_token == request_data.token).first()
        if not student:
            raise HTTPException(status_code=400, detail="Invalid or expired password setup token.")
    elif request_data.student_id:
        # First-time login password setup
        student = db.query(Student).filter(Student.student_id == request_data.student_id).first()
        if not student:
            raise HTTPException(status_code=400, detail="Student not found.")
        
        # Verify this is actually a first-time login (password is mobile number)
        if not verify_password(student.mobile_no, student.hashed_password):
            raise HTTPException(status_code=400, detail="Password has already been set. Please use regular login.")
    else:
        raise HTTPException(status_code=400, detail="Either token or student_id must be provided.")
    
    # Validate password strength
    if len(request_data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")
    
    # Update password
    student.hashed_password = get_password_hash(request_data.new_password)
    student.password_reset_token = None  # Clear token if it exists
    db.commit()
    
    return {
        "success": True,
        "message": "Password set successfully! You can now log in with your student ID and password."
    }



@router.post("/student/signin", response_model=Token)
async def student_signin(student_data: StudentSignIn, db: Session = Depends(get_db)):
    """Student login"""
    # Try to find student by email first, then by student_id
    student = db.query(Student).filter(Student.email == student_data.email.lower()).first()
    
    if not student:
        # Try to find by student_id (username)
        student = db.query(Student).filter(Student.student_id == student_data.email.upper()).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password"
        )
    
    # Check if student has set their password
    if not student.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please set your password first. Check your email for the password setup link."
        )
    
    if not verify_password(student_data.password, student.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password"
        )
    
    # Check if this is first login (password is still mobile number)
    # For first login, the password should be the mobile number
    is_first_login = False
    try:
        # Check if the current password matches the mobile number
        is_first_login = verify_password(student.mobile_no, student.hashed_password)
        print(f"[DEBUG] First login check - Mobile: {student.mobile_no}, Is first login: {is_first_login}")
        
        # Additional check: if password is exactly the mobile number (unhashed comparison)
        # This is a fallback check
        if not is_first_login:
            # Try to hash the mobile number and compare
            mobile_hash = get_password_hash(student.mobile_no)
            if mobile_hash == student.hashed_password:
                is_first_login = True
                print(f"[DEBUG] First login detected via hash comparison")
                
    except Exception as e:
        # If verification fails, it's not first login
        is_first_login = False
        print(f"[DEBUG] First login check failed: {e}")
    
    print(f"[DEBUG] Final is_first_login value: {is_first_login}")
    print(f"[DEBUG] Student mobile: {student.mobile_no}")
    print(f"[DEBUG] Hashed password exists: {bool(student.hashed_password)}")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(student.auth_user_id), 
            "email": student.email, 
            "user_type": "student",
            "student_id": student.student_id,
            "is_first_login": is_first_login
        },
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_id": str(student.auth_user_id),
        "is_first_login": is_first_login,
        "student_id": student.student_id,
        "message": "Please set your password on first login" if is_first_login else "Login successful"
    }
