import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .routes import admin as admin_routes, auth, budget as budget_routes, flow as flow_routes, goals as goals_routes, networth as networth_routes, notifications as notifications_routes, pages, api as api_routes, debts as debts_routes

_MAX_BODY_BYTES = 1 * 1024 * 1024  # 1 MB

_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, is_prod: bool = False):
        super().__init__(app)
        self._is_prod = is_prod

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _CSP
        if self._is_prod:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return PlainTextResponse("Request too large.", status_code=413)
        return await call_next(request)


class VerificationWallMiddleware(BaseHTTPMiddleware):
    """Block logged-in unverified users from protected routes when EMAIL_VERIFICATION_REQUIRED=true.

    Only triggers when:
      - settings.email_verification_required is True
      - User has session (user_id) AND has_email AND not is_verified
      - Path is not in EXEMPT_PREFIXES
    Redirects to /verify-required so the user can resend the verification email.
    """

    EXEMPT_PREFIXES = (
        "/verify-required",
        "/verify",
        "/logout",
        "/api/healthz",
        "/static",
        "/welcome",
        "/login",
        "/forgot-password",
        "/reset-password",
    )

    async def dispatch(self, request: Request, call_next):
        if not settings.email_verification_required:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)

        try:
            session = request.session
        except (AssertionError, AttributeError):
            return await call_next(request)

        if (
            session.get("user_id")
            and session.get("has_email")
            and not session.get("is_verified", True)
        ):
            from starlette.responses import RedirectResponse
            return RedirectResponse("/verify-required", status_code=302)

        return await call_next(request)


def _init_sentry() -> None:
    dsn = os.environ.get("SENTRY_DSN", "")
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        sentry_sdk.init(
            dsn=dsn,
            integrations=[StarletteIntegration(), FastApiIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
    except Exception:
        pass


def create_app() -> FastAPI:
    _init_sentry()

    is_prod = os.environ.get("APP_ENV", "development").lower() == "production"
    app = FastAPI(title="Debt Tracker", docs_url=None if is_prod else "/docs")
    # Order matters: middleware added FIRST is innermost (runs after outer ones).
    # VerificationWall reads request.session, so it must be inner to SessionMiddleware.
    app.add_middleware(VerificationWallMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        max_age=7200,
        https_only=is_prod,
        same_site="lax",
    )
    app.add_middleware(SecurityHeadersMiddleware, is_prod=is_prod)
    app.add_middleware(RequestSizeLimitMiddleware)

    static_dir = Path(__file__).parent.parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(auth.router)
    app.include_router(pages.router)
    app.include_router(api_routes.router)
    app.include_router(debts_routes.router)
    app.include_router(budget_routes.router)
    app.include_router(goals_routes.router)
    app.include_router(networth_routes.router)
    app.include_router(flow_routes.router)
    app.include_router(admin_routes.router)
    app.include_router(notifications_routes.router)

    return app
