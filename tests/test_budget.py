"""Phase 1 budget tests: Expense CRUD, planner expense aggregation, /budget routes."""
import pytest

from app.services.planner import _active_expense_sar, compute_plan
from tests.conftest import get_csrf_token


# ── _active_expense_sar ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_active_expense_sar_excludes_expired():
    expenses = {"Phone": {"monthly_sar": 200, "ends": "2025-12"}}
    assert _active_expense_sar(expenses, "2026-01") == 0.0


@pytest.mark.anyio
async def test_active_expense_sar_includes_indefinite():
    expenses = {"Gym": {"monthly_sar": 150, "ends": None}}
    assert _active_expense_sar(expenses, "2099-12") == 150.0


@pytest.mark.anyio
async def test_active_expense_sar_includes_when_ends_equals_month():
    expenses = {"Phone": {"monthly_sar": 200, "ends": "2026-07"}}
    assert _active_expense_sar(expenses, "2026-07") == 200.0


@pytest.mark.anyio
async def test_active_expense_sar_sums_multiple():
    expenses = {
        "Phone": {"monthly_sar": 200, "ends": "2026-12"},
        "Gym": {"monthly_sar": 150, "ends": None},
        "Old": {"monthly_sar": 999, "ends": "2025-01"},
    }
    assert _active_expense_sar(expenses, "2026-05") == 350.0


@pytest.mark.anyio
async def test_active_expense_sar_empty():
    assert _active_expense_sar({}, "2026-05") == 0.0


# ── compute_plan with expenses ────────────────────────────────────────────────

@pytest.mark.anyio
async def test_compute_plan_subtracts_expenses_from_budget():
    """Two active expenses (300 + 200 = 500 SAR) at rate 1.0 → 500 PHP off budget."""
    data = {
        "months": {
            "2026-06": {"CC1": {"balance": 5000, "min_due": 500}},
        },
        "debts": {"CC1": {"type": "credit_card", "apr_monthly_pct": 0.0}},
        "fixed_payments": {},
        "expenses": {
            "Phone": {"monthly_sar": 300, "ends": None},
            "Gym": {"monthly_sar": 200, "ends": None},
        },
        "income_config": {
            "monthly_sar": 1500,
            "expenses_sar": 0,
            "sar_to_php": 1.0,
        },
    }
    rows, _, _ = compute_plan(data)
    # base_sar=1500, active_expense=500 → budget = (1500-500)*1.0 = 1000
    assert rows[0]["budget"] == 1000.0


@pytest.mark.anyio
async def test_compute_plan_no_expenses_no_phone_field():
    """No phone, no expenses — full base_sar flows to budget."""
    data = {
        "months": {
            "2026-06": {"CC1": {"balance": 5000, "min_due": 500}},
        },
        "debts": {"CC1": {"type": "credit_card", "apr_monthly_pct": 0.0}},
        "fixed_payments": {},
        "expenses": {},
        "income_config": {
            "monthly_sar": 1500,
            "expenses_sar": 0,
            "sar_to_php": 1.0,
        },
    }
    rows, _, _ = compute_plan(data)
    assert rows[0]["budget"] == 1500.0


@pytest.mark.anyio
async def test_compute_plan_expense_expires_mid_horizon():
    """Expense ending early stops being subtracted in later months."""
    data = {
        "months": {
            "2026-06": {"CC1": {"balance": 100_000, "min_due": 500}},
        },
        "debts": {"CC1": {"type": "credit_card", "apr_monthly_pct": 0.0}},
        "fixed_payments": {},
        "expenses": {
            "Phone": {"monthly_sar": 200, "ends": "2026-08"},
        },
        "income_config": {
            "monthly_sar": 1500,
            "expenses_sar": 0,
            "sar_to_php": 1.0,
        },
    }
    rows, _, _ = compute_plan(data)
    # Plan starts 2026-07. 2026-07 and 2026-08 → phone active. 2026-09+ → not.
    by_month = {r["month"]: r["budget"] for r in rows}
    assert by_month["2026-07"] == 1300.0
    assert by_month["2026-08"] == 1300.0
    assert by_month["2026-09"] == 1500.0


