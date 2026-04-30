from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import get_db
from ..db.crud import create_debt, delete_debt, get_debt_by_id, get_debts, update_debt
from ..dependencies import NotAuthenticated, get_current_user
from ..templating import templates

router = APIRouter(prefix="/debts")


def _redirect_login():
    return RedirectResponse("/login", status_code=302)


@router.get("", response_class=HTMLResponse)
async def debts_list(
    request: Request,
    msg: str = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    debts = await get_debts(db, user.id)
    return templates.TemplateResponse(request, "debts.html", {
        "active": "debts",
        "debts": debts,
        "msg": msg,
    })


@router.post("", response_class=HTMLResponse)
async def debts_add(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    form = await request.form()
    name = str(form.get("name", "")).strip()
    if not name:
        debts = await get_debts(db, user.id)
        return templates.TemplateResponse(request, "debts.html", {
            "active": "debts",
            "debts": debts,
            "msg": "Name is required.",
            "msg_type": "error",
        })

    debt_type = str(form.get("type", "credit_card"))
    apr = float(str(form.get("apr_monthly_pct", "0") or "0").replace(",", ""))
    note = str(form.get("note", "")).strip() or None
    is_fixed = form.get("is_fixed") == "1"
    fixed_monthly = _float(form.get("fixed_monthly"))
    fixed_ends = str(form.get("fixed_ends", "")).strip() or None
    fixed_reduced_monthly = _float(form.get("fixed_reduced_monthly"))
    fixed_reduced_threshold = _float(form.get("fixed_reduced_threshold"))

    existing = await get_debts(db, user.id)
    sort_order = max((d.sort_order for d in existing), default=-1) + 1

    await create_debt(
        db,
        user_id=user.id,
        name=name,
        type=debt_type,
        apr_monthly_pct=apr,
        note=note,
        is_fixed=is_fixed,
        fixed_monthly=fixed_monthly,
        fixed_ends=fixed_ends,
        fixed_reduced_monthly=fixed_reduced_monthly,
        fixed_reduced_threshold=fixed_reduced_threshold,
        sort_order=sort_order,
    )
    return RedirectResponse("/debts?msg=Debt+added.", status_code=303)


@router.get("/{debt_id}/edit", response_class=HTMLResponse)
async def debt_edit_get(
    request: Request,
    debt_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    debt = await get_debt_by_id(db, debt_id, user.id)
    if not debt:
        return RedirectResponse("/debts", status_code=302)

    msg = request.query_params.get("msg")
    return templates.TemplateResponse(request, "edit_debt.html", {
        "active": "debts",
        "debt": debt,
        "msg": msg,
    })


@router.post("/{debt_id}/edit")
async def debt_edit_post(
    request: Request,
    debt_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    debt = await get_debt_by_id(db, debt_id, user.id)
    if not debt:
        return RedirectResponse("/debts", status_code=302)

    form = await request.form()
    name = str(form.get("name", "")).strip()
    if not name:
        return templates.TemplateResponse(request, "edit_debt.html", {
            "active": "debts",
            "debt": debt,
            "msg": "Name is required.",
            "msg_type": "error",
        })

    is_fixed = form.get("is_fixed") == "1"
    await update_debt(
        db,
        debt,
        name=name,
        type=str(form.get("type", "credit_card")),
        apr_monthly_pct=float(str(form.get("apr_monthly_pct", "0") or "0").replace(",", "")),
        note=str(form.get("note", "")).strip() or None,
        is_fixed=is_fixed,
        fixed_monthly=_float(form.get("fixed_monthly")) if is_fixed else None,
        fixed_ends=str(form.get("fixed_ends", "")).strip() or None,
        fixed_reduced_monthly=_float(form.get("fixed_reduced_monthly")) if is_fixed else None,
        fixed_reduced_threshold=_float(form.get("fixed_reduced_threshold")) if is_fixed else None,
    )
    return RedirectResponse(f"/debts/{debt_id}/edit?msg=Saved.", status_code=303)


@router.post("/{debt_id}/delete")
async def debt_delete(
    request: Request,
    debt_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return _redirect_login()

    debt = await get_debt_by_id(db, debt_id, user.id)
    if debt:
        await delete_debt(db, debt_id, user.id)
    return RedirectResponse("/debts?msg=Debt+deleted.", status_code=303)


def _float(val) -> float | None:
    if val is None:
        return None
    s = str(val).replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None
