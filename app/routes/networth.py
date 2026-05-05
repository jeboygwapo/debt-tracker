import re
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings, load_env_file
from ..csrf import validate_csrf
from ..db.base import get_db
from ..db.crud import (
    create_account,
    delete_account,
    delete_snapshot,
    get_account_by_id,
    get_accounts,
    get_ai_parse_count,
    get_all_entries,
    get_all_snapshots,
    get_debts,
    get_snapshot_by_id,
    increment_ai_parse_count,
    reorder_accounts,
    snapshot_hash_exists,
    update_account,
    update_income_config,
    upsert_snapshot,
)
from ..dependencies import NotAuthenticated, get_current_user
from ..templating import templates

router = APIRouter(prefix="/networth")

NAME_MAX_LEN = 100
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
ACCOUNT_TYPES = ("bank", "investment", "property", "other")
AI_PARSE_DAILY_LIMIT = 5


def _redirect_login():
    return RedirectResponse("/welcome", status_code=302)


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


def _current_month() -> str:
    today = date.today()
    return f"{today.year}-{today.month:02d}"


def _net_worth_summary(accounts: list, snapshots: list, debt_entries: dict) -> dict:
    """Compute assets, liabilities, net worth, and monthly trend."""
    # Latest snapshot balance per account
    latest_per_account: dict[int, float] = {}
    for snap in sorted(snapshots, key=lambda s: s.month):
        latest_per_account[snap.account_id] = snap.balance

    total_assets = sum(latest_per_account.get(a.id, 0.0) for a in accounts)

    # Latest debt balances from monthly entries
    total_liabilities = sum(
        e.get("balance", 0) or 0
        for month_data in debt_entries.values()
        for e in month_data.values()
    ) if debt_entries else 0.0

    # Get the most recent month's debt total only
    if debt_entries:
        latest_month = max(debt_entries.keys())
        total_liabilities = sum(
            e.get("balance", 0) or 0
            for e in debt_entries[latest_month].values()
        )

    net_worth = total_assets - total_liabilities

    # Monthly trend: aggregate all snapshot balances per month
    month_assets: dict[str, float] = defaultdict(float)
    for snap in snapshots:
        month_assets[snap.month] += snap.balance
    trend_months = sorted(month_assets.keys())
    trend_values = [round(month_assets[m], 2) for m in trend_months]

    return {
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_liabilities, 2),
        "net_worth": round(net_worth, 2),
        "trend_months": trend_months,
        "trend_values": trend_values,
        "latest_per_account": latest_per_account,
    }


def _account_rows(accounts: list, snapshots: list) -> list[dict]:
    """Build display rows: account + latest balance + recent history."""
    snap_by_account: dict[int, list] = defaultdict(list)
    for snap in sorted(snapshots, key=lambda s: s.month, reverse=True):
        snap_by_account[snap.account_id].append(snap)

    rows = []
    for acc in accounts:
        snaps = snap_by_account.get(acc.id, [])
        latest_snap = snaps[0] if snaps else None
        rows.append({
            "account": acc,
            "latest_snap": latest_snap,
            "latest_balance": latest_snap.balance if latest_snap else None,
            "latest_month": latest_snap.month if latest_snap else None,
            "history": snaps[:6],
        })
    return rows


