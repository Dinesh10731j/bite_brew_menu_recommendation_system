from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, Header, status
from psycopg import AsyncConnection

from app.core.config import settings
from app.core.database import DatabasePoolManager
from app.core.logger import logger
from app.models.embedder import TextEmbedder, get_embedder
from app.services.recommendation import RecommendationService


async def get_db_connection_dep() -> AsyncGenerator[Optional[AsyncConnection], None]:
    """
    FastAPI dependency yielding an async database connection from the Neon DB pool.
    If the pool is uninitialized or DB connection fails during startup, yields None.
    """
    pool = DatabasePoolManager.get_pool()
    if pool is None:
        yield None
        return

    try:
        async with pool.connection() as conn:
            yield conn
    except Exception as e:
        logger.error(f"Error acquiring or maintaining database connection: {str(e)}")
        # Do not yield again in except block to prevent 'generator didn't stop after athrow()' error
        raise e


def get_recommendation_service(
    embedder: TextEmbedder = Depends(get_embedder),
    db_conn: Optional[AsyncConnection] = Depends(get_db_connection_dep),
) -> RecommendationService:
    """
    FastAPI dependency injecting initialized RecommendationService instance.
    """
    return RecommendationService(embedder=embedder, db_conn=db_conn)


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Optional[str]:
    """
    Optional security dependency verifying X-API-Key header against config secret.
    If API_KEY_SECRET is configured, requests must supply a valid X-API-Key.
    """
    if not settings.API_KEY_SECRET or settings.API_KEY_SECRET == "dev-secret-key-12345":
        return x_api_key

    if x_api_key != settings.API_KEY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key security header.",
        )
    return x_api_key
