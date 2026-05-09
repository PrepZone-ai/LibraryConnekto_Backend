from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import os
from datetime import datetime
import uuid
import logging

from app.core.config import settings
from app.core.mime_guess import get_mime_from_buffer
from app.api.api_v1.api import api_router
from app.database import engine, init_db, get_db
from app.models import Base
from app.services.notification_scheduler import start_notification_scheduler, stop_notification_scheduler
from app.middleware.rate_limit import (
    get_rate_limiter,
    rate_limit_exceeded_handler,
)
from slowapi.errors import RateLimitExceeded
from app.middleware.security import SecurityHeadersMiddleware
from app.core.logging_config import logger
from app.core.sentry_config import init_sentry

init_sentry()

_app_logger = logging.getLogger(__name__)


async def _sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Return a clean JSON 503 for DB-layer errors instead of a raw text/plain 500."""
    _app_logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable. Please try again."},
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all so unhandled exceptions always produce JSON, never Starlette text/plain."""
    _app_logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# Create FastAPI app
app = FastAPI(
    title="Library Management System API",
    description="FastAPI backend for Library Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

limiter = get_rate_limiter()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# These two handlers ensure unhandled DB and runtime exceptions always return JSON,
# never the raw text/plain "Internal Server Error" from Starlette's ServerErrorMiddleware.
app.add_exception_handler(SQLAlchemyError, _sqlalchemy_error_handler)
app.add_exception_handler(Exception, _unhandled_error_handler)

# CORS middleware - must be added before any routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.add_middleware(SecurityHeadersMiddleware)

# Create upload directory if it doesn't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Add OPTIONS handler for CORS preflight requests
@app.options("/{full_path:path}")
async def options_handler():
    return {"message": "CORS preflight handled"}

# Custom CORS middleware removed - using FastAPI's built-in CORS middleware instead

@app.on_event("startup")
async def startup_event():
    """Create database tables on startup and start notification scheduler."""
    try:
        init_db()
    except Exception as e:
        logger.error(
            "Database initialization failed",
            extra={"event": "db_init", "error": str(e)},
        )
    
    # Start the notification scheduler if enabled
    if getattr(settings, "EMAIL_SCHEDULER_ENABLED", True) and getattr(settings, "SCHEDULER_OWNER", "worker") == "api":
        await start_notification_scheduler()
    else:
        print("[Scheduler] API scheduler disabled (managed by worker/beat or config).")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop notification scheduler on shutdown"""
    await stop_notification_scheduler()

@app.get("/")
async def root():
    return {
        "message": "Library Management System API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "authentication": "/api/v1/auth",
            "admin": "/api/v1/admin",
            "student": "/api/v1/student",
            "booking": "/api/v1/booking",
            "messaging": "/api/v1/messaging",
            "notifications": "/api/v1/notifications",
            "subscription-management": "/api/v1/subscription",
            "payments": "/api/v1/payment",
            "student-removal": "/api/v1/student-removal",
            "referral": "/api/v1/referral",
            "subscription": "/api/v1/subscription",
            "health": "/health",
            "upload": "/upload"
        }
    }

@app.get("/health")
async def health_check():
    """Enhanced health check with DB and cache connectivity."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }

    # Check database
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        health_status["database"] = "connected"
        db.close()
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = f"error: {str(e)}"

    # Check Redis cache (optional)
    try:
        from app.core.cache import get_redis

        r = get_redis()
        if r:
            r.ping()
            health_status["cache"] = "connected"
        else:
            health_status["cache"] = "disconnected"
    except Exception:
        health_status["cache"] = "disconnected"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)

# File upload endpoint
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Secure file upload with size and MIME-type validation."""
    # Read content once to inspect and then save
    content = await file.read()

    # Check file size (use settings.MAX_FILE_SIZE)
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    # Verify MIME type (pure-Python; no libmagic DLL on Windows)
    mime_type = get_mime_from_buffer(content)
    if not mime_type or mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="File type not allowed")

    # Generate safe filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Save file
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    return {
        "filename": unique_filename,
        "original_filename": file.filename,
        "url": f"/uploads/{unique_filename}",
        "size": len(content),
        "mime_type": mime_type,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        port=8000,
        reload=True
    )
