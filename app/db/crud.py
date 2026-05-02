from typing import Optional

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import hash_password
from .models import AiCache, Debt, MonthlyEntry, Notification, NotificationRead, User


# ── Users ────────────────────────────────────────────────────────────────────

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_all_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    is_admin: bool = False,
    income_config: Optional[dict] = None,
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        is_admin=is_admin,
        income_config=income_config or {},
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_password(db: AsyncSession, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    await db.commit()


async def update_income_config(db: AsyncSession, user: User, config: dict) -> None:
    user.income_config = config
    await db.commit()


async def delete_user(db: AsyncSession, user_id: int) -> None:
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()


# ── Debts ─────────────────────────────────────────────────────────────────────

async def get_debts(db: AsyncSession, user_id: int) -> list[Debt]:
    result = await db.execute(
        select(Debt).where(Debt.user_id == user_id).order_by(Debt.sort_order, Debt.id)
    )
    return list(result.scalars().all())


async def get_debt_by_id(db: AsyncSession, debt_id: int, user_id: int) -> Optional[Debt]:
    result = await db.execute(
        select(Debt).where(Debt.id == debt_id, Debt.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_debt(db: AsyncSession, user_id: int, **kwargs) -> Debt:
    debt = Debt(user_id=user_id, **kwargs)
    db.add(debt)
    await db.commit()
    await db.refresh(debt)
    return debt


async def update_debt(db: AsyncSession, debt: Debt, **kwargs) -> Debt:
    for k, v in kwargs.items():
        setattr(debt, k, v)
    await db.commit()
    await db.refresh(debt)
    return debt


async def reorder_debts(db: AsyncSession, user_id: int, ordered_ids: list[int]) -> None:
    for i, debt_id in enumerate(ordered_ids):
        await db.execute(
            update(Debt)
            .where(Debt.id == debt_id, Debt.user_id == user_id)
            .values(sort_order=i)
        )
    await db.commit()


async def delete_debt(db: AsyncSession, debt_id: int, user_id: int) -> None:
    await db.execute(delete(Debt).where(Debt.id == debt_id, Debt.user_id == user_id))
    await db.commit()


# ── Monthly Entries ───────────────────────────────────────────────────────────

async def get_months(db: AsyncSession, user_id: int) -> list[str]:
    result = await db.execute(
        select(MonthlyEntry.month)
        .where(MonthlyEntry.user_id == user_id)
        .distinct()
        .order_by(MonthlyEntry.month)
    )
    return list(result.scalars().all())


async def get_entries_for_month(
    db: AsyncSession, user_id: int, month: str
) -> list[MonthlyEntry]:
    result = await db.execute(
        select(MonthlyEntry)
        .where(MonthlyEntry.user_id == user_id, MonthlyEntry.month == month)
        .options(selectinload(MonthlyEntry.debt))
        .order_by(MonthlyEntry.debt_id)
    )
    return list(result.scalars().all())


async def get_all_entries(db: AsyncSession, user_id: int) -> list[MonthlyEntry]:
    result = await db.execute(
        select(MonthlyEntry)
        .where(MonthlyEntry.user_id == user_id)
        .options(selectinload(MonthlyEntry.debt))
        .order_by(MonthlyEntry.month, MonthlyEntry.debt_id)
    )
    return list(result.scalars().all())


async def upsert_entry(
    db: AsyncSession,
    user_id: int,
    debt_id: int,
    month: str,
    **kwargs,
) -> MonthlyEntry:
    result = await db.execute(
        select(MonthlyEntry).where(
            MonthlyEntry.user_id == user_id,
            MonthlyEntry.debt_id == debt_id,
            MonthlyEntry.month == month,
        )
    )
    entry = result.scalar_one_or_none()
    if entry:
        for k, v in kwargs.items():
            setattr(entry, k, v)
    else:
        entry = MonthlyEntry(user_id=user_id, debt_id=debt_id, month=month, **kwargs)
        db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_entries_for_month(db: AsyncSession, user_id: int, month: str) -> None:
    await db.execute(
        delete(MonthlyEntry).where(
            MonthlyEntry.user_id == user_id, MonthlyEntry.month == month
        )
    )
    await db.commit()


# ── Notifications ─────────────────────────────────────────────────────────────

async def create_notification(db: AsyncSession, title: str, body: str, created_by: int) -> Notification:
    n = Notification(title=title, body=body, created_by=created_by)
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return n


async def get_active_notifications(db: AsyncSession) -> list[Notification]:
    result = await db.execute(
        select(Notification).where(Notification.is_active == True).order_by(Notification.created_at.desc())
    )
    return list(result.scalars().all())


async def get_all_notifications(db: AsyncSession) -> list[Notification]:
    result = await db.execute(select(Notification).order_by(Notification.created_at.desc()))
    return list(result.scalars().all())


async def deactivate_notification(db: AsyncSession, notification_id: int) -> None:
    await db.execute(
        update(Notification).where(Notification.id == notification_id).values(is_active=False)
    )
    await db.commit()


async def get_unread_count(db: AsyncSession, user_id: int) -> int:
    read_sub = select(NotificationRead.notification_id).where(NotificationRead.user_id == user_id)
    result = await db.execute(
        select(Notification).where(Notification.is_active == True, Notification.id.not_in(read_sub))
    )
    return len(result.scalars().all())


async def mark_all_read(db: AsyncSession, user_id: int) -> None:
    active = await get_active_notifications(db)
    read_sub = select(NotificationRead.notification_id).where(NotificationRead.user_id == user_id)
    already_read = {r for r in (await db.execute(read_sub)).scalars().all()}
    for n in active:
        if n.id not in already_read:
            db.add(NotificationRead(user_id=user_id, notification_id=n.id))
    await db.commit()


# ── AI Cache ──────────────────────────────────────────────────────────────────

async def get_ai_cache(db: AsyncSession, user_id: int) -> Optional[AiCache]:
    result = await db.execute(select(AiCache).where(AiCache.user_id == user_id))
    return result.scalar_one_or_none()


async def set_ai_cache(
    db: AsyncSession, user_id: int, data_hash: str, html: str
) -> None:
    from datetime import date
    today = date.today()
    cache = await get_ai_cache(db, user_id)
    if cache:
        new_count = 1 if cache.generated_at != today else cache.daily_count + 1
        cache.data_hash = data_hash
        cache.html = html
        cache.generated_at = today
        cache.daily_count = new_count
    else:
        cache = AiCache(
            user_id=user_id,
            data_hash=data_hash,
            html=html,
            generated_at=today,
            daily_count=1,
        )
        db.add(cache)
    await db.commit()


async def get_ai_daily_count(db: AsyncSession, user_id: int) -> int:
    from datetime import date
    cache = await get_ai_cache(db, user_id)
    if not cache or cache.generated_at != date.today():
        return 0
    return cache.daily_count
