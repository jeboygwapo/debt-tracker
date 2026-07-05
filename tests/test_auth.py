import os
import pytest

from tests.conftest import get_csrf_token


@pytest.mark.anyio
async def test_login_page_loads(client):
    r = await client.get("/login")
    assert r.status_code == 200
    assert "Sign In" in r.text


@pytest.mark.anyio
async def test_login_valid(client):
    token = await get_csrf_token(client, "/login")
    r = await client.post("/login", data={"username": "testadmin", "password": "TestPassword123!", "csrf_token": token})
    assert r.status_code == 200
    assert "Dashboard" in r.text or "Debt Tracker" in r.text


@pytest.mark.anyio
async def test_login_invalid(client):
    token = await get_csrf_token(client, "/login")
    r = await client.post("/login", data={"username": "testadmin", "password": "wrongpassword", "csrf_token": token})
    assert r.status_code == 401
    assert "Invalid" in r.text


@pytest.mark.anyio
async def test_unauthenticated_redirect():
    from httpx import ASGITransport, AsyncClient
    from app import create_app
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
        follow_redirects=False,
    ) as c:
        r = await c.get("/")
        assert r.status_code == 302
        assert "/welcome" in r.headers["location"]


@pytest.mark.anyio
async def test_register_disabled_by_default(client):
    r = await client.get("/register")
    assert r.status_code == 200
    assert "Sign In" in r.text


@pytest.mark.anyio
async def test_register_enabled(client):
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        token = await get_csrf_token(client, "/register")
        r2 = await client.post("/register", data={
            "username": "newuser_pytest",
            "password": "NewPassword123!",
            "confirm_password": "NewPassword123!",
            "csrf_token": token,
        })
        assert r2.status_code == 200
        assert "My Debts" in r2.text or "debts" in str(r2.url)
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"


@pytest.mark.anyio
async def test_register_short_password(client):
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        token = await get_csrf_token(client, "/register")
        r = await client.post("/register", data={
            "username": "baduser",
            "password": "short",
            "confirm_password": "short",
            "csrf_token": token,
        })
        assert r.status_code == 400
        assert "12" in r.text
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"


@pytest.mark.anyio
async def test_register_password_mismatch(client):
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        token = await get_csrf_token(client, "/register")
        r = await client.post("/register", data={
            "username": "mismatchuser",
            "password": "ValidPassword123!",
            "confirm_password": "DifferentPassword123!",
            "csrf_token": token,
        })
        assert r.status_code == 400
        assert "match" in r.text.lower()
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"


@pytest.mark.anyio
async def test_register_duplicate_username(client):
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        token = await get_csrf_token(client, "/register")
        r = await client.post("/register", data={
            "username": "testadmin",
            "password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
            "csrf_token": token,
        })
        assert r.status_code == 400
        assert "not available" in r.text.lower()
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"


@pytest.mark.anyio
async def test_logout(authed_client):
    r = await authed_client.get("/logout")
    assert r.status_code == 200
    r2 = await authed_client.get("/")
    assert "Sign In" in r2.text or "login" in r2.url.path


@pytest.mark.anyio
async def test_landing_page_loads(client):
    r = await client.get("/welcome")
    assert r.status_code == 200
    assert "Sign In" in r.text or "Get Started" in r.text


@pytest.mark.anyio
async def test_landing_page_authenticated_redirects(authed_client):
    from httpx import ASGITransport, AsyncClient
    from app import create_app
    from tests.conftest import get_csrf_token, TEST_USER, TEST_PASS
    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
        follow_redirects=False,
    ) as c:
        token = await get_csrf_token(c, "/login")
        await c.post("/login", data={"username": TEST_USER, "password": TEST_PASS, "csrf_token": token})
        r = await c.get("/welcome")
        assert r.status_code == 302
        assert r.headers["location"] == "/"


