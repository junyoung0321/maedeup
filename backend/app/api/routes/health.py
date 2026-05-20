from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
import redis.asyncio as aioredis

from app.core.config import settings
from app.db.session import get_session

router = APIRouter()


@router.get("/api/v1/health/gemini")
async def gemini_health() -> dict:
    """시연 헬스체크: Gemini 키 유효성 + quota 살아있는지 확인."""
    from app.services.gemini import call_gemini

    response = await call_gemini("ping")
    ok = bool(response and response.strip())
    return {"ok": ok, "len": len(response or "")}


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    db_status = "ok"
    redis_status = "ok"

    try:
        await session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
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
