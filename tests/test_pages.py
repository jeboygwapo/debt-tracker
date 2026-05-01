import os
from datetime import date

import pytest

from tests.conftest import get_csrf_token


@pytest.mark.anyio
async def test_dashboard(authed_client):
    r = await authed_client.get("/")
    assert r.status_code == 200
    assert "Total Debt" in r.text


@pytest.mark.anyio
async def test_add_month_page(authed_client):
    r = await authed_client.get("/add")
    assert r.status_code == 200


@pytest.mark.anyio
async def test_add_month_post(authed_client):
    token = await get_csrf_token(authed_client, "/add")
    r = await authed_client.post("/add", data={
        "month": "2026-01",
        "d_0_balance": "50000",
        "d_0_min_due": "2000",
        "d_0_payment": "2000",
        "csrf_token": token,
    })
    assert r.status_code == 200


@pytest.mark.anyio
async def test_add_month_post_missing_month(authed_client):
    token = await get_csrf_token(authed_client, "/add")
    r = await authed_client.post("/add", data={"month": "", "csrf_token": token})
    assert r.status_code == 200
    assert "required" in r.text.lower()


@pytest.mark.anyio
async def test_add_month_post_invalid_month(authed_client):
    token = await get_csrf_token(authed_client, "/add")
    r = await authed_client.post("/add", data={"month": "not-a-month", "csrf_token": token})
    assert r.status_code == 200
    assert "Invalid" in r.text


@pytest.mark.anyio
async def test_edit_month_post(authed_client):
    token = await get_csrf_token(authed_client, "/edit/2026-01")
    r = await authed_client.post("/edit/2026-01", data={
        "d_0_balance": "48000",
        "d_0_min_due": "2000",
        "csrf_token": token,
    })
    assert r.status_code == 200


@pytest.mark.anyio
async def test_plan_page(authed_client):
    r = await authed_client.get("/plan")
    assert r.status_code == 200


@pytest.mark.anyio
async def test_remit_page(authed_client):
    r = await authed_client.get("/remit")
    assert r.status_code == 200


@pytest.mark.anyio
async def test_remit_post(authed_client):
    token = await get_csrf_token(authed_client, "/remit")
    r = await authed_client.post("/remit", data={"sar": "5000", "csrf_token": token})
    assert r.status_code == 200
    assert "5,000" in r.text or "5000" in r.text


@pytest.mark.anyio
async def test_settings_page(authed_client):
    r = await authed_client.get("/settings")
    assert r.status_code == 200
    assert "Income Config" in r.text


@pytest.mark.anyio
async def test_settings_update_rate(authed_client):
    token = await get_csrf_token(authed_client, "/settings")
    r = await authed_client.post("/settings", data={
        "action": "rate", "rate": "15.5", "csrf_token": token,
    })
    assert r.status_code == 200
    assert "15.5" in r.text


@pytest.mark.anyio
async def test_settings_update_currency(authed_client):
    token = await get_csrf_token(authed_client, "/settings")
    r = await authed_client.post("/settings", data={
        "action": "currency",
        "currency_symbol": "$",
        "income_currency": "USD",
        "csrf_token": token,
    })
    assert r.status_code == 200
    assert "USD" in r.text or "$" in r.text

    # restore defaults
    token2 = await get_csrf_token(authed_client, "/settings")
    await authed_client.post("/settings", data={
        "action": "currency",
        "currency_symbol": "₱",
        "income_currency": "SAR",
        "csrf_token": token2,
    })


@pytest.mark.anyio
async def test_settings_wrong_password(authed_client):
    token = await get_csrf_token(authed_client, "/settings")
    r = await authed_client.post("/settings", data={
        "action": "password",
        "current_password": "wrongpassword",
        "new_password": "NewPassword123!",
        "confirm_password": "NewPassword123!",
        "csrf_token": token,
    })
    assert r.status_code == 200
    assert "incorrect" in r.text.lower()


@pytest.mark.anyio
async def test_edit_existing_month(authed_client):
    r = await authed_client.get("/edit/2026-01")
    assert r.status_code == 200


@pytest.mark.anyio
async def test_edit_nonexistent_month_redirects(authed_client):
    r = await authed_client.get("/edit/1999-01")
    assert r.status_code == 200


@pytest.mark.anyio
async def test_api_analysis(authed_client):
    r = await authed_client.get("/api/analysis")
    assert r.status_code == 200
    data = r.json()
    assert "html" in data or "error" in data


@pytest.mark.anyio
async def test_api_analysis_unauthenticated(client):
    r = await client.get("/api/analysis")
    assert r.status_code == 401
    assert r.json()["error"] == "Unauthorized"


@pytest.mark.anyio
async def test_ai_rate_limit(client):
    from app.db.base import AsyncSessionLocal
    from app.db.crud import create_user, delete_user, get_user_by_username, set_ai_cache

    username = "ratelimit_test_user"
    async with AsyncSessionLocal() as db:
        existing = await get_user_by_username(db, username)
        if not existing:
            await create_user(db, username, "RateLimitPass123!", is_admin=False)
        user = await get_user_by_username(db, username)
        await set_ai_cache(db, user.id, "fakehash", "<p>cached</p>")
        # bump daily_count to the limit so next non-cached call is blocked
        from app.db.models import AiCache
        from sqlalchemy import select, update
        limit = int(os.environ.get("AI_DAILY_LIMIT", 3))
        await db.execute(update(AiCache).where(AiCache.user_id == user.id).values(daily_count=limit))
        await db.commit()

    token = await get_csrf_token(client, "/login")
    await client.post("/login", data={"username": username, "password": "RateLimitPass123!", "csrf_token": token})

    # force=1 bypasses cache → hits rate limit check
    r = await client.get("/api/analysis?force=1")
    assert r.status_code == 429
    assert "limit" in r.json()["error"].lower()

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, username)
        if user:
            await delete_user(db, user.id)


@pytest.mark.anyio
async def test_healthz(client):
    r = await client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
