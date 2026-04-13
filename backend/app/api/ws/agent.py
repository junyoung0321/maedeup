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
from app.models.room import Room
from app.models.user import User
from app.services.gemini import call_gemini
from app.services.intent_classifier import classify_intent
from app.services.langgraph_pipeline import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()
MEETING_RELATED_INTENTS = {"meeting_schedule", "place_suggestion"}


async def _build_conversation_summary(messages: list[ChatMessage]) -> str:
    recent_text = "\n".join(
        f"{message.role}: {message.content.strip()}"
        for message in messages
        if message.content and message.content.strip()
    )
    if not recent_text:
        return ""

    prompt = (
        "다음 대화에서 모임 관련 핵심 정보(결정사항, 장소, 일정, 인원)만 3문장으로 요약해줘: "
        f"{recent_text}"
    )
    return (await call_gemini(prompt)).strip()


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

    # 슬롯 필링 상태 – 연결 세션 내에서 유지
    slot_context: dict = {
        "slot_filling_turns": 0,
        "date_hint": None,
        "place_hint": None,
        "place_coord": None,
        "confirmed_date": None,
        "confirmed_time": None,
        "confirmed_place": None,
        "headcount": None,
        "meeting_type": None,
        "default_place_hint": "서울 강남",
        "message_count_since_last_trigger": 0,
        "total_message_count": 0,
        "conversation_summary": "",
    }

    if room_id.isdigit():
        async with AsyncSessionLocal() as session:
            room = await session.get(Room, int(room_id))
            owner = await session.get(User, room.created_by) if room else None
            slot_context["default_place_hint"] = (
                owner.home_base.strip()
                if owner and owner.home_base and owner.home_base.strip()
                else "서울 강남"
            )

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
                slot_context["message_count_since_last_trigger"] = int(
                    slot_context.get("message_count_since_last_trigger") or 0
                ) + 1
                slot_context["total_message_count"] = int(
                    slot_context.get("total_message_count") or 0
                ) + 1

                if (
                    int(slot_context.get("total_message_count") or 0) > 10
                    and int(slot_context.get("total_message_count") or 0) % 10 == 0
                ):
                    async with AsyncSessionLocal() as session:
                        summary_messages_result = await session.execute(
                            select(ChatMessage)
                            .where(ChatMessage.room_id == room_pk)
                            .where(ChatMessage.pane_type == PaneType.agent)
                            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                            .limit(10)
                        )
                        summary_messages = list(
                            reversed(summary_messages_result.scalars().all())
                        )
                    summary = await _build_conversation_summary(summary_messages)
                    if summary:
                        slot_context["conversation_summary"] = summary

                should_run_pipeline = False
                if int(slot_context.get("slot_filling_turns") or 0) > 0:
                    should_run_pipeline = True
                elif content.strip():
                    intent_result = await classify_intent(content)
                    is_meeting_related = (
                        intent_result.get("intent") in MEETING_RELATED_INTENTS
                        and float(intent_result.get("confidence", 0.0)) >= 0.7
                    )
                    should_run_pipeline = (
                        is_meeting_related
                        and int(slot_context.get("message_count_since_last_trigger") or 0) >= 3
                    )

                if not should_run_pipeline:
                    continue

                async with AsyncSessionLocal() as session:
                    recent_messages_result = await session.execute(
                        select(ChatMessage)
                        .where(ChatMessage.room_id == room_pk)
                        .where(ChatMessage.pane_type == PaneType.agent)
                        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                        .limit(20)
                    )
                    recent_messages = list(reversed(recent_messages_result.scalars().all()))

                    result = await run_pipeline(
                        room_id, recent_messages, session, slot_context=slot_context
                    )

                # 슬롯 컨텍스트 업데이트 (다음 메시지에서 이어받기)
                for key in (
                    "slot_filling_turns",
                    "date_hint",
                    "place_hint",
                    "place_coord",
                    "confirmed_date",
                    "confirmed_time",
                    "confirmed_place",
                    "headcount",
                    "meeting_type",
                    "default_place_hint",
                    "conversation_summary",
                ):
                    if result.get(key) is not None:
                        slot_context[key] = result[key]

                slot_context["message_count_since_last_trigger"] = 0

                # 파이프라인이 발행한 어시스턴트 메시지(슬롯 질문, 오류, 일반 응답 등) Redis 발행
                for new_msg in result.get("new_assistant_messages", []):
                    await r.publish(channel, json.dumps(new_msg, ensure_ascii=False))

                # awaiting_user_reply 시 슬롯 컨텍스트만 유지하고 다음 메시지 대기
                if result.get("awaiting_user_reply") is True:
                    continue

                if result.get("is_location_first") and not result.get("date_hint"):
                    continue

                # 파이프라인 완료 시 슬롯 컨텍스트 초기화
                slot_context.update({
                    "slot_filling_turns": 0,
                    "date_hint": None,
                    "place_hint": None,
                    "place_coord": None,
                    "default_place_hint": slot_context.get("default_place_hint") or "서울 강남",
                    "headcount": None,
                    "meeting_type": None,
                    "message_count_since_last_trigger": 0,
                })

                vote_card_payload = result.get("vote_card_payload")
                if vote_card_payload:
                    await r.publish(
                        channel,
                        json.dumps(
                            {"type": "vote_card", **vote_card_payload},
                            ensure_ascii=False,
                        ),
                    )
                    blocker_notification_payload = result.get("blocker_notification_payload")
                    if blocker_notification_payload:
                        async with AsyncSessionLocal() as session:
                            social_msg = ChatMessage(
                                pane_type=PaneType.social,
                                role="system",
                                content=str(blocker_notification_payload.get("content", "")),
                                sender=str(blocker_notification_payload.get("sender", "매듭이")),
                                room_id=room_pk,
                            )
                            session.add(social_msg)
                            await session.commit()
                            await session.refresh(social_msg)
                        await r.publish(
                            f"social:{room_id}",
                            json.dumps(
                                {
                                    "id": social_msg.id,
                                    "pane_type": social_msg.pane_type.value,
                                    "role": social_msg.role,
                                    "content": social_msg.content,
                                    "sender": social_msg.sender,
                                    "created_at": social_msg.created_at.isoformat(),
                                },
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

    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        await subscriber_task
        manager.remove(room_id, websocket)
        await r.aclose()
