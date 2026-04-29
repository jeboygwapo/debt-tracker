#!/usr/bin/env python3
"""
Debt Tracker CLI — Jayvee Personal Finance
Run: python tracker.py [command]
Commands: summary, add, history, strategy, budget, help
"""

import json
import sys
from pathlib import Path
from datetime import date

DATA_FILE = Path(__file__).parent / "debts.json"

COLORS = {
    "red":    "\033[91m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "cyan":   "\033[96m",
    "bold":   "\033[1m",
    "dim":    "\033[2m",
    "reset":  "\033[0m",
}

def c(color, text):
    return f"{COLORS[color]}{text}{COLORS['reset']}"

def load():
    with open(DATA_FILE) as f:
        return json.load(f)

def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def latest_month(data):
    months = sorted(data["months"].keys())
    return months[-1] if months else None

def fp(amount):
    return f"₱{amount:,.2f}"

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
def cmd_summary(data, month=None):
    if month is None:
        month = latest_month(data)
    if month not in data["months"]:
        print(c("red", f"No data for {month}"))
        return

    entries = data["months"][month]
    print(c("bold", f"\n{'='*65}"))
    print(c("bold", f"  DEBT SUMMARY — {month}"))
    print(c("bold", f"{'='*65}"))

    total_balance = total_min = total_paid = 0
    cc_rows = []
    loan_rows = []
    personal_rows = []

    for name, entry in entries.items():
        balance  = entry.get("balance",  0) or 0
        min_due  = entry.get("min_due",  0) or 0
        payment  = entry.get("payment",  0) or 0
        paid_on  = entry.get("paid_on",  "")
        due_date = entry.get("due_date", "")
        note     = entry.get("note",     "")
        dtype    = data["debts"].get(name, {}).get("type", "credit_card")

        total_balance += balance
        total_min     += min_due
        total_paid    += payment

        if paid_on and paid_on not in ("Good", "Ready"):
            status = c("green", f"✓ {paid_on}")
        elif paid_on in ("Good", "Ready"):
            status = c("yellow", paid_on)
        else:
            status = c("red", "UNPAID")

        row = (name, balance, min_due, payment, due_date, status, note)
        if dtype == "credit_card":
            cc_rows.append(row)
        elif dtype == "personal":
            personal_rows.append(row)
        else:
            loan_rows.append(row)

    def print_section(title, rows):
        if not rows:
            return
        print(c("cyan", f"\n  {title}"))
        print(f"  {'Name':<28} {'Balance':>12} {'Min Due':>10} {'Payment':>10}  {'Due':<10} Status")
        print(f"  {'-'*28} {'-'*12} {'-'*10} {'-'*10}  {'-'*10} {'-'*20}")
        for name, bal, mn, pmt, due, status, note in rows:
            if bal == 0 and not mn:
                print(f"  {c('green', name):<28}  {'DONE':>12}")
            else:
                row_str = f"  {name:<28} {fp(bal):>12} {fp(mn):>10} {fp(pmt):>10}  {due:<10} {status}"
                if note:
                    row_str += c("dim", f"  [{note}]")
                print(row_str)

    print_section("CREDIT CARDS", cc_rows)
    print_section("LOANS", loan_rows)
    print_section("PERSONAL", personal_rows)

    print(c("bold", f"\n{'='*65}"))
    print(f"  {'Total Balance:':<32} {c('red', fp(total_balance))}")
    print(f"  {'Total Min Due:':<32} {fp(total_min)}")
    print(f"  {'Total Paid this cycle:':<32} {c('green', fp(total_paid))}")
    print(c("bold", f"{'='*65}\n"))

# ---------------------------------------------------------------------------
# STRATEGY  (snowball | avalanche)
# ---------------------------------------------------------------------------
def cmd_strategy(data, method="snowball"):
    month = latest_month(data)
    entries = data["months"][month]

    method = method.lower()
    if method not in ("snowball", "avalanche"):
        print(c("red", "Method must be 'snowball' or 'avalanche'"))
        return

    cards = []
    for name, entry in entries.items():
        bal     = entry.get("balance",  0) or 0
        min_due = entry.get("min_due",  0) or 0
        dtype   = data["debts"].get(name, {}).get("type", "credit_card")
        apr     = data["debts"].get(name, {}).get("apr_monthly_pct", 2.0)
        if bal > 0 and dtype == "credit_card":
            monthly_interest = bal * apr / 100
            cards.append((name, bal, min_due, apr, monthly_interest))

    if method == "snowball":
        cards.sort(key=lambda x: x[1])
        title = "SNOWBALL  (lowest balance first — fastest wins)"
        tip   = "Best for: motivation, quick payoff milestones"
    else:
        cards.sort(key=lambda x: x[4], reverse=True)
        title = "AVALANCHE  (highest interest cost first — saves most money)"
        tip   = "Best for: minimizing total interest paid"

    print(c("bold", f"\n{'='*65}"))
    print(c("bold", f"  PAYOFF STRATEGY — {title}"))
    print(c("dim",  f"  {tip}"))
    print(c("bold", f"{'='*65}"))
    print(c("cyan", f"\n  Pay MINIMUM on all. Throw every extra peso at #1.\n"))

    print(f"  {'#':<4} {'Card':<28} {'Balance':>12} {'Min Due':>10} {'Monthly Interest':>17}")
    print(f"  {'-'*4} {'-'*28} {'-'*12} {'-'*10} {'-'*17}")

    for i, (name, bal, mn, apr, interest) in enumerate(cards, 1):
        focus = c("yellow", " ← ATTACK") if i == 1 else ""
        num   = c("yellow", f"#{i}") if i == 1 else f"#{i}"
        print(f"  {num:<4} {name:<28} {fp(bal):>12} {fp(mn):>10} {fp(interest):>17}{focus}")

    total_interest = sum(x[4] for x in cards)
    print(c("dim", f"\n  Total monthly interest on CCs: {fp(total_interest)}"))
    print(c("bold", "\n  Car loan ends in ~2 months → redirect ₱16,066 to #1 card!"))
    print(c("bold", f"{'='*65}\n"))

# ---------------------------------------------------------------------------
# BUDGET PLANNER
# ---------------------------------------------------------------------------
def cmd_budget(data, monthly_budget):
    month = latest_month(data)
    entries = data["months"][month]

    print(c("bold", f"\n{'='*65}"))
    print(c("bold", f"  MONTHLY BUDGET PLAN — {fp(monthly_budget)}/month"))
    print(c("bold", f"  Based on: {month} balances"))
    print(c("bold", f"{'='*65}"))

    all_debts = []
    for name, entry in entries.items():
        bal     = entry.get("balance",  0) or 0
        min_due = entry.get("min_due",  0) or 0
        dtype   = data["debts"].get(name, {}).get("type", "credit_card")
        apr     = data["debts"].get(name, {}).get("apr_monthly_pct", 0.0)
        if bal > 0 and min_due > 0:
            monthly_interest = bal * apr / 100
            all_debts.append({
                "name": name, "balance": bal, "min_due": min_due,
                "type": dtype, "apr": apr, "interest": monthly_interest
            })

    total_min = sum(d["min_due"] for d in all_debts)

    if monthly_budget < total_min:
        print(c("red", f"\n  WARNING: Budget {fp(monthly_budget)} < total minimums {fp(total_min)}"))
        print(c("red",  f"  Shortfall: {fp(total_min - monthly_budget)}"))
        print(c("red",  f"  Risk: missed payments / late fees\n"))
        print(c("yellow", "  Allocation (minimums only, partial):"))
    else:
        extra = monthly_budget - total_min
        print(c("green", f"\n  Total minimums: {fp(total_min)}"))
        print(c("green", f"  Extra available: {fp(extra)} → goes to highest-priority CC\n"))

    # Sort CCs by monthly interest cost (avalanche) for extra allocation
    cc_debts    = sorted([d for d in all_debts if d["type"] == "credit_card"],
                          key=lambda x: x["interest"], reverse=True)
    other_debts = [d for d in all_debts if d["type"] != "credit_card"]

    remaining_budget = monthly_budget
    allocations = {}

    # Assign minimums first
    for d in all_debts:
        pay = min(d["min_due"], remaining_budget, d["balance"])
        allocations[d["name"]] = pay
        remaining_budget -= pay

    # Dump extra into top CC
    if remaining_budget > 0 and cc_debts:
        top = cc_debts[0]["name"]
        allocations[top] += remaining_budget
        remaining_budget = 0

    # Print allocation table
    print(f"  {'Card/Loan':<30} {'Balance':>12} {'Min Due':>10} {'→ PAY':>10}  Note")
    print(f"  {'-'*30} {'-'*12} {'-'*10} {'-'*10}  {'-'*20}")

    for d in other_debts:
        name = d["name"]
        alloc = allocations.get(name, 0)
        tag = c("dim", "(loan/personal)")
        print(f"  {name:<30} {fp(d['balance']):>12} {fp(d['min_due']):>10} {c('cyan', fp(alloc)):>19}  {tag}")

    for d in cc_debts:
        name = d["name"]
        alloc = allocations.get(name, 0)
        extra_tag = ""
        if alloc > d["min_due"]:
            extra_tag = c("yellow", f"  ← +{fp(alloc - d['min_due'])} extra")
        months_to_payoff = d["balance"] / alloc if alloc > 0 else 999
        eta = c("dim", f"~{months_to_payoff:.0f}mo") if alloc > 0 else c("red", "DANGER")
        print(f"  {name:<30} {fp(d['balance']):>12} {fp(d['min_due']):>10} {c('cyan', fp(alloc)):>19}{extra_tag}  {eta}")

    total_alloc = sum(allocations.values())
    print(c("bold", f"\n  {'Total Allocated:':<30} {fp(total_alloc):>12}"))
    print(c("bold", f"{'='*65}\n"))

# ---------------------------------------------------------------------------
# EXPORT — HTML dashboard
# ---------------------------------------------------------------------------
def _get_ai_analysis(data):
    import os, json as _json
    _load_env()
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        latest  = latest_month(data)
        entries = data["months"][latest]
        cfg     = data.get("income_config", {})
        summary = []
        for name, e in entries.items():
            bal  = e.get("balance", 0) or 0
            mn   = e.get("min_due", 0) or 0
            apr  = data["debts"].get(name, {}).get("apr_monthly_pct", 0.0)
            dtype = data["debts"].get(name, {}).get("type", "credit_card")
            if bal > 0:
                summary.append({"name": name, "balance": bal, "min_due": mn,
                                 "apr_monthly_pct": apr, "type": dtype})
        context = {
            "month": latest,
            "debts": summary,
            "monthly_budget_php": (cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)) * cfg.get("sar_to_php", 15),
            "total_debt": sum(d["balance"] for d in summary),
            "total_monthly_interest": sum(d["balance"] * d["apr_monthly_pct"] / 100 for d in summary if d["type"] == "credit_card"),
        }
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are a personal finance advisor for a Filipino OFW in Saudi Arabia. "
                    "Be direct, specific, use numbers. Format response in clean HTML using <p>, <ul>, <li>, <strong> tags only. No markdown."
                )},
                {"role": "user", "content": (
                    f"Debt situation for {latest}:\n{_json.dumps(context, indent=2)}\n\n"
                    "Give: 1) Key observations (3 bullets), 2) Biggest risk, "
                    "3) One specific action this month with exact peso amount, "
                    "4) Projected savings following avalanche plan."
                )}
            ],
            max_tokens=600
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"<p style='color:#ef4444'>AI analysis failed: {e}</p>"

