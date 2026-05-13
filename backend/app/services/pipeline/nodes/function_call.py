"""function_calling 노드 — 캘린더 슬롯 + 장소 검색 실행.

원본 위치: langgraph_pipeline.py 라인 3670~3800.
Phase 4 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

의존:
  - state.GraphState
  - helpers.messaging: _has_node_error, _handle_node_exception
  - helpers.formatting: _room_id_as_int
  - helpers.places: search_place
  - helpers.slots: _load_blocked_dates, _load_busy_by_user_for_state,
    _build_multi_date_slots, _build_preference_time_slots, _build_time_option_slots,
    _filter_out_blocked, _filter_out_rejected, get_free_slots
"""
from __future__ import annotations

import asyncio
import logging
import time

from app.services.pipeline.helpers.formatting import _room_id_as_int
from app.services.pipeline.helpers.messaging import (
    _handle_node_exception,
    _has_node_error,
)
from app.services.pipeline.helpers.places import search_place
from app.services.pipeline.helpers.slots import (
    _build_multi_date_slots,
    _build_preference_time_slots,
    _build_time_option_slots,
    _filter_out_blocked,
    _filter_out_rejected,
    _load_blocked_dates,
    _load_busy_by_user_for_state,
    get_free_slots,
)
from app.services.pipeline.state import GraphState

logger = logging.getLogger(__name__)


async def function_calling(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state
        if state["status"] == "conclusion_false_positive":
            logger.info("[TIMING] function_calling (false_positive): %.2fs", time.monotonic() - _t0)
            return state
        if state["status"] == "time_only_ready":
            state["calendar_free_slots"] = []
            state["place_search_results"] = []
            logger.info("[TIMING] function_calling (time_only_ready): %.2fs", time.monotonic() - _t0)
            return state
        state["blocker_notification_payload"] = None

        # entity_extraction이 "다시 추천해줘" 같은 재시도 지시어에서 "다시"를
        # place_hint로 잘못 뽑는 경우 있음 — 카카오맵 검색이 무의미해지니 스킵.
        _NOISE_PLACE_HINTS = {
            "다시", "재시도", "또", "한번더", "한 번 더", "다시해봐", "다시 해줘",
            "다시 해", "재추천", "추천", "다시추천",
        }
        pl = state.get("place_hint")
        if isinstance(pl, str) and pl.strip() in _NOISE_PLACE_HINTS:
            state["place_hint"] = None

        if state.get("intent") == "place_suggestion":
            place_results = await search_place(state)
            state["place_search_results"] = place_results
            state["status"] = "functions_called"
            logger.info("[TIMING] function_calling (place-suggestion): %.2fs", time.monotonic() - _t0)
            return state

        # 방의 '불가능 날짜' — 모든 경로의 최종 후보에서 제외.
        room_pk = _room_id_as_int(state["room_id"])
        blocked_dates = await _load_blocked_dates(room_pk)
        rejected_dates = state.get("rejected_dates") or []

        # 여러 날짜 선택지 → 각 날짜별 슬롯 생성
        multi_date_hints = state.get("date_hints") or []
        if state.get("intent") != "place_suggestion" and len(multi_date_hints) >= 2:
            # F-8 v2 후속 #2: stalemate path (multi-date)도 GCal busy 반영해 호스트 일정과 충돌하는 슬롯 skip / 라벨 정확.
            busy_by_user = await _load_busy_by_user_for_state(state)
            multi_slots = _filter_out_rejected(
                _filter_out_blocked(
                    _build_multi_date_slots(state, busy_by_user=busy_by_user),
                    blocked_dates,
                ),
                rejected_dates,
            )
            if multi_slots:
                state["calendar_free_slots"] = multi_slots
                state["calendar_strategy"] = "multi_date_vote"
                place_results = await search_place(state)
                state["place_search_results"] = place_results
                state["status"] = "functions_called"
                logger.info("[TIMING] function_calling (multi-date): %.2fs", time.monotonic() - _t0)
                return state

        # 선호 데이터 기반 자동 제안: preference_common_times로 슬롯 생성
        pref_times = state.get("preference_common_times") or []
        if (
            pref_times
            and not state.get("date_hint")
            and state.get("intent") != "place_suggestion"
        ):
            # 생성 단계부터 blocked_dates를 제외하면서 만들어야 5개 채우기 가능.
            # F-8 v2 후속: GCal busy 반영해 호스트 일정과 충돌하는 슬롯 skip / 라벨 정확.
            busy_by_user = await _load_busy_by_user_for_state(state)
            pref_slots = _build_preference_time_slots(
                state, pref_times, blocked_dates, busy_by_user=busy_by_user
            )
            pref_slots = _filter_out_rejected(pref_slots, rejected_dates)
            state["calendar_free_slots"] = pref_slots
            state["calendar_strategy"] = "preference_based"
            place_results = await search_place(state)
            state["place_search_results"] = place_results
            state["status"] = "functions_called"
            logger.info("[TIMING] function_calling (preference-based): %.2fs", time.monotonic() - _t0)
            return state

        if (
            state.get("intent") != "place_suggestion"
            and state.get("is_location_first")
            and not state.get("date_hint")
        ):
            state["calendar_free_slots"] = []
            place_results = await search_place(state)
        elif (
            state.get("intent") != "place_suggestion"
            and state.get("time_options")
            and not state.get("preference_common_times")
        ):
            state["calendar_free_slots"] = _filter_out_rejected(
                _filter_out_blocked(_build_time_option_slots(state), blocked_dates),
                rejected_dates,
            )
            state["calendar_strategy"] = "natural_language_time_options"
            place_results = await search_place(state)
        else:
            free_slots, place_results = await asyncio.gather(
                get_free_slots(state),
                search_place(state),
            )
            # get_free_slots에서 이미 필터링되지만, 이중 방어.
            state["calendar_free_slots"] = _filter_out_rejected(
                _filter_out_blocked(free_slots, blocked_dates),
                rejected_dates,
            )
            blocker_counts: dict[str, int] = {}
            if free_slots and any(slot.get("has_conflict") for slot in free_slots):
                for slot in free_slots:
                    for unavailable_user in slot.get("unavailable_users", []):
                        blocker_counts[unavailable_user] = blocker_counts.get(unavailable_user, 0) + 1
                if blocker_counts:
                    blocker_name = max(
                        blocker_counts.items(),
                        key=lambda item: (item[1], item[0]),
                    )[0]
                    state["blocker_notification_payload"] = {
                        "type": "social_system_message",
                        "room_id": state["room_id"],
                        "sender": "매듭이",
                        "content": f"@{blocker_name}님, 혹시 일정 조정이 가능하신가요? 😊",
                        "blocker_name": blocker_name,
                    }
        state["place_search_results"] = place_results
        state["status"] = "functions_called"
        logger.info("[TIMING] function_calling: %.2fs", time.monotonic() - _t0)
        return state
    except Exception as exc:
        return await _handle_node_exception("function_calling", state, exc)
