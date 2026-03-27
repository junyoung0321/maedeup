import asyncio
import json
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.api.ws.manager import manager
from app.core.config import settings
from app.core.security import verify_token
from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMessage, PaneType
from app.services.gemini import gemini_service

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


def _serialize(msg: ChatMessage) -> str:
    return json.dumps(
        {
            "id": msg.id,
            "pane_type": msg.pane_type.value,
            "role": msg.role,
            "content": msg.content,
            "sender": msg.sender,
            "created_at": msg.created_at.isoformat(),
        }
    )


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

            # 1. 사용자 메시지 저장 & 브로드캐스트
            async with AsyncSessionLocal() as session:
                user_msg = ChatMessage(
                    pane_type=PaneType.agent,
                    role=role,
                    content=content,
                    sender=sender,
                )
                session.add(user_msg)
                await session.commit()
                await session.refresh(user_msg)

            await r.publish(channel, _serialize(user_msg))
            await r.rpush(f"agent_queue:{room_id}", _serialize(user_msg))

            # 2. user 메시지일 때만 Gemini 호출
            if role == "user" and settings.GEMINI_API_KEY:
                # 로딩 신호 전송
                loading_signal = json.dumps({"type": "loading", "room_id": room_id})
                await r.publish(channel, loading_signal)

                try:
                    ai_text = await gemini_service.chat(content)
                except Exception as e:
                    ai_text = f"[AI 오류] {e}"

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

                await r.publish(channel, _serialize(ai_msg))
                await r.rpush(f"agent_queue:{room_id}", _serialize(ai_msg))

    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        await subscriber_task
        manager.remove(room_id, websocket)
        await r.aclose()
