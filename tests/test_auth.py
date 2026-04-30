import os
import pytest


@pytest.mark.anyio
async def test_login_page_loads(client):
    r = await client.get("/login")
    assert r.status_code == 200
    assert "Sign In" in r.text


@pytest.mark.anyio
async def test_login_valid(client):
    r = await client.post("/login", data={"username": "testadmin", "password": "TestPassword123!"})
    assert r.status_code == 200
    assert "Dashboard" in r.text or "Debt Tracker" in r.text


@pytest.mark.anyio
async def test_login_invalid(client):
    r = await client.post("/login", data={"username": "testadmin", "password": "wrongpassword"})
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
        assert "/login" in r.headers["location"]


@pytest.mark.anyio
async def test_register_disabled_by_default(client):
    r = await client.get("/register")
    # should redirect to /login when ALLOW_REGISTRATION not set
    assert r.status_code == 200
    assert "Sign In" in r.text


@pytest.mark.anyio
async def test_register_enabled(client):
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        r = await client.get("/register")
        assert r.status_code == 200
        assert "Create Account" in r.text

        r2 = await client.post("/register", data={
            "username": "newuser_pytest",
            "password": "NewPassword123!",
            "confirm_password": "NewPassword123!",
        })
        assert r2.status_code == 200
        assert "My Debts" in r2.text or "debts" in str(r2.url)
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"


@pytest.mark.anyio
async def test_register_short_password(client):
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        r = await client.post("/register", data={
            "username": "baduser",
            "password": "short",
            "confirm_password": "short",
        })
        assert r.status_code == 400
        assert "12" in r.text
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"


@pytest.mark.anyio
async def test_register_password_mismatch(client):
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        r = await client.post("/register", data={
            "username": "mismatchuser",
            "password": "ValidPassword123!",
            "confirm_password": "DifferentPassword123!",
        })
        assert r.status_code == 400
        assert "match" in r.text.lower()
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"


@pytest.mark.anyio
async def test_register_duplicate_username(client):
    os.environ["ALLOW_REGISTRATION"] = "true"
    try:
        r = await client.post("/register", data={
            "username": "testadmin",
            "password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
        })
        assert r.status_code == 400
        assert "taken" in r.text.lower()
    finally:
        os.environ["ALLOW_REGISTRATION"] = "false"


@pytest.mark.anyio
async def test_logout(authed_client):
    r = await authed_client.get("/logout")
    assert r.status_code == 200
    # after logout, hitting dashboard should show login
    r2 = await authed_client.get("/")
    assert "Sign In" in r2.text or "login" in r2.url.path
