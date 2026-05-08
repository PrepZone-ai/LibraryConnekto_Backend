from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class StudentQRTokenResponse(BaseModel):
    token: str
    expires_at: str


class AdminScanRequest(BaseModel):
    qr_token: str


class TransferInitiateRequest(BaseModel):
    qr_token: Optional[str] = None
    student_uuid: Optional[str] = None
    amount: float
    plan_id: Optional[str] = None


class TransferPaymentConfirmRequest(BaseModel):
    payment_reference: str


class TransferResponse(BaseModel):
    transfer_id: str
    status: str
    payment_reference: Optional[str] = None
    payment_link: Optional[str] = None
    student_id: Optional[str] = None
    source_admin_id: Optional[str] = None
    target_admin_id: Optional[str] = None
    amount: Optional[float] = None
    created_at: Optional[datetime] = None
