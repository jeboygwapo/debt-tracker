import re

import pytest

from tests.conftest import get_csrf_token


@pytest.mark.anyio
async def test_admin_page(authed_client):
    r = await authed_client.get("/admin")
    assert r.status_code == 200
    assert "User Management" in r.text


@pytest.mark.anyio
async def test_admin_blocked_for_non_admin(client):
    from app.db.base import AsyncSessionLocal
    from app.db.crud import create_user, delete_user, get_user_by_username

    async with AsyncSessionLocal() as db:
        existing = await get_user_by_username(db, "nonadmin_test")
        if not existing:
            await create_user(db, "nonadmin_test", "NonAdminPass123!", is_admin=False)

    token = await get_csrf_token(client, "/login")
    await client.post("/login", data={"username": "nonadmin_test", "password": "NonAdminPass123!", "csrf_token": token})
    r2 = await client.get("/admin")
    assert "User Management" not in r2.text

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "nonadmin_test")
        if user:
            await delete_user(db, user.id)


@pytest.mark.anyio
async def test_admin_create_and_delete_user(authed_client):
    token = await get_csrf_token(authed_client, "/admin")
    r = await authed_client.post("/admin/users/create", data={
        "username": "pytest_tempuser",
        "password": "TempUserPass123!",
        "is_admin": "",
        "csrf_token": token,
    })
    assert r.status_code == 200
    assert "pytest_tempuser" in r.text

    match = re.search(r'/admin/users/(\d+)/delete.*?pytest_tempuser|pytest_tempuser.*?/admin/users/(\d+)/delete', r.text, re.DOTALL)
    assert match
    user_id = match.group(1) or match.group(2)

    token2 = await get_csrf_token(authed_client, "/admin")
    r2 = await authed_client.post(f"/admin/users/{user_id}/delete", data={"csrf_token": token2})
    assert r2.status_code == 200
    assert "pytest_tempuser" not in r2.text


@pytest.mark.anyio
async def test_admin_cannot_delete_self(authed_client):
    token = await get_csrf_token(authed_client, "/admin")
    r2 = await authed_client.post("/admin/users/1/delete", data={"csrf_token": token})
    assert r2.status_code == 200
    assert "Cannot delete yourself" in r2.text or "testadmin" in r2.text


@pytest.mark.anyio
async def test_admin_create_duplicate_user(authed_client):
    token = await get_csrf_token(authed_client, "/admin")
    r = await authed_client.post("/admin/users/create", data={
        "username": "testadmin",
        "password": "SomePassword123!",
        "csrf_token": token,
    })
    assert r.status_code == 200
    assert "already exists" in r.text


@pytest.mark.anyio
async def test_admin_create_short_password(authed_client):
    token = await get_csrf_token(authed_client, "/admin")
    r = await authed_client.post("/admin/users/create", data={
        "username": "shortpwuser",
        "password": "short",
        "csrf_token": token,
    })
    assert r.status_code == 200
    assert "12" in r.text or "chars" in r.text or "required" in r.text.lower()
