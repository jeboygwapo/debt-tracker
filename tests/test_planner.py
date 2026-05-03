"""Unit tests for the planner module — pure functions, no DB required.

Tests are async-decorated only to coexist with the autouse session async fixture
in conftest. The planner functions themselves are synchronous.
"""
import pytest

from app.services.planner import (
    EPSILON,
    _dynamic_min_due,
    _snap,
    _sort_ccs,
    allocate_budget,
    compute_plan,
)


# ── _snap ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_snap_zero_below_epsilon():
    assert _snap(0.4) == 0.0
    assert _snap(-0.4) == 0.0


@pytest.mark.anyio
async def test_snap_rounds_above_epsilon():
    assert _snap(123.456) == 123.46
    assert _snap(EPSILON + 0.01) == round(EPSILON + 0.01, 2)


# ── _dynamic_min_due ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_dynamic_min_due_zero_balance():
    assert _dynamic_min_due(2000, 0) == 0.0
    assert _dynamic_min_due(2000, -50) == 0.0


@pytest.mark.anyio
async def test_dynamic_min_due_capped_at_balance():
    assert _dynamic_min_due(99999, 1234) == 1234.0


@pytest.mark.anyio
async def test_dynamic_min_due_floor_500():
    assert _dynamic_min_due(0, 9000) == 500.0


@pytest.mark.anyio
async def test_dynamic_min_due_pct_dominates():
    assert _dynamic_min_due(1000, 50_000) == 2500.0


@pytest.mark.anyio
async def test_dynamic_min_due_balance_below_floor():
    assert _dynamic_min_due(0, 200) == 200.0


@pytest.mark.anyio
async def test_dynamic_min_due_stored_dominates():
    assert _dynamic_min_due(5000, 80_000) == 5000.0


# ── _sort_ccs ─────────────────────────────────────────────────────────────────

def _cc(name, bal, mn, apr):
    return (name, bal, mn, apr)


@pytest.mark.anyio
async def test_sort_avalanche_highest_apr_first():
    cards = [_cc("A", 5000, 200, 2.0), _cc("B", 1000, 100, 5.0), _cc("C", 2000, 150, 3.5)]
    out = _sort_ccs(cards, "avalanche")
    assert [c[0] for c in out] == ["B", "C", "A"]


@pytest.mark.anyio
async def test_sort_snowball_smallest_balance_first():
    cards = [_cc("A", 5000, 200, 2.0), _cc("B", 1000, 100, 5.0), _cc("C", 2000, 150, 3.5)]
    out = _sort_ccs(cards, "snowball")
    assert [c[0] for c in out] == ["B", "C", "A"]


@pytest.mark.anyio
async def test_sort_cash_flow_highest_min_due_first():
    cards = [_cc("A", 5000, 200, 2.0), _cc("B", 1000, 100, 5.0), _cc("C", 2000, 350, 3.5)]
    out = _sort_ccs(cards, "cash_flow")
    assert [c[0] for c in out] == ["C", "A", "B"]


@pytest.mark.anyio
async def test_sort_default_is_avalanche():
    cards = [_cc("A", 5000, 200, 2.0), _cc("B", 1000, 100, 5.0)]
    assert _sort_ccs(cards, "unknown") == _sort_ccs(cards, "avalanche")


# ── allocate_budget ───────────────────────────────────────────────────────────

def _basic_data(allow_prepayment=False):
    return {
        "months": {
            "2026-05": {
                "CC1": {"balance": 10_000, "min_due": 500},
                "CC2": {"balance": 30_000, "min_due": 1500},
                "Loan1": {"balance": 60_000, "min_due": 0},
            }
        },
        "debts": {
            "CC1": {"type": "credit_card", "apr_monthly_pct": 3.5},
            "CC2": {"type": "credit_card", "apr_monthly_pct": 2.0},
            "Loan1": {
                "type": "personal_loan",
                "apr_monthly_pct": 0.0,
                "allow_prepayment": allow_prepayment,
            },
        },
        "fixed_payments": {"Loan1": {"monthly": 5000, "ends": "2027-12"}},
        "income_config": {},
    }


