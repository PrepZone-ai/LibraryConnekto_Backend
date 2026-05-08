from pydantic import BaseModel, EmailStr, model_validator
from typing import Optional
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    user_type: Optional[str] = None

class AdminSignUp(BaseModel):
    email: EmailStr
    password: str
    library_name: Optional[str] = None
    mobile_no: Optional[str] = None
    address: Optional[str] = None
    total_seats: Optional[int] = None
    email_verified: bool = False

class AdminSignIn(BaseModel):
    email: EmailStr
    password: str

class AdminResendVerificationRequest(BaseModel):
    email: EmailStr

class StudentSignUp(BaseModel):
    email: EmailStr
    password: str
    admin_id: str
    name: str
    mobile_no: str
    address: str
    subscription_start: datetime
    subscription_end: datetime
    is_shift_student: bool = False
    shift_time: Optional[str] = None

class StudentSignUpByAdmin(BaseModel):
    email: EmailStr
    name: str
    mobile_no: str
    address: str
    subscription_start: datetime
    subscription_end: datetime
    is_shift_student: bool = False
    shift_time: Optional[str] = None

class StudentSignIn(BaseModel):
    email: str  # Can be either email or student ID
    password: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class PasswordReset(BaseModel):
    email: EmailStr


class StudentForgotPasswordRequest(BaseModel):
    """Provide student_id (e.g. LIBR25001) and/or email; at least one required."""

    student_id: Optional[str] = None
    email: Optional[EmailStr] = None

    @model_validator(mode="after")
    def require_identifier(self):
        sid = (self.student_id or "").strip()
        em = ""
        if self.email is not None:
            em = str(self.email).strip()
        if not sid and not em:
            raise ValueError("Provide student_id or email")
        return self


class AdminResetPasswordConfirm(BaseModel):
    token: str
    new_password: str

class StudentSetPassword(BaseModel):
    student_id: Optional[str] = None
    token: Optional[str] = None
    new_password: str

class UserResponse(BaseModel):
    user_id: str
    email: str
    user_type: str
    is_first_login: bool = False
    email_verified: bool = False
    email_delivery_status: Optional[str] = None
    email_delivery_id: Optional[str] = None
    message: Optional[str] = None
    
    class Config:
        from_attributes = True

class StudentRegistrationResponse(BaseModel):
    user_id: str
    email: str
    user_type: str
    is_first_login: bool = False
    student_id: str
    
    class Config:
        from_attributes = True
