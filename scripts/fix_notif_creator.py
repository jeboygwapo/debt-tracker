import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import update
from app.db.base import AsyncSessionLocal
from app.db.models import Notification

async def fix():
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Notification)
            .where(Notification.title == "What's new in v0.1.0")
            .values(created_by=None)
        )
        await db.commit()
        print("fixed")

asyncio.run(fix())
