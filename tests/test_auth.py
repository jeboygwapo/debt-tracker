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
async def test_logout(authed_client):
    r = await authed_client.get("/logout")
    assert r.status_code == 200
    # after logout, hitting dashboard should show login
    r2 = await authed_client.get("/")
    assert "Sign In" in r2.text or "login" in r2.url.path
