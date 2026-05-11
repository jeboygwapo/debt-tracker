import hashlib
from datetime import date as _date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.base import get_db
from ..db.crud import get_ai_cache, get_ai_daily_count, get_all_entries, get_debts, get_expenses, get_goals, get_unread_count, set_ai_cache, update_income_config
from ..dependencies import NotAuthenticated, get_current_user
from ..ratelimit import ns_is_limited, ns_record
from ..services.ai import compute_hash, get_analysis

router = APIRouter(prefix="/api")


def _flow_hash(income_php: float, debt_total: float, goals, surplus: float) -> str:
    import json as _json
    blob = _json.dumps({
        "income": round(income_php, 2),
        "debts": round(debt_total, 2),
        "surplus": round(surplus, 2),
        "goals": [
            {"id": g.id, "name": g.name, "alloc": float(g.monthly_alloc_php or 0)}
            for g in goals
        ],
    }, sort_keys=True)
    return hashlib.md5(blob.encode()).hexdigest()


@router.get("/notifications/unread")
async def notifications_unread(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return JSONResponse({"count": 0})
    count = await get_unread_count(db, user.id)
    return JSONResponse({"count": count})


@router.get("/healthz")
async def healthz(db: AsyncSession = Depends(get_db)):
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        from app.config import APP_VERSION
        return {"status": "ok", "version": APP_VERSION}
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)


@router.get("/analysis")
async def analysis(
    request: Request,
    force: str = "0",
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if ns_is_limited(request, "ai-analysis"):
        return JSONResponse({"error": "Too many requests. Please wait before retrying."}, status_code=429)
    ns_record(request, "ai-analysis")

    from .pages import _load_user_data
    data = await _load_user_data(db, user)

    do_force = force == "1"
    current_hash = compute_hash(data)
    cache = await get_ai_cache(db, user.id)
    cache_hit = not do_force and cache is not None and cache.data_hash == current_hash

    if not cache_hit and not user.is_admin:
        daily_count = await get_ai_daily_count(db, user.id)
        limit = settings.ai_daily_limit
        if daily_count >= limit:
            return JSONResponse(
                {"error": f"Daily AI limit reached ({limit} analyses/day). Try again tomorrow."},
                status_code=429,
            )

    html = await get_analysis(data, db, user.id, force=do_force)

    if html:
        return JSONResponse({"html": html, "cached": cache_hit})
    return JSONResponse({
        "error": "No OpenAI key configured.",
        "error_link": {"href": "/settings", "text": "Go to Settings →"},
    })


@router.get("/flow/suggestion")
async def flow_suggestion(request: Request, force: str = "0", db: AsyncSession = Depends(get_db)):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if ns_is_limited(request, "ai-flow"):
        return JSONResponse({"error": "Too many requests. Please wait before retrying."}, status_code=429)
    ns_record(request, "ai-flow")

    from .pages import _load_user_data
    from ..db.adapter import build_data_dict
    from ..services.planner import _active_expense_sar, latest_month

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

    from datetime import date as _dt
    def _current_month_str() -> str:
        today = _dt.today()
        return f"{today.year}-{today.month:02d}"

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

    cfg_user = dict(user.income_config or {})
    today_str = _date.today().isoformat()
    current_hash = _flow_hash(income_php, debt_total_php, goals, surplus_php)
    cache_html = cfg_user.get("flow_suggestion_html", "")
    cache_hit = (
        force != "1"
        and cfg_user.get("flow_suggestion_date", "") == today_str
        and cfg_user.get("flow_suggestion_hash", "") == current_hash
        and bool(cache_html)
    )
    if cache_hit:
        return JSONResponse({"html": cache_html, "cached": True})

    from ..config import load_env_file
    load_env_file(settings.env_file)
    if not settings.openai_api_key:
        return JSONResponse({
            "error": "No OpenAI key configured.",
            "error_link": {"href": "/settings", "text": "Go to Settings →"},
        })

    if not user.is_admin:
        daily_count = await get_ai_daily_count(db, user.id)
        limit = settings.ai_daily_limit
        if daily_count >= limit:
            return JSONResponse(
                {"error": f"Daily AI limit reached ({limit} analyses/day). Try again tomorrow."},
                status_code=429,
            )

    try:
        import json as _json
        from openai import OpenAI

        goals_context = [
            {
                "name": g.name,
                "monthly_alloc_php": float(g.monthly_alloc_php or 0),
                "target_php": float(g.target_php or 0),
                "current_php": float(g.current_php or 0),
                "target_date": g.target_date or "none",
            }
            for g in goals
        ]

        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Personal finance advisor for Filipino OFW. Be direct, specific, "
                        "use numbers. Plain text only — no HTML tags, no markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Month: {target_month}\n"
                        f"Monthly income (PHP): {round(income_php, 2)}\n"
                        f"Total debt allocation (PHP): {round(debt_total_php, 2)}\n"
                        f"Total goals allocation (PHP): {round(goals_total_php, 2)}\n"
                        f"Unallocated surplus (PHP): {round(surplus_php, 2)}\n"
                        f"Goals:\n{_json.dumps(goals_context, indent=2)}\n\n"
                        "Give: "
                        "1) Allocation summary — is income covering debts and goals? "
                        "2) Is surplus optimal? Which goal should be prioritized and why? "
                        "3) One specific action this month with exact peso amount. "
                        "4) If surplus > 0, suggest proportional top-up amounts per goal. "
                        "5) Flag if income is insufficient to cover debts + goals."
                    ),
                },
            ],
            max_tokens=600,
        )

        import html as html_lib
        import re
        raw = resp.choices[0].message.content or ""
        raw = re.sub(r"<[^>]+>", "", raw)
        safe = html_lib.escape(raw)
        formatted_html = "<br>".join(safe.splitlines())

    except Exception as e:
        return JSONResponse({"error": f"AI error: {e}"}, status_code=500)

    cfg_user["flow_suggestion_html"] = formatted_html
    cfg_user["flow_suggestion_date"] = today_str
    cfg_user["flow_suggestion_hash"] = current_hash
    await update_income_config(db, user, cfg_user)
    await set_ai_cache(db, user.id, current_hash, "")

    return JSONResponse({"html": formatted_html, "cached": False})
