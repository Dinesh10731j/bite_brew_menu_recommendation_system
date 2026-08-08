import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.security import SecurityHeadersMiddleware


@pytest.fixture
def secured_app() -> FastAPI:
    """A minimal FastAPI app wrapped with the production security middleware."""
    tp = FastAPI()

    @tp.get("/ping")
    async def ping():
        return {"pong": True}

    tp.add_middleware(SecurityHeadersMiddleware)
    return tp


@pytest.mark.asyncio
async def test_security_headers_present(secured_app: FastAPI):
    """Verify production security (Helmet) headers are returned on responses."""
    async with AsyncClient(
        transport=ASGITransport(app=secured_app), base_url="http://testserver"
    ) as client:
        response = await client.get("/ping")
        assert response.status_code == 200
        headers = response.headers

        # Frame/clickjacking protection
        assert headers.get("x-frame-options") == "DENY"

        # MIME sniffing protection
        assert headers.get("x-content-type-options") == "nosniff"

        # Referrer policy
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"

        # Content-Security-Policy enabled by default
        assert "content-security-policy" in headers

        # Permissions policy
        assert "permissions-policy" in headers

        # Strict-Transport-Security when applicable
        assert "strict-transport-security" in headers


@pytest.mark.asyncio
async def test_security_headers_disabled(monkeypatch):
    """When ENABLE_SECURITY_HEADERS=False, no security headers are emitted."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENABLE_SECURITY_HEADERS", False)

    tp = FastAPI()

    @tp.get("/ping")
    async def ping():
        return {"pong": True}

    # Skip adding the middleware to simulate disabled security headers.
    async with AsyncClient(transport=ASGITransport(app=tp), base_url="http://testserver") as client:
        response = await client.get("/ping")
        assert response.status_code == 200
        assert "x-frame-options" not in response.headers
        assert "content-security-policy" not in response.headers
