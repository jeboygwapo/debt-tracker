from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import hash_password, settings
from ..db.base import get_db
from ..db.crud import create_user, get_user_by_username
from ..templating import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {
        "error": None,
        "allow_registration": settings.allow_registration,
    })


@router.post("/login")
async def login_post(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))

    user = await get_user_by_username(db, username)
    if user and user.password_hash == hash_password(password):
        request.session["user_id"] = user.id
        request.session["username"] = user.username
        request.session["is_admin"] = user.is_admin
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        request, "login.html",
        {"error": "Invalid username or password.", "allow_registration": settings.allow_registration},
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    if not settings.allow_registration:
        return RedirectResponse("/login", status_code=302)
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "register.html", {"error": None})


@router.post("/register")
async def register_post(request: Request, db: AsyncSession = Depends(get_db)):
    if not settings.allow_registration:
        return RedirectResponse("/login", status_code=302)

    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    confirm = str(form.get("confirm_password", ""))

    def err(msg):
        return templates.TemplateResponse(
            request, "register.html", {"error": msg}, status_code=400
        )

    if not username:
        return err("Username is required.")
    if len(username) < 3:
        return err("Username must be at least 3 characters.")
    if len(password) < 12:
        return err("Password must be at least 12 characters.")
    if password != confirm:
        return err("Passwords do not match.")

    existing = await get_user_by_username(db, username)
    if existing:
        return err("Username already taken.")

    user = await create_user(db, username=username, password=password, is_admin=False)
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["is_admin"] = user.is_admin
    return RedirectResponse("/debts", status_code=303)
