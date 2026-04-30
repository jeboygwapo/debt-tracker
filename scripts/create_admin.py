#!/usr/bin/env python3
"""One-off: create or promote a user to admin. Run from project root."""
import asyncio
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.config import load_env_file
load_env_file(ROOT / ".env")

from app.db.base import AsyncSessionLocal
from app.db.crud import create_user, get_user_by_username, update_user_password
from app.db.models import User
from sqlalchemy import select


async def main() -> None:
    username = input("Username: ").strip()
    if not username:
        print("Aborted.")
        return

    while True:
        pw = getpass.getpass("Password (min 12 chars): ")
        if len(pw) < 12:
            print("Too short.")
            continue
        pw2 = getpass.getpass("Confirm: ")
        if pw != pw2:
            print("No match.")
            continue
        break

    async with AsyncSessionLocal() as db:
        existing = await get_user_by_username(db, username)
        if existing:
            existing.is_admin = True
            await update_user_password(db, existing, pw)
            await db.commit()
            print(f"Updated '{username}' — password reset, promoted to admin.")
        else:
            await create_user(db, username=username, password=pw, is_admin=True)
            print(f"Created admin user '{username}'.")


if __name__ == "__main__":
    asyncio.run(main())
