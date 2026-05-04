import re
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..csrf import validate_csrf
from ..db.adapter import build_data_dict
from ..db.base import get_db
from ..db.crud import (
    create_expense,
    delete_expense,
    get_ai_cache,
    get_all_entries,
    get_debts,
    get_expense_by_id,
    get_expenses,
    reorder_expenses,
    update_expense,
    update_income_config,
)
from ..dependencies import NotAuthenticated, get_current_user
from ..services.planner import _active_expense_sar, latest_month
from ..templating import templates

router = APIRouter(prefix="/budget")

NAME_MAX_LEN = 80
ENDS_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def _redirect_login():
    return RedirectResponse("/welcome", status_code=302)


def _redirect_self():
    return RedirectResponse("/budget", status_code=303)


def _parse_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    s = str(val).replace(",", "").strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _valid_ends(val: str | None) -> bool:
    if not val:
        return True
    return bool(ENDS_PATTERN.match(val))


def _normalize_ends(val: str | None) -> str | None:
    if not val:
        return None
    val = val.strip()
    return val or None


async def _load_budget_context(db: AsyncSession, user) -> tuple[dict, list]:
    debts = await get_debts(db, user.id)
    entries = await get_all_entries(db, user.id)
    ai_cache = await get_ai_cache(db, user.id)
    expenses = await get_expenses(db, user.id)
    data = build_data_dict(user, debts, entries, ai_cache, expenses=expenses)
    return data, expenses


