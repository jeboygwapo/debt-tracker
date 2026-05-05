import re
from datetime import date
from math import ceil

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..csrf import validate_csrf
from ..db.base import get_db
from ..db.crud import (
    create_goal,
    delete_goal,
    get_goal_by_id,
    get_goals,
    reorder_goals,
    update_goal,
)
from ..dependencies import NotAuthenticated, get_current_user
from ..templating import templates

router = APIRouter(prefix="/goals")

NAME_MAX_LEN = 100
ENDS_PATTERN = re.compile(r"^\d{4}-\d{2}$")


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


def _valid_date(val: str | None) -> bool:
    if not val:
        return True
    return bool(ENDS_PATTERN.match(val))


def _normalize_date(val: str | None) -> str | None:
    if not val:
        return None
    return val.strip() or None


def _goal_progress(goal) -> dict:
    pct = min(100.0, (goal.current_php / goal.target_php * 100) if goal.target_php > 0 else 0.0)
    remaining = max(0.0, goal.target_php - goal.current_php)
    months_left = None
    on_track = None

    today = date.today()

    if goal.target_date:
        try:
            yr, mo = int(goal.target_date[:4]), int(goal.target_date[5:7])
            months_remaining = max(0, (yr - today.year) * 12 + (mo - today.month))
        except (ValueError, IndexError):
            months_remaining = None

        if months_remaining is not None:
            months_left = months_remaining
            if goal.monthly_alloc_php > 0 and remaining > 0:
                needed = ceil(remaining / goal.monthly_alloc_php)
                on_track = needed <= months_remaining
            elif remaining <= 0:
                on_track = True
    elif goal.monthly_alloc_php > 0 and remaining > 0:
        months_left = ceil(remaining / goal.monthly_alloc_php)

    return {
        "pct": round(pct, 1),
        "remaining": remaining,
        "months_left": months_left,
        "on_track": on_track,
        "done": goal.current_php >= goal.target_php and goal.target_php > 0,
    }


