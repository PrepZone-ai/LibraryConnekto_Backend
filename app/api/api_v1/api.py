from fastapi import APIRouter

from app.api.api_v1.endpoints import auth, admin, student, booking, messaging, referral, subscription, notifications, subscription_management, payments, student_removal

api_router = APIRouter()

# Health check endpoint for the API
@api_router.get("/health")
async def api_health_check():
    return {"status": "healthy", "api_version": "v1"}

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(student.router, prefix="/student", tags=["student"])
api_router.include_router(booking.router, prefix="/booking", tags=["booking"])
api_router.include_router(messaging.router, prefix="/messaging", tags=["messaging"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(subscription_management.router, prefix="/subscription", tags=["subscription-management"])
api_router.include_router(payments.router, prefix="/payment", tags=["payments"])
api_router.include_router(student_removal.router, prefix="/student-removal", tags=["student-removal"])
api_router.include_router(referral.router, prefix="/referral", tags=["referral"])
api_router.include_router(subscription.router, prefix="/subscription", tags=["subscription"])
