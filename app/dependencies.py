from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

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
    return user


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin required")
    return user
