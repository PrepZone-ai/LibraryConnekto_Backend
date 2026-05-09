import os
from dotenv import load_dotenv


class Settings:
    def __init__(self):
        # Load environment variables from a .env file if present
        load_dotenv()
        # Environment / Debug
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        self.DEBUG = os.getenv("DEBUG", "true").lower() in ("1", "true", "yes")

        # Database
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/library_management",
        )
        # Database Pool Settings
        self.DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
        self.DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "40"))
        self.DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))

        # JWT / Security
        env_secret = os.getenv("SECRET_KEY")
        if env_secret:
            self.SECRET_KEY = env_secret
        else:
            if self.DEBUG:
                # Only allow a weak default in explicit debug/development mode
                self.SECRET_KEY = "dev-secret-key"
            else:
                raise ValueError(
                    "SECRET_KEY environment variable must be set in non-debug environments."
                )
        self.ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

        # Public web app URL (password reset / setup links in emails)
        self.FRONTEND_BASE_URL = os.getenv(
            "FRONTEND_BASE_URL",
            "http://127.0.0.1:5173",
        ).rstrip("/")

        # CORS (comma-separated list). Use '*' only for local/dev.
        allowed_origins_env = os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
        )
        self.ALLOWED_ORIGINS = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
        # Ensure the configured frontend can call the API even if ALLOWED_ORIGINS was omitted in prod.
        if self.FRONTEND_BASE_URL and self.FRONTEND_BASE_URL not in self.ALLOWED_ORIGINS:
            self.ALLOWED_ORIGINS.append(self.FRONTEND_BASE_URL)

        # File Upload
        self.UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
        self.MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(10 * 1024 * 1024)))

        # Email (optional)
        self.SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
        self.SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        self.SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "LibraryConnekto")

        # Razorpay
        self.RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
        self.RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
        # When true, non-token orders include Route transfers to each library's linked account.
        # Rs.1 booking token orders never include transfers (platform keeps them).
        self.RAZORPAY_ROUTE_ENABLED = os.getenv("RAZORPAY_ROUTE_ENABLED", "true").lower() in (
            "1",
            "true",
            "yes",
        )

        # Redis (cache / rate limiting)
        self.REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        self.REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
        self.REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
        self.REDIS_DB = int(os.getenv("REDIS_DB", "0"))

        # Celery / Queue
        redis_auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        self.CELERY_BROKER_URL = os.getenv(
            "CELERY_BROKER_URL",
            f"redis://{redis_auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}",
        )
        self.CELERY_RESULT_BACKEND = os.getenv(
            "CELERY_RESULT_BACKEND",
            self.CELERY_BROKER_URL,
        )
        self.CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))
        self.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT_SECONDS", "120"))
        self.CELERY_TASK_TIME_LIMIT_SECONDS = int(os.getenv("CELERY_TASK_TIME_LIMIT_SECONDS", "180"))
        self.EMAIL_DELIVERY_MODE = os.getenv("EMAIL_DELIVERY_MODE", "async").lower()  # async|sync

        # Scheduler / Notifications
        self.EMAIL_SCHEDULER_ENABLED = os.getenv("EMAIL_SCHEDULER_ENABLED", "true").lower() in ("1", "true", "yes")
        self.SCHEDULER_OWNER = os.getenv("SCHEDULER_OWNER", "worker")  # api|worker
        self.SCHEDULER_INITIAL_DELAY_SECONDS = int(os.getenv("SCHEDULER_INITIAL_DELAY_SECONDS", "60"))
        self.SCHEDULER_LOOP_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_LOOP_INTERVAL_SECONDS", "60"))
        self.SUBSCRIPTION_CHECKS_DAILY_ENABLED = os.getenv("SUBSCRIPTION_CHECKS_DAILY_ENABLED", "true").lower() in ("1", "true", "yes")
        self.SUBSCRIPTION_EMAIL_FROM_SCHEDULER_ENABLED = os.getenv("SUBSCRIPTION_EMAIL_FROM_SCHEDULER_ENABLED", "false").lower() in ("1", "true", "yes")

        # Attendance automation / scale guards
        self.ATTENDANCE_LOCATION_MAX_DISTANCE_METERS = int(os.getenv("ATTENDANCE_LOCATION_MAX_DISTANCE_METERS", "100"))
        self.ATTENDANCE_CHECK_LOCATION_RATE_LIMIT_SECONDS = int(os.getenv("ATTENDANCE_CHECK_LOCATION_RATE_LIMIT_SECONDS", "300"))
        self.ATTENDANCE_AUTO_CHECKOUT_STALE_MINUTES = int(os.getenv("ATTENDANCE_AUTO_CHECKOUT_STALE_MINUTES", "25"))
        self.ATTENDANCE_LIBRARY_LOCATION_CACHE_TTL_SECONDS = int(os.getenv("ATTENDANCE_LIBRARY_LOCATION_CACHE_TTL_SECONDS", "900"))
        self.QR_SCAN_COOLDOWN_SECONDS = int(os.getenv("QR_SCAN_COOLDOWN_SECONDS", "30"))
        self.TRANSFER_PAYMENT_WEBHOOK_SECRET = os.getenv("TRANSFER_PAYMENT_WEBHOOK_SECRET", "")


settings = Settings()