@pytest.mark.anyio
async def test_register_with_email(client):
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        token = await get_csrf_token(client, "/register")
        r = await client.post("/register", data={
            "username": "emailuser_pytest",
            "password": "NewPassword123!",
            "confirm_password": "NewPassword123!",
            "email": "test@example.com",
            "csrf_token": token,
        })
        assert r.status_code == 200
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"


@pytest.mark.anyio
async def test_register_invalid_email(client):
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        token = await get_csrf_token(client, "/register")
        r = await client.post("/register", data={
            "username": "bademailuser",
            "password": "NewPassword123!",
            "confirm_password": "NewPassword123!",
            "email": "not-an-email",
            "csrf_token": token,
        })
        assert r.status_code == 400
        assert "Invalid" in r.text
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"


@pytest.mark.anyio
async def test_verify_invalid_token(client):
    r = await client.get("/verify/invalidtoken123")
    assert r.status_code == 200
    assert "Invalid" in r.text or "invalid" in r.text


@pytest.mark.anyio
async def test_verify_valid_token(client):
    from app.db.crud import get_user_by_username, set_user_email
    from app.db.base import get_db
    from datetime import datetime, timedelta, timezone
    import secrets

    async for db in get_db():
        user = await get_user_by_username(db, "testadmin")
        token = secrets.token_urlsafe(32)
        expiry = datetime.now(timezone.utc) + timedelta(hours=24)
        await set_user_email(db, user, "admin@example.com", token, expiry)
        await db.refresh(user)

        r = await client.get(f"/verify/{token}")
        assert r.status_code == 200
        assert "Verified" in r.text or "verified" in r.text
        break


@pytest.mark.anyio
async def test_rate_limit_lockout(client):
    """After 5 failed logins the IP is locked out and returns 429."""
    from app.ratelimit import _attempts, _lock

    with _lock:
        _attempts.clear()

    for _ in range(5):
        token = await get_csrf_token(client, "/login")
        await client.post("/login", data={
            "username": "testadmin",
            "password": "BadPassword999!",
            "csrf_token": token,
        })

    token = await get_csrf_token(client, "/login")
    r = await client.post("/login", data={
        "username": "testadmin",
        "password": "BadPassword999!",
        "csrf_token": token,
    })
    assert r.status_code == 429 or "locked" in r.text.lower() or "too many" in r.text.lower()

    # clear lockout so subsequent authed_client fixtures can log in
    with _lock:
        _attempts.clear()


# ── Forgot Password ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_forgot_password_page_loads(client):
    r = await client.get("/forgot-password")
    assert r.status_code == 200
    assert "Forgot Password" in r.text or "Send Reset Link" in r.text


@pytest.mark.anyio
async def test_forgot_password_authenticated_redirects(authed_client):
    from httpx import ASGITransport, AsyncClient
    from app import create_app
    from tests.conftest import get_csrf_token, TEST_USER, TEST_PASS

    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
        follow_redirects=False,
    ) as c:
        token = await get_csrf_token(c, "/login")
        await c.post("/login", data={"username": TEST_USER, "password": TEST_PASS, "csrf_token": token})
        r = await c.get("/forgot-password")
        assert r.status_code == 302
        assert "/settings" in r.headers["location"]


@pytest.mark.anyio
async def test_forgot_password_rate_limit_silent_200(client):
    from app.ratelimit import _ns_attempts, _lock
    import time

    key = ("forgot-password", "testclient")
    with _lock:
        _ns_attempts[key] = [time.monotonic() for _ in range(5)]

    try:
        token = await get_csrf_token(client, "/forgot-password")
        r = await client.post("/forgot-password", data={"identifier": "testadmin", "csrf_token": token})
        assert r.status_code == 200
        assert "Check your inbox" in r.text
    finally:
        with _lock:
            _ns_attempts.pop(key, None)


@pytest.mark.anyio
async def test_forgot_password_empty_identifier_400(client):
    from app.ratelimit import _ns_attempts, _lock

    with _lock:
        for key in list(_ns_attempts.keys()):
            if key[0] == "forgot-password":
                _ns_attempts.pop(key, None)

    token = await get_csrf_token(client, "/forgot-password")
    r = await client.post("/forgot-password", data={"identifier": "", "csrf_token": token})
    assert r.status_code == 400
    assert "Enter your username or email address" in r.text