def cmd_export(data):
    import json as _json
    from pathlib import Path

    months_sorted = sorted(data["months"].keys())
    latest = months_sorted[-1] if months_sorted else None

    # --- history data for chart ---
    history_labels = []
    history_totals = []
    cc_totals      = []
    loan_totals    = []

    for m in months_sorted:
        entries = data["months"][m]
        total = cc = loans = 0
        for name, e in entries.items():
            bal = e.get("balance", 0) or 0
            dtype = data["debts"].get(name, {}).get("type", "credit_card")
            total += bal
            if dtype == "credit_card": cc += bal
            else: loans += bal
        history_labels.append(m)
        history_totals.append(round(total, 2))
        cc_totals.append(round(cc, 2))
        loan_totals.append(round(loans, 2))

    # --- latest breakdown for donut ---
    latest_entries = data["months"].get(latest, {})
    donut_labels, donut_values, donut_colors = [], [], []
    palette = ["#ef4444","#f97316","#eab308","#22c55e","#3b82f6","#8b5cf6","#ec4899","#14b8a6","#f43f5e"]
    for i, (name, e) in enumerate(latest_entries.items()):
        bal = e.get("balance", 0) or 0
        if bal > 0:
            donut_labels.append(name.split("(")[0].strip())
            donut_values.append(round(bal, 2))
            donut_colors.append(palette[i % len(palette)])

    # --- plan simulation for projection chart ---
    cfg        = data.get("income_config", {})
    sar_php    = cfg.get("sar_to_php", 15.0)
    plan_start = cfg.get("plan_start", "2026-07")
    phone_ends = cfg.get("phone", {}).get("ends", "2026-07")
    phone_sar  = cfg.get("phone", {}).get("monthly_sar", 0)
    base_sar   = cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)
    fixed_pmts = data.get("fixed_payments", {})

    sim_bal = {}
    for name, e in latest_entries.items():
        sim_bal[name] = e.get("balance", 0) or 0
    gap = month_diff(latest, plan_start)
    for _ in range(gap):
        for name, e in latest_entries.items():
            bal = sim_bal[name]
            mn  = e.get("min_due", 0) or 0
            dtype = data["debts"].get(name, {}).get("type", "credit_card")
            apr   = data["debts"].get(name, {}).get("apr_monthly_pct", 0.0)
            if bal <= 0: continue
            sim_bal[name] = max(0, bal * (1 + apr/100) - mn if dtype == "credit_card" else bal - mn)

    proj_labels, proj_totals = [], []
    cc_names = [n for n in sim_bal if data["debts"].get(n, {}).get("type") == "credit_card"]
    sim = dict(sim_bal)
    m   = plan_start
    for _ in range(120):
        if all(v <= 0 for v in sim.values()): break
        phone_active = m <= phone_ends
        avail_sar    = base_sar - (phone_sar if phone_active else 0)
        budget       = avail_sar * sar_php
        remaining    = budget
        allocs = {}
        for name in sim:
            if sim[name] <= 0: continue
            if name in fixed_pmts:
                fp_cfg    = fixed_pmts[name]
                threshold = fp_cfg.get("reduced_threshold", 0)
                rate      = fp_cfg.get("reduced_monthly", fp_cfg["monthly"]) if (threshold and sim[name] <= threshold) else fp_cfg["monthly"]
                pay = min(rate, sim[name], remaining)
                allocs[name] = pay; remaining -= pay
        active_ccs = [(n, sim[n]) for n in cc_names if sim[n] > 0]
        for name, bal in active_ccs:
            mn  = latest_entries.get(name, {}).get("min_due", 0) or 0
            pay = min(mn, bal, remaining)
            allocs[name] = allocs.get(name, 0) + pay; remaining -= pay
        active_ccs.sort(key=lambda x: -(x[1] * data["debts"].get(x[0], {}).get("apr_monthly_pct", 3) / 100))
        if remaining > 0 and active_ccs:
            t = active_ccs[0][0]; allocs[t] = allocs.get(t, 0) + remaining
        for name in list(sim):
            if sim[name] <= 0: continue
            bal   = sim[name]
            dtype = data["debts"].get(name, {}).get("type", "credit_card")
            apr   = data["debts"].get(name, {}).get("apr_monthly_pct", 0.0)
            pay   = allocs.get(name, 0)
            sim[name] = max(0, bal * (1 + apr/100) - pay if dtype == "credit_card" else bal - pay)
        proj_labels.append(m)
        proj_totals.append(round(sum(sim.values()), 2))
        m = month_add(m, 1)

    total_now = sum((e.get("balance", 0) or 0) for e in latest_entries.values())
    total_cc  = sum((e.get("balance", 0) or 0) for name, e in latest_entries.items()
                    if data["debts"].get(name, {}).get("type") == "credit_card")
    monthly_interest = sum(
        (e.get("balance", 0) or 0) * data["debts"].get(name, {}).get("apr_monthly_pct", 0) / 100
        for name, e in latest_entries.items()
        if data["debts"].get(name, {}).get("type") == "credit_card"
    )

    # --- payment priority table (avalanche) ---
    cfg        = data.get("income_config", {})
    fixed_pmts = data.get("fixed_payments", {})
    sar_php    = cfg.get("sar_to_php", 15.0)
    phone_ends = cfg.get("phone", {}).get("ends", "2026-07")
    phone_sar  = cfg.get("phone", {}).get("monthly_sar", 0)
    base_sar   = cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)
    avail_sar  = base_sar - (phone_sar if latest <= phone_ends else 0)
    budget_php = avail_sar * sar_php

    remaining = budget_php
    pay_alloc = {}

    for name, e in latest_entries.items():
        bal = e.get("balance", 0) or 0
        if bal <= 0 or name not in fixed_pmts: continue
        fp_cfg    = fixed_pmts[name]
        threshold = fp_cfg.get("reduced_threshold", 0)
        rate      = fp_cfg.get("reduced_monthly", fp_cfg["monthly"]) if (threshold and bal <= threshold) else fp_cfg["monthly"]
        pay = min(rate, bal, remaining)
        pay_alloc[name] = pay; remaining -= pay

    cc_priority = []
    for name, e in latest_entries.items():
        bal  = e.get("balance", 0) or 0
        mn   = e.get("min_due", 0) or 0
        dtype = data["debts"].get(name, {}).get("type", "credit_card")
        apr  = data["debts"].get(name, {}).get("apr_monthly_pct", 0.0)
        if bal > 0 and dtype == "credit_card":
            cc_priority.append((name, bal, mn, apr, bal * apr / 100))

    cc_priority.sort(key=lambda x: -x[4])

    for name, bal, mn, apr, interest in cc_priority:
        pay = min(mn, bal, remaining)
        pay_alloc[name] = pay_alloc.get(name, 0) + pay; remaining -= pay

    if remaining > 0 and cc_priority:
        top = cc_priority[0][0]
        pay_alloc[top] = pay_alloc.get(top, 0) + remaining

    priority_rows_html = ""
    for rank, (name, bal, mn, apr, interest) in enumerate(cc_priority, 1):
        alloc = pay_alloc.get(name, 0)
        extra = alloc - mn
        rank_badge = '<span style="background:#854d0e;color:#fde68a;padding:2px 8px;border-radius:999px;font-weight:700;font-size:.75rem">ATTACK</span>' if rank == 1 else f'#{rank}'
        extra_str  = f'<span style="color:#22c55e;font-weight:600">+₱{extra:,.2f}</span>' if extra > 0.5 else '—'
        total_pay  = f'<strong>₱{alloc:,.2f}</strong>'
        priority_rows_html += f"""<tr>
          <td>{rank_badge}</td>
          <td>{name}</td>
          <td>₱{bal:,.2f}</td>
          <td>₱{mn:,.2f}</td>
          <td style="color:#ef4444">₱{interest:,.2f}</td>
          <td>{extra_str}</td>
          <td>{total_pay}</td>
        </tr>"""

    fixed_rows_html = ""
    for name, e in latest_entries.items():
        if name not in fixed_pmts: continue
        bal  = e.get("balance", 0) or 0
        alloc = pay_alloc.get(name, 0)
        if bal > 0:
            fixed_rows_html += f'<tr><td colspan="2">{name}</td><td>₱{bal:,.2f}</td><td colspan="3">Fixed</td><td><strong>₱{alloc:,.2f}</strong></td></tr>'

    # --- card rows for status table ---
    card_rows_html = ""
    for name, e in latest_entries.items():
        bal    = e.get("balance", 0) or 0
        mn     = e.get("min_due", 0) or 0
        due    = e.get("due_date", "—")
        paid   = e.get("paid_on", "")
        dtype  = data["debts"].get(name, {}).get("type", "credit_card")
        apr    = data["debts"].get(name, {}).get("apr_monthly_pct", 0.0)
        interest = bal * apr / 100 if dtype == "credit_card" else 0
        paid_badge = (f'<span class="badge green">✓ {paid}</span>' if paid and paid not in ("Good","Ready")
                      else f'<span class="badge yellow">{paid}</span>' if paid
                      else '<span class="badge red">Unpaid</span>')
        if bal == 0:
            card_rows_html += f'<tr><td>{name}</td><td colspan="5" style="color:#22c55e;font-weight:600">DONE ✓</td></tr>'
        else:
            card_rows_html += f"""<tr>
              <td>{name}</td>
              <td>₱{bal:,.2f}</td>
              <td>₱{mn:,.2f}</td>
              <td>₱{interest:,.2f}</td>
              <td>{due}</td>
              <td>{paid_badge}</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jayvee — Debt Tracker Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}}
  h1{{font-size:1.5rem;font-weight:700;margin-bottom:4px}}
  .subtitle{{color:#94a3b8;font-size:.875rem;margin-bottom:24px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
  .card{{background:#1e293b;border-radius:12px;padding:20px}}
  .card .label{{color:#94a3b8;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}}
  .card .value{{font-size:1.5rem;font-weight:700}}
  .card .value.red{{color:#ef4444}}
  .card .value.green{{color:#22c55e}}
  .card .value.yellow{{color:#eab308}}
  .card .value.blue{{color:#3b82f6}}
  .charts{{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-bottom:24px}}
  .chart-card{{background:#1e293b;border-radius:12px;padding:20px}}
  .chart-card h3{{font-size:.875rem;color:#94a3b8;margin-bottom:16px;text-transform:uppercase;letter-spacing:.05em}}
  table{{width:100%;border-collapse:collapse}}
  th{{text-align:left;padding:10px 12px;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:#94a3b8;border-bottom:1px solid #334155}}
  td{{padding:10px 12px;font-size:.875rem;border-bottom:1px solid #1e293b}}
  tr:hover td{{background:#1e293b}}
  .badge{{padding:2px 8px;border-radius:999px;font-size:.75rem;font-weight:600}}
  .badge.green{{background:#166534;color:#86efac}}
  .badge.red{{background:#7f1d1d;color:#fca5a5}}
  .badge.yellow{{background:#713f12;color:#fde68a}}
  .section{{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:24px}}
  .section h3{{font-size:.875rem;color:#94a3b8;margin-bottom:16px;text-transform:uppercase;letter-spacing:.05em}}
  @media(max-width:768px){{.charts{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>💳 Jayvee — Debt Tracker</h1>
<p class="subtitle">Last updated: {latest} &nbsp;|&nbsp; Generated {date.today()}</p>

<div class="grid">
  <div class="card"><div class="label">Total Debt</div><div class="value red">₱{total_now:,.2f}</div></div>
  <div class="card"><div class="label">Credit Cards</div><div class="value yellow">₱{total_cc:,.2f}</div></div>
  <div class="card"><div class="label">Interest / Month</div><div class="value red">₱{monthly_interest:,.2f}</div></div>
  <div class="card"><div class="label">Debt-Free Target</div><div class="value green">{proj_labels[-1] if proj_labels else "—"}</div></div>
</div>

<div class="charts">
  <div class="chart-card">
    <h3>Balance Trend + Projection</h3>
    <canvas id="trendChart" height="120"></canvas>
  </div>
  <div class="chart-card">
    <h3>Current Breakdown</h3>
    <canvas id="donutChart"></canvas>
  </div>
</div>

<div class="section" style="border:2px solid #854d0e">
  <h3 style="color:#fde68a">💰 PAY THIS MONTH — Budget ₱{budget_php:,.0f}</h3>
  <p style="color:#94a3b8;font-size:.8rem;margin-bottom:12px">Avalanche strategy: minimums on all, everything extra → ATTACK card. Pay in order shown.</p>
  <table>
    <thead><tr><th>Priority</th><th>Card</th><th>Balance</th><th>Min Due</th><th>Interest/mo</th><th>Extra</th><th>→ PAY THIS MONTH</th></tr></thead>
    <tbody>
      {fixed_rows_html}
      {priority_rows_html}
    </tbody>
  </table>
  <p style="margin-top:12px;color:#94a3b8;font-size:.8rem">Total budget: ₱{budget_php:,.0f} &nbsp;|&nbsp; SAR→PHP rate: {sar_php}</p>
</div>

<div class="section">
  <h3>All Cards — Status {latest}</h3>
  <table>
    <thead><tr><th>Card / Loan</th><th>Balance</th><th>Min Due</th><th>Monthly Interest</th><th>Due Date</th><th>Status</th></tr></thead>
    <tbody>{card_rows_html}</tbody>
  </table>
</div>

<script>
const histLabels = {_json.dumps(history_labels)};
const histTotals = {_json.dumps(history_totals)};
const projLabels = {_json.dumps(proj_labels)};
const projTotals = {_json.dumps(proj_totals)};

const allLabels = [...histLabels, ...projLabels];
const histData  = [...histTotals, ...new Array(projLabels.length).fill(null)];
const projData  = [...new Array(histLabels.length - 1).fill(null), histTotals[histTotals.length-1], ...projTotals];

new Chart(document.getElementById('trendChart'), {{
  type: 'line',
  data: {{
    labels: allLabels,
    datasets: [
      {{label:'Actual',data:histData,borderColor:'#3b82f6',backgroundColor:'rgba(59,130,246,.1)',tension:.3,fill:true,pointRadius:4}},
      {{label:'Projected',data:projData,borderColor:'#22c55e',backgroundColor:'rgba(34,197,94,.05)',borderDash:[5,5],tension:.3,fill:true,pointRadius:2}}
    ]
  }},
  options:{{responsive:true,plugins:{{legend:{{labels:{{color:'#94a3b8'}}}}}},scales:{{x:{{ticks:{{color:'#64748b',maxTicksLimit:12}},grid:{{color:'#1e293b'}}}},y:{{ticks:{{color:'#64748b',callback:v=>'₱'+v.toLocaleString()}},grid:{{color:'#334155'}}}}}}}}
}});

new Chart(document.getElementById('donutChart'), {{
  type: 'doughnut',
  data: {{
    labels: {_json.dumps(donut_labels)},
    datasets: [{{data:{_json.dumps(donut_values)},backgroundColor:{_json.dumps(donut_colors)},borderWidth:2,borderColor:'#1e293b'}}]
  }},
  options:{{responsive:true,plugins:{{legend:{{position:'bottom',labels:{{color:'#94a3b8',font:{{size:11}},padding:8}}}}}}}}
}});
</script>
</body>
</html>"""

    # --- inject AI analysis ---
    print(c("cyan", "  Fetching AI analysis..."))
    ai_html = _get_ai_analysis(data)
    if ai_html:
        ai_section = f"""
<div class="section" style="border:2px solid #1d4ed8;margin-top:0">
  <h3 style="color:#93c5fd">🤖 AI Analysis — GPT-4o-mini</h3>
  <div style="color:#e2e8f0;font-size:.9rem;line-height:1.7">{ai_html}</div>
  <p style="color:#475569;font-size:.75rem;margin-top:12px">Generated {date.today()} · Based on {latest} balances</p>
</div>"""
        html = html.replace("</body>", ai_section + "\n</body>")
    else:
        print(c("yellow", "  No OpenAI key — skipping AI section. Run: python3 tracker.py setkey sk-..."))

    import webbrowser
    out = Path(__file__).parent / "dashboard.html"
    out.write_text(html)
    print(c("green", f"\n  Dashboard saved: {out}"))
    webbrowser.open(f"file://{out}")
    print(c("cyan",  f"  Opened in browser.\n"))


