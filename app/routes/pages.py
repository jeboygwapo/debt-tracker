from datetime import date
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import hash_password, save_env_value, settings
from ..services.planner import allocate_budget, compute_plan, latest_month
from ..storage import load, save
from ..templating import templates

router = APIRouter()

_PALETTE = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#3b82f6", "#8b5cf6", "#ec4899", "#14b8a6", "#f43f5e"]


def _is_logged_in(request: Request) -> bool:
    return bool(request.session.get("logged_in"))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, msg: Optional[str] = None, month: Optional[str] = None):
    if not _is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    data = load()
    latest = latest_month(data)
    viewing = month if (month and month in data["months"]) else latest
    is_latest = viewing == latest
    entries = data["months"].get(viewing, {})
    cfg = data.get("income_config", {})
    fixed_pmts = data.get("fixed_payments", {})

    sar_php = cfg.get("sar_to_php", 15.0)
    phone_ends = cfg.get("phone", {}).get("ends", "2026-07")
    phone_sar = cfg.get("phone", {}).get("monthly_sar", 0)
    base_sar = cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)
    budget_php = (base_sar - (phone_sar if viewing <= phone_ends else 0)) * sar_php

    total_now = sum((e.get("balance", 0) or 0) for e in entries.values())
    total_cc = sum(
        (e.get("balance", 0) or 0) for n, e in entries.items()
        if data["debts"].get(n, {}).get("type") == "credit_card"
    )
    monthly_interest = sum(
        (e.get("balance", 0) or 0) * data["debts"].get(n, {}).get("apr_monthly_pct", 0) / 100
        for n, e in entries.items()
        if data["debts"].get(n, {}).get("type") == "credit_card"
    )

    months_sorted = sorted(data["months"].keys())
    hist_labels = months_sorted
    hist_totals = [
        round(sum((e.get("balance", 0) or 0) for e in data["months"][m].values()), 2)
        for m in months_sorted
    ]

    plan_rows, _ = compute_plan(data)
    proj_labels = [r["month"] for r in plan_rows]
    proj_totals = [round(r["total"], 2) for r in plan_rows]
    debt_free = plan_rows[-1]["month"] if plan_rows else "—"

    donut_labels, donut_values, donut_colors = [], [], []
    for i, (name, e) in enumerate(entries.items()):
        bal = e.get("balance", 0) or 0
        if bal > 0:
            donut_labels.append(name.split("(")[0].strip())
            donut_values.append(round(bal, 2))
            donut_colors.append(_PALETTE[i % len(_PALETTE)])

    pay_alloc, cc_priority = allocate_budget(entries, data, budget_php)

    status_rows = [
        {
            "name": n,
            "balance": e.get("balance", 0) or 0,
            "min_due": e.get("min_due", 0) or 0,
            "payment": e.get("payment", 0) or 0,
            "interest": (
                (e.get("balance", 0) or 0)
                * data["debts"].get(n, {}).get("apr_monthly_pct", 0) / 100
                if data["debts"].get(n, {}).get("type") == "credit_card" else 0
            ),
            "due": e.get("due_date", "—"),
            "paid": e.get("paid_on", ""),
            "done": (e.get("balance", 0) or 0) == 0 and not e.get("min_due"),
        }
        for n, e in entries.items()
    ]

    return templates.TemplateResponse(request, "dashboard.html", {
        "active": "dashboard",
        "latest": latest,
        "viewing": viewing,
        "is_latest": is_latest,
        "months_list": sorted(data["months"].keys(), reverse=True),
        "entries": entries,
        "fixed_pmts": fixed_pmts,
        "pay_alloc": pay_alloc,
        "cc_priority": cc_priority,
        "status_rows": status_rows,
        "total_now": total_now,
        "total_cc": total_cc,
        "monthly_interest": monthly_interest,
        "debt_free": debt_free,
        "budget_php": budget_php,
        "rate": sar_php,
        "hist_labels": hist_labels,
        "hist_totals": hist_totals,
        "proj_labels": proj_labels,
        "proj_totals": proj_totals,
        "donut_labels": donut_labels,
        "donut_values": donut_values,
        "donut_colors": donut_colors,
        "msg": msg,
        "today": date.today(),
        "has_ai": bool(settings.openai_api_key),
    })