# ── Expense CRUD round-trip ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_expense_crud_round_trip():
    from app.db.base import AsyncSessionLocal
    from app.db.crud import (
        create_expense,
        delete_expense,
        get_expense_by_id,
        get_expenses,
        get_user_by_username,
        update_expense,
    )

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        before = await get_expenses(db, user.id)
        baseline = len(before)

        created = await create_expense(
            db, user_id=user.id, name="CrudTest", monthly_sar=123.45, ends="2027-12", sort_order=99,
        )
        assert created.id

        fetched = await get_expense_by_id(db, created.id, user.id)
        assert fetched.name == "CrudTest"
        assert fetched.monthly_sar == 123.45

        updated = await update_expense(db, fetched, name="CrudTest2", monthly_sar=200.0)
        assert updated.name == "CrudTest2"
        assert updated.monthly_sar == 200.0

        all_after = await get_expenses(db, user.id)
        assert len(all_after) == baseline + 1

        deleted = await delete_expense(db, created.id, user.id)
        assert deleted is True

        gone = await get_expense_by_id(db, created.id, user.id)
        assert gone is None


@pytest.mark.anyio
async def test_expense_delete_returns_false_for_nonexistent():
    from app.db.base import AsyncSessionLocal
    from app.db.crud import delete_expense, get_user_by_username

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        assert await delete_expense(db, 999_999, user.id) is False


@pytest.mark.anyio
async def test_reorder_expenses_sets_sort_order():
    from app.db.base import AsyncSessionLocal
    from app.db.crud import (
        create_expense,
        delete_expense,
        get_expenses,
        get_user_by_username,
        reorder_expenses,
    )

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        a = await create_expense(db, user_id=user.id, name="ReorderA", monthly_sar=10, sort_order=10)
        b = await create_expense(db, user_id=user.id, name="ReorderB", monthly_sar=10, sort_order=11)
        c = await create_expense(db, user_id=user.id, name="ReorderC", monthly_sar=10, sort_order=12)

        await reorder_expenses(db, user.id, [c.id, a.id, b.id])

        rows = await get_expenses(db, user.id)
        order_map = {e.id: e.sort_order for e in rows}
        assert order_map[c.id] == 0
        assert order_map[a.id] == 1
        assert order_map[b.id] == 2

        for eid in (a.id, b.id, c.id):
            await delete_expense(db, eid, user.id)


# ── /budget routes ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_budget_get_renders_disposable(authed_client):
    r = await authed_client.get("/budget")
    assert r.status_code == 200
    # template must exist and render — content checks are loose (Frontend Engineer
    # owns the template). Smoke check we got the page back.


@pytest.mark.anyio
async def test_budget_post_add_expense_creates_row(authed_client):
    from app.db.base import AsyncSessionLocal
    from app.db.crud import (
        delete_expense,
        get_expenses,
        get_user_by_username,
    )

    token = await get_csrf_token(authed_client, "/budget")
    r = await authed_client.post("/budget", data={
        "action": "add_expense",
        "name": "RouteAdded",
        "monthly_sar": "75",
        "ends": "2027-01",
        "csrf_token": token,
    })
    assert r.status_code in (200, 303)

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        rows = await get_expenses(db, user.id)
        match = next((e for e in rows if e.name == "RouteAdded"), None)
        assert match is not None
        assert match.monthly_sar == 75.0
        assert match.ends == "2027-01"
        await delete_expense(db, match.id, user.id)


@pytest.mark.anyio
async def test_budget_post_add_expense_rejects_negative(authed_client):
    from app.db.base import AsyncSessionLocal
    from app.db.crud import get_expenses, get_user_by_username

    token = await get_csrf_token(authed_client, "/budget")
    r = await authed_client.post("/budget", data={
        "action": "add_expense",
        "name": "BadAmount",
        "monthly_sar": "-50",
        "csrf_token": token,
    })
    assert r.status_code == 200

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        rows = await get_expenses(db, user.id)
        assert all(e.name != "BadAmount" for e in rows)


@pytest.mark.anyio
async def test_budget_post_update_expense(authed_client):
    from app.db.base import AsyncSessionLocal
    from app.db.crud import (
        create_expense,
        delete_expense,
        get_expense_by_id,
        get_user_by_username,
    )

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        created = await create_expense(db, user_id=user.id, name="ToEdit", monthly_sar=10, sort_order=50)

    token = await get_csrf_token(authed_client, "/budget")
    r = await authed_client.post("/budget", data={
        "action": "update_expense",
        "id": str(created.id),
        "name": "Edited",
        "monthly_sar": "500",
        "ends": "2028-06",
        "csrf_token": token,
    })
    assert r.status_code == 200

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        fetched = await get_expense_by_id(db, created.id, user.id)
        assert fetched.name == "Edited"
        assert fetched.monthly_sar == 500.0
        assert fetched.ends == "2028-06"
        await delete_expense(db, created.id, user.id)


