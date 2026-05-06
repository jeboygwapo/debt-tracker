from typing import Optional

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import hash_password
from .models import Account, AccountSnapshot, AiCache, Debt, Expense, Goal, MonthlyEntry, Notification, NotificationRead, User


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


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_verify_token(db: AsyncSession, token: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.verify_token == token))
    return result.scalar_one_or_none()


async def set_user_email(db: AsyncSession, user: User, email: str, token: str, expiry) -> None:
    user.email = email
    user.is_verified = False
    user.verify_token = token
    user.verify_token_expiry = expiry
    await db.commit()


async def mark_user_verified(db: AsyncSession, user: User) -> None:
    user.is_verified = True
    user.verify_token = None
    user.verify_token_expiry = None
    await db.commit()


async def get_user_by_reset_token(db: AsyncSession, token: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.reset_token == token))
    return result.scalar_one_or_none()


async def set_reset_token(db: AsyncSession, user: User, token: str, expiry) -> None:
    user.reset_token = token
    user.reset_token_expiry = expiry
    await db.commit()


async def clear_reset_token(db: AsyncSession, user: User) -> None:
    user.reset_token = None
    user.reset_token_expiry = None
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
    owned = set((await db.execute(
        select(Debt.id).where(Debt.user_id == user_id)
    )).scalars().all())
    for i, debt_id in enumerate(x for x in ordered_ids if x in owned):
        await db.execute(
            update(Debt).where(Debt.id == debt_id, Debt.user_id == user_id).values(sort_order=i)
        )
    await db.commit()


async def delete_debt(db: AsyncSession, debt_id: int, user_id: int) -> None:
    await db.execute(delete(Debt).where(Debt.id == debt_id, Debt.user_id == user_id))
    await db.commit()


# ── Expenses ──────────────────────────────────────────────────────────────────

async def get_expenses(db: AsyncSession, user_id: int) -> list[Expense]:
    result = await db.execute(
        select(Expense).where(Expense.user_id == user_id).order_by(Expense.sort_order, Expense.id)
    )
    return list(result.scalars().all())


async def get_expense_by_id(db: AsyncSession, expense_id: int, user_id: int) -> Optional[Expense]:
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_expense(db: AsyncSession, user_id: int, **kwargs) -> Expense:
    expense = Expense(user_id=user_id, **kwargs)
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


async def update_expense(db: AsyncSession, expense: Expense, **kwargs) -> Expense:
    for k, v in kwargs.items():
        setattr(expense, k, v)
    await db.commit()
    await db.refresh(expense)
    return expense


async def delete_expense(db: AsyncSession, expense_id: int, user_id: int) -> bool:
    result = await db.execute(
        delete(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    )
    await db.commit()
    return (result.rowcount or 0) > 0


async def reorder_expenses(db: AsyncSession, user_id: int, ordered_ids: list[int]) -> None:
    owned = set((await db.execute(
        select(Expense.id).where(Expense.user_id == user_id)
    )).scalars().all())
    for i, expense_id in enumerate(x for x in ordered_ids if x in owned):
        await db.execute(
            update(Expense).where(Expense.id == expense_id, Expense.user_id == user_id).values(sort_order=i)
        )
    await db.commit()


# ── Accounts & Snapshots ──────────────────────────────────────────────────────

async def get_accounts(db: AsyncSession, user_id: int) -> list[Account]:
    result = await db.execute(
        select(Account).where(Account.user_id == user_id).order_by(Account.sort_order, Account.id)
    )
    return list(result.scalars().all())


async def get_account_by_id(db: AsyncSession, account_id: int, user_id: int) -> Optional[Account]:
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
        .options(selectinload(Account.snapshots))
    )
    return result.scalar_one_or_none()


async def create_account(db: AsyncSession, user_id: int, **kwargs) -> Account:
    account = Account(user_id=user_id, **kwargs)
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def update_account(db: AsyncSession, account: Account, **kwargs) -> Account:
    for k, v in kwargs.items():
        setattr(account, k, v)
    await db.commit()
    await db.refresh(account)
    return account


async def delete_account(db: AsyncSession, account_id: int, user_id: int) -> bool:
    result = await db.execute(
        delete(Account).where(Account.id == account_id, Account.user_id == user_id)
    )
    await db.commit()
    return (result.rowcount or 0) > 0


async def reorder_accounts(db: AsyncSession, user_id: int, ordered_ids: list[int]) -> None:
    owned = set((await db.execute(
        select(Account.id).where(Account.user_id == user_id)
    )).scalars().all())
    for i, account_id in enumerate(x for x in ordered_ids if x in owned):
        await db.execute(
            update(Account).where(Account.id == account_id, Account.user_id == user_id).values(sort_order=i)
        )
    await db.commit()


async def get_snapshots_for_account(db: AsyncSession, account_id: int, user_id: int) -> list[AccountSnapshot]:
    result = await db.execute(
        select(AccountSnapshot)
        .where(AccountSnapshot.account_id == account_id, AccountSnapshot.user_id == user_id)
        .order_by(AccountSnapshot.month.desc())
    )
    return list(result.scalars().all())


