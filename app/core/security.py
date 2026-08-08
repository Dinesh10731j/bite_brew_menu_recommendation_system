"""
Custom HTTP Security Headers middleware — a dependency-free "Helmet" for
FastAPI/Starlette.

Injects production-grade security headers on every response:
- Strict-Transport-Security (HSTS)
- X-Frame-Options (clickjacking protection)
- X-Content-Type-Options (MIME sniffing prevention)
- Content-Security-Policy (CSP)
- Referrer-Policy
- Permissions-Policy
- X-XSS-Protection (legacy, where supported)
"""
from typing import Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that attaches hardened security headers to every
    response, mirroring the behavior of the Node.js `helmet` package.
    """

    def __init__(self, app):
        super().__init__(app)
        self._headers = self._build_headers()

    def _build_headers(self) -> Dict[str, str]:
        """Build the static security header set based on application settings."""
        headers: Dict[str, str] = {}

        # Strict-Transport-Security (only meaningful over HTTPS; applied always for
        # clients that already use HTTPS).
        if settings.HSTS_MAX_AGE > 0:
            hsts = f"max-age={settings.HSTS_MAX_AGE}"
            if settings.HSTS_INCLUDE_SUBDOMAINS:
                hsts += "; includeSubDomains"
            if settings.HSTS_PRELOAD:
                hsts += "; preload"
            headers["Strict-Transport-Security"] = hsts

        # Clickjacking protection
        headers["X-Frame-Options"] = "DENY"

        # MIME sniffing prevention
        headers["X-Content-Type-Options"] = "nosniff"

        # Content-Security-Policy
        if settings.CSP_ENABLED:
            csp = (
                f"default-src {settings.CSP_DEFAULT_SRC}; "
                f"connect-src {settings.CSP_CONNECT_SRC}; "
                "img-src 'self' data: https:; "
                "style-src 'self' 'unsafe-inline'; "
                "font-src 'self' data: https:; "
                "script-src 'self' 'unsafe-inline'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "frame-ancestors 'none'"
            )
            headers["Content-Security-Policy"] = csp

        # Referrer-Policy
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy
        headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # Legacy XSS protection
        headers["X-XSS-Protection"] = "1; mode=block"

        return headers

    async def dispatch(
        self, request: Request, call_next
    ) -> Response:
        response = await call_next(request)
        for name, value in self._headers.items():
            response.headers.setdefault(name, value)
        return response


# Backwards-compatible alias for parity with the Talisman import used elsewhere.
class Talisman:
    """
    Compatibility shim for the `talisman` package that was considered but is
    not available on PyPI. Provides a Flask-style Talisman ASGI wrapper that
    installs the SecurityHeadersMiddleware on the provided ASGI app.
    """

    def __init__(self, asgi_app, force_https: bool = False, **kwargs):
        self.app = asgi_app
        self.force_https = force_https
        # Wrap the underlying ASGI app with the security headers middleware.
        from starlette.applications import Starlette

        if isinstance(asgi_app, Starlette):
            asgi_app.add_middleware(SecurityHeadersMiddleware)
        self.kwargs = kwargs

    def __call__(self, scope, receive, send):
        # If force_https is enabled and the request is not secure, redirect.
        if self.force_https and scope.get("scheme") != "https":
            self._force_https_response(scope, receive, send)
            return
        return self.app(scope, receive, send)

    def _force_https_response(self, scope, receive, send):
        """Return an HTTPS-redirect response for insecure requests."""
        from starlette.datastructures import URL
        from starlette.responses import RedirectResponse

        url = URL(scope=scope)
        https_url = str(url).replace("http://", "https://", 1)
        response = RedirectResponse(url=https_url, status_code=307)
        asgi = response(scope, receive, send)
        return asgi
