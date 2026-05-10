import json
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_delivery_log import EmailDeliveryLog

logger = logging.getLogger(__name__)


def enqueue_email_job(
    db: Session,
    email_type: str,
    to_email: str,
    payload: Dict[str, Any],
    provider: str = "smtp",
) -> UUID:
    from app.tasks.email_tasks import process_email_delivery

    payload_str = json.dumps(payload, default=str)
    log = EmailDeliveryLog(
        email_type=email_type,
        to_email=to_email,
        provider=provider,
        status="queued",
        payload_json=payload_str,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    delivery_mode = settings.EMAIL_DELIVERY_MODE if settings.EMAIL_DELIVERY_MODE in {"async", "sync"} else "async"
    if delivery_mode == "sync":
        logger.info("Processing email job %s (%s) synchronously", log.id, email_type)
        process_email_delivery(str(log.id))
    else:
        try:
            process_email_delivery.delay(str(log.id))
            logger.info("Queued email job %s (%s)", log.id, email_type)
        except Exception:
            # Broker unreachable — task stays in DB with status "queued" for manual retry.
            # Do NOT let a Celery broker error block the API response or crash the worker.
            logger.exception(
                "Failed to enqueue email job %s (%s) — broker may be unreachable",
                log.id,
                email_type,
            )
    return log.id


def enqueue_generic_email_job(
    db: Session,
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
) -> UUID:
    payload = {
        "subject": subject,
        "body": body,
        "html_body": html_body,
    }
    return enqueue_email_job(db, "generic", to_email, payload)
