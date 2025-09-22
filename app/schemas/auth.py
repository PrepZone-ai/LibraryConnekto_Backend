from pydantic import BaseModel, EmailStr
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
