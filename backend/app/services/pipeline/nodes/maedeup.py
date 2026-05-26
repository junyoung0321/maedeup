"""maedeup_card_creation 노드 + 캘린더 등록 헬퍼.

원본 위치: langgraph_pipeline.py 라인 2442~2450 (_register_google_calendar),
  4412~4562 (maedeup_card_creation).

Phase 4 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

의존:
  - state.GraphState
  - helpers.messaging: _has_node_error, _handle_node_exception
  - nodes.vote_card: _card_payload_meeting_id, _ensure_pending_meeting_id
    (vote_card.py가 먼저 만들어졌으므로 일방향 import 안전)
  - nodes.memory: _spawn_memory_extraction_async
    (Step 4.6에서 만들어짐 — 같은 Phase 내 일방향 의존)
  - app.models.MeetingSchedule
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

from sqlmodel import select

from app.models.meeting import MeetingSchedule
from app.observability.snapshot import dump
from app.services.pipeline.helpers.messaging import (
    _handle_node_exception,
    _has_node_error,
)
from app.services.pipeline.nodes.memory import _spawn_memory_extraction_async
from app.services.pipeline.nodes.vote_card import (
    _card_payload_meeting_id,
    _ensure_pending_meeting_id,
)
from app.services.pipeline.state import GraphState

logger = logging.getLogger(__name__)


async def _register_google_calendar(state: GraphState) -> dict[str, Any]:
    """최종 확정 전에는 캘린더 자동 등록을 보류합니다."""
    selected_slot = state["calendar_free_slots"][0] if state.get("calendar_free_slots") else {}
    return {
        "provider": "google_calendar",
        "status": "skipped",
        "reason": "pending_confirmation",
        "scheduled_at": selected_slot.get("start_at"),
    }


async def maedeup_card_creation(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    dump("node_in", state.get("run_id"), {
        "node": "maedeup_card_creation",
        "status": state.get("status"),
        "trigger_reason": state.get("trigger_reason"),
        "has_card": bool(state.get("maedeup_card_payload") or state.get("vote_card_payload")),
        "message_count": len(state.get("message_records", [])),
    })
    try:
        if _has_node_error(state):
            return state
        selected_slot = state["calendar_free_slots"][0] if state.get("calendar_free_slots") else {}
        selected_slot_meeting_id = selected_slot.get("meeting_id") or selected_slot.get("id")
        # Fix J: conclusion/all_members fast paths can enter without a vote card.
        # Reuse any upstream card meeting_id; otherwise create a pending meeting row.
        meeting_id = (
            _card_payload_meeting_id(state.get("vote_card_payload"))
            or _card_payload_meeting_id(state.get("place_recommendation_payload"))
            or _card_payload_meeting_id(selected_slot)
            or (selected_slot_meeting_id if isinstance(selected_slot_meeting_id, int) else None)
        )
        if meeting_id is None:
            meeting_id = await _ensure_pending_meeting_id(
                state,
                f"{state.get('meeting_type') or '모임'} 매듭 카드",
            )
        if state.get("partial_mode") == "time_only":
            parsed_time = state.get("parsed_time_hint")
            date_value = state.get("date_hint")
            # A3-3 (2026-05-08): manual host pick은 confirmed_time을 "HH:MM~HH:MM" 형식으로 박음.
            # 그 경우 정확한 end 시각을 보존 (auto-trigger의 +1h fallback이 manual 범위를 깨뜨리지 않게).
            confirmed_time_raw = state.get("confirmed_time")
            explicit_start: str | None = None
            explicit_end: str | None = None
            if isinstance(confirmed_time_raw, str) and "~" in confirmed_time_raw:
                parts = confirmed_time_raw.split("~", 1)
                if len(parts) == 2:
                    cand_start, cand_end = parts[0].strip(), parts[1].strip()
                    if (
                        re.match(r"^\d{2}:\d{2}$", cand_start)
                        and re.match(r"^\d{2}:\d{2}$", cand_end)
                    ):
                        explicit_start, explicit_end = cand_start, cand_end
            display_time = explicit_start or parsed_time
            selected_time = {}
            start_dt: datetime | None = None
            end_dt: datetime | None = None
            if date_value and display_time:
                import datetime as _dt
                try:
                    start_dt = _dt.datetime.fromisoformat(f"{date_value}T{display_time}:00")
                    if explicit_end:
                        end_dt = _dt.datetime.fromisoformat(f"{date_value}T{explicit_end}:00")
                    else:
                        end_dt = start_dt + _dt.timedelta(hours=1)
                    label = (
                        f"{date_value} {display_time}~{explicit_end}"
                        if explicit_end
                        else f"{date_value} {display_time}"
                    )
                    selected_time = {
                        "label": label,
                        "start_at": start_dt.isoformat(),
                        "end_at": end_dt.isoformat(),
                    }
                except Exception:
                    selected_time = {"label": f"{date_value} {display_time}"}
                    start_dt = None
                    end_dt = None
            elif date_value:
                selected_time = {"label": date_value}
            elif display_time:
                selected_time = {"label": display_time}

            # P0 fix (2026-05-08): partial maedeup 발행 시 DB scheduled_at/end_at 동기화.
            # ACT 5 [이 장소로 확정] 후 갱신 maedeup이 _publish_maedeup_place_update에서
            # DB row 시간을 SoT로 사용 → partial 시점에 정확히 박아두지 않으면 stale 1h fallback 노출.
            if meeting_id and start_dt and end_dt:
                try:
                    db = state["db"]
                    meeting_row = await db.execute(
                        select(MeetingSchedule).where(MeetingSchedule.id == meeting_id)
                    )
                    meeting_obj = meeting_row.scalar_one_or_none()
                    if meeting_obj is not None:
                        ms = start_dt.replace(tzinfo=None) if start_dt.tzinfo else start_dt
                        me = end_dt.replace(tzinfo=None) if end_dt.tzinfo else end_dt
                        meeting_obj.scheduled_at = ms
                        meeting_obj.end_at = me
                        meeting_obj.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                        db.add(meeting_obj)
                        await db.commit()
                        logger.info(
                            "[MAEDEUP] partial DB time sync meeting_id=%s %s~%s",
                            meeting_id, ms.isoformat(), me.isoformat(),
                        )
                except Exception:
                    logger.warning(
                        "partial maedeup DB time sync failed (meeting_id=%s)",
                        meeting_id, exc_info=True,
                    )

            payload = {
                "type": "maedeup_card",
                "meeting_id": meeting_id,
                "date": date_value,
                "time": display_time,
                "place": None,
                "place_pending": True,
                "place_pending_message": "멤버들이 장소를 정하면 자동으로 정리해드릴게요!",
                "headcount": state.get("headcount"),
                "calendar_registered": False,
                "title": f"{state.get('meeting_type') or '모임'} 매듭 카드",
                "meeting_type": state.get("meeting_type") or "모임",
                "date_hint": date_value or state.get("date") or "",
                "selected_time": selected_time,
                "selected_place": {},
            }
            state["maedeup_card_payload"] = payload
            state["status"] = "completed"
            # P0-2: memory_extraction 분리 — graph latency에서 빼서 사용자 인식 latency ↓.
            asyncio.create_task(_spawn_memory_extraction_async(state))
            return state
        if state.get("confirmed_place"):
            selected_place = {
                "name": state.get("confirmed_place"),
                "score": 1.0,
                "is_confirmed": True,
            }
        else:
            selected_place = state["place_search_results"][0] if state.get("place_search_results") else {}
            if selected_place.get("name"):
                state["confirmed_place"] = str(selected_place.get("name"))
        state["calendar_registration"] = await _register_google_calendar(state)
        state["maedeup_card_payload"] = {
            "type": "maedeup_card",
            "room_id": state["room_id"],
            "meeting_id": meeting_id,
            "title": f"{state.get('meeting_type') or '모임'} 매듭 카드",
            "intent": state.get("intent"),
            "date_hint": state.get("date_hint"),
            "place_hint": state.get("place_hint"),
            "headcount": state.get("headcount"),
            "meeting_type": state.get("meeting_type"),
            "selected_time": selected_slot,
            "selected_place": selected_place,
            "vote_card": state.get("vote_card_payload"),
            "place_recommendation": state.get("place_recommendation_payload"),
            "calendar_registration": state.get("calendar_registration"),
        }
        state["status"] = "completed"
        logger.info("[TIMING] maedeup_card_creation: %.2fs", time.monotonic() - _t0)
        dump("node_out", state.get("run_id"), {
            "node": "maedeup_card_creation",
            "status_after": state.get("status"),
            "card_type": (state.get("maedeup_card_payload") or {}).get("type"),
            "slot_count": len(state.get("calendar_free_slots", [])),
        })
        # P0-2: memory_extraction 분리 — graph latency에서 빼서 사용자 인식 latency ↓.
        asyncio.create_task(_spawn_memory_extraction_async(state))
        return state
    except Exception as exc:
        return await _handle_node_exception("maedeup_card_creation", state, exc)
