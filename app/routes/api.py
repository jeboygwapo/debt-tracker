from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..services.ai import _compute_hash, get_analysis
from ..storage import load

router = APIRouter(prefix="/api")


@router.get("/analysis")
async def analysis(request: Request, force: str = "0"):
    if not request.session.get("logged_in"):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    data = load()
    do_force = force == "1"
    cached = not do_force and data.get("ai_cache", {}).get("data_hash") == _compute_hash(data)
    html = get_analysis(data, force=do_force)

    if html:
        return JSONResponse({"html": html, "cached": cached})
    return JSONResponse({
        "error": "No OpenAI key set. <a href='/settings' style='color:#3b82f6'>Add key in Settings →</a>"
    })
