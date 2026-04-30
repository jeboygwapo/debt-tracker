import asyncio
import os
import subprocess
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).parent.parent
TEST_DB = ROOT / "tests" / "test_debttracker.db"
TEST_USER = "testadmin"
TEST_PASS = "TestPassword123!"

# Set test DB BEFORE any app imports so Settings picks it up
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-prod")

import sys
sys.path.insert(0, str(ROOT))

from app import create_app as _create_app
from app.db.base import AsyncSessionLocal
from app.db.crud import create_debt, create_user


def _run_migrations():
    result = subprocess.run(
        ["python", "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    assert result.returncode == 0, f"Migrations failed:\n{result.stderr}"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    TEST_DB.unlink(missing_ok=True)
    _run_migrations()

    async with AsyncSessionLocal() as db:
        user = await create_user(db, username=TEST_USER, password=TEST_PASS, is_admin=True)
        await create_debt(db, user_id=user.id, name="Test CC One", type="credit_card", apr_monthly_pct=2.0, sort_order=0)
        await create_debt(db, user_id=user.id, name="Test CC Two", type="credit_card", apr_monthly_pct=3.0, sort_order=1)
        await create_debt(db, user_id=user.id, name="Test Loan", type="personal_loan", apr_monthly_pct=0.0, is_fixed=True, fixed_monthly=5000.0, fixed_ends="2027-01", sort_order=2)

    yield

    TEST_DB.unlink(missing_ok=True)


@pytest.fixture(scope="session")
def app(setup_test_db):
    return _create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac


@pytest.fixture
async def authed_client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        await ac.post("/login", data={"username": TEST_USER, "password": TEST_PASS})
        yield ac
