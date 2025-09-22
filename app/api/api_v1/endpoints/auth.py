from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from datetime import timedelta

from app.database import get_db
from app.schemas.auth import AdminSignUp, AdminSignIn, StudentSignUp, StudentSignUpByAdmin, StudentSignIn, Token, UserResponse, StudentRegistrationResponse, StudentSetPassword
from app.models.admin import AdminUser, AdminDetails
from app.models.student import Student
from app.auth.jwt import create_access_token, verify_password, get_password_hash
from app.auth.dependencies import get_current_admin
from app.core.config import settings
from app.services.email_service import email_service
import uuid

router = APIRouter()

@router.post("/admin/signup", response_model=UserResponse)
async def admin_signup(admin_data: AdminSignUp, background_tasks: BackgroundTasks, request: Request, db: Session = Depends(get_db)):
    """Register a new admin with email verification"""
    existing_admin = db.query(AdminUser).filter(AdminUser.email == admin_data.email.lower()).first()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin with this email already exists"
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
    # Send verification email in background
    def send_verification_email(email: str, token: str):
        result = email_service.send_admin_verification_email(email, token, str(request.base_url))
        if result["success"]:
            print(f"[EMAIL] Sent verification email to {email}")
        else:
            print(f"[EMAIL ERROR] Could not send verification email: {result['error']}")
    background_tasks.add_task(send_verification_email, admin_user.email, verification_token)
    return UserResponse(
        user_id=str(admin_user.user_id),
        email=admin_user.email,
        user_type="admin",
        is_first_login=True,
        email_verified=False
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

# Remove or comment out the /student/signup endpoint
defunct = True  # This disables the endpoint for self-signup

@router.post("/admin/student/signup", response_model=StudentRegistrationResponse)
async def admin_student_signup(
    student_data: StudentSignUpByAdmin, 
    background_tasks: BackgroundTasks,
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
        
        print(f"✓ Student created successfully: {student.email} with ID: {student.student_id}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating student: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create student: {str(e)}"
        )

    # Send password setup email to student
    def send_student_password_setup_email(email: str, student_id: str, mobile_no: str, token: str, admin_id: str):
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
