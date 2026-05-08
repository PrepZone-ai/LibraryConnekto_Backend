from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token, verify_token
from app.core.config import settings
from app.core.cache import invalidate_admin_caches, invalidate_library_capacity
from app.models.admin import AdminDetails, AdminUser
from app.models.booking import SeatBooking
from app.models.qr_transfer import StudentQRToken, StudentTransferRequest
from app.models.student import Student, StudentExam, StudentTask
from app.models.subscription import SubscriptionPlan
from app.services.email_queue_service import enqueue_generic_email_job
from app.services.student_service import generate_student_id

QR_TOKEN_TTL_MINUTES = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_student_qr_token(db: Session, student: Student) -> dict:
    payload = {
        "sub": str(student.id),
        "type": "student_qr",
        "jti": str(uuid.uuid4()),
    }
    raw_token = create_access_token(payload, expires_delta=timedelta(minutes=QR_TOKEN_TTL_MINUTES))
    decoded = verify_token(raw_token)
    expiry = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)

    db.query(StudentQRToken).filter(
        StudentQRToken.student_id == student.id,
        StudentQRToken.is_active.is_(True),
    ).update({"is_active": False})

    record = StudentQRToken(
        student_id=student.id,
        token_hash=_hash_token(raw_token),
        expires_at=expiry,
        is_active=True,
    )
    db.add(record)
    db.commit()
    return {
        "token": raw_token,
        "expires_at": expiry.isoformat(),
    }


