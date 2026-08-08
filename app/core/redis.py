import json
from typing import Any, Optional
import redis.asyncio as redis

from app.core.config import settings
from app.core.logger import logger


class RedisManager:
    """
    Singleton connection pool manager for Upstash / Standard Redis
    using redis.asyncio.
    """

    _redis: Optional[redis.Redis] = None

    @classmethod
    async def initialize(cls) -> None:
        """Initialize the async Redis client."""
        if not settings.REDIS_URL:
            logger.warning("REDIS_URL not configured. Redis caching is disabled.")
            return

        if cls._redis is None:
            try:
                logger.info("Initializing Redis connection pool...")
                cls._redis = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=5.0,
                )
                # Test connection ping
                await cls._redis.ping()
                logger.info("Redis connection established successfully.")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                cls._redis = None

    @classmethod
    async def close(cls) -> None:
        """Gracefully close Redis connection."""
        if cls._redis is not None:
            logger.info("Closing Redis connection...")
            await cls._redis.aclose()
            cls._redis = None
            logger.info("Redis connection closed.")

    @classmethod
    def get_client(cls) -> Optional[redis.Redis]:
        """Return active Redis client."""
        return cls._redis


async def init_redis() -> None:
    """Startup hook for Redis connection pool."""
    await RedisManager.initialize()


async def close_redis() -> None:
    """Shutdown hook for Redis connection pool."""
    await RedisManager.close()


async def check_redis_health() -> bool:
    """Check Redis health with a PING command."""
    client = RedisManager.get_client()
    if client is None:
        return False
    try:
        res = await client.ping()
        return bool(res)
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        return False


async def get_cached_response(key: str) -> Optional[dict]:
    """Retrieve and deserialize JSON data from Redis cache by key."""
    if not settings.ENABLE_CACHE:
        return None

    client = RedisManager.get_client()
    if client is None:
        return None

    try:
        val = await client.get(key)
        if val:
            logger.info(f"Cache HIT for key: {key}")
            return json.loads(val)
    except Exception as e:
        logger.error(f"Error reading from Redis cache: {str(e)}")
    return None


async def set_cached_response(key: str, data: dict, ttl: int = 3600) -> bool:
    """Serialize and store dictionary data into Redis cache with TTL."""
    if not settings.ENABLE_CACHE:
        return False

    client = RedisManager.get_client()
    if client is None:
        return False

    try:
        serialized = json.dumps(data)
        await client.setex(key, ttl, serialized)
        logger.info(f"Cached response stored in Redis for key: {key} (TTL={ttl}s)")
        return True
    except Exception as e:
        logger.error(f"Error writing to Redis cache: {str(e)}")
        return False
