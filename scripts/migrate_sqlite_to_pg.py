"""One-shot migration: local SQLite → Fly.io Postgres."""
import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import asyncpg

SQLITE_PATH = Path(__file__).parent.parent / "debttracker.db"
PG_URL = "postgresql://jayvee_debt_tracker:opiss8QVFeidXf9@localhost:5432/jayvee_debt_tracker"


def load_sqlite():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    users = [dict(r) for r in cur.execute("SELECT * FROM users").fetchall()]
    debts = [dict(r) for r in cur.execute("SELECT * FROM debts").fetchall()]
    valid_debt_ids = {d["id"] for d in debts}
    entries = [
        dict(r) for r in cur.execute("SELECT * FROM monthly_entries").fetchall()
        if r["debt_id"] in valid_debt_ids
    ]
    conn.close()
    return users, debts, entries


async def migrate(pg_url: str):
    conn = await asyncpg.connect(pg_url)

    users, debts, entries = load_sqlite()
    print(f"Migrating: {len(users)} users, {len(debts)} debts, {len(entries)} entries")

    async with conn.transaction():
        await conn.execute("DELETE FROM monthly_entries")
        await conn.execute("DELETE FROM debts")
        await conn.execute("DELETE FROM users")

        for u in users:
            await conn.execute(
                """INSERT INTO users (id, username, password_hash, is_admin, income_config, created_at)
                   VALUES ($1, $2, $3, $4, $5::jsonb, $6)""",
                u["id"], u["username"], u["password_hash"],
                bool(u["is_admin"]),
                json.dumps(json.loads(u["income_config"]) if u["income_config"] else {}),
                datetime.fromisoformat(u["created_at"]),
            )

        for d in debts:
            await conn.execute(
                """INSERT INTO debts (id, user_id, name, type, apr_monthly_pct, note,
                       is_fixed, fixed_monthly, fixed_ends, fixed_reduced_monthly,
                       fixed_reduced_threshold, sort_order, created_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                d["id"], d["user_id"], d["name"], d["type"],
                d["apr_monthly_pct"], d["note"],
                bool(d["is_fixed"]), d["fixed_monthly"], d["fixed_ends"],
                d["fixed_reduced_monthly"], d["fixed_reduced_threshold"],
                d["sort_order"], datetime.fromisoformat(d["created_at"]),
            )

        for e in entries:
            await conn.execute(
                """INSERT INTO monthly_entries (id, user_id, debt_id, month, balance,
                       min_due, payment, paid_on, due_date, note)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
                e["id"], e["user_id"], e["debt_id"], e["month"],
                e["balance"], e["min_due"], e["payment"],
                e["paid_on"], e["due_date"], e["note"],
            )

        # reset sequences so new inserts get correct next IDs
        await conn.execute("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users))")
        await conn.execute("SELECT setval('debts_id_seq', (SELECT MAX(id) FROM debts))")
        await conn.execute("SELECT setval('monthly_entries_id_seq', (SELECT MAX(id) FROM monthly_entries))")

    print("Migration complete.")
    await conn.close()


if __name__ == "__main__":
    pg_url = sys.argv[1] if len(sys.argv) > 1 else PG_URL
    asyncio.run(migrate(pg_url))
