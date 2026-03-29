import asyncio
import json
import logging
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.api.ws.manager import manager
from app.core.config import settings
from app.core.security import verify_token
from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMessage, PaneType
from app.services.gemini import call_gemini

logger = logging.getLogger(__name__)
router = APIRouter()


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


@router.websocket("/ws/agent/{room_id}")
async def agent_ws(
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
    channel = f"agent:{room_id}"
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
                    pane_type=PaneType.agent,
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
            await r.rpush(f"agent_queue:{room_id}", out)

            logger.warning(f"[AGENT] role={role}, has_key={bool(settings.GEMINI_API_KEY)}")
            if role == "user" and settings.GEMINI_API_KEY:
                logger.warning(f"[AGENT] Calling Gemini for message: {content[:50]}")
                ai_text = await call_gemini(content)
                logger.warning(f"[AGENT] Gemini response: {ai_text[:50]}")

                async with AsyncSessionLocal() as session:
                    ai_msg = ChatMessage(
                        pane_type=PaneType.agent,
                        role="assistant",
                        content=ai_text,
                        sender="AI 어시스턴트",
                    )
                    session.add(ai_msg)
                    await session.commit()
                    await session.refresh(ai_msg)

                ai_out = json.dumps({
                    "id": ai_msg.id,
                    "pane_type": ai_msg.pane_type.value,
                    "role": ai_msg.role,
                    "content": ai_msg.content,
                    "sender": ai_msg.sender,
                    "created_at": ai_msg.created_at.isoformat(),
                })
                await r.publish(channel, ai_out)

    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        await subscriber_task
        manager.remove(room_id, websocket)
        await r.aclose()