@pytest.mark.anyio
async def test_forgot_password_valid_username_sent(client):
    """Valid username with email set returns sent=True."""
    import secrets
    from datetime import datetime, timedelta, timezone
    from unittest.mock import AsyncMock, patch
    from app.db.base import get_db
    from app.db.crud import get_user_by_username, set_user_email, set_reset_token
    from app.ratelimit import _ns_attempts, _lock

    with _lock:
        for key in list(_ns_attempts.keys()):
            if key[0] == "forgot-password":
                _ns_attempts.pop(key, None)

    async for db in get_db():
        user = await get_user_by_username(db, "testadmin")
        verify_tok = secrets.token_urlsafe(32)
        expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
        await set_user_email(db, user, "admin_reset@example.com", verify_tok, expiry)
        break

    token = await get_csrf_token(client, "/forgot-password")
    with patch("app.routes.auth.send_password_reset_email", new=AsyncMock()):
        r = await client.post("/forgot-password", data={"identifier": "testadmin", "csrf_token": token})

    assert r.status_code == 200
    assert "Check your inbox" in r.text

    with _lock:
        for key in list(_ns_attempts.keys()):
            if key[0] == "forgot-password":
                _ns_attempts.pop(key, None)


@pytest.mark.anyio
async def test_forgot_password_valid_email_sent(client):
    """Valid email lookup returns sent=True."""
    from unittest.mock import AsyncMock, patch
    from app.ratelimit import _ns_attempts, _lock

    with _lock:
        for key in list(_ns_attempts.keys()):
            if key[0] == "forgot-password":
                _ns_attempts.pop(key, None)

    token = await get_csrf_token(client, "/forgot-password")
    with patch("app.routes.auth.send_password_reset_email", new=AsyncMock()):
        r = await client.post("/forgot-password", data={"identifier": "admin_reset@example.com", "csrf_token": token})

    assert r.status_code == 200
    assert "Check your inbox" in r.text

    with _lock:
        for key in list(_ns_attempts.keys()):
            if key[0] == "forgot-password":
                _ns_attempts.pop(key, None)


@pytest.mark.anyio
async def test_forgot_password_unknown_identifier_silent(client):
    """Unknown identifier silently returns sent=True (no enumeration)."""
    from app.ratelimit import _ns_attempts, _lock

    with _lock:
        for key in list(_ns_attempts.keys()):
            if key[0] == "forgot-password":
                _ns_attempts.pop(key, None)

    token = await get_csrf_token(client, "/forgot-password")
    r = await client.post("/forgot-password", data={"identifier": "nobody@nowhere.com", "csrf_token": token})
    assert r.status_code == 200
    assert "Check your inbox" in r.text

    with _lock:
        for key in list(_ns_attempts.keys()):
            if key[0] == "forgot-password":
                _ns_attempts.pop(key, None)


@pytest.mark.anyio
async def test_forgot_password_no_email_on_user_silent(client):
    """User exists but has no email — still returns sent=True silently."""
    import secrets
    from datetime import datetime, timedelta, timezone
    from app.db.base import get_db
    from app.db.crud import get_user_by_username
    from app.ratelimit import _ns_attempts, _lock

    with _lock:
        for key in list(_ns_attempts.keys()):
            if key[0] == "forgot-password":
                _ns_attempts.pop(key, None)

    # Strip email off testadmin so it has no email
    async for db in get_db():
        user = await get_user_by_username(db, "testadmin")
        user.email = None
        user.reset_token = None
        user.reset_token_expiry = None
        await db.commit()
        break

    token = await get_csrf_token(client, "/forgot-password")
    r = await client.post("/forgot-password", data={"identifier": "testadmin", "csrf_token": token})
    assert r.status_code == 200
    assert "Check your inbox" in r.text

    with _lock:
        for key in list(_ns_attempts.keys()):
            if key[0] == "forgot-password":
                _ns_attempts.pop(key, None)


