"""slot_filling 노드 + 9개 분기 헬퍼.

원본 위치: langgraph_pipeline.py 라인 3029~3417 (slot_filling, _enrich_with_preferences,
  _slot_filling_stalemate, _slot_filling_conclusion, _slot_filling_all_members,
  _slot_filling_default, _slot_filling_default_multi_date,
  _slot_filling_default_confirmed, _slot_filling_default_with_defaults,
  _slot_filling_default_partial).

Phase 4 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.
10 함수 / 약 400줄. trigger_reason별 분기 처리.

의존:
  - state.GraphState
  - constants.KST
  - helpers.messaging: _has_node_error, _emit_assistant_message, _handle_node_exception
  - helpers.slot_state: _update_slot_state, _build_flexible_time_options
  - helpers.preferences._load_meeting_preferences
  - app.services.scheduling_round.slot_idx_to_time
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

from app.services import scheduling_round as sr
from app.services.pipeline.constants import KST
from app.services.pipeline.helpers.messaging import (
    _emit_assistant_message,
    _handle_node_exception,
    _has_node_error,
)
from app.services.pipeline.helpers.preferences import _load_meeting_preferences
from app.services.pipeline.helpers.slot_state import (
    _build_flexible_time_options,
    _update_slot_state,
)
from app.services.pipeline.state import GraphState

logger = logging.getLogger(__name__)


async def slot_filling(state: GraphState) -> GraphState:
    """빠진 정보를 질문하지 않고, 현재 가진 정보만으로 최선의 행동을 수행합니다.

    - date만 있으면: 날짜 확인 + 나머지는 대화에서 자연스럽게 나오면 정리하겠다고 안내
    - date+place 있으면: 장소 추천 바로 실행 (location_first_ready)
    - date+place+headcount 있으면: 투표 카드 자동 생성 (slots_filled)
    - 아무것도 없으면: 조용히 대기 (질문하지 않음)
    """
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state

        _update_slot_state(state, state.get("extracted_entities", {}))
        pref_data = await _load_meeting_preferences(state)
        _enrich_with_preferences(state, pref_data)

        trigger = state.get("trigger_reason")
        if trigger == "stalemate_judged":
            return await _slot_filling_stalemate(state, pref_data)
        if trigger == "conclusion_detected":
            return await _slot_filling_conclusion(state, pref_data)
        if trigger == "all_members_selected":
            return await _slot_filling_all_members(state, pref_data)
        return await _slot_filling_default(state, pref_data)
    except Exception as exc:
        return await _handle_node_exception("slot_filling", state, exc)


def _enrich_with_preferences(state: GraphState, pref_data: dict[str, Any]) -> None:
    if pref_data.get("has_preferences") and state.get("intent") != "place_suggestion":
        if not state.get("place_hint") and pref_data.get("best_location"):
            state["place_hint"] = pref_data["best_location"]
            logger.info("[PREF] place_hint set from preferences: %s", pref_data["best_location"])
        if not state.get("headcount") and pref_data.get("total_members"):
            state["headcount"] = pref_data["total_members"]
        if not state.get("meeting_type"):
            state["meeting_type"] = "모임"
        if pref_data.get("all_submitted") and state.get("intent") in (
            "meeting_schedule", "place_suggestion", None,
        ):
            common_times = pref_data.get("common_times", [])
            if common_times:
                state["preference_common_times"] = common_times
            if not state.get("all_slots_filled"):
                state["all_slots_filled"] = True
                state["missing_slots"] = []
                if state.get("place_hint"):
                    logger.info("[PREF] All preferences submitted. Auto-suggesting with place=%s", state["place_hint"])
                else:
                    logger.info("[PREF] All preferences submitted. Auto-suggesting (no place hint, time-only)")
        elif not pref_data.get("all_submitted"):
            common_times = pref_data.get("common_times", [])
            if common_times:
                state["preference_common_times"] = common_times

    state["is_location_first"] = (
        bool(state.get("place_hint"))
        and not bool(state.get("date_hint"))
        and state.get("intent") != "meeting_schedule"
    )
    state["time_options"] = _build_flexible_time_options(state)


async def _slot_filling_stalemate(state: GraphState, pref_data: dict[str, Any]) -> GraphState:
    # 해결점 N: 거부 후 다음 주로 확장된 케이스 — 사용자 선호에 맞는 다음주 전체 후보 생성
    if state.get("expanded_to_next_week"):
        common_times = pref_data.get("common_times") or []
        prefers_weekday = any(str(t).startswith("평일") for t in common_times)
        prefers_weekend = any(str(t).startswith("주말") for t in common_times)
        # 선호 미입력 시 기본값: 둘 다 가능 (보수적)
        if not prefers_weekday and not prefers_weekend:
            prefers_weekday = True
            prefers_weekend = True

        rejected_set = {
            r.get("date") for r in (state.get("rejected_dates") or [])
            if isinstance(r, dict) and isinstance(r.get("date"), str)
        }

        # 오늘부터 시작 — 가까운 평일/주말부터 후보 제시. 거부 set 제외.
        today = datetime.now(KST).date()

        # 오늘부터 21일 스캔 — 거부 후 가까운 후보 우선, 다 차면 종료
        candidates: list[str] = []
        for offset in range(21):
            d = today + timedelta(days=offset)
            is_weekend = d.weekday() >= 5
            if is_weekend and not prefers_weekend:
                continue
            if not is_weekend and not prefers_weekday:
                continue
            iso = d.strftime("%Y-%m-%d")
            if iso in rejected_set:
                continue
            candidates.append(iso)
            if len(candidates) >= 5:  # vote UX: 최대 5개
                break

        if not candidates:
            logger.info("[STALEMATE] No alternatives match user preference, fallback to default")
            state.pop("expanded_to_next_week", None)
            return await _slot_filling_default(state, pref_data)

        state["date_hints"] = candidates
        state["date_hint"] = candidates[0]

        rejected_summary = ", ".join(sorted(rejected_set))
        narrator = (
            "안 되는 날짜들 빼고 가까운 일정으로 추천드릴게요! 📅"
        )
        await _emit_assistant_message(state["room_id"], state["db"], narrator, state)
        if not state.get("headcount"):
            state["headcount"] = pref_data.get("total_members", 4)
        if not state.get("meeting_type"):
            state["meeting_type"] = "모임"
        state["all_slots_filled"] = True
        state["missing_slots"] = []
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "multi_date_vote"
        logger.info(
            "[STALEMATE] Generated alternatives from today (rejected=%s, candidates=%s, weekday_pref=%s, weekend_pref=%s)",
            rejected_summary, candidates, prefers_weekday, prefers_weekend,
        )
        return state

    if not (state.get("conflict_detected") and state.get("conflict_options")):
        return await _slot_filling_default(state, pref_data)

    conflict_type = state.get("conflict_type", "date")
    options = state.get("conflict_options", [])
    options_text = "과 ".join(f"**{o}**" for o in options)
    mediation_msg = f"{options_text} 의견이 나뉘네요! 😊\n"
    if pref_data.get("has_preferences"):
        total = pref_data.get("total_members", 0)
        common = pref_data.get("common_times", [])
        if common and conflict_type in ("date", "time"):
            mediation_msg += f"선호 정보를 보면 공통 가능 시간대는 {', '.join(common)}이에요.\n"
        mediation_msg += f"총 {total}명의 선호를 고려해서 "
    mediation_msg += "투표로 결정할까요?"
    await _emit_assistant_message(state["room_id"], state["db"], mediation_msg, state)

    if conflict_type == "date" and len(options) >= 2:
        state["date_hints"] = options
    elif conflict_type == "place" and len(options) >= 2:
        state["place_hint"] = options[0]
    if not state.get("headcount"):
        state["headcount"] = pref_data.get("total_members", 4)
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "multi_date_vote"
    logger.info("[CONFLICT] Mediation triggered: type=%s options=%s", conflict_type, options)
    return state


async def _slot_filling_conclusion(state: GraphState, pref_data: dict[str, Any]) -> GraphState:
    has_date = bool(state.get("date_hint"))
    has_place = bool(state.get("place_hint"))
    if not has_date and not has_place:
        state["new_assistant_messages"] = []
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "conclusion_false_positive"
        logger.info("[TRIGGER] conclusion_detected false positive, silent abort")
        return state

    if not state.get("headcount"):
        state["headcount"] = pref_data.get("total_members", 4)
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "slots_filled" if has_date and has_place else "slots_filled_with_defaults"
    return state


async def _slot_filling_all_members(state: GraphState, pref_data: dict[str, Any]) -> GraphState:
    # A3-3 (2026-05-08): 호스트 [조율] path. manual_chosen_time이 들어오면 그 값으로 시간 박고
    # partial maedeup 카드 직행. ai_auto_trigger 흐름 재사용 — slot_context를 통해 주입.
    manual_time = state.get("manual_chosen_time")
    if isinstance(manual_time, dict):
        date_str = manual_time.get("date")
        start_idx = manual_time.get("start_idx")
        end_idx = manual_time.get("end_idx")
        if (
            isinstance(date_str, str)
            and isinstance(start_idx, int)
            and isinstance(end_idx, int)
            and start_idx >= 0
            and end_idx >= start_idx
        ):
            # TimeBar slot index → "HH:MM" 변환. sr.slot_idx_to_time이 권위 있는 매핑.
            # end_idx는 INCLUSIVE 슬롯이므로 end_str은 (end_idx + 1)으로 다음 슬롯 시작 시각.
            start_str = sr.slot_idx_to_time(start_idx)
            end_str = sr.slot_idx_to_time(end_idx + 1)
            state["confirmed_date"] = date_str
            state["confirmed_time"] = f"{start_str}~{end_str}"
            state["parsed_time_hint"] = start_str
            state["date_hint"] = date_str
            state["partial_mode"] = "time_only"
            state["status"] = "time_only_ready"
            if not state.get("headcount"):
                state["headcount"] = pref_data.get("total_members", 4)
            if not state.get("meeting_type"):
                state["meeting_type"] = "모임"
            state["all_slots_filled"] = True
            state["missing_slots"] = []
            state["awaiting_user_reply"] = False
            state["wait_timed_out"] = False
            state["message_count_since_last_trigger"] = 0
            logger.info(
                "[TRIGGER] all_members_selected manual host pick: %s %s~%s",
                date_str, start_str, end_str,
            )
            return state

    best_location = pref_data.get("best_location")
    if state.get("place_hint"):
        state["status"] = "location_first_ready"
        logger.info("[TRIGGER] all_members_selected with place_hint=%s", state.get("place_hint"))
    elif best_location:
        state["place_hint"] = best_location
        state["status"] = "location_first_ready"
        logger.info("[TRIGGER] all_members_selected using preference location=%s", best_location)
    else:
        state["partial_mode"] = "time_only"
        state["status"] = "time_only_ready"
        logger.info("[TRIGGER] all_members_selected time-only partial card")

    if not state.get("headcount"):
        state["headcount"] = pref_data.get("total_members", 4)
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    return state


async def _slot_filling_default(state: GraphState, pref_data: dict[str, Any]) -> GraphState:
    if state.get("conflict_detected") and state.get("conflict_options"):
        return await _slot_filling_stalemate(state, pref_data)

    multi_date_hints = state.get("date_hints") or []
    if len(multi_date_hints) >= 2:
        return _slot_filling_default_multi_date(state)

    has_date = bool(state.get("date_hint"))
    has_place = bool(state.get("place_hint"))
    has_headcount = state.get("headcount") is not None
    if state.get("is_location_first"):
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "location_first_ready"
        return state

    if state["all_slots_filled"]:
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "slots_filled"
        return state

    if has_date and has_place and has_headcount:
        return await _slot_filling_default_confirmed(state)
    if has_date and has_place:
        return await _slot_filling_default_with_defaults(state, has_headcount)
    return await _slot_filling_default_partial(state, has_date, has_place)


def _slot_filling_default_multi_date(state: GraphState) -> GraphState:
    if not state.get("headcount"):
        state["headcount"] = 4  # 기본값
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "multi_date_vote"
    return state


async def _slot_filling_default_confirmed(state: GraphState) -> GraphState:
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    date_display = state.get("date_hint", "")
    place_display = state.get("place_hint", "")
    confirm_msg = (
        f"{date_display}에 {place_display}에서 {state.get('headcount', '')}명이요! 👍 "
        "일정과 장소를 정리해드릴게요~"
    )
    await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "slots_filled"
    return state


async def _slot_filling_default_with_defaults(state: GraphState, has_headcount: bool) -> GraphState:
    if not has_headcount:
        state["headcount"] = 4  # 기본값
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    date_display = state.get("date_hint", "")
    place_display = state.get("place_hint", "")
    confirm_msg = (
        f"{date_display}에 {place_display}에서요! 👍 "
        "일정과 장소를 정리해드릴게요~"
    )
    await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "slots_filled_with_defaults"
    return state


async def _slot_filling_default_partial(state: GraphState, has_date: bool, has_place: bool) -> GraphState:
    if has_date and not has_place:
        state["slot_filling_turns"] += 1
        if state["slot_filling_turns"] <= 1:
            date_display = state.get("date_hint", "")
            confirm_msg = (
                f"{date_display} 좋아요! 👍 "
                "장소나 인원이 대화에서 나오면 제가 바로 정리해드릴게요~"
            )
            await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)

        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "partial_info_acknowledged"
        return state

    if has_place and not has_date and state.get("intent") != "meeting_schedule":
        state["slot_filling_turns"] += 1
        if state["slot_filling_turns"] <= 1:
            place_display = state.get("place_hint", "")
            confirm_msg = (
                f"{place_display} 근처로요! 🔍 "
                "맛집 몇 개 찾아볼게요~ 날짜는 대화에서 나오면 정리할게요!"
            )
            await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)
        state["is_location_first"] = True
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "partial_info_acknowledged"
        state["all_slots_filled"] = True  # function_calling으로 진행
        return state

    if state.get("intent") in ("meeting_schedule", "place_suggestion"):
        latest_content = ""
        for msg in reversed(state["message_records"]):
            if msg.get("role") == "user" and msg.get("content"):
                latest_content = msg["content"].strip()
                break
        confirm_msg = (
            f"네! \"{latest_content}\" 알겠어요 👍 "
            "좀 더 구체적인 날짜나 장소가 나오면 바로 정리해드릴게요~"
        )
        await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)

    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "no_slots_yet"
    return state
