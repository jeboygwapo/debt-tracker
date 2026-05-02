from fastapi import APIRouter, Depends, Request

from ..csrf import validate_csrf
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import get_db
from ..db.crud import (
    create_notification, create_user, deactivate_notification,
    delete_user, get_all_notifications, get_all_users, get_user_by_id, update_user_password,
)
from ..dependencies import NotAuthenticated, get_current_user
from ..templating import templates

router = APIRouter(prefix="/admin")


async def _require_admin(request: Request, db: AsyncSession):
    try:
        user = await get_current_user(request, db)
    except NotAuthenticated:
        return None, RedirectResponse("/login", status_code=302)
    if not user.is_admin:
        return None, RedirectResponse("/", status_code=302)
    return user, None


@router.get("", response_class=HTMLResponse)
async def admin_index(request: Request, msg: str = None, db: AsyncSession = Depends(get_db)):
    user, redirect = await _require_admin(request, db)
    if redirect:
        return redirect

    users = await get_all_users(db)
    notifications = await get_all_notifications(db)
    return templates.TemplateResponse(request, "admin.html", {
        "active": "admin",
        "users": users,
        "notifications": notifications,
        "current_user_id": user.id,
        "msg": msg,
    })


@router.post("/users/create")
async def admin_create_user(request: Request, db: AsyncSession = Depends(get_db), _: None = Depends(validate_csrf)):
    user, redirect = await _require_admin(request, db)
    if redirect:
        return redirect

    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    is_admin = form.get("is_admin") == "1"

    if not username or len(password) < 12:
        users = await get_all_users(db)
        return templates.TemplateResponse(request, "admin.html", {
            "active": "admin",
            "users": users,
            "current_user_id": user.id,
            "msg": "Username required and password must be 12+ chars.",
            "msg_type": "error",
        })

    from ..db.crud import get_user_by_username
    if await get_user_by_username(db, username):
        users = await get_all_users(db)
        return templates.TemplateResponse(request, "admin.html", {
            "active": "admin",
            "users": users,
            "current_user_id": user.id,
            "msg": f"Username '{username}' already exists.",
            "msg_type": "error",
        })

    await create_user(db, username=username, password=password, is_admin=is_admin)
    return RedirectResponse(f"/admin?msg=User+{username}+created.", status_code=303)


@router.post("/users/{target_id}/reset-password")
async def admin_reset_password(request: Request, target_id: int, db: AsyncSession = Depends(get_db), _: None = Depends(validate_csrf)):
    user, redirect = await _require_admin(request, db)
    if redirect:
        return redirect

    target = await get_user_by_id(db, target_id)
    if not target:
        return RedirectResponse("/admin?msg=User+not+found.", status_code=303)

    form = await request.form()
    new_pw = str(form.get("password", ""))
    if len(new_pw) < 12:
        return RedirectResponse("/admin?msg=Password+must+be+12%2B+chars.", status_code=303)

    await update_user_password(db, target, new_pw)
    return RedirectResponse(f"/admin?msg=Password+reset+for+{target.username}.", status_code=303)


@router.post("/users/{target_id}/delete")
async def admin_delete_user(request: Request, target_id: int, db: AsyncSession = Depends(get_db), _: None = Depends(validate_csrf)):
    user, redirect = await _require_admin(request, db)
    if redirect:
        return redirect

    if target_id == user.id:
        return RedirectResponse("/admin?msg=Cannot+delete+yourself.", status_code=303)

    target = await get_user_by_id(db, target_id)
    if target:
        await delete_user(db, target_id)
    return RedirectResponse(f"/admin?msg=User+deleted.", status_code=303)


@router.post("/notifications/create")
async def admin_create_notification(request: Request, db: AsyncSession = Depends(get_db), _: None = Depends(validate_csrf)):
    user, redirect = await _require_admin(request, db)
    if redirect:
        return redirect

    form = await request.form()
    title = str(form.get("title", "")).strip()
    body = str(form.get("body", "")).strip()

    if not title or not body:
        return RedirectResponse("/admin?msg=Title+and+body+required.", status_code=303)

    await create_notification(db, title=title, body=body, created_by=user.id)
    return RedirectResponse("/admin?msg=Notification+sent.", status_code=303)


@router.post("/notifications/{notification_id}/deactivate")
async def admin_deactivate_notification(request: Request, notification_id: int, db: AsyncSession = Depends(get_db), _: None = Depends(validate_csrf)):
    user, redirect = await _require_admin(request, db)
    if redirect:
        return redirect

    await deactivate_notification(db, notification_id)
    return RedirectResponse("/admin?msg=Notification+deactivated.", status_code=303)
