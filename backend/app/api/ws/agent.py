import asyncio
import json
import logging
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlmodel import select

from app.api.ws.manager import manager
from app.core.config import settings
from app.core.security import verify_token
from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMessage, PaneType
from app.services.langgraph_pipeline import run_pipeline

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

            try:
                room_pk = int(room_id)
            except (TypeError, ValueError):
                room_pk = None

            async with AsyncSessionLocal() as session:
                msg = ChatMessage(
                    pane_type=PaneType.agent,
                    role=role,
                    content=content,
                    sender=sender,
                    room_id=room_pk,
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

            if role == "user":
                async with AsyncSessionLocal() as session:
                    recent_messages_result = await session.execute(
                        select(ChatMessage)
                        .where(ChatMessage.room_id == room_pk)
                        .where(ChatMessage.pane_type == PaneType.agent)
                        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                        .limit(20)
                    )
                    recent_messages = list(reversed(recent_messages_result.scalars().all()))

                    result = await run_pipeline(room_id, recent_messages, session)

                vote_card_payload = result.get("vote_card_payload")
                if vote_card_payload:
                    await r.publish(
                        channel,
                        json.dumps(
                            {"type": "vote_card", **vote_card_payload},
                            ensure_ascii=False,
                        ),
                    )

                place_recommendation_payload = result.get("place_recommendation_payload")
                if place_recommendation_payload:
                    await r.publish(
                        channel,
                        json.dumps(
                            {
                                "type": "place_recommendation",
                                **place_recommendation_payload,
                            },
                            ensure_ascii=False,
                        ),
                    )

                maedeup_card_payload = result.get("maedeup_card_payload")
                if maedeup_card_payload:
                    await r.publish(
                        channel,
                        json.dumps(
                            {"type": "maedeup_card", **maedeup_card_payload},
                            ensure_ascii=False,
                        ),
                    )

                if result.get("awaiting_user_reply") is True:
                    continue

    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        await subscriber_task
        manager.remove(room_id, websocket)
        await r.aclose()
