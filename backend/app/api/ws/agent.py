import asyncio
import copy
from contextlib import suppress
from datetime import datetime
import json
import logging
import time
from typing import Any, Optional

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
from app.services import scheduling_round as sr
from app.services.gemini import call_gemini
from app.services.langgraph_pipeline import KST, _analyze_conversation, run_pipeline
from app.services.quick_classify import quick_classify

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


async def _build_entities_from_timebar(room_id: str, db: Any, redis_client: aioredis.Redis | None) -> dict[str, Any]:
    """Build date/time signals from the room TimeBar availability snapshot."""
    if redis_client is None:
        return {}

    try:
        room_pk = int(room_id)
    except (TypeError, ValueError):
        return {}

    try:
        member_result = await db.execute(
            select(RoomMember.user_id).where(RoomMember.room_id == room_pk)
        )
        member_ids = {int(user_id) for user_id in member_result.scalars().all()}
        if not member_ids:
            return {}

        availability = await sr.load_room_availability(redis_client, room_id=room_pk)
        if not availability:
            return {}

        cells_by_date: dict[str, dict[int, set[int]]] = {}
        for user_id, entries in availability.items():
            uid = int(user_id)
            if uid not in member_ids:
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                date = entry.get("date")
                start = entry.get("start")
                end = entry.get("end")
                if not isinstance(date, str) or len(date) != 10:
                    continue
                try:
                    start_idx = int(start)
                    end_idx = int(end)
                except (TypeError, ValueError):
                    continue
                if start_idx > end_idx:
                    start_idx, end_idx = end_idx, start_idx
                start_idx = max(0, start_idx)
                end_idx = min(sr.TIME_SLOT_MAX - 1, end_idx)
                by_slot = cells_by_date.setdefault(date, {})
                for slot_idx in range(start_idx, end_idx + 1):
                    by_slot.setdefault(slot_idx, set()).add(uid)

        common_slots: list[tuple[str, int]] = []
        for date in sorted(cells_by_date):
            for slot_idx in sorted(cells_by_date[date]):
                if cells_by_date[date][slot_idx] >= member_ids:
                    common_slots.append((date, slot_idx))

        if not common_slots:
            return {}

        date_hint, first_slot_idx = common_slots[0]
        parsed_time_hint = sr.slot_idx_to_time(first_slot_idx)
        date_hints = list(dict.fromkeys(date for date, _ in common_slots))
        time_options = [
            {"label": f"{date} {sr.slot_idx_to_time(slot_idx)}"}
            for date, slot_idx in common_slots[:5]
        ]

        # 첫 날짜에서 가장 긴 연속 슬롯 구간 → "HH:MM~HH:MM" 라벨
        # 시연 narration용 (해결점 B 동적 메시지).
        consensus_label: str | None = None
        slots_for_first_date = sorted(s for d, s in common_slots if d == date_hint)
        if slots_for_first_date:
            best_start = best_end = slots_for_first_date[0]
            cur_start = cur_end = slots_for_first_date[0]
            for idx in slots_for_first_date[1:]:
                if idx == cur_end + 1:
                    cur_end = idx
                else:
                    if (cur_end - cur_start) > (best_end - best_start):
                        best_start, best_end = cur_start, cur_end
                    cur_start = cur_end = idx
            if (cur_end - cur_start) > (best_end - best_start):
                best_start, best_end = cur_start, cur_end
            end_idx = min(best_end + 1, sr.TIME_SLOT_MAX - 1)
            consensus_label = f"{sr.slot_idx_to_time(best_start)}~{sr.slot_idx_to_time(end_idx)}"

        return {
            "date_hint": date_hint,
            "date_hints": date_hints,
            "parsed_time_hint": parsed_time_hint,
            "time_options": time_options,
            "consensus_label": consensus_label,
        }
    except Exception:
        logger.warning("TimeBar entity extraction failed room=%s", room_id, exc_info=True)
        return {}


