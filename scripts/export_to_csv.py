"""
Export all debt tracker data from the DB to CSV files.

Usage:
    python scripts/export_to_csv.py [--out-dir ./backups]

Reads DATABASE_URL from environment or .env file.
Produces:
    debts.csv          — debt definitions
    monthly_entries.csv — all monthly payment entries
"""

import asyncio
import csv
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Load .env before app imports
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.base import AsyncSessionLocal
from app.db.models import Debt, MonthlyEntry, User


async def export(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as db:
        users = list((await db.execute(select(User).order_by(User.id))).scalars().all())

        debts_file = out_dir / "debts.csv"
        entries_file = out_dir / "monthly_entries.csv"

        with open(debts_file, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "user", "id", "name", "type", "apr_monthly_pct", "note",
                "is_fixed", "fixed_monthly", "fixed_ends",
                "fixed_reduced_monthly", "fixed_reduced_threshold", "sort_order",
            ])
            for user in users:
                debts = list(
                    (await db.execute(
                        select(Debt).where(Debt.user_id == user.id).order_by(Debt.sort_order)
                    )).scalars().all()
                )
                for d in debts:
                    w.writerow([
                        user.username, d.id, d.name, d.type, d.apr_monthly_pct, d.note or "",
                        d.is_fixed, d.fixed_monthly or "", d.fixed_ends or "",
                        d.fixed_reduced_monthly or "", d.fixed_reduced_threshold or "", d.sort_order,
                    ])

        with open(entries_file, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "user", "month", "debt", "debt_type",
                "balance", "min_due", "payment", "paid_on", "due_date", "note",
            ])
            for user in users:
                entries = list(
                    (await db.execute(
                        select(MonthlyEntry)
                        .where(MonthlyEntry.user_id == user.id)
                        .options(selectinload(MonthlyEntry.debt))
                        .order_by(MonthlyEntry.month, MonthlyEntry.debt_id)
                    )).scalars().all()
                )
                for e in entries:
                    if not e.debt:
                        continue
                    w.writerow([
                        user.username, e.month, e.debt.name, e.debt.type,
                        e.balance, e.min_due, e.payment,
                        e.paid_on or "", e.due_date or "", e.note or "",
                    ])

    print(f"Exported {debts_file}")
    print(f"Exported {entries_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=f"./backups/{date.today()}")
    args = parser.parse_args()

    asyncio.run(export(Path(args.out_dir)))
