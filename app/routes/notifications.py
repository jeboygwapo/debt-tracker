from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import get_db
from ..db.crud import get_active_notifications, get_unread_count, mark_all_read
from ..dependencies import NotAuthenticated, get_current_user
from ..templating import templates

router = APIRouter()


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/login", status_code=302)

    notifications = await get_active_notifications(db)
    await mark_all_read(db, user.id)

    return templates.TemplateResponse(request, "notifications.html", {
        "active": "notifications",
        "notifications": notifications,
    })
