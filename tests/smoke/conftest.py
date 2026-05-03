"""Smoke-test fixtures.

The parent ``tests/conftest.py`` already pins ``DATABASE_URL`` at the shared
isolated SQLite file and seeds the canonical admin / debts. This conftest only
adds smoke-specific helpers:

  * ``SMOKE_ADMIN_USER`` / ``SMOKE_ADMIN_PASS`` env-driven seeded admin
  * ``smoke_client`` — anonymous ``httpx.AsyncClient`` (ASGITransport)
  * ``smoke_authed_client`` — logged in as the smoke admin
  * ``smoke_csrf_token`` — convenience CSRF helper

No real ports, no subprocess, no extra DB containers.
"""

import os
import re
from typing import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient


SMOKE_ADMIN_USER = os.environ.get("SMOKE_ADMIN_USER", "smokeadmin")
SMOKE_ADMIN_PASS = os.environ.get("SMOKE_ADMIN_PASS", "SmokePassword123!")


@pytest.fixture(scope="package", autouse=True)
async def _smoke_admin(setup_test_db):
    """Idempotent admin seed for smoke tests.

    Runs after the parent autouse ``setup_test_db`` so migrations are guaranteed.
    The user is removed at session teardown so combined runs don't disturb
    integration tests that count user rows in /admin.
    """
    from app.db.base import AsyncSessionLocal
    from app.db.crud import create_user, delete_user, get_user_by_username

    created_id: int | None = None
    async with AsyncSessionLocal() as db:
        existing = await get_user_by_username(db, SMOKE_ADMIN_USER)
        if existing is None:
            user = await create_user(
                db,
                username=SMOKE_ADMIN_USER,
                password=SMOKE_ADMIN_PASS,
                is_admin=True,
            )
            created_id = user.id

    yield

    if created_id is not None:
        async with AsyncSessionLocal() as db:
            await delete_user(db, created_id)


def _new_client(app, *, follow_redirects: bool = True) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=follow_redirects,
    )


@pytest.fixture
async def smoke_client(app) -> AsyncIterator[AsyncClient]:
    async with _new_client(app) as ac:
        yield ac


@pytest.fixture
async def smoke_client_no_redirect(app) -> AsyncIterator[AsyncClient]:
    async with _new_client(app, follow_redirects=False) as ac:
        yield ac


async def _csrf_token(client: AsyncClient, url: str = "/login") -> str:
    r = await client.get(url)
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
    assert match, f"No CSRF token found at {url} (status={r.status_code})"
    return match.group(1)


@pytest.fixture
async def smoke_csrf_token():
    """Expose CSRF helper as a fixture for direct use in tests."""
    return _csrf_token


@pytest.fixture
async def smoke_authed_client(app) -> AsyncIterator[AsyncClient]:
    """Authenticated client using the smoke admin credentials."""
    # Reset any login rate-limit state to avoid cross-test 429s
    from app.ratelimit import _attempts, _lock

    with _lock:
        _attempts.clear()

    async with _new_client(app) as ac:
        token = await _csrf_token(ac, "/login")
        r = await ac.post(
            "/login",
            data={
                "username": SMOKE_ADMIN_USER,
                "password": SMOKE_ADMIN_PASS,
                "csrf_token": token,
            },
        )
        # follow_redirects=True so 200 dashboard lands here
        assert r.status_code == 200, f"smoke admin login failed: {r.status_code}"
        yield ac
