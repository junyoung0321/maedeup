"""간단한 Redis 기반 Rate Limiter (sliding window)."""

import logging
import time

import redis.asyncio as aioredis
from fastapi import HTTPException, Request

from app.core.config import settings

logger = logging.getLogger(__name__)

# 기본 설정: 분당 60회
DEFAULT_LIMIT = 60
DEFAULT_WINDOW_SECONDS = 60


async def check_rate_limit(
    request: Request,
    *,
    limit: int = DEFAULT_LIMIT,
    window: int = DEFAULT_WINDOW_SECONDS,
) -> None:
    """
    Redis sliding window rate limiter.
    Redis가 없으면 rate limiting을 건너뜁니다 (graceful degradation).
    """
    # 유저 식별: JWT sub 또는 IP
    user_id = getattr(request.state, "user_sub", None)
    if not user_id:
        user_id = request.client.host if request.client else "unknown"

    key = f"ratelimit:{request.url.path}:{user_id}"
    now = time.time()

    redis_client = None
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        async with redis_client.pipeline(transaction=True) as pipe:
            window_start = now - window
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window + 1)
            results = await pipe.execute()

        request_count = results[2]
        if request_count > limit:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Limit: {limit}/{window}s",
            )
    except HTTPException:
        raise
    except Exception:
        # Redis 연결 실패 → rate limiting 건너뜀
        logger.debug("Rate limiter skipped (Redis unavailable)")
    finally:
        if redis_client is not None:
            await redis_client.aclose()
