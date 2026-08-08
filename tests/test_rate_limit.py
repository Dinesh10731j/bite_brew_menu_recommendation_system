from fastapi import status
from fastapi.responses import JSONResponse
import pytest
from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from httpx import ASGITransport, AsyncClient


def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Custom 429 handler mirroring the production app; sets Retry-After."""
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"status": "error", "detail": "Rate limit exceeded. Try again later."},
    )
    response.headers["Retry-After"] = str(exc.detail)
    return response


@pytest.fixture
def isolated_limiter():
    """Provide an isolated in-memory limiter and app for rate-limit testing."""
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["3/minute"],  # Very low limit to trigger 429 quickly.
        headers_enabled=False,
        storage_uri="memory://",
    )

    test_app = FastAPI()

    @test_app.get("/limited")
    @limiter.limit("3/minute")
    async def limited_endpoint(request: Request):
        return {"ok": True}

    test_app.state.limiter = limiter
    test_app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    return test_app


@pytest.mark.asyncio
async def test_rate_limit_returns_429(isolated_limiter):
    """Verify the rate limiter enforces a 429 after the limit is exceeded."""
    transport = ASGITransport(app=isolated_limiter)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        statuses = []
        for _ in range(5):
            resp = await client.get("/limited")
            statuses.append(resp.status_code)

        # 3 allowed + 2 rejected
        assert statuses.count(200) == 3
        assert statuses.count(429) == 2


@pytest.mark.asyncio
async def test_rate_limit_has_retry_after_header(isolated_limiter):
    """Verify 429 responses include a Retry-After header."""
    transport = ASGITransport(app=isolated_limiter)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for _ in range(4):
            resp = await client.get("/limited")
        assert resp.status_code == 429
        # slowapi sets the Retry-After header on 429 responses.
        assert "retry-after" in resp.headers