@pytest.mark.anyio
async def test_allocate_budget_returns_four_tuple():
    data = _basic_data()
    entries = data["months"]["2026-05"]
    result = allocate_budget(entries, data, 12_000)
    assert len(result) == 4
    pay_alloc, cc_priority, _attack, _nxt = result
    assert isinstance(pay_alloc, dict)
    assert isinstance(cc_priority, list)


@pytest.mark.anyio
async def test_allocate_budget_avalanche_targets_highest_apr():
    data = _basic_data()
    entries = data["months"]["2026-05"]
    _, _, attack, nxt = allocate_budget(entries, data, 12_000, "avalanche")
    assert attack == "CC1"
    assert nxt == "CC2"


@pytest.mark.anyio
async def test_allocate_budget_snowball_targets_smallest_balance():
    data = _basic_data()
    entries = data["months"]["2026-05"]
    _, _, attack, nxt = allocate_budget(entries, data, 12_000, "snowball")
    assert attack == "CC1"
    assert nxt == "CC2"


@pytest.mark.anyio
async def test_allocate_budget_pays_fixed_loan_first():
    data = _basic_data()
    entries = data["months"]["2026-05"]
    pay_alloc, _, _, _ = allocate_budget(entries, data, 8_000)
    assert pay_alloc["Loan1"] == 5000


@pytest.mark.anyio
async def test_allocate_budget_no_prepay_when_disabled():
    data = _basic_data(allow_prepayment=False)
    entries = data["months"]["2026-05"]
    pay_alloc, _, _, _ = allocate_budget(entries, data, 100_000)
    assert pay_alloc["Loan1"] == 5000


@pytest.mark.anyio
async def test_allocate_budget_prepays_when_enabled_and_surplus():
    data = _basic_data(allow_prepayment=True)
    entries = data["months"]["2026-05"]
    pay_alloc, _, _, _ = allocate_budget(entries, data, 200_000)
    assert pay_alloc["Loan1"] > 5000


@pytest.mark.anyio
async def test_allocate_budget_cc_priority_legacy_5tuple_shape():
    """Templates still iterate (n, bal, mn, apr, interest)."""
    data = _basic_data()
    entries = data["months"]["2026-05"]
    _, cc_priority, _, _ = allocate_budget(entries, data, 12_000)
    for item in cc_priority:
        assert len(item) == 5


@pytest.mark.anyio
async def test_allocate_budget_hybrid_max_one_spillover():
    data = {
        "months": {
            "2026-05": {
                "CC1": {"balance": 1000, "min_due": 100},
                "CC2": {"balance": 5000, "min_due": 200},
                "CC3": {"balance": 8000, "min_due": 300},
            }
        },
        "debts": {
            "CC1": {"type": "credit_card", "apr_monthly_pct": 5.0},
            "CC2": {"type": "credit_card", "apr_monthly_pct": 4.0},
            "CC3": {"type": "credit_card", "apr_monthly_pct": 3.0},
        },
        "fixed_payments": {},
        "income_config": {},
    }
    entries = data["months"]["2026-05"]
    pay_alloc, _, _, _ = allocate_budget(entries, data, 20_000)
    assert pay_alloc["CC1"] == 1000
    assert pay_alloc["CC2"] > _dynamic_min_due(200, 5000)
    cc3_min = _dynamic_min_due(300, 8000)
    assert pay_alloc["CC3"] == cc3_min


# ── compute_plan ──────────────────────────────────────────────────────────────