@router.get("/add", response_class=HTMLResponse)
async def add_month_get(request: Request, msg: Optional[str] = None, saved: Optional[str] = None):
    if not _is_logged_in(request):
        return RedirectResponse("/login", status_code=302)
    data = load()
    latest = latest_month(data)
    prev = data["months"].get(latest, {})

    summary = None
    if saved and saved in data["months"]:
        cfg = data.get("income_config", {})
        sar_php = cfg.get("sar_to_php", 15.0)
        phone_ends = cfg.get("phone", {}).get("ends", "2026-07")
        phone_sar = cfg.get("phone", {}).get("monthly_sar", 0)
        base_sar = cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)
        budget_php = (base_sar - (phone_sar if saved <= phone_ends else 0)) * sar_php
        saved_entries = data["months"][saved]
        pay_alloc, cc_priority = allocate_budget(saved_entries, data, budget_php)
        fixed_pmts = data.get("fixed_payments", {})
        total_due = sum(pay_alloc.values())
        summary = {
            "month": saved,
            "budget_php": budget_php,
            "total_due": total_due,
            "pay_alloc": pay_alloc,
            "cc_priority": cc_priority,
            "fixed_pmts": fixed_pmts,
            "entries": saved_entries,
        }

    return templates.TemplateResponse(request, "add_month.html", {
        "active": "add",
        "debt_names": list(data["debts"].keys()),
        "prev": prev,
        "msg": msg,
        "summary": summary,
        "today": date.today().isoformat(),
    })


@router.post("/add")
async def add_month_post(request: Request):
    if not _is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    data = load()
    debt_names = list(data["debts"].keys())
    form = await request.form()
    month = str(form.get("month", "")).strip()

    if not month:
        return templates.TemplateResponse(request, "add_month.html", {
            "active": "add",
            "debt_names": debt_names,
            "msg": "Month is required.",
        })

    entries = {}
    for i, name in enumerate(debt_names):
        prefix = f"d_{i}_"
        bal_s = str(form.get(f"{prefix}balance", "")).replace(",", "")
        mn_s = str(form.get(f"{prefix}min_due", "")).replace(",", "")
        pmt_s = str(form.get(f"{prefix}payment", "")).replace(",", "")
        due = str(form.get(f"{prefix}due_date", "")).strip()
        paid = str(form.get(f"{prefix}paid_on", "")).strip()
        note = str(form.get(f"{prefix}note", "")).strip()
        if not bal_s:
            continue
        try:
            entry: dict = {
                "balance": float(bal_s),
                "min_due": float(mn_s) if mn_s else 0,
                "payment": float(pmt_s) if pmt_s else 0,
            }
            if due:
                entry["due_date"] = due
            if paid:
                entry["paid_on"] = paid
            if note:
                entry["note"] = note
            entries[name] = entry
        except ValueError:
            continue

    data["months"][month] = entries
    save(data)
    return RedirectResponse(f"/add?saved={month}", status_code=303)


@router.get("/edit/{month}", response_class=HTMLResponse)
async def edit_month_get(request: Request, month: str):
    if not _is_logged_in(request):
        return RedirectResponse("/login", status_code=302)
    data = load()
    if month not in data["months"]:
        return RedirectResponse("/", status_code=302)
    msg = request.query_params.get("msg")
    return templates.TemplateResponse(request, "edit_month.html", {
        "active": "dashboard",
        "month": month,
        "debt_names": list(data["debts"].keys()),
        "entries": data["months"][month],
        "months_list": sorted(data["months"].keys(), reverse=True),
        "today": date.today().isoformat(),
        "msg": msg,
    })


