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
    clear_reset_token,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_reset_token,
    get_user_by_username,
    get_user_by_verify_token,
    mark_user_verified,
    set_reset_token,
    set_user_email,
    update_user_password,
)
from ..ratelimit import clear_attempts, is_locked_out, ns_clear, ns_is_limited, ns_record, record_failure, remaining_lockout
from ..services.email import EmailError, send_password_reset_email, send_verification_email
from ..templating import templates

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VERIFY_TOKEN_TTL_HOURS = 24
RESET_TOKEN_TTL_HOURS = 1
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
    request.session["has_email"] = bool(user.email)
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

        if settings.email_verification_required and user.email and not user.is_verified:
            return RedirectResponse("/verify-required", status_code=303)

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

    if ns_is_limited(request, "register"):
        return templates.TemplateResponse(
            request, "register.html",
            {"error": "Too many registration attempts. Please try again later."},
            status_code=429,
        )
    ns_record(request, "register")

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

    # Single normalized error to prevent username/email enumeration
    if await get_user_by_username(db, username):
        return err("That username or email is not available.")
    if email and await get_user_by_email(db, email):
        return err("That username or email is not available.")

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


@router.get("/verify-required", response_class=HTMLResponse)
async def verify_required(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    user = await get_user_by_id(db, user_id)
    if not user:
        request.session.clear()
        return RedirectResponse("/login", status_code=302)
    if not settings.email_verification_required or not user.email or user.is_verified:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        request, "verify_required.html",
        {"email": user.email, "msg": request.query_params.get("msg")},
    )


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


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_get(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/settings", status_code=302)
    return templates.TemplateResponse(request, "forgot_password.html", {"sent": False, "error": None})


@router.post("/forgot-password")
async def forgot_password_post(request: Request, db: AsyncSession = Depends(get_db), _: None = Depends(validate_csrf)):
    def _sent():
        return templates.TemplateResponse(request, "forgot_password.html", {"sent": True, "error": None})

    if ns_is_limited(request, "forgot-password"):
        return _sent()

    form = await request.form()
    identifier = str(form.get("identifier", "")).strip()

    if not identifier:
        return templates.TemplateResponse(request, "forgot_password.html", {"sent": False, "error": "Enter your username or email address."}, status_code=400)

    ns_record(request, "forgot-password")

    if EMAIL_RE.match(identifier.lower()):
        user = await get_user_by_email(db, identifier.lower())
    else:
        user = await get_user_by_username(db, identifier)

    if not user or not user.email:
        return _sent()

    token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=RESET_TOKEN_TTL_HOURS)
    await set_reset_token(db, user, token, expiry)

    try:
        base_url = str(request.base_url).rstrip("/")
        await send_password_reset_email(user.email, user.username, token, base_url)
    except EmailError:
        pass

    return _sent()


@router.get("/reset-password/{token}", response_class=HTMLResponse)
async def reset_password_get(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_reset_token(db, token)
    if not user:
        return templates.TemplateResponse(request, "reset_password.html", {"status": "invalid", "token": token})
    if user.reset_token_expiry and datetime.now(timezone.utc).replace(tzinfo=None) > user.reset_token_expiry:
        return templates.TemplateResponse(request, "reset_password.html", {"status": "expired", "token": token})
    return templates.TemplateResponse(request, "reset_password.html", {"status": "form", "token": token, "error": None})


@router.post("/reset-password/{token}")
async def reset_password_post(token: str, request: Request, db: AsyncSession = Depends(get_db), _: None = Depends(validate_csrf)):
    user = await get_user_by_reset_token(db, token)
    if not user:
        return templates.TemplateResponse(request, "reset_password.html", {"status": "invalid", "token": token})
    if user.reset_token_expiry and datetime.now(timezone.utc).replace(tzinfo=None) > user.reset_token_expiry:
        return templates.TemplateResponse(request, "reset_password.html", {"status": "expired", "token": token})

    # Rate limit applies only to form validation failures — invalid/expired token
    # branches above terminate before this point and do not consume the bucket.
    # Token entropy (256-bit) makes POST enumeration of unknown tokens infeasible.
    if ns_is_limited(request, "reset-password"):
        return templates.TemplateResponse(
            request, "reset_password.html",
            {"status": "form", "token": token, "error": "Too many attempts. Please try again later."},
            status_code=429,
        )

    form = await request.form()
    new_pw = str(form.get("password", ""))
    confirm = str(form.get("confirm_password", ""))

    def _form_err(msg):
        ns_record(request, "reset-password")
        return templates.TemplateResponse(request, "reset_password.html", {"status": "form", "token": token, "error": msg}, status_code=400)

    if len(new_pw) < 12:
        return _form_err("Password must be at least 12 characters.")
    if new_pw != confirm:
        return _form_err("Passwords do not match.")

    try:
        await update_user_password(db, user, new_pw)
        await clear_reset_token(db, user)
    except Exception:
        return templates.TemplateResponse(
            request, "reset_password.html",
            {"status": "form", "token": token, "error": "Something went wrong. Please try again."},
            status_code=500,
        )
    ns_clear(request, "reset-password")

    return templates.TemplateResponse(request, "reset_password.html", {"status": "success", "token": token})
