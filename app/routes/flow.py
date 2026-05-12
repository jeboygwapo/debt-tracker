import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.adapter import build_data_dict
from ..db.base import get_db
from ..db.crud import get_ai_cache, get_ai_daily_count, get_all_entries, get_debts, get_expenses, get_goals
from ..dependencies import NotAuthenticated, get_current_user
from ..services.planner import _active_expense_sar, latest_month
from ..templating import templates

router = APIRouter()


def _current_month_str() -> str:
    from datetime import date
    today = date.today()
    return f"{today.year}-{today.month:02d}"


@router.get("/flow", response_class=HTMLResponse)
async def flow_get(request: Request, db: AsyncSession = Depends(get_db)):
    from ..config import settings

    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/welcome", status_code=302)

    debts = await get_debts(db, user.id)
    entries = await get_all_entries(db, user.id)
    ai_cache = await get_ai_cache(db, user.id)
    expenses = await get_expenses(db, user.id)
    goals = await get_goals(db, user.id)

    data = build_data_dict(user, debts, entries, ai_cache, expenses=expenses)

    cfg = data.get("income_config", {}) or {}
    ofw_mode = cfg.get("ofw_mode", True)
    rate = cfg.get("sar_to_php", 15.0) if ofw_mode else 1.0
    monthly_sar = float(cfg.get("monthly_sar", 0) or 0)
    expenses_sar = float(cfg.get("expenses_sar", 0) or 0)
    target_month = latest_month(data) or _current_month_str()
    active_exp_sar = _active_expense_sar(data.get("expenses", {}), target_month)
    income_php = (monthly_sar - expenses_sar - active_exp_sar) * rate

    latest_entries = data["months"].get(target_month, {})
    debt_items = [
        {"name": n, "balance": float(e.get("balance", 0) or 0)}
        for n, e in latest_entries.items()
        if float(e.get("balance", 0) or 0) > 0
    ]
    debt_total_php = sum(item["balance"] for item in debt_items)

    goals_total_php = sum(float(g.monthly_alloc_php or 0) for g in goals)
    surplus_php = max(0.0, income_php - debt_total_php - goals_total_php)

    nodes = [
        {"id": "income", "label": "Monthly Income"},
        {"id": "debts", "label": "Debts"},
        {"id": "goals", "label": "Goals"},
    ]
    for item in debt_items:
        nodes.append({"id": f"debt__{item['name']}", "label": item["name"]})

    goals_with_alloc = [g for g in goals if (g.monthly_alloc_php or 0) > 0]
    if goals_with_alloc:
        for g in goals_with_alloc:
            nodes.append({"id": f"goal__{g.id}", "label": g.name})
    else:
        nodes = [n for n in nodes if n["id"] != "goals"]

    if surplus_php > 0:
        nodes.append({"id": "surplus", "label": "Unallocated"})

    links = []
    if debt_total_php > 0:
        links.append({"source": "income", "target": "debts", "value": debt_total_php})
        for item in debt_items:
            links.append({
                "source": "debts",
                "target": f"debt__{item['name']}",
                "value": max(item["balance"], 0.01),
            })

    if goals_total_php > 0 and goals_with_alloc:
        links.append({"source": "income", "target": "goals", "value": goals_total_php})
        for g in goals_with_alloc:
            alloc = float(g.monthly_alloc_php or 0)
            links.append({
                "source": "goals",
                "target": f"goal__{g.id}",
                "value": alloc if alloc > 0 else 0.01,
            })

    if surplus_php > 0:
        links.append({"source": "income", "target": "surplus", "value": surplus_php})

    has_ai = bool(settings.openai_api_key)
    ai_limit = settings.ai_daily_limit
    if has_ai and not user.is_admin:
        daily_count = await get_ai_daily_count(db, user.id)
        ai_remaining = max(0, ai_limit - daily_count)
    else:
        ai_remaining = ai_limit

    return templates.TemplateResponse(request, "flow.html", {
        "request": request,
        "active": "flow",
        "income_php": income_php,
        "debt_total_php": debt_total_php,
        "goals_total_php": goals_total_php,
        "surplus_php": surplus_php,
        "ofw_mode": ofw_mode,
        "rate": rate,
        "target_month": target_month,
        "sankey_nodes": json.dumps(nodes),
        "sankey_links": json.dumps(links),
        "has_ai": has_ai,
        "ai_remaining": ai_remaining,
        "ai_limit": ai_limit,
        "has_data": bool(latest_entries),
        "goals": goals,
        "msg": request.query_params.get("msg"),
    })
