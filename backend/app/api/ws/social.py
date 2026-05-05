import asyncio
from contextlib import suppress
import json
import logging
import re
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlmodel import select

from app.api.ws.manager import manager
from app.core.config import settings
from app.core.security import verify_token
from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMessage, PaneType
from app.models.room import Room, RoomMember
from app.models.user import User
from app.services import scheduling_round as sr
from app.services.finalization_reason import generate_finalization_reason
from app.services.intent_classifier import classify_intent
from app.services.stalemate_judge import judge_stalemate

router = APIRouter()
logger = logging.getLogger(__name__)

# 의도 감지 알림을 트리거할 의도 목록
_NOTIFIABLE_INTENTS = {"meeting_schedule", "place_suggestion"}


async def _maybe_emit_proposal(
    redis_client: aioredis.Redis,
    *,
    room_pk: int,
    user_id: int,
    date: Optional[str],
    start: Optional[int],
    end: Optional[int],
    channel: str,
    skip_record: bool = False,
) -> None:
    """
    Update the caller's availability, then check if the room has a majority
    on any slot. If yes (and the snapshot is novel), create a proposal and
    broadcast it to the room.

    All failure paths are logged but non-fatal — the peer_time_selection
    broadcast must keep working even if this aggregation is down.

    `skip_record=True` bypasses availability write — used when re-aggregating
    after a pure unavailability change (no time selection to record).
    """
    if not skip_record:
        await sr.record_availability(
            redis_client,
            room_id=room_pk,
            user_id=user_id,
            date=date,
            start=start,
            end=end,
        )

    # We need the room host + eligible voter count to build a proposal.
    async with AsyncSessionLocal() as session:
        room_row = await session.execute(select(Room).where(Room.id == room_pk))
        room = room_row.scalar_one_or_none()
        if room is None:
            return
        member_row = await session.execute(
            select(RoomMember).where(RoomMember.room_id == room_pk)
        )
        member_count = len(member_row.scalars().all())

    if member_count <= 0:
        return

    availability = await sr.load_room_availability(redis_client, room_id=room_pk)
    if not availability:
        return

    # 전원 시간대 선택 완료 체크: availability에 등록된 수 >= 멤버 수
    if len(availability) < member_count:
        return

    # 중복 트리거 방지: 같은 availability 스냅샷이면 스킵
    snapshot_hash = sr.compute_snapshot_hash(availability)
    nx_key = f"schedule_auto_trigger:{room_pk}:{snapshot_hash}"
    already = await redis_client.set(nx_key, "1", ex=300, nx=True)
    if not already:
        return

    # 전원 선택 완료 → agent 채널로 AI 파이프라인 자동 트리거
    agent_channel = f"agent:{room_pk}"
    trigger_payload = json.dumps(
        {
            "type": "ai_auto_trigger",
            "intent": "meeting_schedule",
            "confidence": 1.0,
            "content": "모두 시간대를 선택했어요. 일정을 조율해볼게요!",
            "trigger_reason": "all_members_selected",
        },
        ensure_ascii=False,
    )
    await redis_client.publish(agent_channel, trigger_payload)
    logger.info("Auto-triggered schedule recommendation for room %s (all %d members selected)", room_pk, member_count)


async def _publish_social_message(
    redis_client: aioredis.Redis | None,
    channel: str,
    message: str,
) -> None:
    try:
        if redis_client is not None:
            await redis_client.publish(channel, message)
            return
    except Exception:
        logger.warning("Redis publish failed for social channel %s", channel, exc_info=True)

    await manager.broadcast(channel, message)