# ── Reset Password GET ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_reset_password_invalid_token(client):
    r = await client.get("/reset-password/totallybogustoken999")
    assert r.status_code == 200
    assert "Invalid Link" in r.text


@pytest.mark.anyio
async def test_reset_password_expired_token(client):
    import secrets
    from datetime import datetime, timedelta, timezone
    from app.db.base import get_db
    from app.db.crud import get_user_by_username, set_reset_token

    token = secrets.token_urlsafe(32)
    async for db in get_db():
        user = await get_user_by_username(db, "testadmin")
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        await set_reset_token(db, user, token, past)
        break

    r = await client.get(f"/reset-password/{token}")
    assert r.status_code == 200
    assert "Link Expired" in r.text


@pytest.mark.anyio
async def test_reset_password_valid_token_shows_form(client):
    import secrets
    from datetime import datetime, timedelta, timezone
    from app.db.base import get_db
    from app.db.crud import get_user_by_username, set_reset_token

    token = secrets.token_urlsafe(32)
    async for db in get_db():
        user = await get_user_by_username(db, "testadmin")
        future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        await set_reset_token(db, user, token, future)
        break

    r = await client.get(f"/reset-password/{token}")
    assert r.status_code == 200
    assert "Choose a new password" in r.text or "Reset Password" in r.text


# ── Reset Password POST ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_reset_password_post_invalid_token(client):
    # Invalid/expired pages have no form — grab CSRF from login page
    csrf = await get_csrf_token(client, "/login")
    r = await client.post("/reset-password/bogustoken000", data={
        "password": "ValidPassword123!",
        "confirm_password": "ValidPassword123!",
        "csrf_token": csrf,
    })
    assert r.status_code == 200
    assert "Invalid Link" in r.text


@pytest.mark.anyio
async def test_reset_password_post_expired_token(client):
    import secrets
    from datetime import datetime, timedelta, timezone
    from app.db.base import get_db
    from app.db.crud import get_user_by_username, set_reset_token

    token = secrets.token_urlsafe(32)
    async for db in get_db():
        user = await get_user_by_username(db, "testadmin")
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        await set_reset_token(db, user, token, past)
        break

    # Expired page has no form — grab CSRF from login page
    csrf = await get_csrf_token(client, "/login")
    r = await client.post(f"/reset-password/{token}", data={
        "password": "ValidPassword123!",
        "confirm_password": "ValidPassword123!",
        "csrf_token": csrf,
    })
    assert r.status_code == 200
    assert "Link Expired" in r.text


@pytest.mark.anyio
async def test_reset_password_post_short_password(client):
    import secrets
    from datetime import datetime, timedelta, timezone
    from app.db.base import get_db
    from app.db.crud import get_user_by_username, set_reset_token

    token = secrets.token_urlsafe(32)
    async for db in get_db():
        user = await get_user_by_username(db, "testadmin")
        future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        await set_reset_token(db, user, token, future)
        break

    csrf = await get_csrf_token(client, f"/reset-password/{token}")
    r = await client.post(f"/reset-password/{token}", data={
        "password": "short",
        "confirm_password": "short",
        "csrf_token": csrf,
    })
    assert r.status_code == 400
    assert "12" in r.text


@pytest.mark.anyio
async def test_reset_password_post_mismatch(client):
    import secrets
    from datetime import datetime, timedelta, timezone
    from app.db.base import get_db
    from app.db.crud import get_user_by_username, set_reset_token

    token = secrets.token_urlsafe(32)
    async for db in get_db():
        user = await get_user_by_username(db, "testadmin")
        future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        await set_reset_token(db, user, token, future)
        break

    csrf = await get_csrf_token(client, f"/reset-password/{token}")
    r = await client.post(f"/reset-password/{token}", data={
        "password": "ValidPassword123!",
        "confirm_password": "DifferentPassword123!",
        "csrf_token": csrf,
    })
    assert r.status_code == 400
    assert "match" in r.text.lower()


