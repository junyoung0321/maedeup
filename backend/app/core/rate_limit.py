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


async def check_ws_llm_budget(
    redis_client: "aioredis.Redis | None",
    room_id: str,
    user_id: int,
    *,
    limit: int = 30,
    window: int = 60,
) -> bool:
    """WS LLM 진입부 전용 per-(room, user) budget (Redis INCR+EXPIRE).

    Request 객체가 없는 WebSocket 컨텍스트에서 check_rate_limit 대신 사용.
    반환: True=허용(파이프라인 진행), False=한도 초과(skip).
    Redis 미연결/예외 시 항상 True (fail-open) — 전시 happy path 보호.

    동작: 키 wsllm:{room_id}:{user_id} 를 INCR. 첫 호출(반환 1)일 때만
    EXPIRE(window) 설정해 sliding이 아닌 fixed-window 카운터로 동작.
    count > limit 이면 False. (free-use audit round3 #02)
    """
    if redis_client is None:
        return True
    key = f"wsllm:{room_id}:{user_id}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, window)
        if count > limit:
            logger.info(
                "WS LLM budget exceeded room=%s user=%s count=%s limit=%s",
                room_id, user_id, count, limit,
            )
            return False
        return True
    except Exception:
        # Redis 장애 → fail-open (rate limiting 건너뜀)
        logger.debug("WS LLM budget check skipped (Redis unavailable)")
        return True
