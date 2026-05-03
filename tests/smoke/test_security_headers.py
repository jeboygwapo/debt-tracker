"""SMOKE-022, 023 — security headers and request size limit.

Ensures the SecurityHeadersMiddleware and RequestSizeLimitMiddleware
remain wired in ``app/__init__.py``.
"""

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.anyio]


async def test_smoke_022_security_headers_present(smoke_client):
    r = await smoke_client.get("/welcome")
    assert r.status_code == 200
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Content-Security-Policy" in r.headers
    csp = r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp


async def test_smoke_023_request_size_limit_413(smoke_client):
    """1 MB cap on Content-Length — anything larger must 413 before routing."""
    oversized = "x" * (2 * 1024 * 1024)  # 2 MB
    r = await smoke_client.post(
        "/login",
        content=oversized,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 413
