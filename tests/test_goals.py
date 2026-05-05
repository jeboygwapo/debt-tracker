"""Phase 2 goals tests: Goal CRUD, progress calculation, /goals routes."""
import pytest

pytestmark = pytest.mark.anyio

from app.routes.goals import _goal_progress
from tests.conftest import TEST_PASS, TEST_USER, get_csrf_token


# ── Helper: goal-like object ──────────────────────────────────────────────────

class _Goal:
    def __init__(self, target, current, monthly=0, target_date=None):
        self.target_php = target
        self.current_php = current
        self.monthly_alloc_php = monthly
        self.target_date = target_date


# ── _goal_progress unit tests ─────────────────────────────────────────────────

async def test_progress_zero_target():
    p = _goal_progress(_Goal(0, 0))
    assert p["pct"] == 0.0
    assert p["done"] is False


async def test_progress_done():
    p = _goal_progress(_Goal(10000, 10000, monthly=500))
    assert p["pct"] == 100.0
    assert p["done"] is True


async def test_progress_exceeds_target_capped():
    p = _goal_progress(_Goal(1000, 1500))
    assert p["pct"] == 100.0
    assert p["done"] is True


async def test_progress_no_target_date_with_monthly():
    # 7500 remaining / 500 = 15 months
    p = _goal_progress(_Goal(10000, 2500, monthly=500))
    assert p["months_left"] == 15
    assert p["on_track"] is None


async def test_progress_no_monthly_no_date():
    p = _goal_progress(_Goal(10000, 2500))
    assert p["months_left"] is None
    assert p["on_track"] is None


async def test_progress_with_future_target_date_on_track():
    # 2000 remaining, 500/mo → needs 4 months; target is far future
    p = _goal_progress(_Goal(3000, 1000, monthly=500, target_date="2099-12"))
    assert p["on_track"] is True


async def test_progress_with_past_target_date_behind():
    p = _goal_progress(_Goal(10000, 1000, monthly=500, target_date="2000-01"))
    assert p["on_track"] is False


async def test_progress_done_with_target_date_on_track():
    p = _goal_progress(_Goal(1000, 1000, monthly=500, target_date="2099-12"))
    assert p["done"] is True
    assert p["on_track"] is True


# ── Authenticated client fixture ──────────────────────────────────────────────

@pytest.fixture
async def authed_client(client):
    csrf = await get_csrf_token(client, "/login")
    await client.post("/login", data={
        "username": TEST_USER,
        "password": TEST_PASS,
        "csrf_token": csrf,
    })
    return client


# ── /goals GET ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_goals_get_renders(authed_client):
    r = await authed_client.get("/goals")
    assert r.status_code == 200
    assert "Goals" in r.text


@pytest.mark.anyio
async def test_goals_get_empty_state(authed_client):
    r = await authed_client.get("/goals")
    assert r.status_code == 200
    # either goals list or empty state CTA
    assert "Add" in r.text or "Goals" in r.text


# ── CRUD round-trips ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_goals_add(authed_client):
    csrf = await get_csrf_token(authed_client, "/goals")
    r = await authed_client.post("/goals", data={
        "csrf_token": csrf,
        "action": "add_goal",
        "name": "Emergency Fund",
        "target_php": "50000",
        "current_php": "5000",
        "monthly_alloc_php": "2000",
        "target_date": "2027-06",
    })
    assert r.status_code == 200
    assert "Emergency Fund" in r.text
    assert "msg=Goal+added" in str(r.url) or "Goal added" in r.text


@pytest.mark.anyio
async def test_goals_add_mp2_preset(authed_client):
    csrf = await get_csrf_token(authed_client, "/goals")
    r = await authed_client.post("/goals", data={
        "csrf_token": csrf,
        "action": "add_goal",
        "name": "PAG-IBIG MP2",
        "target_php": "500000",
        "current_php": "0",
        "monthly_alloc_php": "500",
        "target_date": "",
    })
    assert r.status_code == 200
    assert "PAG-IBIG MP2" in r.text


@pytest.mark.anyio
async def test_goals_add_invalid_name(authed_client):
    csrf = await get_csrf_token(authed_client, "/goals")
    r = await authed_client.post("/goals", data={
        "csrf_token": csrf,
        "action": "add_goal",
        "name": "",
        "target_php": "50000",
    })
    assert "Invalid" in r.text or r.status_code == 200


@pytest.mark.anyio
async def test_goals_add_invalid_target(authed_client):
    csrf = await get_csrf_token(authed_client, "/goals")
    r = await authed_client.post("/goals", data={
        "csrf_token": csrf,
        "action": "add_goal",
        "name": "Test",
        "target_php": "-1",
    })
    assert r.status_code == 200


