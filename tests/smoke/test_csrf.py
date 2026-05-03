"""SMOKE-006, 015, 016 — CSRF guard on POST routes.

A POST without a valid token must be rejected with 403 (CSRFError →
HTTPException(status_code=403)). The same path with a fresh token
succeeds, proving the guard isn't accidentally always-on.
"""

import os

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.anyio]


async def test_smoke_csrf_login_post_blocked_without_token(smoke_client):
    r = await smoke_client.post(
        "/login",
        data={"username": "x", "password": "y"},
    )
    assert r.status_code == 403


async def test_smoke_csrf_register_post_blocked_without_token(smoke_client):
    prev = os.environ.get("ALLOW_REGISTRATION")
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        r = await smoke_client.post(
            "/register",
            data={
                "username": "csrf_smoke",
                "password": "SomePassword123!",
                "confirm_password": "SomePassword123!",
            },
        )
        assert r.status_code == 403
    finally:
        if prev is None:
            os.environ.pop("ALLOW_REGISTRATION", None)
        else:
            os.environ["ALLOW_REGISTRATION"] = prev


async def test_smoke_csrf_login_post_succeeds_with_token(smoke_client):
    """Sanity: with a valid token + bad creds we get 401, not 403."""
    from tests.smoke.conftest import _csrf_token

    token = await _csrf_token(smoke_client, "/login")
    r = await smoke_client.post(
        "/login",
        data={
            "username": "no-such-user-smoke",
            "password": "WrongPw123!",
            "csrf_token": token,
        },
    )
    assert r.status_code == 401
