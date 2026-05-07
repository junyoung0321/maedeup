"""AI 패널 (agent pane) chat 메시지 발행 헬퍼.

A4-1: confirm 후 "일정 확정됐습니다" 안내 박스 등 다양한 곳에서 재사용.
DB ChatMessage row 영구 저장 + agent:{room_id} 채널 publish.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis

from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMessage, PaneType, Visibility

logger = logging.getLogger(__name__)

_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


async def emit_agent_message(
    redis_client: Optional[aioredis.Redis],
    room_id: int,
    content: str,
) -> Optional[ChatMessage]:
    """AI 패널에 assistant chat 한 줄 발행 + DB row 영구 저장.

    실패는 caller 트랜잭션을 안 깸 (silent). publish 실패 시 DB는 유지.
    Returns the created ChatMessage on success, None on failure.
    """
    try:
        async with AsyncSessionLocal() as sess:
            msg = ChatMessage(
                pane_type=PaneType.agent,
                role="assistant",
                content=content,
                sender="매듭 AI",
                room_id=room_id,
                user_id=None,
                visibility=Visibility.shared.value,
            )
            sess.add(msg)
            await sess.commit()
            await sess.refresh(msg)
    except Exception:
        logger.warning("emit_agent_message: DB write failed room=%s", room_id, exc_info=True)
        return None

    if redis_client is not None:
        channel = f"agent:{room_id}"
        try:
            payload = json.dumps(
                {
                    "id": msg.id,
                    "pane_type": msg.pane_type if isinstance(msg.pane_type, str) else (msg.pane_type.value if msg.pane_type else "agent"),
                    "role": msg.role,
                    "content": msg.content,
                    "sender": msg.sender,
                    "created_at": msg.created_at.isoformat() if msg.created_at else "",
                    "visibility": msg.visibility,
                    "user_id": msg.user_id,
                },
                ensure_ascii=False,
            )
            await redis_client.publish(channel, payload)
        except Exception:
            logger.warning(
                "emit_agent_message: publish failed room=%s msg_id=%s",
                room_id, msg.id, exc_info=True,
            )

    return msg


def format_korean_meeting_time(dt: datetime) -> str:
    """datetime을 '5월 8일 (금) 오후 6:00' 형식으로 포맷.

    naive datetime KST 가정 (백엔드 컨벤션). %-m / %#m 플랫폼 의존성 없이 직접 조립.
    """
    weekday = _WEEKDAY_KO[dt.weekday()]
    hour = dt.hour
    minute = dt.minute
    am_pm = "오전" if hour < 12 else "오후"
    hour12 = hour % 12 or 12
    if minute == 0:
        time_part = f"{am_pm} {hour12}:00"
    else:
        time_part = f"{am_pm} {hour12}:{minute:02d}"
    return f"{dt.month}월 {dt.day}일 ({weekday}) {time_part}"