async def _redis_subscriber(
    channel: str,
    websocket: WebSocket,
    stop_event: asyncio.Event,
) -> None:
    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
    except Exception:
        logger.exception("Redis subscriber unavailable for social channel %s", channel)
        return
    try:
        while not stop_event.is_set():
            try:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.01
                )
            except Exception:
                logger.exception("Redis subscriber read failed for social channel %s", channel)
                break
            if msg:
                data = msg["data"]
                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    try:
                        await websocket.send_text(data)
                    except WebSocketDisconnect:
                        break
                    continue

                try:
                    if parsed.get("type") in ("reminder", "vote_reminder"):
                        await websocket.send_text(json.dumps(parsed, ensure_ascii=False))
                    else:
                        await websocket.send_text(data)
                except WebSocketDisconnect:
                    break
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
        token_payload = verify_token(token)
    except Exception:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    try:
        room_pk: Optional[int] = int(room_id)
    except (TypeError, ValueError):
        room_pk = None

    # 룸 멤버십 + 인증된 사용자 이름 확인 (클라이언트 payload의 sender 스푸핑 방지)
    authed_user_id: int | None = None
    authed_user_name: str = ""
    if room_pk is not None:
        try:
            user_id_check = int(token_payload["sub"])
            async with AsyncSessionLocal() as _session:
                member_result = await _session.execute(
                    select(RoomMember).where(
                        RoomMember.room_id == room_pk,
                        RoomMember.user_id == user_id_check,
                    )
                )
                if member_result.scalar_one_or_none() is None:
                    await websocket.close(code=4003, reason="Not a member of this room")
                    return
                user_result = await _session.execute(
                    select(User).where(User.id == user_id_check)
                )
                user_row = user_result.scalar_one_or_none()
                if user_row is not None:
                    authed_user_id = user_row.id
                    authed_user_name = user_row.name or ""
        except (TypeError, ValueError):
            await websocket.close(code=4003, reason="Invalid user token")
            return
    else:
        await websocket.close(code=4003, reason="Invalid room_id")
        return

    stop_event = asyncio.Event()
    channel = f"social:{room_id}"
    manager.add(channel, websocket)
    subscriber_task = asyncio.create_task(
        _redis_subscriber(channel, websocket, stop_event)
    )

    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception:
        logger.exception("Redis client unavailable for social room %s", room_id)
        r = None

    # 접속 직후 현재 불가능 날짜 + TimeBar 선택 스냅샷을 이 소켓에만 전달
    # (새로고침/재접속 복구).
    if r is not None:
        try:
            unavail_snap = await sr.load_room_unavailability(r, room_id=room_pk)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "unavailable_snapshot",
                        "by_user": {str(uid): dates for uid, dates in unavail_snap.items()},
                    },
                    ensure_ascii=False,
                )
            )
        except Exception:
            logger.debug("unavailable_snapshot push failed room=%s", room_id, exc_info=True)

        try:
            avail_snap = await sr.load_room_availability(r, room_id=room_pk)
            # load_room_availability는 {uid: [{date, start, end}]} 형태.
            # 현재 스키마상 user당 하나의 entry — 첫 원소만 추출해 단순 dict로 내려보냄.
            simplified: dict[str, dict] = {}
            for uid, entries in avail_snap.items():
                if entries and isinstance(entries[0], dict):
                    simplified[str(uid)] = entries[0]
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "availability_snapshot",
                        "by_user": simplified,
                    },
                    ensure_ascii=False,
                )
            )
        except Exception:
            logger.debug("availability_snapshot push failed room=%s", room_id, exc_info=True)

        try:
            date_snap = await sr.load_room_date_selections(r, room_id=room_pk)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "date_selection_snapshot",
                        "by_user": {str(uid): d for uid, d in date_snap.items()},
                    },
                    ensure_ascii=False,
                )
            )
        except Exception:
            logger.debug("date_selection_snapshot push failed room=%s", room_id, exc_info=True)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = payload.get("type")

            # ── 시간 선택 공유 이벤트: When2Meet 스타일, DB 저장 없이 broadcast ─
            if msg_type == "time_selection":
                raw_date = payload.get("date")
                date_value: str | None = None
                if isinstance(raw_date, str) and len(raw_date) == 10:
                    if raw_date[4] == "-" and raw_date[7] == "-":
                        date_value = raw_date
                # slot 범위는 0..TIME_SLOT_MAX-1 (30분 단위, 9~22시 기준 총 26개). 프론트와 동일.
                TIME_SLOT_MAX = 26
                raw_start = payload.get("start")
                raw_end = payload.get("end")

                def _to_slot(v: object) -> int | None:
                    # bool은 int의 서브클래스라 먼저 차단 (True→1, False→0 실수 방지)
                    if isinstance(v, bool):
                        return None
                    if not isinstance(v, (int, float)):
                        return None
                    if isinstance(v, float) and (v != v):  # NaN 방어
                        return None
                    iv = int(v)
                    if iv < 0 or iv >= TIME_SLOT_MAX:
                        return None
                    return iv

                start_value = _to_slot(raw_start)
                end_value = _to_slot(raw_end)
                # start/end 둘 중 하나만 유효하거나 역순이면 해제로 간주
                if start_value is None or end_value is None:
                    start_value = None
                    end_value = None
                elif start_value > end_value:
                    start_value, end_value = end_value, start_value

                out = json.dumps(
                    {
                        "type": "peer_time_selection",
                        "user_id": authed_user_id,
                        "sender": authed_user_name,
                        "date": date_value,
                        "start": start_value,
                        "end": end_value,
                    },
                    ensure_ascii=False,
                )
                await _publish_social_message(r, channel, out)

                # ── Server-side availability aggregation + majority detector ──
                # Record the caller's current selection, then check whether the
                # room has reached a majority on any time range. If so, try to
                # emit (or reuse) a FinalizationProposal. Failures here are
                # never fatal to the peer_time_selection broadcast above.
                if r is not None and authed_user_id is not None:
                    try:
                        await _maybe_emit_proposal(
                            r, room_pk=int(room_id),
                            user_id=authed_user_id,
                            date=date_value,
                            start=start_value,
                            end=end_value,
                            channel=channel,
                        )
                    except Exception:
                        logger.warning(
                            "Finalization aggregation failed for room %s",
                            room_id, exc_info=True,
                        )
                continue

            # ── 불가능 날짜 토글: Redis 영속화 + broadcast ──────────────
            if msg_type == "unavailable_toggle":
                raw_date = payload.get("date")
                if (
                    not isinstance(raw_date, str)
                    or len(raw_date) != 10
                    or raw_date[4] != "-"
                    or raw_date[7] != "-"
                ):
                    continue
                unavailable_flag = bool(payload.get("unavailable", True))

                if r is not None and authed_user_id is not None:
                    dates_after = await sr.record_unavailable_toggle(
                        r,
                        room_id=room_pk,
                        user_id=authed_user_id,
                        date=raw_date,
                        unavailable=unavailable_flag,
                    )
                else:
                    dates_after = []

                out = json.dumps(
                    {
                        "type": "peer_unavailable_update",
                        "user_id": authed_user_id,
                        "sender": authed_user_name,
                        "dates": dates_after,
                    },
                    ensure_ascii=False,
                )
                await _publish_social_message(r, channel, out)

                # 불가능 날짜 변경으로 과반 슬롯이 달라질 수 있으니 재집계 트리거.
                if r is not None and authed_user_id is not None:
                    try:
                        await _maybe_emit_proposal(
                            r, room_pk=room_pk,
                            user_id=authed_user_id,
                            date=None, start=None, end=None,
                            channel=channel,
                            skip_record=True,
                        )
                    except Exception:
                        logger.warning(
                            "Finalization aggregation failed after unavailable_toggle room=%s",
                            room_id, exc_info=True,
                        )
                continue

            # ── 날짜 선택 공유 이벤트: Redis 영속화 + broadcast ────────────
            if msg_type == "date_selection":
                raw_date = payload.get("date")
                date_value: str | None = None
                if isinstance(raw_date, str) and len(raw_date) == 10:
                    # YYYY-MM-DD 기본 검증
                    if raw_date[4] == "-" and raw_date[7] == "-":
                        date_value = raw_date
                if r is not None and authed_user_id is not None:
                    await sr.record_date_selection(
                        r, room_id=room_pk, user_id=authed_user_id, date=date_value,
                    )
                # sender/user_id는 서버에서 인증된 값만 사용 (클라이언트 payload 신뢰 X)
                out = json.dumps(
                    {
                        "type": "peer_date_selection",
                        "user_id": authed_user_id,
                        "sender": authed_user_name,
                        "date": date_value,
                    },
                    ensure_ascii=False,
                )
                await _publish_social_message(r, channel, out)
                continue

            role = payload.get("role", "user")
            content = payload.get("content", "")
            sender = payload.get("sender")

            # 메시지 길이 제한 (2000자)
            if len(content) > 2000:
                content = content[:2000]

            async with AsyncSessionLocal() as session:
                msg = ChatMessage(
                    pane_type=PaneType.social,
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
                    "pane_type": msg.pane_type,
                    "role": msg.role,
                    "content": msg.content,
                    "sender": msg.sender,
                    "created_at": msg.created_at.isoformat(),
                }
            )
            await _publish_social_message(r, channel, out)

            # ── 의도 감지 (백그라운드로 실행해 응답 지연 최소화) ──────────
            if settings.GEMINI_API_KEY and r is not None and role == "user" and content.strip():
                asyncio.create_task(
                    _detect_and_notify_intent(r, channel, content, msg.id)
                )

    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        with suppress(Exception):
            await subscriber_task
        manager.remove(channel, websocket)
        if r is not None:
            await r.aclose()


