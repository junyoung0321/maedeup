"""알림 발행 단일 통로.

모든 알림은 이 함수를 통과한다. DB INSERT + (선택적) Redis publish.
호출 시점: 유저 발생 이벤트 커밋 직후(예: 친구 요청, 룸 참여). LangGraph 노드 경로는
별도 fan-out worker(Day 1 오후 구현 예정)가 Redis envelope을 소비해 이 함수를 호출한다.
"""
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification import Notification

logger = logging.getLogger(__name__)


async def notify(
    session: AsyncSession,
    *,
    user_id: int,
    type: str,
    title: str,
    body: Optional[str] = None,
    room_id: Optional[int] = None,
    payload: Optional[dict[str, Any]] = None,
) -> Notification:
    """알림 DB INSERT + Redis publish. 자체 커밋한다.

    호출자는 자신의 트랜잭션을 먼저 커밋한 뒤 이 함수를 호출하는 것을 권장.
    (이 함수 실패가 원 트랜잭션을 되돌리지 않도록.)

    Redis publish 실패는 로깅만 하고 DB 저장을 유지한다.
    """
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        room_id=room_id,
        payload=payload or {},
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)

    # Redis publish (WS 리스너가 Day 2에 붙는다; 그 전까지 no-op)
    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        envelope = {
            "id": notification.id,
            "user_id": user_id,
            "type": type,
            "title": title,
            "body": body,
            "room_id": room_id,
            "payload": payload or {},
            "read_at": None,
            "created_at": notification.created_at.isoformat(),
        }
        await r.publish(f"notifications:user:{user_id}", json.dumps(envelope))
        await r.aclose()
    except Exception:
        logger.warning(
            "Redis publish failed for user %d (notification %d saved to DB)",
            user_id,
            notification.id,
            exc_info=True,
        )

    return notification
