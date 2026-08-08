"""
Rate limiting infrastructure backed by slowapi.

Uses Redis (via `limits` async storage) when `REDIS_URL` is configured so that
limits are shared across multiple workers in production. Falls back to an
in-memory storage when Redis is unavailable (e.g. local development or tests).
"""
from typing import Optional

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.logger import logger


def _resolve_storage() -> str:
    """Return storage URI for the rate limiter."""
    if settings.REDIS_URL:
        return settings.REDIS_URL
    # In-memory fallback (single-process only). slowapi/limits supports
    # "memory://" which is a per-process in-memory store.
    return "memory://"


def get_limiter() -> Limiter:
    """
    Build and return a configured Limiter singleton.

    The limiter is initialized once at import time. Using a module-level
    singleton keeps the storage and key-functions consistent across routers.
    """
    storage_uri = _resolve_storage()
    logger.info(f"Rate limiter storage configured: {storage_uri.split('@')[-1] if '@' in storage_uri else storage_uri}")

    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=storage_uri,
        default_limits=[settings.DEFAULT_RATE_LIMIT],
        headers_enabled=False,
        in_memory_fallback_enabled=True,
        in_memory_fallback="memory://",
    )
    return limiter


def get_client_ip(request: Request) -> str:
    """Extract the client IP address from the request, honoring proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # X-Forwarded-For may contain a comma-separated chain; take the leftmost.
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Module-level singleton limiter
limiter = get_limiter()
