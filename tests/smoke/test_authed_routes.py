"""SMOKE-008..014, 017, 019, 020 — authenticated surface area.

Hits each protected route with a logged-in session and asserts the page
renders with a recognisable marker. Goal: catch dead routes / template
import regressions in <2s per test.
"""

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.anyio]


async def test_smoke_008_dashboard(smoke_authed_client):
    r = await smoke_authed_client.get("/")
    assert r.status_code == 200
    assert "Total Debt" in r.text or "Dashboard" in r.text


async def test_smoke_009_add_month_page(smoke_authed_client):
    r = await smoke_authed_client.get("/add")
    assert r.status_code == 200
    assert "month" in r.text.lower()


async def test_smoke_010_debts_list(smoke_authed_client):
    r = await smoke_authed_client.get("/debts")
    assert r.status_code == 200
    assert "My Debts" in r.text


async def test_smoke_011_remit_page(smoke_authed_client):
    r = await smoke_authed_client.get("/remit")
    assert r.status_code == 200
    assert "Planner" in r.text or "remit" in r.text.lower()


async def test_smoke_012_plan_page(smoke_authed_client):
    r = await smoke_authed_client.get("/plan")
    assert r.status_code == 200
    assert "Avalanche" in r.text or "Strategy" in r.text or "Snowball" in r.text


async def test_smoke_013_settings_page(smoke_authed_client):
    r = await smoke_authed_client.get("/settings")
    assert r.status_code == 200
    assert "Income Config" in r.text


async def test_smoke_014_admin_page(smoke_authed_client):
    """Smoke admin is_admin=True so /admin must render the user table."""
    r = await smoke_authed_client.get("/admin")
    assert r.status_code == 200
    assert "User Management" in r.text


async def test_smoke_017_logout_clears_session(smoke_authed_client):
    """Logging out then hitting / must redirect to /welcome (not stay on dashboard)."""
    await smoke_authed_client.get("/logout")
    r = await smoke_authed_client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/welcome" in r.headers["location"]


async def test_smoke_019_notifications_unread_endpoint(smoke_authed_client):
    """JSON endpoint used by the nav badge — must always answer 200 with int count."""
    r = await smoke_authed_client.get("/api/notifications/unread")
    assert r.status_code == 200
    body = r.json()
    assert "count" in body
    assert isinstance(body["count"], int)


async def test_smoke_020_api_analysis_responds(smoke_authed_client):
    """Authed analysis endpoint returns either AI html OR a structured error.

    Smoke does not require an OpenAI key; we just verify the contract.
    """
    r = await smoke_authed_client.get("/api/analysis")
    assert r.status_code in (200, 429)
    body = r.json()
    assert "html" in body or "error" in body