@router.get("", response_class=HTMLResponse)
async def goals_get(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    goals = await get_goals(db, user.id)
    progress = {g.id: _goal_progress(g) for g in goals}

    return templates.TemplateResponse(request, "goals.html", {
        "active": "goals",
        "goals": goals,
        "progress": progress,
        "msg": request.query_params.get("msg"),
    })


@router.get("/{goal_id}/edit", response_class=HTMLResponse)
async def goal_edit_get(request: Request, goal_id: int, db: AsyncSession = Depends(get_db)):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    goal = await get_goal_by_id(db, goal_id, user.id)
    if not goal:
        return RedirectResponse("/goals?msg=Goal+not+found.", status_code=303)

    return templates.TemplateResponse(request, "edit_goal.html", {
        "active": "goals",
        "goal": goal,
        "msg": request.query_params.get("msg"),
    })


@router.post("")
async def goals_post(
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

    if action == "add_goal":
        return await _handle_add(db, user, form)
    if action == "update_goal":
        return await _handle_update(db, user, form)
    if action == "delete_goal":
        return await _handle_delete(db, user, form)
    if action == "deposit":
        return await _handle_deposit(db, user, form)
    if action == "reorder":
        return await _handle_reorder(db, user, form)

    return RedirectResponse("/goals", status_code=303)


async def _handle_add(db, user, form) -> RedirectResponse:
    name = str(form.get("name", "")).strip()
    if not name or len(name) > NAME_MAX_LEN:
        return RedirectResponse("/goals?msg=Invalid+goal+name.", status_code=303)

    target = _parse_float(form.get("target_php"), default=-1.0)
    if target < 0:
        return RedirectResponse("/goals?msg=Invalid+target+amount.", status_code=303)

    current = _parse_float(form.get("current_php"), default=0.0)
    if current < 0:
        return RedirectResponse("/goals?msg=Invalid+current+amount.", status_code=303)

    monthly = _parse_float(form.get("monthly_alloc_php"), default=0.0)
    if monthly < 0:
        return RedirectResponse("/goals?msg=Invalid+monthly+allocation.", status_code=303)

    target_date = _normalize_date(str(form.get("target_date", "")))
    if not _valid_date(target_date):
        return RedirectResponse("/goals?msg=Invalid+target+date.", status_code=303)

    existing = await get_goals(db, user.id)
    sort_order = max((g.sort_order for g in existing), default=-1) + 1

    await create_goal(
        db,
        user_id=user.id,
        name=name,
        target_php=target,
        current_php=current,
        monthly_alloc_php=monthly,
        target_date=target_date,
        sort_order=sort_order,
    )
    return RedirectResponse("/goals?msg=Goal+added.", status_code=303)


async def _handle_update(db, user, form) -> RedirectResponse:
    try:
        goal_id = int(str(form.get("id", "0")))
    except ValueError:
        return RedirectResponse("/goals?msg=Invalid+goal+id.", status_code=303)

    goal = await get_goal_by_id(db, goal_id, user.id)
    if not goal:
        return RedirectResponse("/goals?msg=Goal+not+found.", status_code=303)

    name = str(form.get("name", "")).strip()
    if not name or len(name) > NAME_MAX_LEN:
        return RedirectResponse(f"/goals/{goal_id}/edit?msg=Invalid+goal+name.", status_code=303)

    target = _parse_float(form.get("target_php"), default=-1.0)
    if target < 0:
        return RedirectResponse(f"/goals/{goal_id}/edit?msg=Invalid+target+amount.", status_code=303)

    current = _parse_float(form.get("current_php"), default=-1.0)
    if current < 0:
        return RedirectResponse(f"/goals/{goal_id}/edit?msg=Invalid+current+amount.", status_code=303)

    monthly = _parse_float(form.get("monthly_alloc_php"), default=-1.0)
    if monthly < 0:
        return RedirectResponse(f"/goals/{goal_id}/edit?msg=Invalid+monthly+allocation.", status_code=303)

    target_date = _normalize_date(str(form.get("target_date", "")))
    if not _valid_date(target_date):
        return RedirectResponse(f"/goals/{goal_id}/edit?msg=Invalid+target+date.", status_code=303)

    await update_goal(
        db, goal,
        name=name,
        target_php=target,
        current_php=current,
        monthly_alloc_php=monthly,
        target_date=target_date,
    )
    return RedirectResponse("/goals?msg=Goal+updated.", status_code=303)


async def _handle_delete(db, user, form) -> RedirectResponse:
    try:
        goal_id = int(str(form.get("id", "0")))
    except ValueError:
        return RedirectResponse("/goals?msg=Invalid+goal+id.", status_code=303)

    deleted = await delete_goal(db, goal_id, user.id)
    msg = "Goal+deleted." if deleted else "Goal+not+found."
    return RedirectResponse(f"/goals?msg={msg}", status_code=303)


async def _handle_deposit(db, user, form) -> RedirectResponse:
    try:
        goal_id = int(str(form.get("id", "0")))
    except ValueError:
        return RedirectResponse("/goals?msg=Invalid+goal+id.", status_code=303)

    goal = await get_goal_by_id(db, goal_id, user.id)
    if not goal:
        return RedirectResponse("/goals?msg=Goal+not+found.", status_code=303)

    amount = _parse_float(form.get("amount"), default=-1.0)
    if amount < 0:
        return RedirectResponse("/goals?msg=Invalid+deposit+amount.", status_code=303)

    new_current = goal.current_php + amount
    await update_goal(db, goal, current_php=new_current)
    return RedirectResponse("/goals?msg=Deposit+recorded.", status_code=303)


async def _handle_reorder(db, user, form) -> RedirectResponse:
    raw = str(form.get("order", "")).strip()
    try:
        ordered_ids = [int(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        return RedirectResponse("/goals?msg=Invalid+order.", status_code=303)

    if ordered_ids:
        await reorder_goals(db, user.id, ordered_ids)
    return RedirectResponse("/goals?msg=Order+saved.", status_code=303)