@router.get("", response_class=HTMLResponse)
async def networth_get(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    accounts = await get_accounts(db, user.id)
    snapshots = await get_all_snapshots(db, user.id)
    debts = await get_debts(db, user.id)
    entries = await get_all_entries(db, user.id)

    # Build debt months dict (simplified — just latest month)
    from ..db.adapter import build_months_dict
    months_dict = build_months_dict(entries, debts)

    summary = _net_worth_summary(accounts, snapshots, months_dict)
    rows = _account_rows(accounts, snapshots)

    load_env_file(settings.env_file)
    parse_count = await get_ai_parse_count(db, user)

    return templates.TemplateResponse(request, "networth.html", {
        "active": "networth",
        "accounts": accounts,
        "rows": rows,
        "summary": summary,
        "account_types": ACCOUNT_TYPES,
        "parse_count": parse_count,
        "parse_limit": AI_PARSE_DAILY_LIMIT,
        "has_ai": bool(settings.openai_api_key),
        "current_month": _current_month(),
        "msg": request.query_params.get("msg"),
    })


@router.get("/accounts/{account_id}/edit", response_class=HTMLResponse)
async def account_edit_get(request: Request, account_id: int, db: AsyncSession = Depends(get_db)):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    account = await get_account_by_id(db, account_id, user.id)
    if not account:
        return RedirectResponse("/networth?msg=Account+not+found.", status_code=303)

    snapshots = sorted(account.snapshots, key=lambda s: s.month, reverse=True)
    return templates.TemplateResponse(request, "edit_account.html", {
        "active": "networth",
        "account": account,
        "snapshots": snapshots,
        "account_types": ACCOUNT_TYPES,
        "current_month": _current_month(),
        "msg": request.query_params.get("msg"),
    })


@router.post("")
async def networth_post(
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

    if action == "add_account":
        return await _handle_add_account(db, user, form)
    if action == "update_account":
        return await _handle_update_account(db, user, form)
    if action == "delete_account":
        return await _handle_delete_account(db, user, form)
    if action == "add_snapshot":
        return await _handle_add_snapshot(db, user, form)
    if action == "delete_snapshot":
        return await _handle_delete_snapshot(db, user, form)
    if action == "confirm_parse":
        return await _handle_confirm_parse(db, user, form)
    if action == "reorder":
        return await _handle_reorder(db, user, form)

    return RedirectResponse("/networth", status_code=303)


@router.post("/parse")
async def networth_parse(
    request: Request,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    csrf_token: str = Form(...),
):
    """Parse a bank statement image/PDF via AI. Returns JSON preview."""
    import secrets
    expected = request.session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(csrf_token, expected):
        return JSONResponse({"error": "Invalid CSRF token."}, status_code=403)

    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    load_env_file(settings.env_file)
    if not settings.openai_api_key:
        return JSONResponse({"error": "OpenAI API key not configured."}, status_code=422)

    if not user.is_admin:
        count = await get_ai_parse_count(db, user)
        if count >= AI_PARSE_DAILY_LIMIT:
            return JSONResponse(
                {"error": f"Daily parse limit reached ({AI_PARSE_DAILY_LIMIT}/day). Try again tomorrow."},
                status_code=429,
            )

    content = await file.read()
    content_type = file.content_type or ""

    from ..services.statement_parser import ParseError, parse_statement
    try:
        result = await parse_statement(content, content_type, settings.openai_api_key)
    except ParseError as e:
        return JSONResponse({"error": str(e)}, status_code=422)

    # Dedup check
    if await snapshot_hash_exists(db, user.id, result["hash"]):
        return JSONResponse({"error": "This statement has already been imported."}, status_code=409)

    if not user.is_admin:
        await increment_ai_parse_count(db, user)

    return JSONResponse({"ok": True, "result": result})


async def _handle_add_account(db, user, form) -> RedirectResponse:
    name = str(form.get("name", "")).strip()
    if not name or len(name) > NAME_MAX_LEN:
        return RedirectResponse("/networth?msg=Invalid+account+name.", status_code=303)

    acc_type = str(form.get("type", "bank")).strip()
    if acc_type not in ACCOUNT_TYPES:
        acc_type = "bank"

    existing = await get_accounts(db, user.id)
    sort_order = max((a.sort_order for a in existing), default=-1) + 1

    await create_account(db, user_id=user.id, name=name, type=acc_type, sort_order=sort_order)
    return RedirectResponse("/networth?msg=Account+added.", status_code=303)


async def _handle_update_account(db, user, form) -> RedirectResponse:
    try:
        account_id = int(str(form.get("id", "0")))
    except ValueError:
        return RedirectResponse("/networth?msg=Invalid+account+id.", status_code=303)

    account = await get_account_by_id(db, account_id, user.id)
    if not account:
        return RedirectResponse("/networth?msg=Account+not+found.", status_code=303)

    name = str(form.get("name", "")).strip()
    if not name or len(name) > NAME_MAX_LEN:
        return RedirectResponse(f"/networth/accounts/{account_id}/edit?msg=Invalid+account+name.", status_code=303)

    acc_type = str(form.get("type", "bank")).strip()
    if acc_type not in ACCOUNT_TYPES:
        acc_type = account.type

    await update_account(db, account, name=name, type=acc_type)
    return RedirectResponse("/networth?msg=Account+updated.", status_code=303)


async def _handle_delete_account(db, user, form) -> RedirectResponse:
    try:
        account_id = int(str(form.get("id", "0")))
    except ValueError:
        return RedirectResponse("/networth?msg=Invalid+account+id.", status_code=303)

    deleted = await delete_account(db, account_id, user.id)
    msg = "Account+deleted." if deleted else "Account+not+found."
    return RedirectResponse(f"/networth?msg={msg}", status_code=303)


async def _handle_add_snapshot(db, user, form) -> RedirectResponse:
    try:
        account_id = int(str(form.get("account_id", "0")))
    except ValueError:
        return RedirectResponse("/networth?msg=Invalid+account+id.", status_code=303)

    account = await get_account_by_id(db, account_id, user.id)
    if not account:
        return RedirectResponse("/networth?msg=Account+not+found.", status_code=303)

    month = str(form.get("month", "")).strip()
    if not MONTH_RE.match(month):
        return RedirectResponse(
            f"/networth/accounts/{account_id}/edit?msg=Invalid+month+format.", status_code=303
        )

    balance = _parse_float(form.get("balance"), default=-1.0)
    if balance < 0:
        return RedirectResponse(
            f"/networth/accounts/{account_id}/edit?msg=Invalid+balance.", status_code=303
        )

    await upsert_snapshot(db, account_id=account_id, user_id=user.id, month=month, balance=balance)
    return RedirectResponse(
        f"/networth/accounts/{account_id}/edit?msg=Snapshot+saved.", status_code=303
    )


async def _handle_delete_snapshot(db, user, form) -> RedirectResponse:
    try:
        snapshot_id = int(str(form.get("id", "0")))
    except ValueError:
        return RedirectResponse("/networth?msg=Invalid+snapshot+id.", status_code=303)

    snap = await get_snapshot_by_id(db, snapshot_id, user.id)
    account_id = snap.account_id if snap else None

    deleted = await delete_snapshot(db, snapshot_id, user.id)
    if account_id:
        msg = "Snapshot+deleted." if deleted else "Snapshot+not+found."
        return RedirectResponse(f"/networth/accounts/{account_id}/edit?msg={msg}", status_code=303)
    return RedirectResponse("/networth?msg=Snapshot+deleted.", status_code=303)


async def _handle_confirm_parse(db, user, form) -> RedirectResponse:
    try:
        account_id = int(str(form.get("account_id", "0")))
    except ValueError:
        return RedirectResponse("/networth?msg=Invalid+account+id.", status_code=303)

    account = await get_account_by_id(db, account_id, user.id)
    if not account:
        return RedirectResponse("/networth?msg=Account+not+found.", status_code=303)

    month = str(form.get("month", "")).strip()
    if not MONTH_RE.match(month):
        return RedirectResponse("/networth?msg=Invalid+month.", status_code=303)

    balance = _parse_float(form.get("balance"), default=-1.0)
    if balance < 0:
        return RedirectResponse("/networth?msg=Invalid+balance.", status_code=303)

    statement_hash = str(form.get("statement_hash", "")).strip() or None

    await upsert_snapshot(
        db,
        account_id=account_id,
        user_id=user.id,
        month=month,
        balance=balance,
        source="ai_parsed",
        statement_hash=statement_hash,
    )
    return RedirectResponse("/networth?msg=Statement+imported.", status_code=303)


async def _handle_reorder(db, user, form) -> RedirectResponse:
    raw = str(form.get("order", "")).strip()
    try:
        ordered_ids = [int(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        return RedirectResponse("/networth?msg=Invalid+order.", status_code=303)

    if ordered_ids:
        await reorder_accounts(db, user.id, ordered_ids)
    return RedirectResponse("/networth?msg=Order+saved.", status_code=303)
