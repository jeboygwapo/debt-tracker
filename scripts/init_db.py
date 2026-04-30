#!/usr/bin/env python3
"""
First-run init: create tables + seed admin user.
Run from project root: python scripts/init_db.py
"""
import asyncio
import getpass
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.config import load_env_file, save_env_value, settings

ENV_FILE = ROOT / ".env"


def ensure_secret_key() -> None:
    load_env_file(ENV_FILE)
    if settings.secret_key == "dev-secret-change-me":
        key = secrets.token_hex(32)
        save_env_value(ENV_FILE, "SECRET_KEY", key)
        print(f"[init] Generated SECRET_KEY → {ENV_FILE}")
    load_env_file(ENV_FILE)


def run_migrations() -> None:
    print("[init] Running alembic migrations...")
    result = subprocess.run(
        ["python", "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("[error] Migration failed:")
        print(result.stderr)
        sys.exit(1)
    print("[init] Migrations OK.")


async def seed_admin() -> None:
    from app.db.base import AsyncSessionLocal
    from app.db.crud import create_user, get_all_users

    async with AsyncSessionLocal() as db:
        users = await get_all_users(db)
        if users:
            print(f"[init] DB already has {len(users)} user(s). Skipping admin seed.")
            return

        print("\n[init] No users found. Create admin account.")
        username = input("  Username [admin]: ").strip() or "admin"

        while True:
            pw = getpass.getpass("  Password (min 12 chars): ")
            if len(pw) < 12:
                print("  Password too short, try again.")
                continue
            pw2 = getpass.getpass("  Confirm password: ")
            if pw != pw2:
                print("  Passwords don't match, try again.")
                continue
            break

        await create_user(db, username=username, password=pw, is_admin=True)
        print(f"[init] Admin user '{username}' created.")


def main() -> None:
    ensure_secret_key()
    run_migrations()
    asyncio.run(seed_admin())
    print("\n[init] Done. Run: python main.py")


if __name__ == "__main__":
    main()
