import pytest


@pytest.mark.anyio
async def test_debts_list(authed_client):
    r = await authed_client.get("/debts")
    assert r.status_code == 200
    assert "My Debts" in r.text


@pytest.mark.anyio
async def test_debt_add_and_delete(authed_client):
    # Add
    r = await authed_client.post("/debts", data={
        "name": "Test Card DELETE ME",
        "type": "credit_card",
        "apr_monthly_pct": "2.5",
        "note": "pytest created",
    })
    assert r.status_code == 200
    assert "Test Card DELETE ME" in r.text

    # Find ID — look backwards from debt name to nearest data-id (its own row)
    import re
    idx = r.text.find("Test Card DELETE ME")
    assert idx != -1, "Debt name not found in response"
    ids_before = re.findall(r'data-id="(\d+)"', r.text[:idx])
    assert ids_before, "Could not find data-id before debt name"
    debt_id = ids_before[-1]

    # Delete
    r2 = await authed_client.post(f"/debts/{debt_id}/delete")
    assert r2.status_code == 200
    assert "Test Card DELETE ME" not in r2.text


@pytest.mark.anyio
async def test_debt_add_missing_name(authed_client):
    r = await authed_client.post("/debts", data={
        "name": "",
        "type": "credit_card",
        "apr_monthly_pct": "2.0",
    })
    assert r.status_code == 200
    assert "required" in r.text.lower() or "Name" in r.text


@pytest.mark.anyio
async def test_debt_edit_page(authed_client):
    # Get first debt ID from list
    r = await authed_client.get("/debts")
    import re
    match = re.search(r'/debts/(\d+)/edit', r.text)
    assert match
    debt_id = match.group(1)

    r2 = await authed_client.get(f"/debts/{debt_id}/edit")
    assert r2.status_code == 200
    assert "Edit Debt" in r2.text


@pytest.mark.anyio
async def test_debt_reorder(authed_client):
    r = await authed_client.get("/debts")
    import re
    ids = re.findall(r'/debts/(\d+)/edit', r.text)
    assert len(ids) >= 2
    # reverse order
    reversed_order = ",".join(reversed(ids))
    r2 = await authed_client.post("/debts/reorder", data={"order": reversed_order})
    assert r2.status_code == 200


@pytest.mark.anyio
async def test_debt_edit_nonexistent(authed_client):
    r = await authed_client.get("/debts/99999/edit")
    assert r.url.path == "/debts"
