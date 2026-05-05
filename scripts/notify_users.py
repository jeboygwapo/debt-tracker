"""Post-deploy: broadcast a system notification to all users.

Usage:
    python3 scripts/notify_users.py "v0.3.1 — Security fix" "Session state now syncs correctly."

Run on Fly.io after deploy:
    flyctl ssh console -a personal-debt-tracker -C \
      "python3 scripts/notify_users.py 'Title' 'Body'"
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.config import load_env_file  # noqa: E402
load_env_file(ROOT / ".env")

from app.db.base import AsyncSessionLocal  # noqa: E402
from app.db.crud import create_notification, get_all_users  # noqa: E402


async def main(title: str, body: str) -> None:
    async with AsyncSessionLocal() as db:
        users = await get_all_users(db)
        if not users:
            print("No users found — nothing to notify.")
            return
        admin = next((u for u in users if u.is_admin), users[0])
        n = await create_notification(db, title=title, body=body, created_by=admin.id)
        print(f"Notification #{n.id} created: '{title}'")
        print(f"Visible to all {len(users)} user(s).")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: notify_users.py <title> <body>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
