from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, status
from fastapi.responses import JSONResponse
import os


def get_rate_limiter() -> Limiter:
    """Create and return rate limiter instance."""
    storage_uri = os.getenv("RATE_LIMIT_STORAGE", "memory://")
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["1000/hour"],
        storage_uri=storage_uri,
    )
    return limiter


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "retry_after": exc.retry_after,
        },
    )

