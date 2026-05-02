import asyncio
from contextlib import suppress
import json
import logging
import time
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlmodel import select

from app.api.ws.manager import manager
from app.core.config import settings
from app.core.security import verify_token
from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMessage, PaneType, Visibility
from app.models.room import Room, RoomMember
from app.models.user import User
from app.repositories.messages import MessageReader
from app.services.gemini import call_gemini
from app.services.langgraph_pipeline import extract_meeting_summary, run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


async def _publish_agent_message(
    redis_client: aioredis.Redis | None,
    channel: str,
    message: str,
    *,
    queue_key: str | None = None,
) -> None:
    try:
        if redis_client is not None:
            receivers = await redis_client.publish(channel, message)
            logger.info("Redis publish to %s: %d receivers, msg_len=%d", channel, receivers, len(message))
            if queue_key:
                await redis_client.rpush(queue_key, message)
            return
    except Exception:
        logger.warning("Redis publish failed for agent channel %s", channel, exc_info=True)

    logger.info("Fallback broadcast to %s via manager", channel)
    await manager.broadcast(channel, message)


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
    channels: list[str],
    websocket: WebSocket,
    stop_event: asyncio.Event,
    auto_trigger_queue: asyncio.Queue | None = None,
) -> None:
    """Subscribe multiple Redis pub/sub channels on a single connection.

    docs/ai-separation.md §4.2 — WS subscribes BOTH `agent:{room}` (shared) and
    `agent:{room}:user:{user_id}` (private) so the client receives both streams.
    Ordering across channels is not guaranteed; the client must sort by
    `chat_message.id` (event sequence).
    """
    if not channels:
        return
    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        pubsub = r.pubsub()
        await pubsub.subscribe(*channels)
    except Exception:
        logger.exception("Redis subscriber unavailable for agent channels %s", channels)
        return
    try:
        while not stop_event.is_set():
            try:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.01
                )
            except Exception:
                logger.exception("Redis subscriber read failed for channels %s", channels)
                break
            if msg:
                data = msg["data"]
                try:
                    parsed = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    parsed = None

                try:
                    await websocket.send_text(data)
                except WebSocketDisconnect:
                    break

                # ai_auto_trigger는 shared 채널에서 옴 → auto_trigger_queue로 전달
                if parsed and parsed.get("type") == "ai_auto_trigger" and auto_trigger_queue is not None:
                    await auto_trigger_queue.put(parsed)
            else:
                await asyncio.sleep(0.01)
    finally:
        for ch in channels:
            with suppress(Exception):
                await pubsub.unsubscribe(ch)
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
        token_payload = verify_token(token)
    except Exception:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    # 룸 멤버십 확인
    try:
        room_pk_check = int(room_id)
        user_id_check = int(token_payload["sub"])
        async with AsyncSessionLocal() as _session:
            member_result = await _session.execute(
                select(RoomMember).where(
                    RoomMember.room_id == room_pk_check,
                    RoomMember.user_id == user_id_check,
                )
            )
            if member_result.scalar_one_or_none() is None:
                await websocket.close(code=4003, reason="Not a member of this room")
                return
    except (TypeError, ValueError):
        await websocket.close(code=4003, reason="Invalid room_id")
        return

    stop_event = asyncio.Event()
    # docs/ai-separation.md §4.1 — 채널 분리
    shared_channel = f"agent:{room_id}"
    user_channel = f"agent:{room_id}:user:{user_id_check}"
    # 이전 코드와의 호환을 위해 channel 변수는 유지 (기본 발행 채널 = shared)
    channel = shared_channel
    auto_trigger_queue: asyncio.Queue = asyncio.Queue()
    manager.add(shared_channel, websocket)
    manager.add(user_channel, websocket)
    subscriber_task = asyncio.create_task(
        _redis_subscriber(
            [shared_channel, user_channel],
            websocket,
            stop_event,
            auto_trigger_queue,
        )
    )

    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception:
        logger.exception("Redis client unavailable for agent room %s", room_id)
        r = None

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

    # ── 소셜 채팅에서 감지된 의도를 자동으로 파이프라인에 전달하는 백그라운드 태스크 ──
    _last_auto_trigger_time: float = 0.0
    _AUTO_TRIGGER_DEBOUNCE_SECONDS = 60.0

    async def _process_auto_triggers() -> None:
        nonlocal _last_auto_trigger_time
        while not stop_event.is_set():
            try:
                trigger = await asyncio.wait_for(auto_trigger_queue.get(), timeout=0.5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                continue
            except Exception:
                break

            trigger_content = trigger.get("content", "")
            trigger_intent = trigger.get("intent", "")
            if not trigger_content:
                continue

            # room-singleton lock (Phase 3 eng review §3.4):
            # N users connected = N subscribers to shared channel, all dequeue the trigger.
            # Redis SET NX picks one winner per room; others skip pipeline execution so the
            # AI doesn't run N times per auto-trigger.
            nx_key = f"nx_autotrigger:{room_id}"
            acquired = False
            if r is not None:
                try:
                    acquired = bool(
                        await r.set(
                            nx_key, str(user_id_check), nx=True, ex=int(_AUTO_TRIGGER_DEBOUNCE_SECONDS)
                        )
                    )
                except Exception:
                    logger.warning("Auto-trigger NX lock failed", exc_info=True)
                    acquired = False
            if not acquired:
                logger.debug(
                    "Auto-trigger skipped for room %s user %s (another WS holds the lock)",
                    room_id, user_id_check,
                )
                continue

            # Local debounce as a belt-and-suspenders guard (same-connection dup)
            now = time.monotonic()
            if now - _last_auto_trigger_time < _AUTO_TRIGGER_DEBOUNCE_SECONDS:
                logger.debug(
                    "Auto-trigger local-debounced for room %s (%.1fs since last)",
                    room_id,
                    now - _last_auto_trigger_time,
                )
                continue
            _last_auto_trigger_time = now

            # 소셜 채팅 기반 모임 요약 추출 및 발행
            try:
                async with AsyncSessionLocal() as session:
                    summary = await extract_meeting_summary(room_id, session)
                if summary and any(summary.get(k) for k in ("date", "place", "headcount", "type")):
                    await _publish_agent_message(
                        r,
                        channel,
                        json.dumps(
                            {
                                "type": "meeting_summary",
                                "date": summary.get("date"),
                                "place": summary.get("place"),
                                "headcount": summary.get("headcount"),
                                "meeting_type": summary.get("type"),
                                "notes": summary.get("notes", []),
                            },
                            ensure_ascii=False,
                        ),
                    )
            except Exception:
                logger.warning("Meeting summary extraction failed for room %s", room_id, exc_info=True)

            # 의도에 맞는 프롬프트 생성
            if trigger_intent == "meeting_schedule":
                prompt = f"채팅방에서 모임 일정 관련 대화가 감지되었어요: \"{trigger_content}\"\n모임 일정 조율을 시작해줘"
            elif trigger_intent == "place_suggestion":
                prompt = f"채팅방에서 장소 관련 대화가 감지되었어요: \"{trigger_content}\"\n장소 추천을 시작해줘"
            else:
                continue

            try:
                room_pk_val = int(room_id)
            except (TypeError, ValueError):
                room_pk_val = None

            # 사용자 메시지를 DB에 저장 (자동 트리거로 생성된 메시지 → 공용)
            async with AsyncSessionLocal() as session:
                auto_msg = ChatMessage(
                    pane_type=PaneType.agent,
                    role="user",
                    content=prompt,
                    sender="system",
                    room_id=room_pk_val,
                    user_id=None,
                    visibility=Visibility.shared.value,
                )
                session.add(auto_msg)
                await session.commit()
                await session.refresh(auto_msg)

            # 파이프라인 실행 (auto-trigger → shared 시야)
            try:
                async with AsyncSessionLocal() as session:
                    context = await MessageReader.load_agent_context(
                        session=session,
                        room_id=room_pk_val,
                        viewer_user_id=None,  # auto-trigger: shared-only view
                    )

                    result = await run_pipeline(
                        room_id, context, session, slot_context=slot_context
                    )

                # 슬롯 컨텍스트 업데이트
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
                    "missing_slots",
                ):
                    if result.get(key) is not None:
                        slot_context[key] = result[key]

                slot_context["message_count_since_last_trigger"] = 0

                # 어시스턴트 응답 메시지 발행
                for new_msg in result.get("new_assistant_messages", []):
                    await _publish_agent_message(
                        r,
                        channel,
                        json.dumps(new_msg, ensure_ascii=False),
                    )

                # 투표 카드 등 추가 페이로드 발행
                vote_card_payload = result.get("vote_card_payload")
                if vote_card_payload:
                    await _publish_agent_message(
                        r,
                        channel,
                        json.dumps(
                            {"type": "vote_card", **vote_card_payload},
                            ensure_ascii=False,
                        ),
                    )

                place_recommendation_payload = result.get("place_recommendation_payload")
                if place_recommendation_payload:
                    await _publish_agent_message(
                        r,
                        channel,
                        json.dumps(
                            {"type": "place_recommendation", **place_recommendation_payload},
                            ensure_ascii=False,
                        ),
                    )

                maedeup_card_payload = result.get("maedeup_card_payload")
                if maedeup_card_payload:
                    await _publish_agent_message(
                        r,
                        channel,
                        json.dumps(
                            {"type": "maedeup_card", **maedeup_card_payload},
                            ensure_ascii=False,
                        ),
                    )

            except Exception:
                logger.exception("Auto-trigger pipeline failed for room %s", room_id)

    auto_trigger_task = asyncio.create_task(_process_auto_triggers())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # ── slot_select 구조화 메시지 처리 (LLM 파이프라인 우회) ──
            if payload.get("type") == "slot_select":
                action = payload.get("action")
                if action == "confirm_date":
                    # 날짜 확정 → 슬롯 컨텍스트에 저장하고 확인 메시지 발행
                    slot_context["confirmed_date"] = payload.get("date")
                    ack_payload = {
                        "type": "slot_select_ack",
                        "action": "confirm_date",
                        "date": payload.get("date"),
                    }
                    await _publish_agent_message(
                        r, user_channel, json.dumps(ack_payload, ensure_ascii=False),
                    )
                elif action == "confirm_time":
                    # 시간 확정 → 슬롯 컨텍스트 저장 후 장소 추천 파이프라인 실행
                    slot_context["confirmed_time"] = payload.get("time")
                    slot_context["confirmed_date"] = payload.get("date") or slot_context.get("confirmed_date")

                    try:
                        room_pk_val = int(room_id)
                    except (TypeError, ValueError):
                        room_pk_val = None

                    synthetic_content = "일정이 확정되었습니다. 장소를 추천해주세요"
                    async with AsyncSessionLocal() as session:
                        synth_msg = ChatMessage(
                            pane_type=PaneType.agent,
                            role="user",
                            content=synthetic_content,
                            sender="system",
                            room_id=room_pk_val,
                            user_id=user_id_check,
                            visibility=Visibility.private.value,
                        )
                        session.add(synth_msg)
                        await session.commit()
                        await session.refresh(synth_msg)

                    async with AsyncSessionLocal() as session:
                        context = await MessageReader.load_agent_context(
                            session=session,
                            room_id=room_pk_val,
                            viewer_user_id=user_id_check,
                        )

                        result = await run_pipeline(
                            room_id, context, session, slot_context=slot_context
                        )

                    # 슬롯 컨텍스트 업데이트
                    for key in (
                        "slot_filling_turns", "date_hint", "place_hint", "place_coord",
                        "confirmed_date", "confirmed_time", "confirmed_place",
                        "headcount", "meeting_type", "default_place_hint",
                        "conversation_summary", "missing_slots",
                    ):
                        if result.get(key) is not None:
                            slot_context[key] = result[key]

                    for new_msg in result.get("new_assistant_messages", []):
                        await _publish_agent_message(
                            r, user_channel, json.dumps(new_msg, ensure_ascii=False),
                        )

                    place_recommendation_payload = result.get("place_recommendation_payload")
                    if place_recommendation_payload:
                        # 모임 차원 카드는 방 전체 공유 (private→private이면 다른 멤버가 못 봄).
                        await _publish_agent_message(
                            r, shared_channel,
                            json.dumps(
                                {"type": "place_recommendation", **place_recommendation_payload},
                                ensure_ascii=False,
                            ),
                        )

                    maedeup_card_payload = result.get("maedeup_card_payload")
                    if maedeup_card_payload:
                        await _publish_agent_message(
                            r, shared_channel,
                            json.dumps(
                                {"type": "maedeup_card", **maedeup_card_payload},
                                ensure_ascii=False,
                            ),
                        )
                continue

            role = payload.get("role", "user")
            content = payload.get("content", "")
            sender = payload.get("sender")

            # 메시지 길이 제한 (2000자)
            if len(content) > 2000:
                content = content[:2000]

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
                    user_id=user_id_check,
                    visibility=Visibility.private.value,
                )
                session.add(msg)
                await session.commit()
                await session.refresh(msg)

            out = json.dumps(
                {
                    "id": msg.id,
                    "pane_type": msg.pane_type,
                    "role": msg.role,
                    "content": msg.content,
                    "sender": msg.sender,
                    "created_at": msg.created_at.isoformat(),
                    "user_id": msg.user_id,
                    "visibility": msg.visibility,
                    "shared_from_id": msg.shared_from_id,
                    "shared_by_user_id": msg.shared_by_user_id,
                }
            )
            await _publish_agent_message(
                r,
                user_channel,
                out,
                queue_key=f"agent_queue:{room_id}:user:{user_id_check}",
            )

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
                        summary_context = await MessageReader.load_agent_context(
                            session=session,
                            room_id=room_pk,
                            viewer_user_id=user_id_check,
                            limit=10,
                        )
                    summary = await _build_conversation_summary(
                        summary_context.messages
                    )
                    if summary:
                        slot_context["conversation_summary"] = summary

                # AI 패널에서 직접 보낸 메시지는 항상 파이프라인 실행
                # (사용자가 명시적으로 AI에게 말한 것이므로 debounce 없음)
                if not content.strip():
                    continue

                # "취소", "다시", "리셋" 키워드 감지 → 슬롯 컨텍스트 초기화
                _reset_keywords = ("취소", "다시 해", "다시해", "처음부터", "리셋", "초기화")
                if any(kw in content for kw in _reset_keywords):
                    slot_context.update({
                        "slot_filling_turns": 0,
                        "date_hint": None,
                        "place_hint": None,
                        "place_coord": None,
                        "confirmed_date": None,
                        "confirmed_time": None,
                        "confirmed_place": None,
                        "headcount": None,
                        "meeting_type": None,
                        "message_count_since_last_trigger": 0,
                        "default_place_hint": slot_context.get("default_place_hint") or "서울 강남",
                    })

                async with AsyncSessionLocal() as session:
                    context = await MessageReader.load_agent_context(
                        session=session,
                        room_id=room_pk,
                        viewer_user_id=user_id_check,
                    )

                    result = await run_pipeline(
                        room_id, context, session, slot_context=slot_context
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
                    "missing_slots",
                ):
                    if result.get(key) is not None:
                        slot_context[key] = result[key]

                slot_context["message_count_since_last_trigger"] = 0

                logger.info(
                    "Pipeline result: status=%s, new_msgs=%d, intent=%s",
                    result.get("status"),
                    len(result.get("new_assistant_messages", [])),
                    result.get("intent"),
                )

                # 파이프라인이 발행한 어시스턴트 메시지(슬롯 질문, 오류, 일반 응답 등) — user 전용
                for new_msg in result.get("new_assistant_messages", []):
                    await _publish_agent_message(
                        r,
                        user_channel,
                        json.dumps(new_msg, ensure_ascii=False),
                    )

                # awaiting_user_reply 시 슬롯 컨텍스트만 유지하고 다음 메시지 대기
                if result.get("awaiting_user_reply") is True:
                    continue

                # location_first: 장소 추천 페이로드를 먼저 발행 후 슬롯 컨텍스트 유지 (private)
                if result.get("is_location_first") and not result.get("date_hint"):
                    place_recommendation_payload = result.get("place_recommendation_payload")
                    if place_recommendation_payload:
                        await _publish_agent_message(
                            r,
                            user_channel,
                            json.dumps(
                                {
                                    "type": "place_recommendation",
                                    **place_recommendation_payload,
                                },
                                ensure_ascii=False,
                            ),
                        )
                    continue

                # 부분 정보만 확인된 경우 → 슬롯 컨텍스트 유지하고 다음 대화 대기
                if result.get("status") in ("partial_info_acknowledged", "no_slots_yet"):
                    continue

                # 파이프라인 완료 시 슬롯 컨텍스트 초기화
                slot_context.update({
                    "slot_filling_turns": 0,
                    "date_hint": None,
                    "place_hint": None,
                    "place_coord": None,
                    "confirmed_date": None,
                    "confirmed_time": None,
                    "confirmed_place": None,
                    "default_place_hint": slot_context.get("default_place_hint") or "서울 강남",
                    "headcount": None,
                    "meeting_type": None,
                    "message_count_since_last_trigger": 0,
                })

                vote_card_payload = result.get("vote_card_payload")
                if vote_card_payload:
                    # 모임 일정 투표는 방 전체 공유 — 방장 혼자 본다면 투표 자체가 성립 안 함.
                    await _publish_agent_message(
                        r,
                        shared_channel,
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
                        await _publish_agent_message(
                            r,
                            f"social:{room_id}",
                            json.dumps(
                                {
                                    "id": social_msg.id,
                                    "pane_type": social_msg.pane_type,
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
                    # 장소 추천도 모임 전체 공유 — 모두가 보고 선택에 참고해야 함.
                    await _publish_agent_message(
                        r,
                        shared_channel,
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
                    # 최종 매듭 카드도 공유.
                    await _publish_agent_message(
                        r,
                        shared_channel,
                        json.dumps(
                            {"type": "maedeup_card", **maedeup_card_payload},
                            ensure_ascii=False,
                        ),
                    )

    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        with suppress(Exception):
            await subscriber_task
        with suppress(Exception, asyncio.CancelledError):
            auto_trigger_task.cancel()
            await auto_trigger_task
        manager.remove(shared_channel, websocket)
        manager.remove(user_channel, websocket)
        if r is not None:
            await r.aclose()
