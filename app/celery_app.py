import sys

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings


celery_app = Celery(
    "libraryconnekto",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT_SECONDS,
    imports=("app.tasks.email_tasks",),
)

# Windows: default prefork pool breaks task dispatch (billiard/multiprocessing);
# Celery raises ValueError in fast_trace_task ("not enough values to unpack").
if sys.platform == "win32":
    celery_app.conf.worker_pool = "solo"

celery_app.autodiscover_tasks(["app.tasks"])

if settings.SCHEDULER_OWNER == "worker":
    celery_app.conf.beat_schedule = {
        "subscription-notification-checks-daily": {
            "task": "app.tasks.email_tasks.run_subscription_notifications",
            "schedule": crontab(hour=1, minute=0),
        },
        # Removal requests are created inside run_subscription_notifications after expiry.
        # Optional manual trigger: POST /api/v1/student-removal/check-overdue
    }
