#!/usr/bin/env python3
"""
One-time migration: imports debts.json into the DB for an existing user.
Run AFTER init_db.py has created the admin user.

Usage:
  python scripts/migrate_json_to_db.py                        # uses debts.json, prompts username
  python scripts/migrate_json_to_db.py debts.json admin
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.config import load_env_file

load_env_file(ROOT / ".env")

from app.db.base import AsyncSessionLocal
from app.db.crud import (
    create_debt,
    get_debts,
    get_user_by_username,
    update_income_config,
    upsert_entry,
)

_TYPE_MAP = {
    "credit_card": "credit_card",
    "loan": "personal_loan",
    "personal_loan": "personal_loan",
    "personal": "personal_loan",
    "other": "other",
}


async def migrate(json_path: Path, username: str) -> None:
    data = json.loads(json_path.read_text())

    async with AsyncSessionLocal() as db:
        user = await get_user_by_username(db, username)
        if not user:
            print(f"[error] User '{username}' not found. Run init_db.py first.")
            sys.exit(1)

        print(f"[migrate] Targeting user '{username}' (id={user.id})")

        # income config
        cfg = {k: v for k, v in data.get("income_config", {}).items() if k != "note_expenses"}
        await update_income_config(db, user, cfg)
        print("[migrate] Income config updated.")

        # debts
        fixed_pmts = data.get("fixed_payments", {})
        debts_meta = data.get("debts", {})

        existing = await get_debts(db, user.id)
        debt_map = {d.name: d.id for d in existing}

        for i, (name, meta) in enumerate(debts_meta.items()):
            if name in debt_map:
                print(f"  [skip] Debt already exists: {name}")
                continue
            fp = fixed_pmts.get(name, {})
            raw_type = meta.get("type", "credit_card")
            debt_type = _TYPE_MAP.get(raw_type, "other")
            debt = await create_debt(
                db,
                user_id=user.id,
                name=name,
                type=debt_type,
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
            print(f"  [debt] {name} → id={debt.id} (type={debt_type})")

        # monthly entries
        months = data.get("months", {})
        for month in sorted(months.keys()):
            entries = months[month]
            skipped = 0
            for debt_name, e in entries.items():
                if debt_name not in debt_map:
                    print(f"  [warn] Unknown debt '{debt_name}' in {month}, skipping")
                    skipped += 1
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
            msg = f"  [month] {month} — {len(entries) - skipped} entries"
            if skipped:
                msg += f" ({skipped} skipped)"
            print(msg)

    print("\n[migrate] Done.")


if __name__ == "__main__":
    json_file = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "debts.json"
    uname = sys.argv[2] if len(sys.argv) > 2 else input("Username to migrate into: ").strip()

    if not json_file.exists():
        print(f"[error] {json_file} not found")
        sys.exit(1)

    asyncio.run(migrate(json_file, uname))
