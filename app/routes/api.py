from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import get_db
from ..db.crud import get_ai_cache, set_ai_cache
from ..dependencies import NotAuthenticated, get_current_user
from ..services.ai import compute_hash, get_analysis

router = APIRouter(prefix="/api")


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
    cached = not do_force and cache is not None and cache.data_hash == current_hash

    html = await get_analysis(data, db, user.id, force=do_force)

    if html:
        return JSONResponse({"html": html, "cached": cached})
    return JSONResponse({
        "error": "No OpenAI key set. <a href='/settings' style='color:#3b82f6'>Add key in Settings →</a>"
    })
