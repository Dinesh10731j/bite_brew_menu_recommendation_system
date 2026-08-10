from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.ai_command_center.router import router as ai_router
from app.api.v1 import health, personalization, recommend
from app.core.config import settings
from app.core.database import close_db_pool, init_db_pool
from app.core.logger import logger
from app.core.rate_limit import limiter
from app.core.redis import close_redis, init_redis
from app.core.security import SecurityHeadersMiddleware
from app.models.embedder import TextEmbedder


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager handling startup and shutdown events.
    - Pre-loads SentenceTransformers ML model singleton into memory.
    - Opens Neon PostgreSQL database connection pool.
    - Opens Upstash Redis connection pool.
    - Gracefully cleans up connection pools on termination.
    """
    logger.info(f"Starting {settings.APP_NAME} in environment '{settings.APP_ENV}'...")

    # 1. Pre-load ML Model Singleton
    try:
        TextEmbedder.initialize_on_startup()
    except Exception as e:
        logger.error(f"Error during ML model pre-loading: {str(e)}")

    # 2. Initialize Database Connection Pool
    try:
        await init_db_pool()
    except Exception as e:
        logger.error(f"Error during database pool initialization: {str(e)}")

    # 3. Initialize Redis Connection Pool
    try:
        await init_redis()
    except Exception as e:
        logger.error(f"Error during Redis initialization: {str(e)}")

    logger.info("Application startup sequence complete.")
    yield

    # 4. Shutdown & Cleanup
    logger.info("Initiating application shutdown sequence...")
    await close_db_pool()
    await close_redis()
    logger.info("Application shutdown complete.")


# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade AI Menu Recommendation microservice using FastAPI, Neon PostgreSQL (pgvector) & Upstash Redis",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Configuration for MERN Stack Integration (Express / React)
# The settings validator already normalizes CORS_ORIGINS / ALLOWED_HOSTS to a
# list regardless of whether they came from a Python default, a comma-separated
# env string, or a JSON-array env string. The isinstance guards below are a
# defensive fallback so the middleware never receives a raw string.
origins = (
    settings.CORS_ORIGINS
    if isinstance(settings.CORS_ORIGINS, list)
    else [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
)

# Trusted Host Header Allowlist (mirrors production frontend + localhost)
allowed_hosts = (
    settings.ALLOWED_HOSTS
    if isinstance(settings.ALLOWED_HOSTS, list)
    else [h.strip() for h in settings.ALLOWED_HOSTS.split(",") if h.strip()]
)

logger.info("Configured CORS origins: %s", origins)
logger.info("Configured allowed hosts: %s", allowed_hosts)

# NOTE: Starlette builds its middleware stack in LIFO order — middleware added
# LAST runs FIRST (outermost) on incoming requests. To ensure CORSMiddleware
# intercepts and answers browser OPTIONS preflight requests BEFORE
# TrustedHostMiddleware can reject them with a 400 "Invalid host header", we
# register TrustedHostMiddleware FIRST (innermost) and CORSMiddleware AFTER it
# (thus outermost). This keeps host validation for real GET/POST traffic while
# letting CORS preflights succeed regardless of the Host header.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*", "content-type"],
    # Long-lived preflight cache (CORS middleware default is 600s).
    max_age=86400,
)


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a standardized 429 Too Many Requests response."""
    logger.warning(
        "Rate limit exceeded for %s from %s",
        request.url.path,
        request.client.host if request.client else "unknown",
    )
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "status": "error",
            "detail": "Too many requests. Please slow down and try again later.",
        },
    )
    response.headers["Retry-After"] = str(exc.detail)
    return response


# Register slowapi rate-limit exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)


if settings.ENABLE_SECURITY_HEADERS:
    app.add_middleware(SecurityHeadersMiddleware)

# Include API Route Modules
app.include_router(health.router, prefix="/api/v1")
app.include_router(recommend.router, prefix="/api/v1")
app.include_router(personalization.router, prefix="/api/v1")
app.include_router(ai_router)


@app.options("/{full_path:path}", include_in_schema=False)
async def cors_preflight(full_path: str, request: Request) -> JSONResponse:
    """
    Defensive CORS preflight handler for OPTIONS requests.

    Returns a 200 OK with the appropriate CORS headers so that browsers can
    complete the preflight even if it reaches a route not explicitly defined.
    The Starlette CORSMiddleware normally handles this, but this fallback
    guarantees a non-400 response for preflight to allowed origins.
    """
    origin = request.headers.get("origin", "")
    # Reuse the module-level normalized origins list so the fallback handler can
    # never drift from what the CORSMiddleware was configured with.
    allowed = origins
    # Only reflect an origin that is explicitly allowlisted. Never fall back to
    # echoing an arbitrary origin: that would defeat CORS security.
    if origin and origin in allowed:
        response = JSONResponse(status_code=status.HTTP_200_OK, content={})
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "86400"
        if settings.CORS_ALLOW_CREDENTIALS:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    # Disallowed origin: return a 400 without an Access-Control-Allow-Origin
    # header, matching the CORSMiddleware behavior so the browser cannot
    # proceed with the cross-origin request.
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Disallowed CORS origin"},
    )


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Root redirect returning basic metadata and API documentation link."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "app_name": settings.APP_NAME,
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs",
            "health": "/api/v1/health",
            "recommend_endpoint": "/api/v1/recommend",
            "ai_command_center": "/api/ai/command-center",
        },
    )