# ---------------------------------------------------------------------------
# ADD MONTH
# ---------------------------------------------------------------------------
def cmd_add(data):
    print(c("bold", "\n  ADD NEW MONTH"))
    print(c("cyan", "  Format: YYYY-MM (e.g. 2026-06)\n"))

    month = input("  Month: ").strip()
    if not month:
        print(c("red", "  Cancelled."))
        return

    if month in data["months"]:
        confirm = input(c("yellow", f"  {month} exists. Overwrite? [y/N]: ")).strip().lower()
        if confirm != "y":
            print("  Cancelled.")
            return

    data["months"][month] = {}
    print(c("cyan", "\n  Enter data for each debt. Type 'done' to skip a card entirely.\n"))

    for name in data["debts"]:
        print(c("bold", f"  [{name}]"))
        try:
            bal_str = input("    Balance ('done' to skip): ").strip()
            if bal_str.lower() == "done":
                print(c("yellow", f"    Skipped"))
                continue

            balance  = float(bal_str.replace(",", ""))       if bal_str  else 0
            min_str  = input("    Min Due: ").strip()
            min_due  = float(min_str.replace(",", ""))        if min_str  else 0
            pmt_str  = input("    Payment: ").strip()
            payment  = float(pmt_str.replace(",", ""))        if pmt_str  else 0
            due_date = input("    Due Date (e.g. Jun 12): ").strip()
            paid_on  = input("    Paid On (date/blank): ").strip()
            note     = input("    Note: ").strip()

            entry = {"balance": balance, "min_due": min_due, "payment": payment}
            if due_date: entry["due_date"] = due_date
            if paid_on:  entry["paid_on"]  = paid_on
            if note:     entry["note"]     = note

            data["months"][month][name] = entry
            print()
        except (ValueError, KeyboardInterrupt):
            print(c("yellow", "\n  Skipped.\n"))
            continue

    save(data)
    print(c("green", f"\n  Saved {month}!"))
    cmd_summary(data, month)