@pytest.mark.anyio
async def test_reset_password_post_success(client):
    import secrets
    from datetime import datetime, timedelta, timezone
    from app.db.base import get_db
    from app.db.crud import get_user_by_username, get_user_by_reset_token, set_reset_token

    token = secrets.token_urlsafe(32)
    async for db in get_db():
        user = await get_user_by_username(db, "testadmin")
        future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        await set_reset_token(db, user, token, future)
        break

    csrf = await get_csrf_token(client, f"/reset-password/{token}")
    r = await client.post(f"/reset-password/{token}", data={
        "password": "NewTestPassword123!",
        "confirm_password": "NewTestPassword123!",
        "csrf_token": csrf,
    })
    assert r.status_code == 200
    assert "Password Updated" in r.text

    # Verify token was cleared
    async for db in get_db():
        user = await get_user_by_reset_token(db, token)
        assert user is None
        # Restore original password so other tests aren't broken
        from app.db.crud import get_user_by_username, update_user_password
        user = await get_user_by_username(db, "testadmin")
        await update_user_password(db, user, "TestPassword123!")
        break


# ── Registration security: rate limit + enumeration ─────────────────────────


@pytest.mark.anyio
async def test_register_rate_limit_429_after_5(client):
    """6th register attempt within window must return 429.

    Uses invalid passwords so the user isn't logged in between attempts —
    rate limit fires regardless of validation outcome (records every POST).
    """
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        for i in range(5):
            token = await get_csrf_token(client, "/register")
            r = await client.post("/register", data={
                "username": f"ratelimit{i}",
                "password": "short",
                "confirm_password": "short",
                "csrf_token": token,
            })
            assert r.status_code == 400

        token = await get_csrf_token(client, "/register")
        r6 = await client.post("/register", data={
            "username": "ratelimit6",
            "password": "short",
            "confirm_password": "short",
            "csrf_token": token,
        })
        assert r6.status_code == 429
        assert "too many" in r6.text.lower()
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"


@pytest.mark.anyio
async def test_register_duplicate_email_normalized(client):
    """Duplicate email returns same vague error as duplicate username (no enumeration).

    Seeds a user with email directly in DB (bypasses register flow which only
    persists email when RESEND_API_KEY is set), then attempts to register
    a second user with the same email.
    """
    from app.db.base import AsyncSessionLocal
    from app.db.crud import create_user, set_user_email, delete_user, get_user_by_email
    from datetime import datetime, timedelta, timezone

    seed_id = None
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        async with AsyncSessionLocal() as db:
            seed = await create_user(db, username="enumseed", password="EnumPassword123!", is_admin=False)
            seed_id = seed.id
            future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
            await set_user_email(db, seed, "enumcollide@example.com", "tok", future)

        token = await get_csrf_token(client, "/register")
        r = await client.post("/register", data={
            "username": "differentuser",
            "password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
            "email": "enumcollide@example.com",
            "csrf_token": token,
        })
        assert r.status_code == 400
        body = r.text.lower()
        assert "not available" in body
        assert "already registered" not in body
        assert "email already" not in body
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"
        if seed_id is not None:
            async with AsyncSessionLocal() as db:
                await delete_user(db, seed_id)


# ── Verification wall middleware ───────────────────────────────────────────


