from typing import Any, Dict, List, Optional, Tuple


EPSILON = 0.5
MIN_DUE_PCT = 0.05
MIN_DUE_FLOOR_PHP = 500.0
PLAN_HORIZON_MONTHS = 120


def _snap(x: float) -> float:
    if abs(x) < EPSILON:
        return 0.0
    return round(x, 2)


def month_add(ym: str, n: int) -> str:
    y, m = int(ym[:4]), int(ym[5:])
    m += n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y}-{m:02d}"


def month_diff(a: str, b: str) -> int:
    ya, ma = int(a[:4]), int(a[5:])
    yb, mb = int(b[:4]), int(b[5:])
    return (yb - ya) * 12 + (mb - ma)


def latest_month(data: Dict) -> Optional[str]:
    months = sorted(data["months"].keys())
    return months[-1] if months else None


def _sort_ccs(cc_data: List[Tuple[str, float, float, float]], strategy: str):
    if strategy == "snowball":
        return sorted(cc_data, key=lambda x: x[1])
    if strategy == "cash_flow":
        return sorted(cc_data, key=lambda x: -x[2])
    return sorted(cc_data, key=lambda x: -x[3])


def _dynamic_min_due(stored_min: float, balance: float) -> float:
    if balance <= 0:
        return 0.0
    pct_min = balance * MIN_DUE_PCT
    floor = MIN_DUE_FLOOR_PHP if balance > MIN_DUE_FLOOR_PHP else balance
    return min(max(stored_min, pct_min, floor), balance)


def _fixed_rate(fp_cfg: Dict, balance: float) -> float:
    threshold = fp_cfg.get("reduced_threshold", 0)
    if threshold and balance <= threshold:
        return fp_cfg.get("reduced_monthly", fp_cfg["monthly"])
    return fp_cfg["monthly"]


def _active_expense_sar(expenses: Dict, month: str) -> float:
    """Sum monthly_sar of expenses where ends is None or ends >= month."""
    if not expenses:
        return 0.0
    total = 0.0
    for cfg in expenses.values():
        ends = cfg.get("ends")
        if ends and ends < month:
            continue
        total += float(cfg.get("monthly_sar", 0) or 0)
    return total


def _build_cc_data(
    sim_balances: Dict[str, float],
    cc_names: List[str],
    data: Dict,
) -> List[Tuple[str, float, float, float]]:
    """Return list of (name, balance, min_due, apr_pct) for active CCs."""
    out: List[Tuple[str, float, float, float]] = []
    debts_meta = data.get("debts", {})
    months = data.get("months", {})
    latest = latest_month(data) or ""
    latest_entries = months.get(latest, {})
    for n in cc_names:
        bal = sim_balances.get(n, 0) or 0
        if bal <= 0:
            continue
        stored_min = latest_entries.get(n, {}).get("min_due", 0) or 0
        min_due = _dynamic_min_due(stored_min, bal)
        apr = debts_meta.get(n, {}).get("apr_monthly_pct", 0.0)
        out.append((n, bal, min_due, apr))
    return out


def _allocate_hybrid(
    cc_sorted: List[Tuple[str, float, float, float]],
    fixed_active_set: List[str],
    sim_balances: Dict[str, float],
    fixed_pmts: Dict,
    stored_mins: Dict[str, float],
    data: Dict,
    remaining: float,
) -> Tuple[Dict[str, float], float]:
    """Hybrid cascade: fixed → CC mins → top-card + max-1 spillover → fixed prepay."""
    allocs: Dict[str, float] = {}

    # Step 1: pay each fixed loan its required amount
    for n in fixed_active_set:
        bal = sim_balances.get(n, 0) or 0
        if bal <= 0 or remaining <= 0:
            continue
        rate = _fixed_rate(fixed_pmts[n], bal)
        pay = min(rate, bal, remaining)
        allocs[n] = _snap(pay)
        remaining = _snap(remaining - pay)

    # Step 2: pay dynamic min_due on every CC
    for n, bal, _mn, _apr in cc_sorted:
        if remaining <= 0:
            break
        mn = _dynamic_min_due(stored_mins.get(n, 0) or 0, bal)
        pay = min(mn, bal, remaining)
        allocs[n] = _snap(allocs.get(n, 0) + pay)
        remaining = _snap(remaining - pay)

    # Step 3: HYBRID — top card attack with max 1 spillover
    spilled = False
    for n, bal, _mn, _apr in cc_sorted:
        if remaining <= 0:
            break
        owed = max(0, bal - allocs.get(n, 0))
        if owed <= 0:
            continue
        extra = min(owed, remaining)
        allocs[n] = _snap(allocs.get(n, 0) + extra)
        remaining = _snap(remaining - extra)
        if owed > extra:
            break
        if spilled:
            break
        spilled = True

    # Step 4: surplus → fixed loans only if allow_prepayment=True
    if remaining > 0:
        debts_meta = data.get("debts", {})
        prepay_eligible = sorted(
            [
                (n, sim_balances[n])
                for n in sim_balances
                if n in fixed_pmts
                and sim_balances[n] > 0
                and debts_meta.get(n, {}).get("allow_prepayment", False)
            ],
            key=lambda x: x[1],
        )
        for n, bal in prepay_eligible:
            if remaining <= 0:
                break
            owed = max(0, bal - allocs.get(n, 0))
            extra = min(owed, remaining)
            if extra > 0:
                allocs[n] = _snap(allocs.get(n, 0) + extra)
                remaining = _snap(remaining - extra)

    for n, bal in sim_balances.items():
        if bal > 0 and n not in allocs:
            allocs[n] = 0.0

    return allocs, remaining