async def get_all_snapshots(db: AsyncSession, user_id: int) -> list[AccountSnapshot]:
    result = await db.execute(
        select(AccountSnapshot)
        .where(AccountSnapshot.user_id == user_id)
        .options(selectinload(AccountSnapshot.account))
        .order_by(AccountSnapshot.month.desc(), AccountSnapshot.account_id)
    )
    return list(result.scalars().all())


async def get_snapshot_by_id(db: AsyncSession, snapshot_id: int, user_id: int) -> Optional[AccountSnapshot]:
    result = await db.execute(
        select(AccountSnapshot).where(
            AccountSnapshot.id == snapshot_id, AccountSnapshot.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def snapshot_hash_exists(db: AsyncSession, user_id: int, statement_hash: str) -> bool:
    result = await db.execute(
        select(AccountSnapshot.id).where(
            AccountSnapshot.user_id == user_id,
            AccountSnapshot.statement_hash == statement_hash,
        )
    )
    return result.scalar_one_or_none() is not None


async def upsert_snapshot(
    db: AsyncSession,
    account_id: int,
    user_id: int,
    month: str,
    balance: float,
    source: str = "manual",
    statement_hash: Optional[str] = None,
) -> AccountSnapshot:
    result = await db.execute(
        select(AccountSnapshot).where(
            AccountSnapshot.account_id == account_id,
            AccountSnapshot.user_id == user_id,
            AccountSnapshot.month == month,
        )
    )
    snap = result.scalar_one_or_none()
    if snap:
        snap.balance = balance
        snap.source = source
        if statement_hash:
            snap.statement_hash = statement_hash
    else:
        snap = AccountSnapshot(
            account_id=account_id,
            user_id=user_id,
            month=month,
            balance=balance,
            source=source,
            statement_hash=statement_hash,
        )
        db.add(snap)
    await db.commit()
    await db.refresh(snap)
    return snap


async def delete_snapshot(db: AsyncSession, snapshot_id: int, user_id: int) -> bool:
    result = await db.execute(
        delete(AccountSnapshot).where(
            AccountSnapshot.id == snapshot_id, AccountSnapshot.user_id == user_id
        )
    )
    await db.commit()
    return (result.rowcount or 0) > 0


async def get_ai_parse_count(db: AsyncSession, user: User) -> int:
    from datetime import date
    cfg = user.income_config or {}
    if cfg.get("ai_parse_date") != str(date.today()):
        return 0
    return int(cfg.get("ai_parse_count", 0))


async def increment_ai_parse_count(db: AsyncSession, user: User) -> int:
    from datetime import date
    cfg = dict(user.income_config or {})
    today = str(date.today())
    if cfg.get("ai_parse_date") != today:
        cfg["ai_parse_date"] = today
        cfg["ai_parse_count"] = 1
    else:
        cfg["ai_parse_count"] = int(cfg.get("ai_parse_count", 0)) + 1
    user.income_config = cfg
    await db.commit()
    return cfg["ai_parse_count"]


# ── Goals ─────────────────────────────────────────────────────────────────────

async def get_goals(db: AsyncSession, user_id: int) -> list[Goal]:
    result = await db.execute(
        select(Goal).where(Goal.user_id == user_id).order_by(Goal.sort_order, Goal.id)
    )
    return list(result.scalars().all())


async def get_goal_by_id(db: AsyncSession, goal_id: int, user_id: int) -> Optional[Goal]:
    result = await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_goal(db: AsyncSession, user_id: int, **kwargs) -> Goal:
    goal = Goal(user_id=user_id, **kwargs)
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return goal


async def update_goal(db: AsyncSession, goal: Goal, **kwargs) -> Goal:
    for k, v in kwargs.items():
        setattr(goal, k, v)
    await db.commit()
    await db.refresh(goal)
    return goal


async def delete_goal(db: AsyncSession, goal_id: int, user_id: int) -> bool:
    result = await db.execute(
        delete(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
    )
    await db.commit()
    return (result.rowcount or 0) > 0


async def reorder_goals(db: AsyncSession, user_id: int, ordered_ids: list[int]) -> None:
    owned = set((await db.execute(
        select(Goal.id).where(Goal.user_id == user_id)
    )).scalars().all())
    for i, goal_id in enumerate(x for x in ordered_ids if x in owned):
        await db.execute(
            update(Goal).where(Goal.id == goal_id, Goal.user_id == user_id).values(sort_order=i)
        )
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
        select(Notification)
        .where(Notification.is_active == True)
        .options(selectinload(Notification.creator))
        .order_by(Notification.created_at.desc())
    )
    return list(result.scalars().all())


async def get_all_notifications(db: AsyncSession) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .options(selectinload(Notification.creator))
        .order_by(Notification.created_at.desc())
    )
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
