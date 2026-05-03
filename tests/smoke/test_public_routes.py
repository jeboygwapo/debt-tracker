"""SMOKE-002..007, 024, 025 — public surface area.

Covers the unauthenticated routes that must answer without a session:
landing, login GET, register gate (on/off), 404 fallthrough, and a
sample of redirects from protected pages.
"""

import os

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.anyio]


async def test_smoke_002_landing_page(smoke_client):
    r = await smoke_client.get("/welcome")
    assert r.status_code == 200
    assert "Sign In" in r.text or "Get Started" in r.text


async def test_smoke_003_login_form_renders(smoke_client):
    r = await smoke_client.get("/login")
    assert r.status_code == 200
    # CSRF token must be present in the rendered form
    assert 'name="csrf_token"' in r.text
    assert "Sign In" in r.text


async def test_smoke_004_root_redirects_to_welcome(smoke_client_no_redirect):
    r = await smoke_client_no_redirect.get("/")
    assert r.status_code == 302
    assert r.headers["location"].endswith("/welcome")


async def test_smoke_005_protected_route_redirects(smoke_client_no_redirect):
    r = await smoke_client_no_redirect.get("/settings")
    assert r.status_code == 302
    assert "/welcome" in r.headers["location"]


async def test_smoke_006_unknown_route_404(smoke_client):
    r = await smoke_client.get("/this-route-does-not-exist")
    assert r.status_code == 404


async def test_smoke_007_register_disabled_redirects(smoke_client_no_redirect):
    """When ALLOW_REGISTRATION is unset/false, /register redirects to /login."""
    prev = os.environ.get("ALLOW_REGISTRATION")
    os.environ["ALLOW_REGISTRATION"] = "false"
    try:
        r = await smoke_client_no_redirect.get("/register")
        assert r.status_code == 302
        assert r.headers["location"].endswith("/login")
    finally:
        if prev is None:
            os.environ.pop("ALLOW_REGISTRATION", None)
        else:
            os.environ["ALLOW_REGISTRATION"] = prev


async def test_smoke_007b_register_enabled_form(smoke_client):
    """When ALLOW_REGISTRATION=true, /register renders a form with CSRF.

    Companion to SMOKE-007 (disabled redirects). Together they prove the
    self-signup gate is wired correctly.
    """
    prev = os.environ.get("ALLOW_REGISTRATION")
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        r = await smoke_client.get("/register")
        assert r.status_code == 200
        assert 'name="csrf_token"' in r.text
        assert "Create Account" in r.text or "Register" in r.text
    finally:
        if prev is None:
            os.environ.pop("ALLOW_REGISTRATION", None)
        else:
            os.environ["ALLOW_REGISTRATION"] = prev


async def test_smoke_024_docs_404_in_production():
    """SMOKE-024 — /docs must be disabled when APP_ENV=production.

    Builds a fresh FastAPI instance with APP_ENV set BEFORE create_app()
    so the ``docs_url=None`` branch is taken. Uses an in-place ASGI client
    so it does not interfere with the shared app/session fixtures.
    """
    from httpx import ASGITransport, AsyncClient

    prev_env = os.environ.get("APP_ENV")
    prev_secret = os.environ.get("SECRET_KEY")
    os.environ["APP_ENV"] = "production"
    # SECRET_KEY must be non-default in prod or settings raises RuntimeError
    os.environ["SECRET_KEY"] = "smoke-prod-secret-key-not-real"

    try:
        from app import create_app

        prod_app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=prod_app),
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            r = await client.get("/docs")
            assert r.status_code == 404
    finally:
        if prev_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = prev_env
        if prev_secret is None:
            os.environ.pop("SECRET_KEY", None)
        else:
            os.environ["SECRET_KEY"] = prev_secret


async def test_smoke_025_login_invalid_credentials(smoke_client):
    """Wrong password returns 401 with no session set."""
    from tests.smoke.conftest import _csrf_token

    token = await _csrf_token(smoke_client, "/login")
    r = await smoke_client.post(
        "/login",
        data={
            "username": "nobody-here",
            "password": "WrongPassword123!",
            "csrf_token": token,
        },
    )
    assert r.status_code == 401
    assert "Invalid" in r.text
