"""One-time script to create all tables via SQLModel.metadata.create_all"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Import ALL models so SQLModel.metadata is aware of them
import app.models.intent  # noqa
import app.models.user  # noqa
import app.models.chat  # noqa
import app.models.event  # noqa
import app.models.room  # noqa
import app.models.meeting  # noqa
import app.models.vote  # noqa
import app.models.friendship  # noqa
import app.models.ai_memory  # noqa

from app.db.session import engine
from sqlmodel import SQLModel


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    print("All tables created successfully.")
    await engine.dispose()


asyncio.run(main())
