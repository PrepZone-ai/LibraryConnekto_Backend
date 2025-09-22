import os
from dotenv import load_dotenv


class Settings:
    def __init__(self):
        # Load environment variables from a .env file if present
        load_dotenv()
        # Database
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/library_management",
        )
        # JWT
        self.SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-prod")
        self.ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

        # CORS (comma-separated list). Use '*' only for local/dev.
        allowed_origins_env = os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
        )
        self.ALLOWED_ORIGINS = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

        # File Upload
        self.UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
        self.MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(10 * 1024 * 1024)))

        # Email (optional)
        self.SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
        self.SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

        # Razorpay
        self.RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
        self.RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

        # Scheduler / Notifications
        self.EMAIL_SCHEDULER_ENABLED = os.getenv("EMAIL_SCHEDULER_ENABLED", "true").lower() in ("1", "true", "yes")
        self.SCHEDULER_INITIAL_DELAY_SECONDS = int(os.getenv("SCHEDULER_INITIAL_DELAY_SECONDS", "60"))
        self.SCHEDULER_LOOP_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_LOOP_INTERVAL_SECONDS", "60"))
        self.SUBSCRIPTION_CHECKS_DAILY_ENABLED = os.getenv("SUBSCRIPTION_CHECKS_DAILY_ENABLED", "true").lower() in ("1", "true", "yes")
        self.SUBSCRIPTION_EMAIL_FROM_SCHEDULER_ENABLED = os.getenv("SUBSCRIPTION_EMAIL_FROM_SCHEDULER_ENABLED", "false").lower() in ("1", "true", "yes")


settings = Settings()
