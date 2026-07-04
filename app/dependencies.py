from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db.base import get_db
from .db.crud import get_user_by_id
from .db.models import User


class NotAuthenticated(Exception):
    pass


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise NotAuthenticated()
    user = await get_user_by_id(db, user_id)
    if not user:
        request.session.clear()
        raise NotAuthenticated()

    if settings.email_verification_required and user.email and not user.is_verified:
        request.session.clear()
        request.session["pending_verify_user_id"] = user.id
        raise NotAuthenticated()

    # Sync display prefs from DB on every request so multi-session and
    # admin edits are reflected without requiring re-login.
    cfg = user.income_config or {}
    request.session["currency_symbol"] = cfg.get("currency_symbol", "₱")
    request.session["income_currency"] = cfg.get("income_currency", "SAR")
    request.session["ofw_mode"] = cfg.get("ofw_mode", True)
    request.session["is_verified"] = user.is_verified
    request.session["has_email"] = bool(user.email)

    return user


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin required")
    return user