@pytest.mark.anyio
async def test_verify_required_redirects_unverified_user():
    """When EMAIL_VERIFICATION_REQUIRED=true, unverified user with email is walled off."""
    from httpx import ASGITransport, AsyncClient
    from app import create_app
    from app.db.base import AsyncSessionLocal
    from app.db.crud import create_user, set_user_email, delete_user
    from datetime import datetime, timedelta, timezone

    prev = os.environ.get("EMAIL_VERIFICATION_REQUIRED")
    os.environ["EMAIL_VERIFICATION_REQUIRED"] = "true"

    user_id = None
    try:
        async with AsyncSessionLocal() as db:
            user = await create_user(db, username="walltest", password="WallPassword123!", is_admin=False)
            user_id = user.id
            future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
            await set_user_email(db, user, "walltest@example.com", "verifytoken123", future)

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=False,
        ) as c:
            token = await get_csrf_token(c, "/login")
            login = await c.post("/login", data={
                "username": "walltest",
                "password": "WallPassword123!",
                "csrf_token": token,
            })
            assert login.status_code == 303
            assert login.headers["location"] == "/verify-required"

            r = await c.get("/")
            assert r.status_code == 302
            assert r.headers["location"] == "/verify-required"

            r2 = await c.get("/debts")
            assert r2.status_code == 302
            assert r2.headers["location"] == "/verify-required"

            r3 = await c.get("/verify-required")
            assert r3.status_code == 200
            assert "walltest@example.com" in r3.text

            r4 = await c.get("/logout")
            assert r4.status_code == 303
    finally:
        if prev is None:
            os.environ.pop("EMAIL_VERIFICATION_REQUIRED", None)
        else:
            os.environ["EMAIL_VERIFICATION_REQUIRED"] = prev
        if user_id is not None:
            async with AsyncSessionLocal() as db:
                await delete_user(db, user_id)


@pytest.mark.anyio
async def test_verify_required_no_block_when_setting_off():
    """When EMAIL_VERIFICATION_REQUIRED=false (default), unverified user can use the app."""
    from httpx import ASGITransport, AsyncClient
    from app import create_app
    from app.db.base import AsyncSessionLocal
    from app.db.crud import create_user, set_user_email, delete_user
    from datetime import datetime, timedelta, timezone

    prev = os.environ.get("EMAIL_VERIFICATION_REQUIRED")
    os.environ["EMAIL_VERIFICATION_REQUIRED"] = "false"

    user_id = None
    try:
        async with AsyncSessionLocal() as db:
            user = await create_user(db, username="nowalltest", password="WallPassword123!", is_admin=False)
            user_id = user.id
            future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
            await set_user_email(db, user, "nowall@example.com", "tok", future)

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=False,
        ) as c:
            token = await get_csrf_token(c, "/login")
            login = await c.post("/login", data={
                "username": "nowalltest",
                "password": "WallPassword123!",
                "csrf_token": token,
            })
            assert login.status_code == 303
            assert login.headers["location"] == "/"
    finally:
        if prev is None:
            os.environ.pop("EMAIL_VERIFICATION_REQUIRED", None)
        else:
            os.environ["EMAIL_VERIFICATION_REQUIRED"] = prev
        if user_id is not None:
            async with AsyncSessionLocal() as db:
                await delete_user(db, user_id)


@pytest.mark.anyio
async def test_register_requires_email_when_verify_required(client):
    """When EMAIL_VERIFICATION_REQUIRED=true, register without email → 400."""
    prev = os.environ.get("EMAIL_VERIFICATION_REQUIRED")
    os.environ["ALLOW_REGISTRATION"] = "true"
    os.environ["EMAIL_VERIFICATION_REQUIRED"] = "true"
    try:
        token = await get_csrf_token(client, "/register")
        r = await client.post("/register", data={
            "username": "needsemailuser",
            "password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
            "csrf_token": token,
        })
        assert r.status_code == 400
        assert "Email" in r.text or "email" in r.text
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"
        if prev is None:
            os.environ.pop("EMAIL_VERIFICATION_REQUIRED", None)
        else:
            os.environ["EMAIL_VERIFICATION_REQUIRED"] = prev


