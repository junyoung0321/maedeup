from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
import redis.asyncio as aioredis

from app.core.config import settings
from app.db.session import get_session

router = APIRouter()


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    db_status = "ok"
    redis_status = "ok"

    try:
        await session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
    except Exception as e:
        redis_status = f"error: {e}"

    return {
        "status": "ok" if db_status == "ok" and redis_status == "ok" else "degraded",
        "services": {
            "database": db_status,
            "redis": redis_status,
        },
    }
