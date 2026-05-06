import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings, verify_password
from ..csrf import validate_csrf
from ..db.base import get_db
from ..db.crud import (
    create_user,
    get_user_by_email,
    get_user_by_username,
    get_user_by_verify_token,
    mark_user_verified,
    set_user_email,
)
from ..ratelimit import clear_attempts, is_locked_out, record_failure, remaining_lockout
from ..services.email import EmailError, send_verification_email
from ..templating import templates

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VERIFY_TOKEN_TTL_HOURS = 24
EMAIL_RESEND_COOLDOWN_SECONDS = 300  # 5 minutes


def _can_send_email(user) -> bool:
    cfg = user.income_config or {}
    sent_at_str = cfg.get("verify_email_sent_at")
    if not sent_at_str:
        return True
    try:
        sent_at = datetime.fromisoformat(sent_at_str)
        return (datetime.now(timezone.utc) - sent_at).total_seconds() >= EMAIL_RESEND_COOLDOWN_SECONDS
    except Exception:
        return True


async def _record_email_sent(db, user) -> None:
    from ..db.crud import update_income_config
    cfg = dict(user.income_config or {})
    cfg["verify_email_sent_at"] = datetime.now(timezone.utc).isoformat()
    await update_income_config(db, user, cfg)


def _session_login(request: Request, user) -> None:
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["is_admin"] = user.is_admin
    request.session["is_verified"] = user.is_verified
    cfg = user.income_config or {}
    request.session["currency_symbol"] = cfg.get("currency_symbol", "₱")
    request.session["income_currency"] = cfg.get("income_currency", "SAR")
    request.session["ofw_mode"] = cfg.get("ofw_mode", True)


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
        _session_login(request, user)

        if settings.email_verification_required and not user.is_verified:
            return RedirectResponse("/?unverified=1", status_code=303)

        return RedirectResponse("/", status_code=303)

    count = record_failure(request)
    remaining = max(0, 5 - count)
    error = (
        f"Invalid username or password. {remaining} attempt(s) remaining."
        if remaining > 0
        else "Too many failed attempts. Locked out for 15 minutes."
    )
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
    email = str(form.get("email", "")).strip().lower()

    def err(msg):
        return templates.TemplateResponse(
            request, "register.html", {"error": msg}, status_code=400
        )

    if not username or len(username) < 3:
        return err("Username must be at least 3 characters.")
    if len(password) < 12:
        return err("Password must be at least 12 characters.")
    if password != confirm:
        return err("Passwords do not match.")
    if email and not EMAIL_RE.match(email):
        return err("Invalid email address.")

    if await get_user_by_username(db, username):
        return err("Username already taken.")
    if email and await get_user_by_email(db, email):
        return err("Email already registered.")

    user = await create_user(db, username=username, password=password, is_admin=False)

    if email and settings.resend_api_key:
        token = secrets.token_urlsafe(32)
        expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=VERIFY_TOKEN_TTL_HOURS)
        await set_user_email(db, user, email, token, expiry)
        await db.refresh(user)
        try:
            base_url = str(request.base_url).rstrip("/")
            await send_verification_email(email, username, token, base_url)
            await _record_email_sent(db, user)
        except EmailError:
            pass  # don't block registration if email fails

    _session_login(request, user)
    return RedirectResponse("/debts", status_code=303)


@router.get("/verify/{token}", response_class=HTMLResponse)
async def verify_email(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_verify_token(db, token)

    if not user:
        return templates.TemplateResponse(request, "verify.html", {"status": "invalid"})

    if user.verify_token_expiry and datetime.now(timezone.utc).replace(tzinfo=None) > user.verify_token_expiry:
        return templates.TemplateResponse(request, "verify.html", {"status": "expired", "user_id": user.id})

    await mark_user_verified(db, user)

    if request.session.get("user_id") == user.id:
        request.session["is_verified"] = True

    return templates.TemplateResponse(request, "verify.html", {"status": "success"})


@router.post("/verify/resend")
async def resend_verification(request: Request, db: AsyncSession = Depends(get_db), _: None = Depends(validate_csrf)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    from ..db.crud import get_user_by_id
    user = await get_user_by_id(db, user_id)
    if not user or not user.email or user.is_verified:
        return RedirectResponse("/settings?msg=Nothing+to+resend", status_code=303)

    if not _can_send_email(user):
        return RedirectResponse("/settings?msg=Please+wait+5+minutes+before+resending", status_code=303)

    token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=VERIFY_TOKEN_TTL_HOURS)
    await set_user_email(db, user, user.email, token, expiry)
    await db.refresh(user)

    try:
        base_url = str(request.base_url).rstrip("/")
        await send_verification_email(user.email, user.username, token, base_url)
        await _record_email_sent(db, user)
        msg = "Verification+email+sent"
    except EmailError:
        msg = "Failed+to+send+email.+Check+RESEND_API_KEY"

    return RedirectResponse(f"/settings?msg={msg}", status_code=303)