# ── 합의/결론 감지 패턴 ──────────────────────────────────────────────
_CONCLUSION_PATTERNS = re.compile(
    r"확정|그걸로\s*하자|그때\s*보자|오케이.*보자|ㅇㅋ.*보자|그러자|좋아.*하자|"
    r"그렇게\s*하자|그날로\s*하자|거기로\s*하자|거기서\s*보자|그럼\s*그때|"
    r"콜|ㅇㅇ.*하자|결정|최종|fix"
)


def _is_conclusion(text: str) -> bool:
    """메시지가 모임 합의/결론에 해당하는지 판별합니다."""
    return bool(_CONCLUSION_PATTERNS.search(text))


async def _detect_and_notify_intent(
    r: aioredis.Redis,
    channel: str,
    content: str,
    trigger_message_id: int,
) -> None:
    """
    메시지 의도를 분류하고, 대화 흐름에 개입이 필요한지 판정합니다.

    1단계 — 경량 필터 (비용 0):
        - classify_intent로 의도 추출 (meeting_schedule / place_suggestion / general)
        - 모임 관련 의도면 intent_detected 이벤트 발행 (프론트 배너용)
        - 모든 user 메시지에 대해 카운터 +1

    2단계 — 조건부 LLM 판정 (쿨다운 있음):
        - 카운터 >= 3 이고 60초 쿨다운 해제된 상태에서
        - 최근 10개 메시지를 judge_stalemate에 보내 교착 여부 판정
        - yes → auto_trigger 발행 + 카운터 리셋
        - no → 쿨다운만 설정 (카운터 유지, 다음 메시지 기다림)

    3단계 — 합의 감지 (regex 폴백):
        - 확정/결정 패턴이 명확히 보이면 즉시 정리 카드 트리거
    """
    try:
        result = await classify_intent(content)
        room_id = channel.split(":", 1)[1] if ":" in channel else channel
        counter_key = f"social_msg_count:{room_id}"
        cooldown_key = f"social_judge_cooldown:{room_id}"
        agent_channel = f"agent:{room_id}"

        # ── 배너 알림: 모임 관련 의도면 프론트로 발행 ───────────────────
        if (
            result["intent"] in _NOTIFIABLE_INTENTS
            and result["confidence"] >= 0.6
        ):
            await _publish_social_message(
                r,
                channel,
                json.dumps(
                    {
                        "type": "intent_detected",
                        "intent": result["intent"],
                        "confidence": result["confidence"],
                        "method": result["method"],
                        "trigger_message_id": trigger_message_id,
                    }
                ),
            )

        # ── 결론 감지: 명시적 합의 패턴 → 즉시 정리 카드 ────────────────
        if _is_conclusion(content) and result["intent"] in _NOTIFIABLE_INTENTS:
            await r.delete(counter_key)
            try:
                await r.publish(
                    agent_channel,
                    json.dumps(
                        {
                            "type": "ai_auto_trigger",
                            "intent": result["intent"],
                            "confidence": result["confidence"],
                            "content": content,
                            "trigger_message_id": trigger_message_id,
                            "trigger_reason": "conclusion_detected",
                        },
                        ensure_ascii=False,
                    ),
                )
            except Exception:
                logger.warning(
                    "Failed to publish conclusion auto_trigger to %s",
                    agent_channel,
                    exc_info=True,
                )
            return

        # ── 카운터 증가 (모든 user 메시지 대상) ──────────────────────────
        count = await r.incr(counter_key)
        await r.expire(counter_key, 600)

        if count < 4:
            logger.debug(
                "Social msg count for room %s: %d (threshold: 4, skipping judge)",
                room_id,
                count,
            )
            return

        # ── 쿨다운 체크: 최근 60초 내 judge 호출이 있었다면 skip ─────────
        if await r.get(cooldown_key):
            logger.debug("Stalemate judge cooldown active for room %s", room_id)
            return

        # ── 최근 10개 메시지 로드 ────────────────────────────────────
        try:
            room_pk = int(room_id)
        except (TypeError, ValueError):
            return

        async with AsyncSessionLocal() as session:
            rs = await session.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.room_id == room_pk,
                    ChatMessage.pane_type == PaneType.social,
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(10)
            )
            recent = list(reversed(rs.scalars().all()))

        msgs_for_judge = [
            {"sender": m.sender or "익명", "content": m.content}
            for m in recent
            if m.content and m.content.strip()
        ]
        if not msgs_for_judge:
            return

        # ── LLM 판정 ────────────────────────────────────────────────
        judgment = await judge_stalemate(msgs_for_judge)
        # 판정 결과와 무관하게 60초 쿨다운 (연속 호출 방지)
        await r.setex(cooldown_key, 60, "1")

        if not judgment.get("stalemate"):
            logger.debug(
                "Stalemate judge says no for room %s: %s",
                room_id,
                judgment.get("reason"),
            )
            return

        # ── 교착 확정 → auto_trigger 발행 + 카운터 리셋 ──────────────────
        await r.delete(counter_key)

        judged_intent = judgment.get("intent")
        if judged_intent not in _NOTIFIABLE_INTENTS:
            judged_intent = (
                result["intent"]
                if result["intent"] in _NOTIFIABLE_INTENTS
                else "meeting_schedule"
            )

        try:
            await r.publish(
                agent_channel,
                json.dumps(
                    {
                        "type": "ai_auto_trigger",
                        "intent": judged_intent,
                        "confidence": result["confidence"],
                        "content": content,
                        "trigger_message_id": trigger_message_id,
                        "trigger_reason": "stalemate_judged",
                        "judge_reason": judgment.get("reason", ""),
                    },
                    ensure_ascii=False,
                ),
            )
            logger.info(
                "Stalemate judge triggered for room %s: %s",
                room_id,
                judgment.get("reason"),
            )
        except Exception:
            logger.warning(
                "Failed to publish stalemate auto_trigger to %s",
                agent_channel,
                exc_info=True,
            )
    except Exception:
        # 의도 감지 실패는 채팅 흐름에 영향을 주지 않도록 무시
        logger.debug("Intent detection failed for channel %s", channel, exc_info=True)
