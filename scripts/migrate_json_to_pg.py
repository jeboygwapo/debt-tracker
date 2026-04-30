#!/usr/bin/env python3
"""One-time migration: imports debts.json into Postgres for a given user."""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import load_env_file, settings

load_env_file(Path(__file__).parent.parent / ".env")

from app.db.base import AsyncSessionLocal, engine
from app.db.crud import (
    create_debt,
    create_user,
    get_debts,
    get_user_by_username,
    upsert_entry,
    update_income_config,
)
from app.db.models import Base


async def migrate(json_path: Path, username: str, password: str) -> None:
    data = json.loads(json_path.read_text())

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, username)
        if not user:
            user = await create_user(db, username, password, is_admin=True)
            print(f"Created user: {username} (id={user.id})")
        else:
            print(f"User {username} already exists (id={user.id}), updating data.")

        await update_income_config(db, user, data.get("income_config", {}))

        fixed_pmts = data.get("fixed_payments", {})
        debts_meta = data.get("debts", {})

        debt_map: dict[str, int] = {}
        existing = await get_debts(db, user.id)
        for d in existing:
            debt_map[d.name] = d.id

        for i, (name, meta) in enumerate(debts_meta.items()):
            if name in debt_map:
                print(f"  Debt already exists: {name}")
                continue
            fp = fixed_pmts.get(name, {})
            debt = await create_debt(
                db,
                user_id=user.id,
                name=name,
                type=meta.get("type", "credit_card"),
                apr_monthly_pct=meta.get("apr_monthly_pct", 0.0),
                note=meta.get("note"),
                is_fixed=bool(fp),
                fixed_monthly=fp.get("monthly"),
                fixed_ends=fp.get("ends"),
                fixed_reduced_monthly=fp.get("reduced_monthly"),
                fixed_reduced_threshold=fp.get("reduced_threshold"),
                sort_order=i,
            )
            debt_map[name] = debt.id
            print(f"  Created debt: {name} (id={debt.id})")

        for month, entries in data.get("months", {}).items():
            for debt_name, e in entries.items():
                if debt_name not in debt_map:
                    print(f"  WARNING: unknown debt '{debt_name}' in {month}, skipping")
                    continue
                await upsert_entry(
                    db,
                    user_id=user.id,
                    debt_id=debt_map[debt_name],
                    month=month,
                    balance=e.get("balance") or 0.0,
                    min_due=e.get("min_due") or 0.0,
                    payment=e.get("payment") or 0.0,
                    paid_on=e.get("paid_on") or None,
                    due_date=e.get("due_date") or None,
                    note=e.get("note") or None,
                )
            print(f"  Migrated month: {month} ({len(entries)} entries)")

    print("\nMigration complete.")


if __name__ == "__main__":
    json_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("debts.json")
    uname = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("APP_USER", "admin")
    passwd = sys.argv[3] if len(sys.argv) > 3 else input("Password for user: ")

    if not json_file.exists():
        print(f"ERROR: {json_file} not found")
        sys.exit(1)

    asyncio.run(migrate(json_file, uname, passwd))