async def _emit_auto_trigger_greeting(
    redis_client: aioredis.Redis | None,
    room_id: str,
    channel: str,
    content: str,
) -> None:
    try:
        async with AsyncSessionLocal() as sess:
            greeting = ChatMessage(
                pane_type=PaneType.agent,
                role="assistant",
                content=content,
                sender="매듭 AI",
                room_id=int(room_id) if room_id else None,
                user_id=None,
                visibility=Visibility.shared.value,
            )
            sess.add(greeting)
            await sess.commit()
            await sess.refresh(greeting)
        await _publish_agent_message(
            redis_client,
            channel,
            json.dumps(
                {
                    "id": greeting.id,
                    "pane_type": greeting.pane_type,
                    "role": greeting.role,
                    "content": greeting.content,
                    "sender": greeting.sender,
                    "created_at": greeting.created_at.isoformat(),
                    "visibility": greeting.visibility,
                    "user_id": greeting.user_id,
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        logger.debug("Failed to emit auto-trigger greeting", exc_info=True)


async def _sync_chat_rejected_to_unavailability(
    redis_client: aioredis.Redis | None,
    room_pk: int,
    signals: dict | None,
) -> None:
    """채팅 대화에서 추출한 rejected_dates/accepted_dates를 멤버별 unavailability로 동기화.

    안전 조건: 비게스트 authed 멤버 + 이름 명시 + 이름 유일 매핑만. 이름 충돌 발생 시 해당 이름 skip.
    """
    if not isinstance(signals, dict):
        return
    rejected = signals.get("rejected_dates") or []
    accepted = signals.get("accepted_dates") or []
    if not isinstance(rejected, list):
        rejected = []
    if not isinstance(accepted, list):
        accepted = []
    if not rejected and not accepted:
        return
    if redis_client is None:
        return

    names: set[str] = set()
    for entry in rejected + accepted:
        if isinstance(entry, dict) and isinstance(entry.get("user"), str):
            name = entry["user"].strip()
            if name:
                names.add(name)
    if not names:
        return

    try:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(User.id, User.name)
                .join(RoomMember, RoomMember.user_id == User.id)
                .where(RoomMember.room_id == room_pk)
                .where(User.name.in_(names))
                .where(User.is_guest.is_(False))
            )
            rows = (await db.execute(stmt)).all()
    except Exception:
        logger.warning("Member name lookup failed for room %s", room_pk, exc_info=True)
        return

    name_to_id: dict[str, int] = {}
    collisions: set[str] = set()
    for uid, nm in rows:
        if nm in name_to_id and name_to_id[nm] != uid:
            collisions.add(nm)
        else:
            name_to_id[nm] = uid
    for nm in collisions:
        name_to_id.pop(nm, None)
        logger.info("[CHAT_UNAVAIL_SYNC] Skip name collision: %s (room=%s)", nm, room_pk)
    if not name_to_id:
        return

    social_channel = f"social:{room_pk}"
    applied_count = 0

    async def _toggle_and_publish(entry: dict, unavailable: bool) -> None:
        nonlocal applied_count
        if not isinstance(entry, dict):
            return
        user_name = entry.get("user")
        date = entry.get("date")
        if not isinstance(user_name, str) or not isinstance(date, str):
            return
        uid = name_to_id.get(user_name.strip())
        if uid is None:
            return
        try:
            dates_after = await sr.record_unavailable_toggle(
                redis_client,
                room_id=room_pk,
                user_id=uid,
                date=date,
                unavailable=unavailable,
            )
        except Exception:
            logger.warning(
                "record_unavailable_toggle failed room=%s uid=%s date=%s",
                room_pk, uid, date, exc_info=True,
            )
            return
        applied_count += 1
        out = json.dumps(
            {
                "type": "peer_unavailable_update",
                "user_id": uid,
                "sender": user_name,
                "dates": dates_after,
            },
            ensure_ascii=False,
        )
        try:
            await redis_client.publish(social_channel, out)
        except Exception:
            logger.warning("Publish peer_unavailable_update failed room=%s", room_pk, exc_info=True)

    for entry in rejected:
        await _toggle_and_publish(entry, unavailable=True)
    for entry in accepted:
        await _toggle_and_publish(entry, unavailable=False)

    if applied_count:
        logger.info(
            "[CHAT_UNAVAIL_SYNC] Applied %d unavailability toggles (room=%s)",
            applied_count, room_pk,
        )


async def _run_auto_trigger_pipeline(
    room_id: str,
    trigger_content: str,
    trigger_intent: str,
    trigger_reason: str,
    slot_context: dict,
) -> None:
    logger.info(
        "[AUTO_TRIGGER] pipeline entry: room=%s intent=%s reason=%s",
        room_id, trigger_intent, trigger_reason,
    )
    shared_channel = f"agent:{room_id}"
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception:
        logger.exception("Redis client unavailable for detached auto-trigger room %s", room_id)
        redis_client = None

    try:
        # 해결점 B: trigger_reason별 분석중 메시지 즉시 발행 (LLM 분석 전)
        # — 5~15초 LLM 대기 동안 사용자에게 "AI가 일하는 중"임을 알림.
        # all_members_selected는 TimeBar 합의 구간을 동적으로 박아 시연 임팩트 ↑.
        greeting: str | None = None
        if trigger_reason == "stalemate_judged":
            greeting = "대화가 길어지네요, AI가 정리해볼게요 🗓️"
        elif trigger_reason == "all_members_selected":
            consensus_label: str | None = None
            try:
                async with AsyncSessionLocal() as session:
                    timebar_data = await _build_entities_from_timebar(
                        room_id, session, redis_client
                    )
                if isinstance(timebar_data, dict):
                    label = timebar_data.get("consensus_label")
                    if isinstance(label, str) and label:
                        consensus_label = label
            except Exception:
                logger.debug(
                    "consensus_label probe failed for room %s", room_id, exc_info=True
                )
            greeting = (
                f"모두 시간 선택 완료! {consensus_label}이 겹쳐요"
                if consensus_label
                else "모두 시간 선택 완료! 일정 확정해드릴게요 📅"
            )
        if greeting:
            await _emit_auto_trigger_greeting(
                redis_client,
                room_id,
                shared_channel,
                greeting,
            )

        try:
            async with AsyncSessionLocal() as session:
                analysis = await _analyze_conversation(
                    room_id,
                    session,
                    datetime.now(KST).strftime("%Y-%m-%d"),
                )
                if analysis is not None:
                    card = analysis.get("card")
                    summary = card if isinstance(card, dict) else {}
                    signals = analysis.get("signals")
                    slot_context["pre_extracted_signals"] = signals if isinstance(signals, dict) else None
                    # 해결점 P (임시): 채팅 자연어 거부를 멤버 unavailability로 sync.
                    try:
                        room_pk_for_sync = int(room_id)
                    except (TypeError, ValueError):
                        room_pk_for_sync = None
                    if room_pk_for_sync is not None:
                        await _sync_chat_rejected_to_unavailability(
                            redis_client, room_pk_for_sync, signals if isinstance(signals, dict) else None
                        )
                else:
                    # 해결점 D: legacy fallback (extract_meeting_summary) 제거.
                    # _analyze_conversation 실패 시 빈 summary로 진행.
                    slot_context["pre_extracted_signals"] = None
                    summary = {}
            if summary and any(summary.get(k) for k in ("date", "place", "headcount", "type")):
                await _publish_agent_message(
                    redis_client,
                    shared_channel,
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

        if trigger_intent not in {"meeting_schedule", "place_suggestion"}:
            return

        try:
            room_pk_val = int(room_id)
        except (TypeError, ValueError):
            room_pk_val = None

        # 해결점 G: 트리거 시점 메시지 원문을 state에 박아 intent_detection race 방지.
        slot_context["trigger_message_text"] = trigger_content
        # 해결점 C: trigger_reason을 state에 주입 → LangGraph entry conditional edge가
        # 이걸 보고 시작 노드 결정 (stalemate/conclusion → entity_extraction, all_members → slot_filling).
        slot_context["trigger_reason"] = trigger_reason
        if trigger_reason == "all_members_selected":
            async with AsyncSessionLocal() as session:
                timebar_data = await _build_entities_from_timebar(room_id, session, redis_client)
            if timebar_data:
                pre_extracted = slot_context.get("pre_extracted_signals")
                if not isinstance(pre_extracted, dict):
                    pre_extracted = {}
                    slot_context["pre_extracted_signals"] = pre_extracted
                pre_extracted.update(timebar_data)
                slot_context["date_hint"] = timebar_data.get("date_hint")
                slot_context["date_hints"] = timebar_data.get("date_hints", [])
                slot_context["parsed_time_hint"] = timebar_data.get("parsed_time_hint")
                slot_context["time_options"] = timebar_data.get("time_options", [])
                consensus_label = timebar_data.get("consensus_label")
                if consensus_label:
                    slot_context["confirmed_time"] = consensus_label

        async with AsyncSessionLocal() as session:
            context = await MessageReader.load_agent_context(
                session=session,
                room_id=room_pk_val,
                viewer_user_id=None,
            )
            result = await run_pipeline(
                room_id,
                context,
                session,
                slot_context=slot_context,
            )

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

        if result.get("status") == "conclusion_false_positive":
            logger.info("[TRIGGER] conclusion_detected false positive, silent abort")
            return

        for new_msg in result.get("new_assistant_messages", []):
            await _publish_agent_message(
                redis_client,
                shared_channel,
                json.dumps(new_msg, ensure_ascii=False),
            )

        vote_card_payload = result.get("vote_card_payload")
        if vote_card_payload:
            await _publish_agent_message(
                redis_client,
                shared_channel,
                json.dumps({"type": "vote_card", **vote_card_payload}, ensure_ascii=False),
            )

        place_recommendation_payload = result.get("place_recommendation_payload")
        if place_recommendation_payload:
            await _publish_agent_message(
                redis_client,
                shared_channel,
                json.dumps(
                    {"type": "place_recommendation", **place_recommendation_payload},
                    ensure_ascii=False,
                ),
            )

        maedeup_card_payload = result.get("maedeup_card_payload")
        if maedeup_card_payload:
            await _publish_agent_message(
                redis_client,
                shared_channel,
                json.dumps({"type": "maedeup_card", **maedeup_card_payload}, ensure_ascii=False),
            )
    except Exception:
        logger.exception("Detached auto-trigger pipeline failed for room %s", room_id)
    finally:
        if redis_client is not None:
            with suppress(Exception):
                await redis_client.aclose()


def _log_detached_task_result(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    try:
        exc = task.exception()
    except Exception:
        logger.exception("Failed to inspect detached auto-trigger task")
        return
    if exc is not None:
        logger.error(
            "Detached auto-trigger task crashed",
            exc_info=(type(exc), exc, exc.__traceback__),
        )


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

            logger.info("[AUTO_TRIGGER] received: %r", trigger)
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

            trigger_reason = trigger.get("trigger_reason", "")
            if trigger_intent not in {"meeting_schedule", "place_suggestion"}:
                continue

            # A3-3: 호스트 [조율] 모달이 선택한 manual_chosen_time을 slot_context로 전달.
            # Codex P1 회귀 hotfix (2026-05-08): deepcopy + selective deepcopy 둘 다 silent fail.
            # 진짜 원인 미확정 — 단순 shallow로 복원. P1 finding은 시연 후 재처리.
            sc = dict(slot_context)
            manual_time = trigger.get("manual_chosen_time")
            if isinstance(manual_time, dict):
                sc["manual_chosen_time"] = manual_time
            logger.info(
                "[AUTO_TRIGGER] passed filter: room=%s intent=%s reason=%s",
                room_id, trigger_intent, trigger_reason,
            )
            try:
                task = asyncio.create_task(
                    _run_auto_trigger_pipeline(
                        room_id,
                        trigger_content,
                        trigger_intent,
                        trigger_reason,
                        sc,
                    )
                )
                task.add_done_callback(_log_detached_task_result)
                logger.info(
                    "[AUTO_TRIGGER] task spawned: name=%s done=%s",
                    task.get_name(), task.done(),
                )
            except Exception:
                logger.exception("[AUTO_TRIGGER] task spawn failed")

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
                    # 시간 확정 → 슬롯 컨텍스트 저장 후 장소 추천 파이프라인 실행.
                    # (이전엔 가짜 user 메시지를 DB에 INSERT해서 시뮬했으나,
                    #  WS 일반 핸들러가 그걸 user 입력으로 잘못 인식 + quick_classify 호출 →
                    #  엉뚱한 vote_card 생성 부작용. 직접 run_pipeline 호출로 변경.)
                    slot_context["confirmed_time"] = payload.get("time")
                    slot_context["confirmed_date"] = payload.get("date") or slot_context.get("confirmed_date")

                    try:
                        room_pk_val = int(room_id)
                    except (TypeError, ValueError):
                        room_pk_val = None

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

                qc = await quick_classify(content)
                if qc["kind"] == "general":
                    prompt = (
                        "사용자의 메시지에 짧고 자연스럽게 답하세요. "
                        "모임 일정이나 장소 조율이 필요한 요청이면 사용자가 다시 구체적으로 말할 수 있게 안내하세요.\n\n"
                        f"사용자: {content}"
                    )
                    reply = (await call_gemini(prompt)).strip()
                    if not reply:
                        reply = "일정이나 장소를 정리하고 싶으면 편하게 말해주세요."
                    await _emit_auto_trigger_greeting(
                        r,
                        room_id,
                        shared_channel,
                        reply,
                    )
                    continue

                slot_context["trigger_reason"] = "direct_request"
                slot_context["direct_request_kind"] = qc["kind"]

                async with AsyncSessionLocal() as session:
                    context = await MessageReader.load_agent_context(
                        session=session,
                        room_id=room_pk,
                        viewer_user_id=user_id_check,
                    )

                    try:
                        result = await run_pipeline(
                            room_id, context, session, slot_context=slot_context
                        )
                    finally:
                        slot_context.pop("trigger_reason", None)
                        slot_context.pop("direct_request_kind", None)

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

                if result.get("status") == "conclusion_false_positive":
                    logger.info("[TRIGGER] conclusion_detected false positive, silent abort")
                    continue

                # 파이프라인이 발행한 어시스턴트 메시지 — shared는 전체, private는 user 전용
                for new_msg in result.get("new_assistant_messages", []):
                    target_ch = shared_channel if new_msg.get("visibility") == "shared" else user_channel
                    await _publish_agent_message(
                        r,
                        target_ch,
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
                if vote_card_payload:
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
