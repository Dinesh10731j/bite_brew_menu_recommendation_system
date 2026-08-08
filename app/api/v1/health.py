from datetime import datetime, timezone
from fastapi import APIRouter, status

from app.core.config import settings
from app.core.database import check_db_health
from app.core.redis import check_redis_health
from app.models.embedder import TextEmbedder
from app.schemas.response import HealthCheckResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health & Readiness Probe",
    description="Returns operational health of service, including Neon PostgreSQL, Upstash Redis, and ML embedding singleton states.",
)
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint for container orchestrators and monitoring probes.
    """
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()
    embedder = TextEmbedder.get_instance()
    model_ok = embedder._is_loaded or embedder._model is not None

    overall_status = "ok" if (db_ok or redis_ok or model_ok) else "degraded"

    return HealthCheckResponse(
        status=overall_status,
        environment=settings.APP_ENV,
        database_connected=db_ok,
        redis_connected=redis_ok,
        embedding_model_loaded=model_ok,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
