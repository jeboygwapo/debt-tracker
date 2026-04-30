import pytest


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
async def test_plan_page(authed_client):
    r = await authed_client.get("/plan")
    assert r.status_code == 200


@pytest.mark.anyio
async def test_remit_page(authed_client):
    r = await authed_client.get("/remit")
    assert r.status_code == 200


@pytest.mark.anyio
async def test_settings_page(authed_client):
    r = await authed_client.get("/settings")
    assert r.status_code == 200
    assert "Income Config" in r.text


@pytest.mark.anyio
async def test_edit_existing_month(authed_client):
    r = await authed_client.get("/edit/2026-05")
    assert r.status_code == 200


@pytest.mark.anyio
async def test_edit_nonexistent_month_redirects(authed_client):
    r = await authed_client.get("/edit/1999-01")
    # redirects to /
    assert r.status_code == 200


@pytest.mark.anyio
async def test_api_analysis(authed_client):
    r = await authed_client.get("/api/analysis")
    assert r.status_code == 200
    data = r.json()
    assert "html" in data or "error" in data
