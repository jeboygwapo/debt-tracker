import re

import pytest

from tests.conftest import get_csrf_token


@pytest.mark.anyio
async def test_debts_list(authed_client):
    r = await authed_client.get("/debts")
    assert r.status_code == 200
    assert "My Debts" in r.text


@pytest.mark.anyio
async def test_debt_add_and_delete(authed_client):
    token = await get_csrf_token(authed_client, "/debts")
    r = await authed_client.post("/debts", data={
        "name": "Test Card DELETE ME",
        "type": "credit_card",
        "apr_monthly_pct": "2.5",
        "note": "pytest created",
        "csrf_token": token,
    })
    assert r.status_code == 200
    assert "Test Card DELETE ME" in r.text

    idx = r.text.find("Test Card DELETE ME")
    assert idx != -1
    ids_before = re.findall(r'data-id="(\d+)"', r.text[:idx])
    assert ids_before
    debt_id = ids_before[-1]

    token2 = await get_csrf_token(authed_client, "/debts")
    r2 = await authed_client.post(f"/debts/{debt_id}/delete", data={"csrf_token": token2})
    assert r2.status_code == 200
    assert "Test Card DELETE ME" not in r2.text


@pytest.mark.anyio
async def test_debt_add_missing_name(authed_client):
    token = await get_csrf_token(authed_client, "/debts")
    r = await authed_client.post("/debts", data={
        "name": "",
        "type": "credit_card",
        "apr_monthly_pct": "2.0",
        "csrf_token": token,
    })
    assert r.status_code == 200
    assert "required" in r.text.lower() or "Name" in r.text


@pytest.mark.anyio
async def test_debt_edit_page(authed_client):
    r = await authed_client.get("/debts")
    match = re.search(r'/debts/(\d+)/edit', r.text)
    assert match
    debt_id = match.group(1)

    r2 = await authed_client.get(f"/debts/{debt_id}/edit")
    assert r2.status_code == 200
    assert "Edit Debt" in r2.text


@pytest.mark.anyio
async def test_debt_reorder(authed_client):
    r = await authed_client.get("/debts")
    ids = re.findall(r'/debts/(\d+)/edit', r.text)
    assert len(ids) >= 2
    reversed_order = ",".join(reversed(ids))
    token = await get_csrf_token(authed_client, "/debts")
    r2 = await authed_client.post("/debts/reorder", data={"order": reversed_order, "csrf_token": token})
    assert r2.status_code == 200


@pytest.mark.anyio
async def test_debt_edit_nonexistent(authed_client):
    r = await authed_client.get("/debts/99999/edit")
    assert r.url.path == "/debts"
