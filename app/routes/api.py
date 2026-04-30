from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.base import get_db
from ..db.crud import get_ai_cache, get_ai_daily_count, set_ai_cache
from ..dependencies import NotAuthenticated, get_current_user
from ..services.ai import compute_hash, get_analysis

router = APIRouter(prefix="/api")


@router.get("/healthz")
async def healthz(db: AsyncSession = Depends(get_db)):
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        return {"status": "ok"}
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
        "error": "No OpenAI key set. <a href='/settings' style='color:#3b82f6'>Add key in Settings →</a>"
    })
