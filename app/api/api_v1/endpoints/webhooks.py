import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.database import get_db
from app.models.email_delivery_log import EmailDeliveryLog
from app.core.config import settings
from app.services.qr_transfer_service import complete_transfer_payment, mark_transfer_payment_verified

router = APIRouter()


@router.post("/email-events")
async def ingest_email_events(
    payload: dict,
    x_email_webhook_secret: str | None = Header(default=None),
):
    """
    Provider-agnostic webhook skeleton.
    Keep disabled by default unless EMAIL_WEBHOOK_ENABLED=true and secret is validated.
    """
    # Skeleton only for future SES/SendGrid/Postmark migration.
    return {
        "accepted": True,
        "message": "Webhook endpoint is ready; provider mapping can be enabled via config.",
        "received_events": len(payload.get("events", [])) if isinstance(payload, dict) else 0,
        "secret_provided": bool(x_email_webhook_secret),
    }


@router.post("/payments/transfer")
async def ingest_transfer_payment_webhook(
    request: Request,
    payload: dict,
    x_webhook_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Transfer payment webhook with HMAC signature verification."""
    if not settings.TRANSFER_PAYMENT_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret is not configured")
    if not x_webhook_signature:
        raise HTTPException(status_code=401, detail="Missing webhook signature")

    raw = await request.body()
    expected = hmac.new(
        settings.TRANSFER_PAYMENT_WEBHOOK_SECRET.encode("utf-8"),
        raw,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_webhook_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payment_reference = payload.get("payment_reference")
    if not payment_reference:
        raise HTTPException(status_code=400, detail="payment_reference is required")
    transfer = complete_transfer_payment(db, payment_reference)
    return {
        "success": True,
        "transfer_id": str(transfer.id),
        "status": transfer.status,
    }


@router.post("/payments/razorpay-transfer")
async def ingest_razorpay_transfer_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: str | None = Header(default=None),
):
    """Razorpay webhook for transfer payment capture events."""
    if not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=503, detail="Razorpay secret is not configured")
    if not x_razorpay_signature:
        raise HTTPException(status_code=401, detail="Missing Razorpay signature")

    raw = await request.body()
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        raw,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_razorpay_signature):
        raise HTTPException(status_code=401, detail="Invalid Razorpay signature")

    payload = json.loads(raw.decode("utf-8") or "{}")
    if payload.get("event") != "payment.captured":
        return {"success": True, "ignored": True}

    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    notes = payment_entity.get("notes", {}) or {}
    payment_reference = notes.get("payment_reference")
    razorpay_order_id = payment_entity.get("order_id")
    razorpay_payment_id = payment_entity.get("id")
    if not all([payment_reference, razorpay_order_id, razorpay_payment_id]):
        raise HTTPException(status_code=400, detail="Incomplete webhook payment payload")

    mark_transfer_payment_verified(
        db,
        payment_reference=payment_reference,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
    )
    transfer = complete_transfer_payment(db, payment_reference)
    return {
        "success": True,
        "transfer_id": str(transfer.id),
        "status": transfer.status,
    }


@router.get("/email-deliveries")
async def list_email_deliveries(
    status: str | None = Query(default=None),
    email_type: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    query = db.query(EmailDeliveryLog)
    if status:
        query = query.filter(EmailDeliveryLog.status == status)
    if email_type:
        query = query.filter(EmailDeliveryLog.email_type == email_type)
    total = query.count()
    items = query.order_by(EmailDeliveryLog.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": str(item.id),
                "email_type": item.email_type,
                "to_email": item.to_email,
                "status": item.status,
                "attempt_count": item.attempt_count,
                "last_error": item.last_error,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "sent_at": item.sent_at.isoformat() if item.sent_at else None,
            }
            for item in items
        ],
    }