@router.get("", response_class=HTMLResponse)
async def budget_get(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    data, expenses = await _load_budget_context(db, user)
    cfg = data.get("income_config", {}) or {}

    monthly_sar = float(cfg.get("monthly_sar", 0) or 0)
    expenses_sar = float(cfg.get("expenses_sar", 0) or 0)
    sar_to_php = float(cfg.get("sar_to_php", 15.0) or 0)

    latest = latest_month(data)
    target_month = latest or _current_month_str()
    active_exp_sar = _active_expense_sar(data.get("expenses", {}), target_month)
    disposable_sar = monthly_sar - expenses_sar - active_exp_sar
    disposable_php = disposable_sar * sar_to_php

    return templates.TemplateResponse(request, "budget.html", {
        "active": "budget",
        "data": data,
        "income_config": cfg,
        "expenses": expenses,
        "active_expenses_sar": active_exp_sar,
        "disposable_sar": disposable_sar,
        "disposable_php": disposable_php,
        "target_month": target_month,
        "msg": request.query_params.get("msg"),
    })


@router.get("/expenses/{expense_id}/edit", response_class=HTMLResponse)
async def expense_edit_get(
    request: Request,
    expense_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    expense = await get_expense_by_id(db, expense_id, user.id)
    if not expense:
        return RedirectResponse("/budget?msg=Expense+not+found.", status_code=303)

    return templates.TemplateResponse(request, "edit_expense.html", {
        "active": "budget",
        "expense": expense,
        "msg": request.query_params.get("msg"),
    })


@router.post("")
async def budget_post(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    form = await request.form()
    action = str(form.get("action", "")).strip()

    if action == "income":
        return await _handle_income(db, user, form)
    if action == "rate":
        return await _handle_rate(db, user, form)
    if action == "add_expense":
        return await _handle_add_expense(db, user, form)
    if action == "update_expense":
        return await _handle_update_expense(db, user, form)
    if action == "delete_expense":
        return await _handle_delete_expense(db, user, form)
    if action == "reorder":
        return await _handle_reorder(db, user, form)

    return _redirect_self()


async def _handle_income(db: AsyncSession, user, form) -> RedirectResponse:
    monthly = _parse_float(form.get("monthly_sar"), default=-1.0)
    expenses_cap = _parse_float(form.get("expenses_sar"), default=-1.0)
    if monthly < 0 or expenses_cap < 0:
        return RedirectResponse("/budget?msg=Invalid+income+values.", status_code=303)

    cfg = dict(user.income_config or {})
    cfg["monthly_sar"] = monthly
    cfg["expenses_sar"] = expenses_cap
    await update_income_config(db, user, cfg)
    return RedirectResponse("/budget?msg=Income+updated.", status_code=303)


async def _handle_rate(db: AsyncSession, user, form) -> RedirectResponse:
    rate = _parse_float(form.get("rate"), default=-1.0)
    if rate < 0:
        return RedirectResponse("/budget?msg=Invalid+rate.", status_code=303)

    cfg = dict(user.income_config or {})
    cfg["sar_to_php"] = rate
    await update_income_config(db, user, cfg)
    return RedirectResponse("/budget?msg=Rate+updated.", status_code=303)


async def _handle_add_expense(db: AsyncSession, user, form) -> RedirectResponse:
    name = str(form.get("name", "")).strip()
    if not name or len(name) > NAME_MAX_LEN:
        return RedirectResponse("/budget?msg=Invalid+expense+name.", status_code=303)

    monthly = _parse_float(form.get("monthly_sar"), default=-1.0)
    if monthly < 0:
        return RedirectResponse("/budget?msg=Invalid+monthly+amount.", status_code=303)

    ends = _normalize_ends(str(form.get("ends", "")))
    if not _valid_ends(ends):
        return RedirectResponse("/budget?msg=Invalid+end+month.", status_code=303)

    existing = await get_expenses(db, user.id)
    sort_order = max((e.sort_order for e in existing), default=-1) + 1

    await create_expense(
        db,
        user_id=user.id,
        name=name,
        monthly_sar=monthly,
        ends=ends,
        sort_order=sort_order,
    )
    return RedirectResponse("/budget?msg=Expense+added.", status_code=303)


async def _handle_update_expense(db: AsyncSession, user, form) -> RedirectResponse:
    try:
        expense_id = int(str(form.get("id", "0")))
    except ValueError:
        return RedirectResponse("/budget?msg=Invalid+expense+id.", status_code=303)

    expense = await get_expense_by_id(db, expense_id, user.id)
    if not expense:
        return RedirectResponse("/budget?msg=Expense+not+found.", status_code=303)

    name = str(form.get("name", "")).strip()
    if not name or len(name) > NAME_MAX_LEN:
        return RedirectResponse("/budget?msg=Invalid+expense+name.", status_code=303)

    monthly = _parse_float(form.get("monthly_sar"), default=-1.0)
    if monthly < 0:
        return RedirectResponse("/budget?msg=Invalid+monthly+amount.", status_code=303)

    ends = _normalize_ends(str(form.get("ends", "")))
    if not _valid_ends(ends):
        return RedirectResponse("/budget?msg=Invalid+end+month.", status_code=303)

    await update_expense(db, expense, name=name, monthly_sar=monthly, ends=ends)
    return RedirectResponse("/budget?msg=Expense+updated.", status_code=303)


async def _handle_delete_expense(db: AsyncSession, user, form) -> RedirectResponse:
    try:
        expense_id = int(str(form.get("id", "0")))
    except ValueError:
        return RedirectResponse("/budget?msg=Invalid+expense+id.", status_code=303)

    deleted = await delete_expense(db, expense_id, user.id)
    msg = "Expense+deleted." if deleted else "Expense+not+found."
    return RedirectResponse(f"/budget?msg={msg}", status_code=303)


async def _handle_reorder(db: AsyncSession, user, form) -> RedirectResponse:
    raw = str(form.get("order", "")).strip()
    try:
        ordered_ids = [int(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        return RedirectResponse("/budget?msg=Invalid+order.", status_code=303)

    if ordered_ids:
        await reorder_expenses(db, user.id, ordered_ids)
    return RedirectResponse("/budget?msg=Order+saved.", status_code=303)


def _current_month_str() -> str:
    today = date.today()
    return f"{today.year}-{today.month:02d}"
