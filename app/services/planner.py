from typing import Any, Dict, List, Optional, Tuple


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


def allocate_budget(
    entries: Dict,
    data: Dict,
    budget_php: float,
) -> Tuple[Dict[str, float], List[Tuple]]:
    fixed_pmts = data.get("fixed_payments", {})
    remaining = budget_php
    pay_alloc: Dict[str, float] = {}

    for name, e in entries.items():
        bal = e.get("balance", 0) or 0
        if bal <= 0 or name not in fixed_pmts:
            continue
        fp_cfg = fixed_pmts[name]
        threshold = fp_cfg.get("reduced_threshold", 0)
        rate = (
            fp_cfg.get("reduced_monthly", fp_cfg["monthly"])
            if (threshold and bal <= threshold)
            else fp_cfg["monthly"]
        )
        pay = min(rate, bal, remaining)
        pay_alloc[name] = pay
        remaining -= pay

    cc_priority: List[Tuple] = []
    for name, e in entries.items():
        bal = e.get("balance", 0) or 0
        mn = e.get("min_due", 0) or 0
        dtype = data["debts"].get(name, {}).get("type", "credit_card")
        apr = data["debts"].get(name, {}).get("apr_monthly_pct", 0.0)
        if bal > 0 and dtype == "credit_card":
            cc_priority.append((name, bal, mn, apr, bal * apr / 100))

    cc_priority.sort(key=lambda x: -x[4])

    for name, bal, mn, apr, interest in cc_priority:
        pay = min(mn, bal, remaining)
        pay_alloc[name] = pay_alloc.get(name, 0) + pay
        remaining -= pay

    if remaining > 0 and cc_priority:
        top = cc_priority[0][0]
        pay_alloc[top] = pay_alloc.get(top, 0) + remaining

    return pay_alloc, cc_priority


def compute_plan(
    data: Dict,
    strategy: str = "avalanche",
) -> Tuple[List[Dict], Dict[str, str]]:
    latest = latest_month(data)
    if not latest:
        return [], {}

    cfg = data.get("income_config", {})
    fixed_pmts = data.get("fixed_payments", {})
    sar_php = cfg.get("sar_to_php", 15.0)
    plan_start = cfg.get("plan_start", "2026-07")
    phone_ends = cfg.get("phone", {}).get("ends", "2026-07")
    phone_sar = cfg.get("phone", {}).get("monthly_sar", 0)
    base_sar = cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)
    entries = data["months"].get(latest, {})

    balances = {n: (e.get("balance", 0) or 0) for n, e in entries.items()}
    gap = month_diff(latest, plan_start)
    for _ in range(gap):
        for n, e in entries.items():
            bal = balances[n]
            if bal <= 0:
                continue
            mn = e.get("min_due", 0) or 0
            dtype = data["debts"].get(n, {}).get("type", "credit_card")
            apr = data["debts"].get(n, {}).get("apr_monthly_pct", 0.0)
            if dtype == "credit_card":
                balances[n] = max(0, bal * (1 + apr / 100) - mn)
            else:
                balances[n] = max(0, bal - mn)

    sim = {k: v for k, v in balances.items() if v > 0}
    cc_names = [n for n in sim if data["debts"].get(n, {}).get("type") == "credit_card"]
    payoffs: Dict[str, str] = {}
    rows: List[Dict] = []
    m = plan_start

    for _ in range(120):
        if all(v <= 0 for v in sim.values()):
            break

        phone_active = m <= phone_ends
        budget = (base_sar - (phone_sar if phone_active else 0)) * sar_php
        remaining = budget
        allocs: Dict[str, float] = {}

        for n in list(sim):
            if sim[n] <= 0 or n not in fixed_pmts:
                continue
            fp_cfg = fixed_pmts[n]
            threshold = fp_cfg.get("reduced_threshold", 0)
            rate = (
                fp_cfg.get("reduced_monthly", fp_cfg["monthly"])
                if (threshold and sim[n] <= threshold)
                else fp_cfg["monthly"]
            )
            pay = min(rate, sim[n], remaining)
            allocs[n] = pay
            remaining -= pay

        cc_data = [
            (n, sim[n], sim[n] * data["debts"].get(n, {}).get("apr_monthly_pct", 3) / 100)
            for n in cc_names if sim[n] > 0
        ]
        cc_data.sort(key=lambda x: -x[2] if strategy == "avalanche" else x[1])

        for n, bal, _ in cc_data:
            mn = entries.get(n, {}).get("min_due", 0) or 0
            pay = min(mn, bal, remaining)
            allocs[n] = allocs.get(n, 0) + pay
            remaining -= pay

        if remaining > 0 and cc_data:
            t = cc_data[0][0]
            allocs[t] = allocs.get(t, 0) + remaining

        month_payoffs = []
        for n in list(sim):
            if sim[n] <= 0:
                continue
            bal = sim[n]
            dtype = data["debts"].get(n, {}).get("type", "credit_card")
            apr = data["debts"].get(n, {}).get("apr_monthly_pct", 0.0)
            pay = allocs.get(n, 0)
            if dtype == "credit_card":
                sim[n] = max(0, bal * (1 + apr / 100) - pay)
            else:
                sim[n] = max(0, bal - pay)
            if sim[n] == 0 and n not in payoffs:
                payoffs[n] = m
                month_payoffs.append(n)

        rows.append({
            "month": m,
            "budget": budget,
            "total": sum(sim.values()),
            "payoffs": month_payoffs,
            "allocs": allocs,
        })
        m = month_add(m, 1)

    return rows, payoffs