@pytest.mark.anyio
async def test_budget_post_delete_expense(authed_client):
    from app.db.base import AsyncSessionLocal
    from app.db.crud import (
        create_expense,
        get_expense_by_id,
        get_user_by_username,
    )

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        created = await create_expense(db, user_id=user.id, name="ToDelete", monthly_sar=10, sort_order=51)

    token = await get_csrf_token(authed_client, "/budget")
    r = await authed_client.post("/budget", data={
        "action": "delete_expense",
        "id": str(created.id),
        "csrf_token": token,
    })
    assert r.status_code == 200

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        gone = await get_expense_by_id(db, created.id, user.id)
        assert gone is None


@pytest.mark.anyio
async def test_budget_post_income_persists(authed_client):
    from app.db.base import AsyncSessionLocal
    from app.db.crud import get_user_by_username, update_income_config

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        original = dict(user.income_config or {})

    token = await get_csrf_token(authed_client, "/budget")
    r = await authed_client.post("/budget", data={
        "action": "income",
        "monthly_sar": "9000",
        "expenses_sar": "1500",
        "csrf_token": token,
    })
    assert r.status_code == 200

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        assert user.income_config["monthly_sar"] == 9000.0
        assert user.income_config["expenses_sar"] == 1500.0
        await update_income_config(db, user, original)


@pytest.mark.anyio
async def test_budget_post_rate_persists(authed_client):
    from app.db.base import AsyncSessionLocal
    from app.db.crud import get_user_by_username, update_income_config

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        original = dict(user.income_config or {})

    token = await get_csrf_token(authed_client, "/budget")
    r = await authed_client.post("/budget", data={
        "action": "rate",
        "rate": "16.5",
        "csrf_token": token,
    })
    assert r.status_code == 200

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        assert user.income_config["sar_to_php"] == 16.5
        await update_income_config(db, user, original)


@pytest.mark.anyio
async def test_budget_post_reorder(authed_client):
    from app.db.base import AsyncSessionLocal
    from app.db.crud import (
        create_expense,
        delete_expense,
        get_expenses,
        get_user_by_username,
    )

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        e1 = await create_expense(db, user_id=user.id, name="ReO1", monthly_sar=10, sort_order=70)
        e2 = await create_expense(db, user_id=user.id, name="ReO2", monthly_sar=10, sort_order=71)

    token = await get_csrf_token(authed_client, "/budget")
    r = await authed_client.post("/budget", data={
        "action": "reorder",
        "order": f"{e2.id},{e1.id}",
        "csrf_token": token,
    })
    assert r.status_code == 200

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        rows = await get_expenses(db, user.id)
        order_map = {e.id: e.sort_order for e in rows}
        assert order_map[e2.id] < order_map[e1.id]
        await delete_expense(db, e1.id, user.id)
        await delete_expense(db, e2.id, user.id)


# ── /settings cleanup — income & rate handlers removed ───────────────────────

@pytest.mark.anyio
async def test_settings_post_income_action_no_longer_writes(authed_client):
    """Old `income` action removed from /settings — must not mutate config."""
    from app.db.base import AsyncSessionLocal
    from app.db.crud import get_user_by_username

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        before = dict(user.income_config or {})

    token = await get_csrf_token(authed_client, "/settings")
    r = await authed_client.post("/settings", data={
        "action": "income",
        "monthly_sar": "99999",
        "expenses_sar": "99999",
        "csrf_token": token,
    })
    # silently ignored — no write happens, page renders
    assert r.status_code == 200

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        assert user.income_config.get("monthly_sar") == before.get("monthly_sar")
        assert user.income_config.get("expenses_sar") == before.get("expenses_sar")


@pytest.mark.anyio
async def test_settings_post_rate_action_no_longer_writes(authed_client):
    """Old `rate` action removed from /settings — must not mutate config."""
    from app.db.base import AsyncSessionLocal
    from app.db.crud import get_user_by_username

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        before = (user.income_config or {}).get("sar_to_php")

    token = await get_csrf_token(authed_client, "/settings")
    r = await authed_client.post("/settings", data={
        "action": "rate",
        "rate": "999.99",
        "csrf_token": token,
    })
    assert r.status_code == 200

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, "testadmin")
        assert (user.income_config or {}).get("sar_to_php") == before