def _legacy_cc_priority(
    cc_sorted: List[Tuple[str, float, float, float]],
) -> List[Tuple[str, float, float, float, float]]:
    """Templates iterate `(n, bal, mn, apr, interest)` — preserve that shape."""
    return [(n, bal, mn, apr, bal * apr / 100) for n, bal, mn, apr in cc_sorted]


def allocate_budget(
    entries: Dict,
    data: Dict,
    budget_php: float,
    strategy: str = "avalanche",
) -> Tuple[Dict[str, float], List[Tuple], Optional[str], Optional[str]]:
    fixed_pmts = data.get("fixed_payments", {})
    debts_meta = data.get("debts", {})

    sim_balances: Dict[str, float] = {
        n: (e.get("balance", 0) or 0) for n, e in entries.items()
    }
    stored_mins: Dict[str, float] = {
        n: (e.get("min_due", 0) or 0) for n, e in entries.items()
    }

    cc_names = [
        n for n in sim_balances
        if debts_meta.get(n, {}).get("type") == "credit_card"
    ]
    cc_data = _build_cc_data(sim_balances, cc_names, data)
    cc_sorted = _sort_ccs(cc_data, strategy)

    fixed_active_set = [
        n for n in sim_balances
        if n in fixed_pmts and sim_balances[n] > 0
    ]

    allocs, _remaining = _allocate_hybrid(
        cc_sorted=cc_sorted,
        fixed_active_set=fixed_active_set,
        sim_balances=sim_balances,
        fixed_pmts=fixed_pmts,
        stored_mins=stored_mins,
        data=data,
        remaining=budget_php,
    )

    attack_target = cc_sorted[0][0] if cc_sorted else None
    next_target = cc_sorted[1][0] if len(cc_sorted) > 1 else None

    return allocs, _legacy_cc_priority(cc_sorted), attack_target, next_target


def compute_plan(
    data: Dict,
    strategy: str = "avalanche",
) -> Tuple[List[Dict], Dict[str, str], Dict[str, Any]]:
    latest = latest_month(data)
    if not latest:
        return [], {}, {"truncated": False, "attack_target": None, "next_target": None}

    cfg = data.get("income_config", {})
    fixed_pmts = data.get("fixed_payments", {})
    debts_meta = data.get("debts", {})
    expenses = data.get("expenses", {})
    sar_php = cfg.get("sar_to_php", 15.0)
    plan_start = month_add(latest, 1)
    base_sar = cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)
    entries = data["months"].get(latest, {})

    stored_mins: Dict[str, float] = {
        n: (e.get("min_due", 0) or 0) for n, e in entries.items()
    }

    sim: Dict[str, float] = {
        n: (e.get("balance", 0) or 0) for n, e in entries.items()
    }

    sim = {k: v for k, v in sim.items() if v > 0}
    cc_names = [n for n in sim if debts_meta.get(n, {}).get("type") == "credit_card"]
    payoffs: Dict[str, str] = {}
    rows: List[Dict] = []
    m = plan_start

    prev_total = sum(sim.values())
    last_attack: Optional[str] = None
    last_next: Optional[str] = None

    for _ in range(PLAN_HORIZON_MONTHS):
        if all(v <= 0 for v in sim.values()):
            break

        budget = (base_sar - _active_expense_sar(expenses, m)) * sar_php

        cc_data = _build_cc_data(sim, cc_names, data)
        cc_sorted = _sort_ccs(cc_data, strategy)
        attack_target = cc_sorted[0][0] if cc_sorted else None
        next_target = cc_sorted[1][0] if len(cc_sorted) > 1 else None
        last_attack = attack_target
        last_next = next_target

        fixed_active_set = [
            n for n in sim if n in fixed_pmts and sim[n] > 0
        ]

        allocs, _remaining = _allocate_hybrid(
            cc_sorted=cc_sorted,
            fixed_active_set=fixed_active_set,
            sim_balances=sim,
            fixed_pmts=fixed_pmts,
            stored_mins=stored_mins,
            data=data,
            remaining=budget,
        )

        month_payoffs: List[str] = []
        for n in list(sim):
            if sim[n] <= 0:
                continue
            bal = sim[n]
            dtype = debts_meta.get(n, {}).get("type", "credit_card")
            apr = debts_meta.get(n, {}).get("apr_monthly_pct", 0.0)
            pay = allocs.get(n, 0)
            if dtype == "credit_card":
                sim[n] = _snap(max(0, (bal - pay) * (1 + apr / 100)))
            else:
                sim[n] = _snap(max(0, bal - pay))
            if sim[n] == 0 and n not in payoffs:
                payoffs[n] = m
                month_payoffs.append(n)

        this_total = sum(sim.values())
        delta = _snap(prev_total - this_total)
        rows.append({
            "month": m,
            "budget": _snap(budget),
            "total": _snap(this_total),
            "delta": delta,
            "payoffs": month_payoffs,
            "allocs": allocs,
            "attack_target": attack_target,
            "next_target": next_target,
        })
        prev_total = this_total
        m = month_add(m, 1)

    truncated = any(v > 0 for v in sim.values())
    meta = {
        "truncated": truncated,
        "attack_target": last_attack,
        "next_target": last_next,
    }
    return rows, payoffs, meta
