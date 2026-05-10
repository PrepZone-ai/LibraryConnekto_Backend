import os
from dotenv import load_dotenv


def _env(key: str, default: str = "") -> str:
    """Read an env var and strip any stray Windows carriage-return characters.

    Systemd's EnvironmentFile= and some CI systems do not strip \\r from
    values when the .env file was saved with Windows (CRLF) line endings.
    This causes database URLs, secrets, and other values to silently include
    a trailing \\r which breaks psycopg2 and other libraries.
    """
    return os.getenv(key, default).strip("\r\n ")


class Settings:
    def __init__(self):
        # Load environment variables from a .env file if present
        load_dotenv()
        # Environment / Debug
        self.ENVIRONMENT = _env("ENVIRONMENT", "development")
        self.DEBUG = _env("DEBUG", "true").lower() in ("1", "true", "yes")

        # Database
        self.DATABASE_URL = _env(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/library_management",
        )
        # Database Pool Settings
        # Budget per gunicorn worker with 4 workers and Postgres max_connections=100:
        #   sync  pool: pool_size=5 + max_overflow=10 = 15 connections max
        #   async pool: pool_size=2 + max_overflow=3  =  5 connections max
        #   per worker max = 20 connections × 4 workers = 80 total  (<100 ✓)
        # Raise limits via env vars only if your Postgres server is configured for more.
        self.DB_POOL_SIZE = int(_env("DB_POOL_SIZE", "5"))
        self.DB_MAX_OVERFLOW = int(_env("DB_MAX_OVERFLOW", "10"))
        # Async pool is kept small — most endpoints use the sync engine.
        self.DB_ASYNC_POOL_SIZE = int(_env("DB_ASYNC_POOL_SIZE", "2"))
        self.DB_ASYNC_MAX_OVERFLOW = int(_env("DB_ASYNC_MAX_OVERFLOW", "3"))
        self.DB_POOL_RECYCLE = int(_env("DB_POOL_RECYCLE", "1800"))

        # JWT / Security
        env_secret = _env("SECRET_KEY")
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
        self.ALGORITHM = _env("JWT_ALGORITHM", "HS256")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(_env("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8 hours

        # Public web app URL (password reset / setup links in emails)
        self.FRONTEND_BASE_URL = _env("FRONTEND_BASE_URL", "http://127.0.0.1:5173").rstrip("/")

        # CORS (comma-separated list). Use '*' only for local/dev.
        allowed_origins_env = _env(
            "ALLOWED_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
        )
        self.ALLOWED_ORIGINS = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
        # Ensure the configured frontend can call the API even if ALLOWED_ORIGINS was omitted in prod.
        if self.FRONTEND_BASE_URL and self.FRONTEND_BASE_URL not in self.ALLOWED_ORIGINS:
            self.ALLOWED_ORIGINS.append(self.FRONTEND_BASE_URL)

        # File Upload
        self.UPLOAD_DIR = _env("UPLOAD_DIR", "uploads")
        self.MAX_FILE_SIZE = int(_env("MAX_FILE_SIZE", str(10 * 1024 * 1024)))

        # Email (optional)
        self.SMTP_HOST = _env("SMTP_HOST", "smtp.gmail.com")
        self.SMTP_PORT = int(_env("SMTP_PORT", "465"))
        self.SMTP_USERNAME = _env("SMTP_USERNAME", "")
        self.SMTP_PASSWORD = _env("SMTP_PASSWORD", "")
        self.SMTP_FROM_NAME = _env("SMTP_FROM_NAME", "LibraryConnekto")

        # Razorpay
        self.RAZORPAY_KEY_ID = _env("RAZORPAY_KEY_ID", "")
        self.RAZORPAY_KEY_SECRET = _env("RAZORPAY_KEY_SECRET", "")
        # When true, non-token orders include Route transfers to each library's linked account.
        # Rs.1 booking token orders never include transfers (platform keeps them).
        self.RAZORPAY_ROUTE_ENABLED = _env("RAZORPAY_ROUTE_ENABLED", "true").lower() in (
            "1",
            "true",
            "yes",
        )

        # Redis (cache / rate limiting)
        self.REDIS_HOST = _env("REDIS_HOST", "localhost")
        self.REDIS_PORT = int(_env("REDIS_PORT", "6379"))
        self.REDIS_PASSWORD = _env("REDIS_PASSWORD") or None
        self.REDIS_DB = int(_env("REDIS_DB", "0"))

        # Celery / Queue
        redis_auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        self.CELERY_BROKER_URL = _env(
            "CELERY_BROKER_URL",
            f"redis://{redis_auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}",
        )
        self.CELERY_RESULT_BACKEND = _env(
            "CELERY_RESULT_BACKEND",
            self.CELERY_BROKER_URL,
        )
        self.CELERY_WORKER_CONCURRENCY = int(_env("CELERY_WORKER_CONCURRENCY", "4"))
        self.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS = int(_env("CELERY_TASK_SOFT_TIME_LIMIT_SECONDS", "120"))
        self.CELERY_TASK_TIME_LIMIT_SECONDS = int(_env("CELERY_TASK_TIME_LIMIT_SECONDS", "180"))
        self.EMAIL_DELIVERY_MODE = _env("EMAIL_DELIVERY_MODE", "async").lower()  # async|sync

        # Scheduler / Notifications
        self.EMAIL_SCHEDULER_ENABLED = _env("EMAIL_SCHEDULER_ENABLED", "true").lower() in ("1", "true", "yes")
        self.SCHEDULER_OWNER = _env("SCHEDULER_OWNER", "worker")  # api|worker
        self.SCHEDULER_INITIAL_DELAY_SECONDS = int(_env("SCHEDULER_INITIAL_DELAY_SECONDS", "60"))
        self.SCHEDULER_LOOP_INTERVAL_SECONDS = int(_env("SCHEDULER_LOOP_INTERVAL_SECONDS", "60"))
        self.SUBSCRIPTION_CHECKS_DAILY_ENABLED = _env("SUBSCRIPTION_CHECKS_DAILY_ENABLED", "true").lower() in ("1", "true", "yes")
        self.SUBSCRIPTION_EMAIL_FROM_SCHEDULER_ENABLED = _env("SUBSCRIPTION_EMAIL_FROM_SCHEDULER_ENABLED", "false").lower() in ("1", "true", "yes")

        # Attendance automation / scale guards
        self.ATTENDANCE_LOCATION_MAX_DISTANCE_METERS = int(_env("ATTENDANCE_LOCATION_MAX_DISTANCE_METERS", "100"))
        self.ATTENDANCE_CHECK_LOCATION_RATE_LIMIT_SECONDS = int(_env("ATTENDANCE_CHECK_LOCATION_RATE_LIMIT_SECONDS", "300"))
        self.ATTENDANCE_AUTO_CHECKOUT_STALE_MINUTES = int(_env("ATTENDANCE_AUTO_CHECKOUT_STALE_MINUTES", "25"))
        self.ATTENDANCE_LIBRARY_LOCATION_CACHE_TTL_SECONDS = int(_env("ATTENDANCE_LIBRARY_LOCATION_CACHE_TTL_SECONDS", "900"))
        self.QR_SCAN_COOLDOWN_SECONDS = int(_env("QR_SCAN_COOLDOWN_SECONDS", "30"))
        self.TRANSFER_PAYMENT_WEBHOOK_SECRET = _env("TRANSFER_PAYMENT_WEBHOOK_SECRET", "")


settings = Settings()