# ---------------------------------------------------------------------------
# AI ANALYZE — OpenAI
# ---------------------------------------------------------------------------
def _load_env():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                import os; os.environ.setdefault(k.strip(), v.strip())

def cmd_setrate(data):
    current = data.get("income_config", {}).get("sar_to_php", 15.0)
    print(c("dim", f"\n  Current rate: 1 SAR = ₱{current}"))
    ans = input(c("bold", "  Enter new rate (e.g. 14.85): ")).strip()
    if not ans.replace(".", "").isdigit():
        print(c("yellow", "  Rate unchanged."))
        return
    new_rate = float(ans)
    data["income_config"]["sar_to_php"] = new_rate
    save(data)
    print(c("green", f"  Rate updated → 1 SAR = ₱{new_rate}"))
    monthly = (data["income_config"]["monthly_sar"] - data["income_config"]["expenses_sar"]) * new_rate
    print(c("cyan",  f"  New monthly budget (after expenses): ₱{monthly:,.2f}\n"))

def cmd_remit(data, sar_amount):
    cfg      = data.get("income_config", {})
    rate     = cfg.get("sar_to_php", 15.0)
    php      = sar_amount * rate
    standard = (cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0) - cfg.get("phone", {}).get("monthly_sar", 0)) * rate

    print(c("bold", f"\n{'='*55}"))
    print(c("bold", f"  REMITTANCE PLAN"))
    print(c("bold", f"{'='*55}"))
    print(f"  Sending:       {sar_amount:,.0f} SAR")
    print(f"  Rate:          1 SAR = ₱{rate}")
    print(c("green", f"  PHP received:  ₱{php:,.2f}"))
    if php > standard:
        print(c("cyan", f"  Extra vs plan: +₱{php - standard:,.2f} ← throw at attack card"))
    elif php < standard:
        print(c("yellow", f"  Short vs plan: -₱{standard - php:,.2f} ← may not cover all minimums"))
    print()
    cmd_budget(data, php)

