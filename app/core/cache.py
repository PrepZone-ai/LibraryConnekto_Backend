"""
Redis cache utilities for self-hosted Redis.
Uses REDIS_HOST, REDIS_PORT, REDIS_PASSWORD from settings.
If Redis is unavailable, all cache operations are no-ops (app continues to work).
"""
import json
import logging
from functools import wraps
from typing import Any, Callable, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy singleton Redis client; None if Redis is unavailable
_redis_client: Optional[Any] = None

# Key prefixes for namespacing
PREFIX_ADMIN_DASHBOARD = "admin_dashboard"
PREFIX_ADMIN_ATTENDANCE_TRENDS = "admin_attendance_trends"
PREFIX_ADMIN_REVENUE_TRENDS = "admin_revenue_trends"
PREFIX_STUDENT_DASHBOARD = "student_dashboard"
PREFIX_LIBRARY_OCCUPIED = "library_occupied"
PREFIX_ATTENDANCE_LOCATION_RATE_LIMIT = "attendance_location_rate_limit"
PREFIX_ADMIN_LOCATION = "admin_location"


def get_redis():
    """Return Redis client or None if unavailable (lazy init, resilient to connection failure)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.warning("Redis unavailable; cache disabled: %s", e)
        _redis_client = False  # mark as attempted so we don't retry every time
        return None


# For backwards compatibility: expose a client that may be None
def _client():
    c = get_redis()
    return c if c is not False else None


# Expose as redis_client for code that does redis_client.get(); they must handle None
class _RedisProxy:
    def __getattr__(self, name):
        c = _client()
        if c is None:
            raise AttributeError("Redis is not available")
        return getattr(c, name)


redis_client = _RedisProxy()


def cache_key(prefix: str, *parts: Any) -> str:
    """Build a cache key from a prefix and stringifiable parts."""
    return ":".join([prefix] + [str(p) for p in parts])


# Key builders for consistent invalidation
def admin_dashboard_key(admin_id: str) -> str:
    return cache_key(PREFIX_ADMIN_DASHBOARD, admin_id)


def admin_attendance_trends_key(admin_id: str, days: int) -> str:
    return cache_key(PREFIX_ADMIN_ATTENDANCE_TRENDS, admin_id, days)


def admin_revenue_trends_key(admin_id: str, months: int) -> str:
    return cache_key(PREFIX_ADMIN_REVENUE_TRENDS, admin_id, months)


def student_dashboard_key(student_id: str) -> str:
    return cache_key(PREFIX_STUDENT_DASHBOARD, student_id)


def library_occupied_key(library_id: str) -> str:
    return cache_key(PREFIX_LIBRARY_OCCUPIED, library_id)


def attendance_location_rate_limit_key(student_id: str) -> str:
    return cache_key(PREFIX_ATTENDANCE_LOCATION_RATE_LIMIT, student_id)


def admin_location_key(admin_id: str) -> str:
    return cache_key(PREFIX_ADMIN_LOCATION, admin_id)


def get_cached(key: str) -> Optional[Any]:
    """Get a JSON-serialized value from cache. Returns None on miss or if Redis is down."""
    client = _client()
    if not client:
        return None
    try:
        raw = client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.debug("Cache get failed for %s: %s", key, e)
        return None


def set_cached(key: str, value: Any, ttl: int = 60) -> None:
    """Set a value in cache with TTL (seconds). No-op if Redis is down."""
    client = _client()
    if not client:
        return
    try:
        client.setex(key, ttl, json.dumps(value, default=str))
    except Exception as e:
        logger.debug("Cache set failed for %s: %s", key, e)


def set_if_absent(key: str, value: str, ttl: int) -> bool:
    """Set key only if absent. Returns True when set, else False."""
    client = _client()
    if not client:
        return True  # fail-open when redis is unavailable
    try:
        return bool(client.set(key, value, ex=ttl, nx=True))
    except Exception as e:
        logger.debug("Cache set-if-absent failed for %s: %s", key, e)
        return True


def invalidate_cache(pattern: str) -> None:
    """Delete all keys matching pattern (e.g. 'admin_dashboard:*'). No-op if Redis is down."""
    client = _client()
    if not client:
        return
    try:
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
    except Exception as e:
        logger.debug("Cache invalidate failed for %s: %s", pattern, e)


def invalidate_admin_caches(admin_id: str) -> None:
    """Invalidate all admin-related caches for the given admin (dashboard, trends)."""
    invalidate_cache(admin_dashboard_key(admin_id))
    invalidate_cache(f"{PREFIX_ADMIN_ATTENDANCE_TRENDS}:{admin_id}:*")
    invalidate_cache(f"{PREFIX_ADMIN_REVENUE_TRENDS}:{admin_id}:*")


def invalidate_student_dashboard(student_id: str) -> None:
    """Invalidate student dashboard cache for the given student."""
    invalidate_cache(f"{PREFIX_STUDENT_DASHBOARD}:{student_id}")


def invalidate_library_capacity(library_id: str) -> None:
    """Invalidate cached occupied count for a library (after booking confirm/cancel)."""
    invalidate_cache(f"{PREFIX_LIBRARY_OCCUPIED}:{library_id}")


def cached(ttl: int = 60, key_builder: Optional[Callable[..., str]] = None):
    """
    Decorator to cache async function results in Redis.
    key_builder: callable(*args, **kwargs) -> str. If None, key is func.__name__ (not recommended for routes with Depends).
    If Redis is unavailable, the function is called normally.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if key_builder is not None:
                try:
                    key = key_builder(*args, **kwargs)
                except Exception:
                    key = None
            else:
                key = cache_key(func.__name__, *args, **kwargs)
            if key:
                val = get_cached(key)
                if val is not None:
                    return val
            result = await func(*args, **kwargs)
            if key:
                set_cached(key, result, ttl)
            return result

        return async_wrapper

    return decorator
