from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import verify_password, settings
from ..csrf import validate_csrf
from ..db.base import get_db
from ..db.crud import create_user, get_user_by_username
from ..ratelimit import is_locked_out, record_failure, clear_attempts, remaining_lockout
from ..templating import templates

router = APIRouter()


@router.get("/welcome", response_class=HTMLResponse)
async def landing(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "landing.html", {})


@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=302)
    error = None
    if is_locked_out(request):
        mins = remaining_lockout(request) // 60 + 1
        error = f"Too many failed attempts. Try again in {mins} minute(s)."
    return templates.TemplateResponse(request, "login.html", {
        "error": error,
        "allow_registration": settings.allow_registration,
    })


@router.post("/login")
async def login_post(request: Request, db: AsyncSession = Depends(get_db), _: None = Depends(validate_csrf)):
    if is_locked_out(request):
        mins = remaining_lockout(request) // 60 + 1
        return templates.TemplateResponse(
            request, "login.html",
            {"error": f"Too many failed attempts. Try again in {mins} minute(s).", "allow_registration": settings.allow_registration},
            status_code=429,
        )

    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))

    user = await get_user_by_username(db, username)
    if user and verify_password(password, user.password_hash):
        clear_attempts(request)
        request.session["user_id"] = user.id
        request.session["username"] = user.username
        request.session["is_admin"] = user.is_admin
        request.session["currency_symbol"] = (user.income_config or {}).get("currency_symbol", "₱")
        request.session["income_currency"] = (user.income_config or {}).get("income_currency", "SAR")
        request.session["ofw_mode"] = (user.income_config or {}).get("ofw_mode", True)
        return RedirectResponse("/", status_code=303)

    count = record_failure(request)
    remaining = max(0, 5 - count)
    error = f"Invalid username or password. {remaining} attempt(s) remaining." if remaining > 0 else "Too many failed attempts. Locked out for 15 minutes."
    return templates.TemplateResponse(
        request, "login.html",
        {"error": error, "allow_registration": settings.allow_registration},
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
async def register_post(request: Request, db: AsyncSession = Depends(get_db), _: None = Depends(validate_csrf)):
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
    request.session["currency_symbol"] = "₱"
    request.session["income_currency"] = "SAR"
    request.session["ofw_mode"] = True
    return RedirectResponse("/debts", status_code=303)
