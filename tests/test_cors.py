from app.core.config import settings


async def test_cors_preflight_recommend_returns_200(client):
    """The OPTIONS preflight from the allowed Netlify origin must return 200
    with the correct CORS headers — not a 400 from TrustedHostMiddleware."""
    resp = await client.options(
        "/api/v1/recommend",
        headers={
            "Origin": "https://bitebrew.netlify.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") in settings.CORS_ORIGINS


async def test_cors_preflight_disallowed_origin_rejected(client):
    """Preflights from origins NOT in the allowlist must be rejected (400) —
    this is correct CORS security behavior and prevents cross-origin abuse."""
    resp = await client.options(
        "/api/v1/recommend",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 400

