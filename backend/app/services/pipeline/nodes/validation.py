"""supervisor_validation 노드 — 슬롯/장소 후보 검증.

원본 위치: langgraph_pipeline.py 라인 3803~3893.
Phase 4 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

의존:
  - state.GraphState
  - helpers.messaging: _has_node_error, _emit_assistant_message, _handle_node_exception
  - helpers.dates: _parse_iso_datetime
  - helpers.slot_state: _coerce_headcount
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.observability.snapshot import dump
from app.services.pipeline.helpers.dates import _parse_iso_datetime
from app.services.pipeline.helpers.messaging import (
    _emit_assistant_message,
    _handle_node_exception,
    _has_node_error,
)
from app.services.pipeline.helpers.slot_state import _coerce_headcount
from app.services.pipeline.state import GraphState

logger = logging.getLogger(__name__)


async def supervisor_validation(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    dump("node_in", state.get("run_id"), {
        "node": "supervisor_validation",
        "status": state.get("status"),
        "trigger_reason": state.get("trigger_reason"),
        "has_card": bool(state.get("maedeup_card_payload") or state.get("vote_card_payload")),
        "message_count": len(state.get("message_records", [])),
    })
    try:
        if _has_node_error(state):
            return state
        if state.get("status") in ("conclusion_false_positive", "time_only_ready"):
            return state
        errors: list[str] = []
        now = datetime.now(timezone.utc)
        valid_slots: list[dict[str, Any]] = []
        has_preference_time_slots = bool(
            state.get("calendar_strategy") == "preference_based"
            and state.get("preference_common_times")
        )
        is_location_first = bool(
            state.get("is_location_first")
            and not state.get("date_hint")
            and not has_preference_time_slots
        )
        is_multi_date_vote = state.get("calendar_strategy") == "multi_date_vote"

        headcount = state.get("headcount")
        if headcount is None and not is_location_first and not is_multi_date_vote:
            errors.append("headcount is required")
        elif headcount is not None and headcount > 20:
            errors.append("headcount exceeds current recommendation constraints")

        if not is_location_first:
            # Fix (2026-05-18): 과거 슬롯은 조용히 필터 (errors에 추가 X). 이전 동작은
            # 미래 슬롯이 충분한데도 과거 슬롯 1개만 있어도 validation_passed=False로
            # 떨어져서 vote_card 생성 실패. 늦은 시간(예: 22시) 데모에서 항상 재현.
            # 슬롯 timestamp 자체가 손상된 경우(parse 실패, end<=start)만 진짜 errors.
            past_slot_count = 0
            for slot in state.get("calendar_free_slots", []):
                start_at = _parse_iso_datetime(slot.get("start_at"))
                end_at = _parse_iso_datetime(slot.get("end_at"))
                if start_at is None or end_at is None:
                    errors.append("calendar slot has invalid timestamps")
                    continue
                if start_at < now:
                    past_slot_count += 1
                    continue
                if end_at <= start_at:
                    errors.append("calendar slot duration is invalid")
                    continue
                valid_slots.append(slot)
            if past_slot_count:
                logger.info(
                    "[VALIDATION] filtered %d past slots (room=%s, valid_remaining=%d)",
                    past_slot_count, state.get("room_id"), len(valid_slots),
                )

        valid_places: list[dict[str, Any]] = []
        for place in state.get("place_search_results", []):
            max_headcount = _coerce_headcount(place.get("max_headcount"))
            if headcount is not None and max_headcount is not None and max_headcount < headcount:
                continue
            valid_places.append(place)

        is_preference_based = state.get("calendar_strategy") == "preference_based"

        is_place_only = state.get("intent") == "place_suggestion"
        if not valid_slots and not is_location_first and not is_place_only:
            if not state.get("expanded_to_next_week"):
                # 1차 시도: 호스트 GCal full-block → 다음 주로 확장 redirect
                state["expanded_to_next_week"] = True
                state["needs_next_week_expansion"] = True
                logger.info(
                    "[VALIDATION] no valid slots → triggering next-week expansion (room=%s)",
                    state.get("room_id"),
                )
            else:
                # 2차 시도도 fail → 정상 error 흐름
                errors.append("no valid free time slots available")
        # preference_based 추천은 시간 후보가 주된 결과물 — 장소 검색이 실패해도
        # 일정 투표 카드라도 내보내기 위해 통과.
        if (
            not valid_places
            and not is_location_first
            and not is_multi_date_vote
            and not is_preference_based
        ):
            errors.append("no place recommendations satisfy the headcount")

        state["calendar_free_slots"] = valid_slots
        state["place_search_results"] = valid_places
        state["validation_errors"] = errors

        # location_first 모드에서는 장소 결과만 중요 — 시간 슬롯 없어도 통과
        # multi_date_vote 모드에서는 시간 슬롯만 중요 — 장소 없어도 통과
        if is_location_first or is_multi_date_vote or is_place_only:
            state["validation_passed"] = bool(valid_slots) if is_multi_date_vote else True
            state["status"] = "validated"
        elif state.get("needs_next_week_expansion"):
            # 다음 주 확장 redirect — validation 실패 아닌 별도 분기
            state["validation_passed"] = False
            state["status"] = "needs_expansion"
        else:
            state["validation_passed"] = not errors
            state["status"] = "validated" if not errors else "validation_failed"

        if not state["validation_passed"] and errors:
            error_summary = "; ".join(errors)
            await _emit_assistant_message(
                state["room_id"],
                state["db"],
                f"죄송해요, 조건에 맞는 시간이나 장소를 찾지 못했어요. ({error_summary}) "
                "날짜나 장소 조건을 조금 바꿔서 다시 시도해볼까요?",
                state,
            )

        logger.info("[TIMING] supervisor_validation: %.2fs", time.monotonic() - _t0)
        dump("node_out", state.get("run_id"), {
            "node": "supervisor_validation",
            "status_after": state.get("status"),
            "card_type": None,
            "slot_count": len(state.get("calendar_free_slots", [])),
        })
        return state
    except Exception as exc:
        return await _handle_node_exception("supervisor_validation", state, exc)