@pytest.mark.anyio
async def test_register_requires_resend_key_when_verify_required(client):
    """When EMAIL_VERIFICATION_REQUIRED=true but no RESEND_API_KEY, register → 400."""
    prev_verify = os.environ.get("EMAIL_VERIFICATION_REQUIRED")
    prev_key = os.environ.get("RESEND_API_KEY")
    os.environ["ALLOW_REGISTRATION"] = "true"
    os.environ["EMAIL_VERIFICATION_REQUIRED"] = "true"
    os.environ.pop("RESEND_API_KEY", None)
    try:
        token = await get_csrf_token(client, "/register")
        r = await client.post("/register", data={
            "username": "nokeyuser",
            "password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
            "email": "nokey@example.com",
            "csrf_token": token,
        })
        assert r.status_code == 400
        assert "temporarily unavailable" in r.text.lower()
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"
        if prev_verify is None:
            os.environ.pop("EMAIL_VERIFICATION_REQUIRED", None)
        else:
            os.environ["EMAIL_VERIFICATION_REQUIRED"] = prev_verify
        if prev_key is not None:
            os.environ["RESEND_API_KEY"] = prev_key


@pytest.mark.anyio
async def test_unverified_login_partial_session_only():
    """Unverified login sets pending_verify_user_id, not user_id."""
    from httpx import ASGITransport, AsyncClient
    from app import create_app
    from app.db.base import AsyncSessionLocal
    from app.db.crud import create_user, set_user_email, delete_user
    from datetime import datetime, timedelta, timezone

    prev = os.environ.get("EMAIL_VERIFICATION_REQUIRED")
    os.environ["EMAIL_VERIFICATION_REQUIRED"] = "true"

    user_id = None
    try:
        async with AsyncSessionLocal() as db:
            user = await create_user(db, username="partialsess", password="WallPassword123!", is_admin=False)
            user_id = user.id
            future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
            await set_user_email(db, user, "partial@example.com", "toktok", future)

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=False,
        ) as c:
            token = await get_csrf_token(c, "/login")
            login = await c.post("/login", data={
                "username": "partialsess",
                "password": "WallPassword123!",
                "csrf_token": token,
            })
            assert login.status_code == 303
            assert login.headers["location"] == "/verify-required"

            # Any protected route redirects to /verify-required via middleware
            r = await c.get("/settings")
            assert r.status_code == 302
            assert r.headers["location"] == "/verify-required"
    finally:
        if prev is None:
            os.environ.pop("EMAIL_VERIFICATION_REQUIRED", None)
        else:
            os.environ["EMAIL_VERIFICATION_REQUIRED"] = prev
        if user_id is not None:
            async with AsyncSessionLocal() as db:
                await delete_user(db, user_id)


@pytest.mark.anyio
async def test_full_verify_gate_happy_path():
    """Register → verify-required → click token link → login → dashboard."""
    from httpx import ASGITransport, AsyncClient
    from unittest.mock import AsyncMock, patch
    from app import create_app
    from app.db.base import AsyncSessionLocal
    from app.db.crud import get_user_by_username, delete_user

    prev_verify = os.environ.get("EMAIL_VERIFICATION_REQUIRED")
    prev_reg = os.environ.get("ALLOW_REGISTRATION")
    prev_key = os.environ.get("RESEND_API_KEY")
    os.environ["ALLOW_REGISTRATION"] = "true"
    os.environ["EMAIL_VERIFICATION_REQUIRED"] = "true"
    os.environ["RESEND_API_KEY"] = "re_test_dummy"

    user_id = None
    try:
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=False,
        ) as c:
            with patch("app.routes.auth.send_verification_email", new=AsyncMock()):
                token = await get_csrf_token(c, "/register")
                reg = await c.post("/register", data={
                    "username": "happypath",
                    "password": "HappyPass1234!",
                    "confirm_password": "HappyPass1234!",
                    "email": "happy@example.com",
                    "csrf_token": token,
                })
            assert reg.status_code == 303
            assert reg.headers["location"] == "/verify-required"

            # Protected route → wall
            r = await c.get("/settings")
            assert r.status_code == 302
            assert r.headers["location"] == "/verify-required"

            # Pull real verify token from DB and hit link
            async with AsyncSessionLocal() as db:
                user = await get_user_by_username(db, "happypath")
                user_id = user.id
                verify_token = user.verify_token
            assert verify_token

            v = await c.get(f"/verify/{verify_token}")
            assert v.status_code == 200
            assert "verified" in v.text.lower()

            # Log in again → dashboard
            login_csrf = await get_csrf_token(c, "/login")
            login = await c.post("/login", data={
                "username": "happypath",
                "password": "HappyPass1234!",
                "csrf_token": login_csrf,
            })
            assert login.status_code == 303
            assert login.headers["location"] == "/"

            home = await c.get("/")
            assert home.status_code == 200
    finally:
        for key, prev in (
            ("ALLOW_REGISTRATION", prev_reg),
            ("EMAIL_VERIFICATION_REQUIRED", prev_verify),
            ("RESEND_API_KEY", prev_key),
        ):
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
        if user_id is not None:
            async with AsyncSessionLocal() as db:
                await delete_user(db, user_id)


