from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.api.api_v1.api import api_router
from app.database import engine, init_db
from app.models import Base
from app.services.notification_scheduler import start_notification_scheduler, stop_notification_scheduler
from app.core.config import settings

# Create FastAPI app
app = FastAPI(
    title="Library Management System API",
    description="FastAPI backend for Library Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware - must be added before any routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

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
    """Create database tables on startup and start notification scheduler"""
    # Initialize database and create tables
    try:
        init_db()
        print("✅ Database initialization completed")
    except Exception as e:
        print(f"⚠️  Database initialization failed: {e}")
        # Don't exit, let the app start anyway
    
    # Start the notification scheduler if enabled
    if getattr(settings, "EMAIL_SCHEDULER_ENABLED", True):
        await start_notification_scheduler()
    else:
        print("[Scheduler] EMAIL_SCHEDULER_ENABLED is false; scheduler will not start.")

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
    return {"status": "healthy"}

# File upload endpoint
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file"""
    import uuid

    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    return {
        "filename": unique_filename,
        "original_filename": file.filename,
        "url": f"/uploads/{unique_filename}",
        "size": len(content)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        port=8000,
        reload=True
    )