def cmd_setkey(key):
    env_file = Path(__file__).parent / ".env"
    env_file.write_text(f"OPENAI_API_KEY={key.strip()}\n")
    print(c("green", f"  API key saved to {env_file}"))
    print(c("cyan",  "  Run: python3 tracker.py analyze"))

def cmd_analyze(data):
    import os, json as _json
    _load_env()
    try:
        from openai import OpenAI
    except ImportError:
        print(c("red", "  OpenAI not installed. Run: pip install openai"))
        return

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print(c("red",  "  No API key. Run:"))
        print(c("cyan", "  python3 tracker.py setkey sk-your-key-here"))
        return

    client = OpenAI(api_key=api_key)
    latest = latest_month(data)
    entries = data["months"][latest]

    summary = []
    for name, e in entries.items():
        bal  = e.get("balance", 0) or 0
        mn   = e.get("min_due", 0) or 0
        apr  = data["debts"].get(name, {}).get("apr_monthly_pct", 0.0)
        dtype = data["debts"].get(name, {}).get("type", "credit_card")
        if bal > 0:
            summary.append({"name": name, "balance": bal, "min_due": mn,
                             "apr_monthly_pct": apr, "type": dtype})

    cfg = data.get("income_config", {})
    context = {
        "month": latest,
        "debts": summary,
        "monthly_budget_php": (cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)) * cfg.get("sar_to_php", 15),
        "total_debt": sum(d["balance"] for d in summary),
        "total_monthly_interest": sum(d["balance"] * d["apr_monthly_pct"] / 100 for d in summary if d["type"] == "credit_card"),
    }

    print(c("cyan", "\n  Asking AI to analyze your debt situation...\n"))

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "You are a personal finance advisor specializing in debt payoff for Filipino OFWs. "
                "Be direct and specific. Give concrete numbers. No fluff. "
                "Highlight risks, quick wins, and one key action for this month."
            )},
            {"role": "user", "content": (
                f"Here is my current debt situation for {latest}:\n\n"
                f"{_json.dumps(context, indent=2)}\n\n"
                "Give me: 1) Key observations (3 bullets), "
                "2) Biggest risk right now, "
                "3) One specific action I must do this month, "
                "4) Projected savings if I follow the avalanche plan."
            )}
        ],
        max_tokens=600
    )

    print(c("bold", "  ── AI Analysis ─────────────────────────────────────\n"))
    print(resp.choices[0].message.content)
    print(c("bold", "\n  ─────────────────────────────────────────────────────\n"))