@pytest.mark.anyio
async def test_reset_password_scan_rate_limit(client):
    """5 invalid GET /reset-password/{token} hits → 6th returns 429."""
    from app.ratelimit import _ns_attempts, _lock

    with _lock:
        for key in list(_ns_attempts.keys()):
            if key[0] == "reset-password-scan":
                _ns_attempts.pop(key, None)

    try:
        for i in range(5):
            r = await client.get(f"/reset-password/bogus_scan_{i}")
            assert r.status_code == 200
        r6 = await client.get("/reset-password/bogus_scan_6")
        assert r6.status_code == 429
    finally:
        with _lock:
            for key in list(_ns_attempts.keys()):
                if key[0] == "reset-password-scan":
                    _ns_attempts.pop(key, None)


@pytest.mark.anyio
async def test_reset_password_scan_limit_blocks_post(client):
    """Scan limit hit on POST returns 429 without touching DB."""
    from app.ratelimit import _ns_attempts, _lock

    with _lock:
        for key in list(_ns_attempts.keys()):
            if key[0] == "reset-password-scan":
                _ns_attempts.pop(key, None)

    try:
        for i in range(5):
            await client.get(f"/reset-password/scan_pre_{i}")

        csrf = await get_csrf_token(client, "/login")
        r = await client.post("/reset-password/anytoken", data={
            "password": "SomePassword123!",
            "confirm_password": "SomePassword123!",
            "csrf_token": csrf,
        })
        assert r.status_code == 429
    finally:
        with _lock:
            for key in list(_ns_attempts.keys()):
                if key[0] == "reset-password-scan":
                    _ns_attempts.pop(key, None)


@pytest.mark.anyio
async def test_verify_required_no_block_for_users_without_email():
    """Users who registered without email are not blocked even when verification required."""
    from httpx import ASGITransport, AsyncClient
    from app import create_app
    from app.db.base import AsyncSessionLocal
    from app.db.crud import create_user, delete_user

    prev = os.environ.get("EMAIL_VERIFICATION_REQUIRED")
    os.environ["EMAIL_VERIFICATION_REQUIRED"] = "true"

    user_id = None
    try:
        async with AsyncSessionLocal() as db:
            user = await create_user(db, username="noemailuser", password="WallPassword123!", is_admin=False)
            user_id = user.id

        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=False,
        ) as c:
            token = await get_csrf_token(c, "/login")
            login = await c.post("/login", data={
                "username": "noemailuser",
                "password": "WallPassword123!",
                "csrf_token": token,
            })
            assert login.status_code == 303
            assert login.headers["location"] == "/"

            r = await c.get("/", follow_redirects=False)
            assert r.status_code == 200
    finally:
        if prev is None:
            os.environ.pop("EMAIL_VERIFICATION_REQUIRED", None)
        else:
            os.environ["EMAIL_VERIFICATION_REQUIRED"] = prev
        if user_id is not None:
            async with AsyncSessionLocal() as db:
                await delete_user(db, user_id)