def _plan_data():
    return {
        "months": {
            "2026-06": {
                "CC1": {"balance": 5000, "min_due": 500},
                "CC2": {"balance": 8000, "min_due": 600},
            }
        },
        "debts": {
            "CC1": {"type": "credit_card", "apr_monthly_pct": 3.0},
            "CC2": {"type": "credit_card", "apr_monthly_pct": 2.0},
        },
        "fixed_payments": {},
        "income_config": {
            "monthly_sar": 8000,
            "expenses_sar": 2000,
            "sar_to_php": 15.0,
            "plan_start": "2026-07",
            "phone": {"monthly_sar": 0, "ends": "2025-12"},
        },
    }


@pytest.mark.anyio
async def test_compute_plan_returns_three_values():
    data = _plan_data()
    rows, payoffs, meta = compute_plan(data)
    assert isinstance(rows, list)
    assert isinstance(payoffs, dict)
    assert "truncated" in meta
    assert "attack_target" in meta
    assert "next_target" in meta


@pytest.mark.anyio
async def test_compute_plan_empty_data_returns_empty():
    data = {"months": {}, "debts": {}, "fixed_payments": {}, "income_config": {}}
    rows, payoffs, meta = compute_plan(data)
    assert rows == []
    assert payoffs == {}
    assert meta["truncated"] is False


@pytest.mark.anyio
async def test_compute_plan_rows_have_new_fields():
    data = _plan_data()
    rows, _, _ = compute_plan(data)
    assert rows
    for r in rows:
        assert "attack_target" in r
        assert "next_target" in r
        assert "delta" in r


@pytest.mark.anyio
async def test_compute_plan_truncated_flag_when_horizon_exceeded():
    data = {
        "months": {
            "2026-06": {"CC1": {"balance": 1_000_000, "min_due": 5000}},
        },
        "debts": {"CC1": {"type": "credit_card", "apr_monthly_pct": 5.0}},
        "fixed_payments": {},
        "income_config": {
            "monthly_sar": 100,
            "expenses_sar": 50,
            "sar_to_php": 1.0,
            "plan_start": "2026-07",
            "phone": {"monthly_sar": 0, "ends": "2025-12"},
        },
    }
    rows, _, meta = compute_plan(data)
    assert len(rows) == 120
    assert meta["truncated"] is True


@pytest.mark.anyio
async def test_allocate_budget_seeds_zero_for_unfunded_active_debt():
    """Active debts with no allocation must still appear in pay_alloc with 0.0."""
    data = {
        "months": {
            "2026-05": {
                "CC1": {"balance": 10_000, "min_due": 500},
                "CC2": {"balance": 5_000, "min_due": 250},
            }
        },
        "debts": {
            "CC1": {"type": "credit_card", "apr_monthly_pct": 5.0},
            "CC2": {"type": "credit_card", "apr_monthly_pct": 2.0},
        },
        "fixed_payments": {},
        "income_config": {},
    }
    entries = data["months"]["2026-05"]
    pay_alloc, _, _, _ = allocate_budget(entries, data, 0)
    assert "CC1" in pay_alloc
    assert "CC2" in pay_alloc
    assert pay_alloc["CC1"] == 0.0
    assert pay_alloc["CC2"] == 0.0


@pytest.mark.anyio
async def test_compute_plan_interest_order_payment_first():
    """Payment posts first, interest accrues on remaining principal."""
    data = {
        "months": {
            "2026-06": {"CC1": {"balance": 1000, "min_due": 500}},
        },
        "debts": {"CC1": {"type": "credit_card", "apr_monthly_pct": 10.0}},
        "fixed_payments": {},
        "income_config": {
            "monthly_sar": 500,
            "expenses_sar": 0,
            "sar_to_php": 1.0,
            "plan_start": "2026-06",
            "phone": {"monthly_sar": 0, "ends": "2025-12"},
        },
    }
    rows, _, _ = compute_plan(data)
    # First row: balance 1000, dynamic min_due capped at balance? bal>500 so floor=500.
    # Stored=500, pct=50, floor=500 → min_due=500. Budget=500. Pays 500.
    # New bal = (1000-500) * 1.10 = 550
    assert rows[0]["total"] == 550.0