# ---------------------------------------------------------------------------
# HISTORY
# ---------------------------------------------------------------------------
def cmd_history(data):
    print(c("bold", f"\n{'='*55}"))
    print(c("bold", f"  DEBT HISTORY — Total Balance Trend"))
    print(c("bold", f"{'='*55}"))

    months = sorted(data["months"].keys())
    prev_total = None

    for month in months:
        entries = data["months"][month]
        total = sum((e.get("balance", 0) or 0) for e in entries.values())
        change = ""
        if prev_total is not None:
            diff = total - prev_total
            change = c("green", f"  ↓ {fp(abs(diff))}") if diff < 0 else c("red", f"  ↑ {fp(diff)}")
        bar_len = int(total / 10000)
        bar = "█" * min(bar_len, 40)
        print(f"  {month}  {fp(total):>15}  {c('cyan', bar)}{change}")
        prev_total = total

    print(c("bold", f"{'='*55}\n"))

# ---------------------------------------------------------------------------
# PLAN  — full month-by-month projection
# ---------------------------------------------------------------------------
def month_add(ym, n):
    """Add n months to 'YYYY-MM' string."""
    y, m = int(ym[:4]), int(ym[5:])
    m += n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y}-{m:02d}"

def month_diff(ym_a, ym_b):
    """ym_b - ym_a in months."""
    ya, ma = int(ym_a[:4]), int(ym_a[5:])
    yb, mb = int(ym_b[:4]), int(ym_b[5:])
    return (yb - ya) * 12 + (mb - ma)