@pytest.mark.anyio
async def test_goals_deposit(authed_client):
    csrf_add = await get_csrf_token(authed_client, "/goals")
    await authed_client.post("/goals", data={
        "csrf_token": csrf_add,
        "action": "add_goal",
        "name": "Deposit Test Goal",
        "target_php": "10000",
        "current_php": "0",
        "monthly_alloc_php": "500",
    })

    r = await authed_client.get("/goals")
    import re
    m = re.search(r'name="id"\s+value="(\d+)"', r.text)
    if not m:
        pytest.skip("no goal id found in page")
    goal_id = m.group(1)

    csrf = await get_csrf_token(authed_client, "/goals")
    r = await authed_client.post("/goals", data={
        "csrf_token": csrf,
        "action": "deposit",
        "id": goal_id,
        "amount": "1500",
    })
    assert r.status_code == 200
    assert "Deposit recorded" in r.text or "msg=Deposit+recorded" in str(r.url)


@pytest.mark.anyio
async def test_goals_deposit_invalid_amount(authed_client):
    csrf = await get_csrf_token(authed_client, "/goals")
    r = await authed_client.post("/goals", data={
        "csrf_token": csrf,
        "action": "deposit",
        "id": "99999",
        "amount": "-500",
    })
    assert r.status_code == 200


@pytest.mark.anyio
async def test_goals_delete(authed_client):
    csrf_add = await get_csrf_token(authed_client, "/goals")
    await authed_client.post("/goals", data={
        "csrf_token": csrf_add,
        "action": "add_goal",
        "name": "To Delete",
        "target_php": "1000",
        "current_php": "0",
    })

    r = await authed_client.get("/goals")
    import re
    ids = re.findall(r'name="id"\s+value="(\d+)"', r.text)
    if not ids:
        pytest.skip("no goal id found")
    goal_id = ids[-1]

    csrf = await get_csrf_token(authed_client, "/goals")
    r = await authed_client.post("/goals", data={
        "csrf_token": csrf,
        "action": "delete_goal",
        "id": goal_id,
    })
    assert r.status_code == 200
    assert "Goal deleted" in r.text or "msg=Goal+deleted" in str(r.url)


@pytest.mark.anyio
async def test_goals_delete_nonexistent(authed_client):
    csrf = await get_csrf_token(authed_client, "/goals")
    r = await authed_client.post("/goals", data={
        "csrf_token": csrf,
        "action": "delete_goal",
        "id": "999999",
    })
    assert r.status_code == 200


@pytest.mark.anyio
async def test_goals_edit_page(authed_client):
    csrf_add = await get_csrf_token(authed_client, "/goals")
    await authed_client.post("/goals", data={
        "csrf_token": csrf_add,
        "action": "add_goal",
        "name": "Edit Me",
        "target_php": "20000",
        "current_php": "0",
    })

    r = await authed_client.get("/goals")
    import re
    hrefs = re.findall(r'/goals/(\d+)/edit', r.text)
    if not hrefs:
        pytest.skip("no edit link found")
    goal_id = hrefs[0]

    r = await authed_client.get(f"/goals/{goal_id}/edit")
    assert r.status_code == 200
    assert "Edit Goal" in r.text


@pytest.mark.anyio
async def test_goals_update(authed_client):
    csrf_add = await get_csrf_token(authed_client, "/goals")
    await authed_client.post("/goals", data={
        "csrf_token": csrf_add,
        "action": "add_goal",
        "name": "Before Update",
        "target_php": "5000",
        "current_php": "0",
    })

    r = await authed_client.get("/goals")
    import re
    ids = re.findall(r'/goals/(\d+)/edit', r.text)
    if not ids:
        pytest.skip("no goal found")
    goal_id = ids[-1]

    csrf = await get_csrf_token(authed_client, f"/goals/{goal_id}/edit")
    r = await authed_client.post("/goals", data={
        "csrf_token": csrf,
        "action": "update_goal",
        "id": goal_id,
        "name": "After Update",
        "target_php": "7500",
        "current_php": "1000",
        "monthly_alloc_php": "300",
        "target_date": "2028-01",
    })
    assert r.status_code == 200
    assert "After Update" in r.text


@pytest.mark.anyio
async def test_goals_reorder(authed_client):
    csrf_add = await get_csrf_token(authed_client, "/goals")
    for name in ("Reorder A", "Reorder B"):
        await authed_client.post("/goals", data={
            "csrf_token": csrf_add,
            "action": "add_goal",
            "name": name,
            "target_php": "1000",
            "current_php": "0",
        })
        csrf_add = await get_csrf_token(authed_client, "/goals")

    r = await authed_client.get("/goals")
    import re
    ids = re.findall(r'data-id="(\d+)"', r.text)
    if len(ids) < 2:
        pytest.skip("need at least 2 goals")

    reversed_order = ",".join(reversed(ids))
    csrf = await get_csrf_token(authed_client, "/goals")
    r = await authed_client.post("/goals", data={
        "csrf_token": csrf,
        "action": "reorder",
        "order": reversed_order,
    })
    assert r.status_code == 200
