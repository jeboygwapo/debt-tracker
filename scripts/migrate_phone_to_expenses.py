#!/usr/bin/env python3
"""One-shot migration: copy income_config.phone into Expense rows.

Idempotent — running twice does nothing the second time.
Does NOT clear income_config.phone (planner ignores it; left for audit).

Run from project root:
    python scripts/migrate_phone_to_expenses.py
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.config import load_env_file  # noqa: E402

load_env_file(ROOT / ".env")

from app.db.base import AsyncSessionLocal  # noqa: E402
from app.db.crud import (  # noqa: E402
    create_expense,
    get_all_users,
    get_expenses,
)

PHONE_NAME = "Phone"


async def migrate() -> tuple[int, int]:
    created = 0
    skipped = 0
    async with AsyncSessionLocal() as db:
        users = await get_all_users(db)
        for user in users:
            cfg = user.income_config or {}
            phone = cfg.get("phone") or {}
            phone_sar = float(phone.get("monthly_sar", 0) or 0)
            if phone_sar <= 0:
                continue

            existing = await get_expenses(db, user.id)
            already = any(e.name.strip().lower() == PHONE_NAME.lower() for e in existing)
            if already:
                print(f"[skip] user={user.username}: Phone expense already exists")
                skipped += 1
                continue

            ends = phone.get("ends") or None
            sort_order = max((e.sort_order for e in existing), default=-1) + 1
            await create_expense(
                db,
                user_id=user.id,
                name=PHONE_NAME,
                monthly_sar=phone_sar,
                ends=ends,
                sort_order=sort_order,
            )
            print(f"[ok] user={user.username}: created Phone {phone_sar} SAR ends={ends or '∞'}")
            created += 1

    return created, skipped


def main() -> None:
    created, skipped = asyncio.run(migrate())
    print(f"\nDone. created={created} skipped={skipped}")


if __name__ == "__main__":
    main()