def cmd_plan(data, strategy="avalanche"):
    cfg        = data.get("income_config", {})
    fixed_pmts = data.get("fixed_payments", {})
    sar_php    = cfg.get("sar_to_php", 15.0)
    plan_start = cfg.get("plan_start", "2026-07")
    phone_ends = cfg.get("phone", {}).get("ends", "2026-07")
    phone_sar  = cfg.get("phone", {}).get("monthly_sar", 0)
    base_sar   = cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)

    latest = latest_month(data)
    entries = data["months"][latest]

    # --- build starting balances (project latest → plan_start at minimums) ---
    balances = {}
    for name, entry in entries.items():
        balances[name] = entry.get("balance", 0) or 0

    gap = month_diff(latest, plan_start)
    for _ in range(gap):
        for name, entry in entries.items():
            bal  = balances[name]
            mn   = entry.get("min_due", 0) or 0
            dtype = data["debts"].get(name, {}).get("type", "credit_card")
            apr  = data["debts"].get(name, {}).get("apr_monthly_pct", 0.0)
            if bal <= 0:
                continue
            if dtype == "credit_card":
                bal = bal * (1 + apr / 100) - mn
            else:
                bal = bal - mn
            balances[name] = max(0, bal)

    # Remove zero / done debts
    balances = {k: v for k, v in balances.items() if v > 0}

    # Credit cards only for extra attack; loans/personal are fixed
    cc_names = [n for n in balances if data["debts"].get(n, {}).get("type") == "credit_card"]
    fixed_names = [n for n in balances if n in fixed_pmts]

    print(c("bold", f"\n{'='*72}"))
    print(c("bold", f"  PAYOFF PLAN — {strategy.upper()} | Starting {plan_start}"))
    print(c("bold", f"  SAR→PHP rate: {sar_php:.1f}  |  Strategy: {strategy}"))
    print(c("bold", f"{'='*72}"))

    # Print starting balances
    print(c("cyan", f"\n  Estimated balances at {plan_start}:"))
    total_start = sum(balances.values())
    for name, bal in sorted(balances.items(), key=lambda x: -x[1]):
        tag = c("dim", "(fixed)") if name in fixed_pmts else ""
        print(f"    {name:<30} {fp(bal):>14}  {tag}")
    print(f"    {'─'*46}")
    print(f"    {'TOTAL':<30} {c('red', fp(total_start)):>14}")

    # --- simulate month by month ---
    sim     = dict(balances)
    payoffs = {}
    month   = plan_start
    history = []
    MAX_MONTHS = 120

    for i in range(MAX_MONTHS):
        if all(v <= 0 for v in sim.values()):
            break

        # Monthly PHP budget
        phone_active = month <= phone_ends
        avail_sar    = base_sar - (phone_sar if phone_active else 0)
        budget_php   = avail_sar * sar_php

        # Fixed payments first
        allocations = {}
        remaining   = budget_php

        for name in list(sim):
            if sim[name] <= 0:
                continue
            if name in fixed_pmts:
                fp_cfg    = fixed_pmts[name]
                threshold = fp_cfg.get("reduced_threshold", 0)
                rate      = fp_cfg.get("reduced_monthly", fp_cfg["monthly"]) if (threshold and sim[name] <= threshold) else fp_cfg["monthly"]
                pay = min(rate, sim[name], remaining)
                allocations[name] = pay
                remaining -= pay

        # Minimums on CCs
        active_ccs = [(n, sim[n]) for n in cc_names if sim[n] > 0]
        for name, bal in active_ccs:
            mn  = entries.get(name, {}).get("min_due", 0) or 0
            pay = min(mn, bal, remaining)
            allocations[name] = allocations.get(name, 0) + pay
            remaining -= pay

        # Extra → top CC by strategy
        active_ccs_data = []
        for name, bal in active_ccs:
            apr      = data["debts"].get(name, {}).get("apr_monthly_pct", 2.0)
            interest = bal * apr / 100
            active_ccs_data.append((name, bal, interest))

        if strategy == "avalanche":
            active_ccs_data.sort(key=lambda x: -x[2])
        else:
            active_ccs_data.sort(key=lambda x: x[1])

        if remaining > 0 and active_ccs_data:
            target = active_ccs_data[0][0]
            allocations[target] = allocations.get(target, 0) + remaining
            remaining = 0

        # Apply payments + interest
        month_payoffs = []
        for name in list(sim):
            if sim[name] <= 0:
                continue
            bal   = sim[name]
            dtype = data["debts"].get(name, {}).get("type", "credit_card")
            apr   = data["debts"].get(name, {}).get("apr_monthly_pct", 0.0)
            pay   = allocations.get(name, 0)

            if dtype == "credit_card":
                new_bal = bal * (1 + apr / 100) - pay
            else:
                new_bal = bal - pay

            sim[name] = max(0, new_bal)
            if sim[name] == 0 and name not in payoffs:
                payoffs[name] = month
                month_payoffs.append(name)

        total_bal = sum(sim.values())
        history.append({
            "month": month, "budget": budget_php, "allocations": dict(allocations),
            "balances": dict(sim), "total": total_bal, "payoffs": month_payoffs
        })
        month = month_add(month, 1)

    # --- print plan ---
    print(c("cyan", f"\n  {'Month':<10} {'Budget':>12}  {'Target CC':<28} {'Extra':>10}  {'Total Debt':>14}  Event"))
    print(f"  {'-'*10} {'-'*12}  {'-'*28} {'-'*10}  {'-'*14}  {'-'*20}")

    for row in history:
        # Find which CC got extra
        extra_cc, extra_amt = "", 0
        for name in cc_names:
            mn = entries.get(name, {}).get("min_due", 0) or 0
            alloc = row["allocations"].get(name, 0)
            if alloc > mn + 1:
                extra_cc  = name.split("(")[0].strip()[:27]
                extra_amt = alloc - mn

        events = ""
        if row["payoffs"]:
            events = c("green", "✓ " + ", ".join(n.split("(")[0].strip() for n in row["payoffs"]))

        total_str = fp(row["total"])
        if row["total"] < total_start * 0.5:
            total_str = c("green", total_str)
        elif row["total"] < total_start * 0.75:
            total_str = c("yellow", total_str)
        else:
            total_str = c("red", total_str)

        extra_str = fp(extra_amt) if extra_amt > 0 else c("dim", "—")
        print(f"  {row['month']:<10} {fp(row['budget']):>12}  {extra_cc:<28} {extra_str:>10}  {total_str:>22}  {events}")

    # --- summary ---
    print(c("bold", f"\n{'='*72}"))
    print(c("bold", "  PAYOFF SUMMARY"))
    print(c("bold", f"{'='*72}"))
    for name, when in sorted(payoffs.items(), key=lambda x: x[1]):
        months_took = month_diff(plan_start, when) + 1
        print(f"  {name:<32} paid off {c('green', when)}  ({months_took} months from start)")

    if not all(v <= 0 for v in sim.values()):
        remaining_debts = {k: v for k, v in sim.items() if v > 0}
        print(c("yellow", f"\n  Still remaining after {MAX_MONTHS} months:"))
        for name, bal in remaining_debts.items():
            print(f"    {name:<32} {fp(bal)}")
    else:
        last_month = history[-1]["month"] if history else "?"
        total_months = month_diff(plan_start, last_month) + 1
        print(c("green", f"\n  ALL DEBTS CLEARED by {last_month}  ({total_months} months / {total_months//12}y {total_months%12}m)"))

    total_interest = sum(
        row["budget"] - sum(
            data["debts"].get(n, {}).get("apr_monthly_pct", 0) / 100 * row["balances"].get(n, 0)
            for n in cc_names
        )
        for row in history
    )
    print(c("bold", f"{'='*72}\n"))


