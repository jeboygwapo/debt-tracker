"""
Runs on every deploy (fly.toml release_command):
1. alembic upgrade head
2. Post changelog notification for current APP_VERSION if not already posted
"""
import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def run_migrations() -> None:
    result = subprocess.run(
        ["python3", "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(result.returncode)


def parse_changelog(version: str) -> str | None:
    changelog_path = Path(__file__).parent.parent / "CHANGELOG"
    if not changelog_path.exists():
        return None
    text = changelog_path.read_text()
    pattern = rf"==\s*{re.escape(version)}\s*==\n(.*?)(?=\n==|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


async def post_notification(version: str, body: str) -> None:
    from sqlalchemy import select
    from app.db.base import AsyncSessionLocal
    from app.db.models import Notification, User

    async with AsyncSessionLocal() as db:
        title = f"What's new in v{version}"
        existing = await db.execute(
            select(Notification).where(Notification.title == title)
        )
        if existing.scalar_one_or_none():
            print(f"[post_deploy] Notification for v{version} already exists — skipping.")
            return

        admin = await db.execute(
            select(User).where(User.is_admin == True).order_by(User.id)
        )
        admin_user = admin.scalar_one_or_none()
        created_by = admin_user.id if admin_user else None

        n = Notification(title=title, body=body, created_by=created_by)
        db.add(n)
        await db.commit()
        print(f"[post_deploy] Posted notification: {title}")


def main() -> None:
    run_migrations()

    from app.config import APP_VERSION
    from app.config import load_env_file
    load_env_file(Path(__file__).parent.parent / ".env")

    body = parse_changelog(APP_VERSION)
    if not body:
        print(f"[post_deploy] No CHANGELOG entry for v{APP_VERSION} — skipping notification.")
        return

    asyncio.run(post_notification(APP_VERSION, body))


if __name__ == "__main__":
    main()