@router.post("/edit/{month}")
async def edit_month_post(request: Request, month: str):
    if not _is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    data = load()
    debt_names = list(data["debts"].keys())
    form = await request.form()
    entries = {}

    for i, name in enumerate(debt_names):
        prefix = f"d_{i}_"
        bal_s = str(form.get(f"{prefix}balance", "")).replace(",", "")
        mn_s = str(form.get(f"{prefix}min_due", "")).replace(",", "")
        pmt_s = str(form.get(f"{prefix}payment", "")).replace(",", "")
        due = str(form.get(f"{prefix}due_date", "")).strip()
        paid = str(form.get(f"{prefix}paid_on", "")).strip()
        note = str(form.get(f"{prefix}note", "")).strip()
        if not bal_s:
            continue
        try:
            entry: dict = {
                "balance": float(bal_s),
                "min_due": float(mn_s) if mn_s else 0,
                "payment": float(pmt_s) if pmt_s else 0,
            }
            if due:
                entry["due_date"] = due
            if paid:
                entry["paid_on"] = paid
            if note:
                entry["note"] = note
            entries[name] = entry
        except ValueError:
            continue

    data["months"][month] = entries
    save(data)
    return RedirectResponse(f"/edit/{month}?msg=Saved", status_code=303)


@router.get("/remit", response_class=HTMLResponse)
async def remit_get(request: Request):
    if not _is_logged_in(request):
        return RedirectResponse("/login", status_code=302)
    data = load()
    rate = data.get("income_config", {}).get("sar_to_php", 15.0)
    return templates.TemplateResponse(request, "remit.html", {
        "active": "remit", "rate": rate, "result": None, "sar_input": "",
    })


@router.post("/remit", response_class=HTMLResponse)
async def remit_post(request: Request):
    if not _is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    data = load()
    cfg = data.get("income_config", {})
    rate = cfg.get("sar_to_php", 15.0)
    form = await request.form()
    sar_input = str(form.get("sar", ""))
    result = None

    try:
        sar_amount = float(sar_input.replace(",", ""))
        php = sar_amount * rate
        latest = latest_month(data)
        entries = data["months"].get(latest, {})
        standard = (cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)) * rate
        pay_alloc, cc_priority = allocate_budget(entries, data, php)
        result = {
            "sar": sar_amount,
            "php": php,
            "standard": standard,
            "pay_alloc": pay_alloc,
            "entries": entries,
            "cc_priority": cc_priority,
            "fixed_pmts": data.get("fixed_payments", {}),
        }
    except ValueError:
        pass

    return templates.TemplateResponse(request, "remit.html", {
        "active": "remit", "rate": rate, "result": result, "sar_input": sar_input,
    })


@router.get("/plan", response_class=HTMLResponse)
async def plan_page(request: Request, strategy: str = "avalanche"):
    if not _is_logged_in(request):
        return RedirectResponse("/login", status_code=302)
    data = load()
    rows, payoffs = compute_plan(data, strategy)
    return templates.TemplateResponse(request, "plan.html", {
        "active": "plan",
        "rows": rows,
        "payoffs": payoffs,
        "strategy": strategy,
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_get(request: Request):
    if not _is_logged_in(request):
        return RedirectResponse("/login", status_code=302)
    data = load()
    return templates.TemplateResponse(request, "settings.html", {
        "active": "settings",
        "cfg": data.get("income_config", {}),
        "msg": None,
    })


@router.post("/settings", response_class=HTMLResponse)
async def settings_post(request: Request):
    if not _is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    data = load()
    form = await request.form()
    action = str(form.get("action", ""))
    msg = None

    if action == "rate":
        try:
            new_rate = float(str(form.get("rate", "0")))
            data["income_config"]["sar_to_php"] = new_rate
            save(data)
            msg = f"Rate updated → 1 SAR = ₱{new_rate}"
        except ValueError:
            msg = "Invalid rate."
    elif action == "apikey":
        key = str(form.get("apikey", "")).strip()
        if key:
            save_env_value(settings.env_file, "OPENAI_API_KEY", key)
            msg = "API key saved."
    elif action == "password":
        current = str(form.get("current_password", ""))
        new_pw = str(form.get("new_password", ""))
        confirm = str(form.get("confirm_password", ""))
        if hash_password(current) != settings.app_password_hash:
            msg = "❌ Current password incorrect."
        elif len(new_pw) < 12:
            msg = "❌ New password must be at least 12 characters."
        elif new_pw != confirm:
            msg = "❌ Passwords do not match."
        else:
            save_env_value(settings.env_file, "APP_PASSWORD_HASH", hash_password(new_pw))
            msg = "✓ Password updated."

    return templates.TemplateResponse(request, "settings.html", {
        "active": "settings",
        "cfg": data.get("income_config", {}),
        "msg": msg,
    })