# ---------------------------------------------------------------------------
# HELP
# ---------------------------------------------------------------------------
def cmd_help():
    print(c("bold", """
  Debt Tracker — Commands
  -----------------------
  python tracker.py                    → summary (latest month)
  python tracker.py summary            → summary (latest month)
  python tracker.py summary 2026-03    → specific month
  python tracker.py strategy           → snowball (default)
  python tracker.py strategy snowball  → lowest balance first
  python tracker.py strategy avalanche → highest interest first
  python tracker.py plan               → full payoff timeline (avalanche)
  python tracker.py plan snowball      → full payoff timeline (snowball)
  python tracker.py budget 50000       → allocate ₱50k/month
  python tracker.py add                → add new month (25th workflow)
  python tracker.py history            → balance trend
  python tracker.py help               → this help

  APR rates set in debts.json (apr_monthly_pct per debt).
  PH BSP cap = 2% monthly for credit cards.
"""))

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    data = load()
    args = sys.argv[1:]

    if not args:
        cmd_summary(data)
    elif args[0] == "summary":
        cmd_summary(data, args[1] if len(args) > 1 else None)
    elif args[0] == "strategy":
        cmd_strategy(data, args[1] if len(args) > 1 else "snowball")
    elif args[0] == "plan":
        cmd_plan(data, args[1] if len(args) > 1 else "avalanche")
    elif args[0] == "export":
        cmd_export(data)
    elif args[0] == "analyze":
        cmd_analyze(data)
    elif args[0] == "setrate":
        cmd_setrate(data)
    elif args[0] == "remit":
        if len(args) < 2:
            print(c("red", "Usage: python3 tracker.py remit <sar_amount>"))
        else:
            cmd_remit(data, float(args[1].replace(",", "")))
    elif args[0] == "setkey":
        if len(args) < 2:
            print(c("red", "Usage: python3 tracker.py setkey sk-your-key-here"))
        else:
            cmd_setkey(args[1])
    elif args[0] == "export":
        cmd_export(data)
    elif args[0] == "budget":
        if len(args) < 2:
            print(c("red", "Usage: python tracker.py budget <amount>"))
        else:
            cmd_budget(data, float(args[1].replace(",", "")))
    elif args[0] == "add":
        cmd_add(data)
    elif args[0] == "history":
        cmd_history(data)
    elif args[0] == "help":
        cmd_help()
    else:
        print(c("red", f"Unknown command: {args[0]}"))
        cmd_help()

if __name__ == "__main__":
    main()
