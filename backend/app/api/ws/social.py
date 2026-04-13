import asyncio
import json
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.api.ws.manager import manager
from app.core.config import settings
from app.core.security import verify_token
from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMessage, PaneType
from app.services.intent_classifier import classify_intent

router = APIRouter()

# 의도 감지 알림을 트리거할 의도 목록
_NOTIFIABLE_INTENTS = {"meeting_schedule", "place_suggestion"}


async def _redis_subscriber(
    channel: str,
    websocket: WebSocket,
    stop_event: asyncio.Event,
) -> None:
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        while not stop_event.is_set():
            msg = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=0.01
            )
            if msg:
                await websocket.send_text(msg["data"])
            else:
                await asyncio.sleep(0.01)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await r.aclose()


@router.websocket("/ws/social/{room_id}")
async def social_ws(
    websocket: WebSocket,
    room_id: str,
    token: Optional[str] = Query(default=None),
) -> None:
    await websocket.accept()

    # 토큰 검증
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return
    try:
        verify_token(token)
    except Exception:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    manager.add(room_id, websocket)

    stop_event = asyncio.Event()
    channel = f"social:{room_id}"
    subscriber_task = asyncio.create_task(
        _redis_subscriber(channel, websocket, stop_event)
    )

    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)

            role = payload.get("role", "user")
            content = payload.get("content", "")
            sender = payload.get("sender")

            async with AsyncSessionLocal() as session:
                msg = ChatMessage(
                    pane_type=PaneType.social,
                    role=role,
                    content=content,
                    sender=sender,
                )
                session.add(msg)
                await session.commit()
                await session.refresh(msg)

            out = json.dumps(
                {
                    "id": msg.id,
                    "pane_type": msg.pane_type.value,
                    "role": msg.role,
                    "content": msg.content,
                    "sender": msg.sender,
                    "created_at": msg.created_at.isoformat(),
                }
            )
            await r.publish(channel, out)

            # ── 의도 감지 (백그라운드로 실행해 응답 지연 최소화) ──────────
            if settings.GEMINI_API_KEY and role == "user" and content.strip():
                asyncio.create_task(
                    _detect_and_notify_intent(r, channel, content, msg.id)
                )

    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        await subscriber_task
        manager.remove(room_id, websocket)
        await r.aclose()


async def _detect_and_notify_intent(
    r: aioredis.Redis,
    channel: str,
    content: str,
    trigger_message_id: int,
) -> None:
    """
    메시지 의도를 분류하고, 모임/장소 관련 의도가 감지되면
    같은 채널에 intent_detected 이벤트를 발행합니다.
    """
    try:
        result = await classify_intent(content)
        if result["intent"] in _NOTIFIABLE_INTENTS:
            event = json.dumps(
                {
                    "type": "intent_detected",
                    "intent": result["intent"],
                    "confidence": result["confidence"],
                    "method": result["method"],
                    "trigger_message_id": trigger_message_id,
                }
            )
            await r.publish(channel, event)
    except Exception:
        # 의도 감지 실패는 채팅 흐름에 영향을 주지 않도록 무시
        pass
