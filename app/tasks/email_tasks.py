import json
import logging
from datetime import datetime
from typing import Any, Dict

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.email_delivery_log import EmailDeliveryLog
from app.services.email_service import email_service
from app.services.subscription_notification_service import SubscriptionNotificationService
from app.services.student_removal_service import StudentRemovalService

logger = logging.getLogger(__name__)


def _send_by_type(email_type: str, to_email: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if email_type == "admin_verification":
        return email_service.send_admin_verification_email(
            email=to_email,
            token=payload["token"],
            base_url=payload["base_url"],
        )
    if email_type == "student_password_setup":
        return email_service.send_student_password_setup_email(
            email=to_email,
            student_id=payload["student_id"],
            mobile_no=payload["mobile_no"],
            token=payload["token"],
            library_name=payload["library_name"],
            base_url=payload["base_url"],
        )
    if email_type == "admin_password_reset":
        return email_service.send_admin_password_reset_email(
            email=to_email,
            reset_url=payload["reset_url"],
        )
    if email_type == "student_password_reset":
        return email_service.send_student_password_reset_email(
            email=to_email,
            student_id=payload["student_id"],
            library_name=payload["library_name"],
            reset_url=payload["reset_url"],
        )
    if email_type == "booking_submission":
        return email_service.send_booking_submission_email(
            email=to_email,
            student_name=payload["student_name"],
            library_name=payload["library_name"],
            booking_details=payload["booking_details"],
        )
    if email_type == "booking_approval":
        return email_service.send_booking_approval_email(
            email=to_email,
            student_name=payload["student_name"],
            library_name=payload["library_name"],
            booking_details=payload["booking_details"],
            payment_url=payload.get("payment_url"),
        )
    if email_type == "booking_rejection":
        return email_service.send_booking_rejection_email(
            email=to_email,
            student_name=payload["student_name"],
            library_name=payload["library_name"],
            booking_details=payload["booking_details"],
            rejection_reason=payload.get("rejection_reason"),
        )
    if email_type == "payment_confirmation":
        return email_service.send_payment_confirmation_email(
            email=to_email,
            student_name=payload["student_name"],
            library_name=payload["library_name"],
            plan_name=payload["plan_name"],
            amount=payload["amount"],
            payment_id=payload["payment_id"],
            subscription_end=payload["subscription_end"],
            base_url=payload.get("base_url", ""),
        )
    if email_type == "referral_invitation":
        return email_service.send_referral_invitation_email(
            email=to_email,
            referrer_name=payload["referrer_name"],
            referral_code=payload["referral_code"],
            library_name=payload.get("library_name", ""),
            invite_url=payload.get("invite_url", ""),
        )
    if email_type == "generic":
        return email_service.send_email(
            to_email=to_email,
            subject=payload["subject"],
            body=payload["body"],
            html_body=payload.get("html_body"),
        )
    raise ValueError(f"Unsupported email_type: {email_type}")


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def process_email_delivery(self, delivery_log_id: str) -> None:
    db = SessionLocal()
    try:
        log = db.query(EmailDeliveryLog).filter(EmailDeliveryLog.id == delivery_log_id).first()
        if not log:
            logger.error("Email log %s not found", delivery_log_id)
            return
        payload = json.loads(log.payload_json or "{}")
        result = _send_by_type(log.email_type, log.to_email, payload)
        log.attempt_count = int(log.attempt_count or 0) + int(result.get("attempts", 1))
        if result.get("success"):
            log.status = "sent"
            log.last_error = None
            log.sent_at = datetime.utcnow()
        else:
            log.status = "failed"
            log.last_error = result.get("error") or result.get("message") or "Unknown email error"
        db.commit()
    except Exception as exc:
        db.rollback()
        log = db.query(EmailDeliveryLog).filter(EmailDeliveryLog.id == delivery_log_id).first()
        if log:
            log.status = "failed"
            log.last_error = str(exc)
            log.attempt_count = int(log.attempt_count or 0) + 1
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task
def run_subscription_notifications() -> None:
    db = SessionLocal()
    try:
        service = SubscriptionNotificationService(db)
        service.check_and_send_subscription_warnings()
        service.check_and_send_expired_notifications()
        # After marking subscriptions expired, notify admins via removal requests
        removal_service = StudentRemovalService(db)
        removal_service.check_and_create_removal_requests()
    finally:
        db.close()


@celery_app.task
def run_overdue_student_checks() -> None:
    db = SessionLocal()
    try:
        removal_service = StudentRemovalService(db)
        removal_service.check_and_create_removal_requests()
    finally:
        db.close()
