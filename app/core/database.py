import asyncio
import contextlib
import sys
from typing import AsyncGenerator, Optional
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

# Fix Windows ProactorEventLoop compatibility for psycopg async mode
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.config import settings
from app.core.logger import logger


class DatabasePoolManager:
    """
    Singleton connection pool manager handling database connection lifecycle
    with psycopg3 AsyncConnectionPool for Neon PostgreSQL.
    """

    _pool: Optional[AsyncConnectionPool] = None

    @classmethod
    async def initialize(cls) -> None:
        """Initialize the async database connection pool."""
        if cls._pool is None:
            try:
                logger.info("Initializing Neon PostgreSQL AsyncConnectionPool...")
                cls._pool = AsyncConnectionPool(
                    conninfo=settings.DATABASE_URL,
                    min_size=settings.DB_POOL_MIN_SIZE,
                    max_size=settings.DB_POOL_MAX_SIZE,
                    timeout=settings.DB_TIMEOUT_SECONDS,
                    kwargs={"row_factory": dict_row},
                    open=False,
                )
                await cls._pool.open()
                logger.info("Database connection pool established successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize database connection pool: {str(e)}")
                cls._pool = None

    @classmethod
    async def close(cls) -> None:
        """Gracefully shutdown the database connection pool."""
        if cls._pool is not None:
            logger.info("Closing database connection pool...")
            await cls._pool.close()
            cls._pool = None
            logger.info("Database connection pool closed.")

    @classmethod
    def get_pool(cls) -> Optional[AsyncConnectionPool]:
        """Return active connection pool instance."""
        return cls._pool


async def init_db_pool() -> None:
    """Startup lifespan hook for database pool."""
    await DatabasePoolManager.initialize()


async def close_db_pool() -> None:
    """Shutdown lifespan hook for database pool."""
    await DatabasePoolManager.close()


@contextlib.asynccontextmanager
async def get_db_connection():
    """
    Async context manager yielding a database connection from the connection pool.
    """
    pool = DatabasePoolManager.get_pool()
    if pool is None:
        raise RuntimeError(
            "Database connection pool is not initialized. Please ensure DATABASE_URL is valid and pool is open."
        )

    async with pool.connection() as conn:
        yield conn


async def check_db_health() -> bool:
    """
    Executes a SELECT 1 query to verify database connectivity.
    """
    pool = DatabasePoolManager.get_pool()
    if pool is None:
        return False

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1;")
                result = await cur.fetchone()
                return result is not None
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False
