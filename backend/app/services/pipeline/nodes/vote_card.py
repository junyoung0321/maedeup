"""vote_card_creation 노드 + meeting_id 헬퍼.

원본 위치: langgraph_pipeline.py 라인 3896~3904 (_card_payload_meeting_id),
  3907~4020 (_ensure_pending_meeting_id), 4023~4147 (vote_card_creation).

Phase 4 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

의존:
  - state.GraphState
  - helpers.messaging: _has_node_error, _emit_assistant_message, _handle_node_exception
  - helpers.formatting: _format_confirmed_time, _room_id_as_int
  - helpers.dates: _parse_iso_datetime
  - helpers.slot_state: _normalize_preferred_times
  - helpers.slots: _filter_out_rejected
  - app.db.session.AsyncSessionLocal
  - app.models: MeetingSchedule, RoomMember
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import select

from app.db.session import AsyncSessionLocal
from app.models.meeting import MeetingSchedule
from app.models.room import RoomMember
from app.services.pipeline.helpers.dates import _parse_iso_datetime
from app.services.pipeline.helpers.formatting import (
    _format_confirmed_time,
    _room_id_as_int,
)
from app.services.pipeline.helpers.messaging import (
    _emit_assistant_message,
    _handle_node_exception,
    _has_node_error,
)
from app.services.pipeline.helpers.slot_state import _normalize_preferred_times
from app.services.pipeline.helpers.slots import _filter_out_rejected
from app.services.pipeline.state import GraphState
from app.services.slot_ranker import rank_slots

logger = logging.getLogger(__name__)


def _card_payload_meeting_id(payload: dict[str, Any] | None) -> int | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("meeting_id")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


async def _ensure_pending_meeting_id(state: GraphState, title: str) -> int:
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    if room_pk is None:
        raise ValueError(f"room_id is invalid for pending meeting creation: {state['room_id']!r}")

    # F-1 fix (2026-05-07) + Codex P2 강화 (2026-05-07):
    # 같은 흐름 (vote_card → place → maedeup)에서 발행된 pending meeting을 재사용해
    # frontend cardsByMeetingId가 단일 meeting_id로 라이프사이클 유지하도록 함. 단,
    # "룸의 최신 pending"을 무조건 재사용하면 무관한 stale pending(예: 어제 vote에서 남은 것)에
    # 새 카드가 잘못 붙는 사각지대가 있어, 가드 2단계:
    #   1) date_hint와 scheduled_at이 일치하는 pending 우선 (강한 증거 — 시간 제한 X,
    #      장시간 합의 흐름도 정상 처리)
    #   2) date_hint 없음/매칭 실패 → 최근 30분 내 생성된 pending만 (약한 증거,
    #      stale flow 차단용 단일 세션 보장)
    # 둘 다 매칭 실패 시 새로 생성.
    existing_pending: MeetingSchedule | None = None

    date_hint = state.get("date_hint")
    date_iso = date_hint[:10] if isinstance(date_hint, str) and re.match(r"^\d{4}-\d{2}-\d{2}", date_hint) else None

    if date_iso:
        # Codex P2 review v2 (2026-05-07): vote_options에 multi-date 슬롯이 있을 때
        # MeetingSchedule.scheduled_at은 첫 옵션만 반영하므로 SQL where절만으론 부분 매칭.
        # 따라서 룸 최근 pending 10건을 가져와 Python에서 scheduled_at OR vote_options 매칭.
        try:
            target_date = datetime.fromisoformat(f"{date_iso}T00:00:00")
            next_day = target_date + timedelta(days=1)
            candidates = (
                await db.execute(
                    select(MeetingSchedule)
                    .where(MeetingSchedule.room_id == room_pk)
                    .where(MeetingSchedule.status == "pending")
                    .order_by(MeetingSchedule.created_at.desc())
                    .limit(10)
                )
            ).scalars().all()
            for cand in candidates:
                # 1) scheduled_at primary date 매칭
                sched_at = cand.scheduled_at
                if sched_at is not None and target_date <= sched_at < next_day:
                    existing_pending = cand
                    break
                # 2) vote_options 슬롯 중 어느 하나라도 같은 날짜면 매칭 (multi-date vote 케이스)
                for opt in (cand.vote_options or []):
                    if not isinstance(opt, dict):
                        continue
                    opt_start = opt.get("start_at")
                    if isinstance(opt_start, str) and opt_start.startswith(date_iso):
                        existing_pending = cand
                        break
                if existing_pending is not None:
                    break
        except (ValueError, TypeError):
            existing_pending = None

    if existing_pending is None:
        # date_hint 매칭 실패 또는 없음 → 최근 30분 내 pending만 fallback (stale flow 차단).
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        recent_threshold = now_naive - timedelta(minutes=30)
        existing_pending = (
            await db.execute(
                select(MeetingSchedule)
                .where(MeetingSchedule.room_id == room_pk)
                .where(MeetingSchedule.status == "pending")
                .where(MeetingSchedule.created_at > recent_threshold)
                .order_by(MeetingSchedule.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if existing_pending is not None and existing_pending.id is not None:
        logger.info(
            "Reusing existing pending meeting id=%s for room=%s (F-1: same-flow continuation)",
            existing_pending.id, room_pk,
        )
        return existing_pending.id

    member_result = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room_pk).limit(1)
    )
    first_member = member_result.scalar_one_or_none()
    if first_member is None:
        raise ValueError(f"No members found in room {room_pk}; cannot determine created_by")

    selected_slot = state["calendar_free_slots"][0] if state.get("calendar_free_slots") else {}
    slot_start = _parse_iso_datetime(selected_slot.get("start_at")) if selected_slot.get("start_at") else None
    slot_end = _parse_iso_datetime(selected_slot.get("end_at")) if selected_slot.get("end_at") else None
    if slot_start is None:
        slot_start = datetime.now(timezone.utc).replace(tzinfo=None)
    if slot_end is None:
        slot_end = slot_start + timedelta(hours=2)
    if slot_start.tzinfo is not None:
        slot_start = slot_start.replace(tzinfo=None)
    if slot_end.tzinfo is not None:
        slot_end = slot_end.replace(tzinfo=None)

    new_meeting = MeetingSchedule(
        room_id=room_pk,
        title=title,
        scheduled_at=slot_start,
        end_at=slot_end,
        vote_options=None,
        votes={},
        status="pending",
        created_by=first_member.user_id,
    )
    db.add(new_meeting)
    await db.commit()
    await db.refresh(new_meeting)
    if new_meeting.id is None:
        raise ValueError("Pending meeting creation did not return an id")
    logger.info("Created pending meeting id=%s for card payload", new_meeting.id)
    return new_meeting.id


async def vote_card_creation(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state

        if state.get("no_date_selection"):
            narrator = "먼저 오른쪽 캘린더에서 가능한 날짜를 선택해주세요. 멤버들이 날짜를 선택하면 최적 시간대를 추천해드릴게요. 📅"
            async with AsyncSessionLocal() as db:
                await _emit_assistant_message(state["room_id"], db, narrator, state, shared=True)
            state["status"] = "vote_card_skipped"
            logger.info("[TIMING] vote_card_creation: skipped (no date selection) %.2fs", time.monotonic() - _t0)
            return state

        selected_slot = state["calendar_free_slots"][0] if state.get("calendar_free_slots") else {}
        start_at = _parse_iso_datetime(selected_slot.get("start_at")) if selected_slot else None
        meeting_id = selected_slot.get("meeting_id") or selected_slot.get("id")
        if state.get("date_hint"):
            state["confirmed_date"] = state.get("date_hint")
        if start_at is not None:
            state["confirmed_time"] = _format_confirmed_time(start_at)
        is_multi_date = state.get("calendar_strategy") == "multi_date_vote"
        calendar_slots = state.get("calendar_free_slots") or []

        # 단일 날짜 + 슬롯 1개 = 투표 불필요 (선호 기반은 항상 투표 카드 생성)
        # Fix 8b (2026-05-14): direct_request인 경우 단일 슬롯도 카드 발행.
        # "내일 오후 6시 잡아줘"처럼 사용자가 명시 시간 지정한 케이스 — 카드 보장.
        is_preference_based = state.get("calendar_strategy") == "preference_based"
        is_direct_request = state.get("trigger_reason") == "direct_request"
        if (
            not is_multi_date
            and not is_preference_based
            and not is_direct_request
            and len(calendar_slots) <= 1
        ):
            state["status"] = "vote_card_skipped"
            logger.info("[TIMING] vote_card_creation: skipped (single slot) %.2fs", time.monotonic() - _t0)
            return state

        vote_title = (
            f"{state.get('meeting_type') or '모임'} 날짜 투표 📅"
            if is_multi_date
            else f"{state.get('meeting_type') or '모임'} 시간 투표"
        )

        pref_times = _normalize_preferred_times(state.get("preference_common_times"))
        has_weekday_pref = any(t.startswith("평일") for t in pref_times)
        vote_slots = state.get("calendar_free_slots", [])
        # 안전망: 상위 노드가 예외로 중단됐을 때도 거부 날짜는 카드에 안 들어가게.
        rejected_safety = state.get("rejected_dates") or []
        if rejected_safety:
            vote_slots = _filter_out_rejected(vote_slots, rejected_safety)
        if has_weekday_pref:
            weekday_only = [s for s in vote_slots if not s.get("is_weekend", False)]
            if weekday_only:
                vote_slots = weekday_only

        # Fix 11 (2026-05-14): slot_ranker로 모임 유형 기반 재정렬.
        # 식사면 12~13/18~20시, 카페면 14~15시 등 시간대 점수화.
        # multi_date_vote는 날짜별 카드라 시간 순위 무의미 → skip.
        # preference_based는 이미 선호 시간대로 만들어졌으니 추가 정렬 불필요 → skip.
        if not is_multi_date and not is_preference_based and len(vote_slots) >= 2:
            try:
                ranked = rank_slots(
                    vote_slots,
                    {"meeting_type": state.get("meeting_type")},
                    top_k=len(vote_slots),  # 전체 유지, 순서만 변경
                )
                if ranked:
                    vote_slots = ranked
                    logger.info(
                        "[FIX-11] vote_slots reranked by slot_ranker (meeting_type=%s)",
                        state.get("meeting_type"),
                    )
            except Exception:
                logger.debug("slot_ranker failed, keeping original order", exc_info=True)

        # meeting_id가 없으면 DB에 pending meeting 생성 (필터된 vote_slots 사용)
        if not meeting_id:
            db = state["db"]
            room_pk = _room_id_as_int(state["room_id"])
            if room_pk is None:
                raise ValueError(f"room_id is invalid for pending meeting creation: {state['room_id']!r}")
            member_result = await db.execute(
                select(RoomMember).where(RoomMember.room_id == room_pk).limit(1)
            )
            first_member = member_result.scalar_one_or_none()
            if first_member is None:
                raise ValueError(f"No members found in room {room_pk}; cannot determine created_by")
            created_by = first_member.user_id
            first_slot = vote_slots[0] if vote_slots else {}
            slot_start = _parse_iso_datetime(first_slot.get("start_at")) if first_slot.get("start_at") else datetime.now(timezone.utc).replace(tzinfo=None)
            slot_end = _parse_iso_datetime(first_slot.get("end_at")) if first_slot.get("end_at") else slot_start + timedelta(hours=2)
            new_meeting = MeetingSchedule(
                room_id=room_pk,
                title=vote_title,
                scheduled_at=slot_start if not hasattr(slot_start, 'tzinfo') or slot_start.tzinfo is None else slot_start.replace(tzinfo=None),
                end_at=slot_end if not hasattr(slot_end, 'tzinfo') or slot_end.tzinfo is None else slot_end.replace(tzinfo=None),
                vote_options=[
                    {"slot_id": s.get("slot_id"), "label": s.get("label"), "start_at": s.get("start_at"), "end_at": s.get("end_at")}
                    for s in vote_slots
                ],
                votes={},
                status="pending",
                created_by=created_by,
            )
            db.add(new_meeting)
            await db.commit()
            await db.refresh(new_meeting)
            meeting_id = new_meeting.id
            logger.info("Created pending meeting id=%s for vote card", meeting_id)

        state["vote_card_payload"] = {
            "type": "vote_card",
            "title": vote_title,
            "room_id": state["room_id"],
            "meeting_id": meeting_id,
            "time_options": [
                {
                    "slot_id": slot.get("slot_id"),
                    "label": slot.get("label"),
                    "start_at": slot.get("start_at"),
                    "end_at": slot.get("end_at"),
                    "is_holiday": slot.get("is_holiday", False),
                    "holiday_name": slot.get("holiday_name"),
                    "is_weekend": slot.get("is_weekend", False),
                }
                for slot in vote_slots
            ],
            "headcount": state.get("headcount"),
            "blocker_notification": state.get("blocker_notification_payload"),
            "calendar_strategy": state.get("calendar_strategy"),
        }
        state["status"] = "vote_card_created"

        # ── Narrator 메시지 큐에 넣기 (해결점 L: EARLY-EMIT 제거, 정상 emit 경로 단일화)
        try:
            best_label = state.get("calendar_free_slots", [{}])[0].get("label", "")
            if state.get("date_conflict"):
                summary = state.get("date_selection_summary", {})
                parts = [f"{d}: {c}명" for d, c in sorted(summary.items(), key=lambda x: -x[1])]
                narrator = f"날짜가 엇갈리네요 ({', '.join(parts)}). 가장 많이 선택된 날짜 기준으로 {best_label}을(를) 추천드려요. 📅"
            else:
                narrator = f"캘린더 확인 결과, {best_label}을(를) 추천드려요. 📅 아래에서 확인해주세요."
            async with AsyncSessionLocal() as db:
                await _emit_assistant_message(state["room_id"], db, narrator, state, shared=True)
        except Exception:
            logger.debug("vote_card narrator emit failed", exc_info=True)

        logger.info("[TIMING] vote_card_creation: %.2fs", time.monotonic() - _t0)
        return state
    except Exception as exc:
        return await _handle_node_exception("vote_card_creation", state, exc)