def resolve_student_from_qr_token(db: Session, token: str) -> Student:
    payload = verify_token(token)
    if payload.get("type") != "student_qr":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR token type")

    token_hash = _hash_token(token)
    qr = db.query(StudentQRToken).filter(
        StudentQRToken.token_hash == token_hash,
        StudentQRToken.is_active.is_(True),
    ).first()
    if not qr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR token not found or inactive")
    if qr.expires_at < _utcnow():
        qr.is_active = False
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="QR token expired")

    now = _utcnow()
    if qr.last_scanned_at:
        elapsed = (now - qr.last_scanned_at).total_seconds()
        if elapsed < settings.QR_SCAN_COOLDOWN_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"QR scanned too recently. Try again in {int(settings.QR_SCAN_COOLDOWN_SECONDS - elapsed)}s",
            )
    qr.last_scanned_at = now
    student = db.query(Student).filter(Student.id == qr.student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    db.commit()
    return student


def deactivate_qr_token(db: Session, token: str) -> None:
    token_hash = _hash_token(token)
    qr = db.query(StudentQRToken).filter(
        StudentQRToken.token_hash == token_hash,
        StudentQRToken.is_active.is_(True),
    ).first()
    if qr:
        qr.is_active = False
        db.commit()


def build_student_scan_summary(db: Session, student: Student) -> dict:
    library = db.query(AdminDetails).filter(AdminDetails.user_id == student.admin_id).first()
    tasks_total = db.query(func.count(StudentTask.id)).filter(StudentTask.student_id == student.id).scalar() or 0
    tasks_completed = db.query(func.count(StudentTask.id)).filter(
        StudentTask.student_id == student.id,
        StudentTask.completed.is_(True),
    ).scalar() or 0
    upcoming_exams = db.query(func.count(StudentExam.id)).filter(
        StudentExam.student_id == student.auth_user_id,
        StudentExam.is_completed.is_(False),
    ).scalar() or 0
    return {
        "student_id": student.student_id,
        "student_uuid": str(student.id),
        "name": student.name,
        "email": student.email,
        "mobile_no": student.mobile_no,
        "current_library_name": library.library_name if library else "Unknown Library",
        "current_admin_id": str(student.admin_id),
        "subscription_status": student.subscription_status,
        "subscription_end": student.subscription_end.isoformat() if student.subscription_end else None,
        "task_summary": {"total": int(tasks_total), "completed": int(tasks_completed)},
        "upcoming_exams": int(upcoming_exams),
    }


def initiate_transfer(
    db: Session,
    *,
    target_admin: AdminUser,
    student: Student,
    amount: Decimal,
    plan_id: str | None,
) -> StudentTransferRequest:
    existing = db.query(StudentTransferRequest).filter(
        StudentTransferRequest.student_id == student.id,
        StudentTransferRequest.target_admin_id == target_admin.user_id,
        StudentTransferRequest.status.in_(["initiated", "payment_pending"]),
    ).first()
    if existing:
        return existing

    source_library = db.query(AdminDetails).filter(AdminDetails.user_id == student.admin_id).first()
    target_library = db.query(AdminDetails).filter(AdminDetails.user_id == target_admin.user_id).first()
    payment_reference = f"TRANSFER_{uuid.uuid4().hex[:16].upper()}"
    payment_link = f"{settings.FRONTEND_BASE_URL}/transfer/payment?ref={payment_reference}"

    transfer = StudentTransferRequest(
        student_id=student.id,
        source_admin_id=student.admin_id,
        target_admin_id=target_admin.user_id,
        plan_id=plan_id,
        amount=amount,
        status="payment_pending",
        payment_reference=payment_reference,
        payment_link=payment_link,
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    enqueue_generic_email_job(
        db=db,
        to_email=student.email,
        subject="Library transfer payment link",
        body=(
            f"Hello {student.name},\n\n"
            f"You have been invited to transfer from "
            f"{source_library.library_name if source_library else 'your current library'} to "
            f"{target_library.library_name if target_library else 'a new library'}.\n\n"
            f"Amount to pay: INR {float(amount):.2f}\n"
            f"Payment reference: {payment_reference}\n"
            f"Complete payment: {payment_link}\n\n"
            "After payment, your profile will be moved automatically."
        ),
        html_body=(
            f"<p>Hello {student.name},</p>"
            f"<p>You have been invited to transfer to "
            f"<strong>{target_library.library_name if target_library else 'a new library'}</strong>.</p>"
            f"<p><strong>Amount:</strong> INR {float(amount):.2f}<br/>"
            f"<strong>Reference:</strong> {payment_reference}</p>"
            f"<p><a href=\"{payment_link}\">Pay and complete transfer</a></p>"
        ),
    )
    return transfer


def complete_transfer_payment(db: Session, payment_reference: str) -> StudentTransferRequest:
    transfer = db.query(StudentTransferRequest).filter(
        StudentTransferRequest.payment_reference == payment_reference
    ).first()
    if not transfer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer request not found")
    if transfer.status == "completed":
        return transfer
    if transfer.status not in {"payment_pending", "paid"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transfer not payable")

    student = db.query(Student).filter(Student.id == transfer.student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    source_admin_id = student.admin_id
    source_library = db.query(AdminDetails).filter(AdminDetails.user_id == source_admin_id).first()
    source_library_id = source_library.id if source_library else None

    # Before moving the student, mark currently occupied source-library seats as freed
    # and cancel old active seat bookings so those seats become vacant immediately.
    from app.services.library_seat_reuse_service import record_freed_seats_for_removed_student

    record_freed_seats_for_removed_student(db, student)
    source_active_bookings_query = db.query(SeatBooking).filter(
        SeatBooking.student_id == student.auth_user_id,
        SeatBooking.status.in_(["pending", "approved", "active"]),
    )
    if source_library_id:
        source_active_bookings_query = source_active_bookings_query.filter(
            SeatBooking.library_id == source_library_id
        )
    source_active_bookings = source_active_bookings_query.all()
    for booking in source_active_bookings:
        booking.status = "cancelled"

    # Generate a new library-scoped student_id based on the target admin's library.
    # generate_student_id is async, but our context is sync; fall back to old ID if it fails.
    new_student_id: str | None = None
    try:
        import asyncio

        loop = asyncio.get_event_loop()
        if loop.is_running():
            # In case we're already in an event loop, don't break it; keep old ID.
            new_student_id = None
        else:
            new_student_id = loop.run_until_complete(
                generate_student_id(str(transfer.target_admin_id), db)
            )
    except Exception:
        new_student_id = None

    student.admin_id = transfer.target_admin_id
    if new_student_id:
        student.student_id = new_student_id
    student.subscription_status = "Active"
    transfer.status = "completed"
    transfer.paid_at = _utcnow()
    transfer.completed_at = _utcnow()
    db.commit()
    db.refresh(transfer)

    if source_library_id:
        invalidate_library_capacity(str(source_library_id))
    target_library = db.query(AdminDetails).filter(AdminDetails.user_id == transfer.target_admin_id).first()
    if target_library:
        invalidate_library_capacity(str(target_library.id))
    invalidate_admin_caches(str(source_admin_id))
    invalidate_admin_caches(str(transfer.target_admin_id))
    return transfer


def mark_transfer_payment_verified(
    db: Session,
    *,
    payment_reference: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
) -> StudentTransferRequest:
    transfer = db.query(StudentTransferRequest).filter(
        StudentTransferRequest.payment_reference == payment_reference
    ).first()
    if not transfer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer request not found")
    if transfer.status == "completed":
        return transfer
    if transfer.status not in {"payment_pending", "initiated", "paid"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transfer is not in payable state")

    if transfer.razorpay_order_id and transfer.razorpay_order_id != razorpay_order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order mismatch for transfer")

    transfer.razorpay_order_id = razorpay_order_id
    transfer.razorpay_payment_id = razorpay_payment_id
    transfer.payment_verified_at = _utcnow()
    transfer.status = "paid"
    transfer.paid_at = _utcnow()
    db.commit()
    db.refresh(transfer)
    return transfer


def list_transfer_requests(db: Session, admin_id) -> list[StudentTransferRequest]:
    return db.query(StudentTransferRequest).filter(
        StudentTransferRequest.target_admin_id == admin_id
    ).order_by(StudentTransferRequest.created_at.desc()).all()


def get_transfer_by_reference(db: Session, payment_reference: str) -> StudentTransferRequest:
    transfer = db.query(StudentTransferRequest).filter(
        StudentTransferRequest.payment_reference == payment_reference
    ).first()
    if not transfer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer request not found")
    return transfer
