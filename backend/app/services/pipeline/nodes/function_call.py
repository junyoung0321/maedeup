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
import re
import time
from datetime import datetime, timedelta, timezone

from app.observability.snapshot import dump
from app.services.kakao_maps import KakaoApiError
from app.services.pipeline.helpers.formatting import _room_id_as_int
from app.services.pipeline.helpers.messaging import (
    _handle_node_exception,
    _has_node_error,
)
from app.services.pipeline.helpers.places import search_place


async def _safe_search_place(state: GraphState) -> list[dict]:
    """PR-V1.5 / F7 — KakaoApiError를 swallow하고 빈 list 반환.

    state["kakao_api_error"] = True 박아서 place_recommendation 노드의
    narrator가 "장소 검색 서비스 일시 불가" 메시지로 분기 가능.
    """
    try:
        return await search_place(state)
    except KakaoApiError as exc:
        logger.warning("[KAKAO_API_ERROR] %s", exc)
        state["kakao_api_error"] = True
        state["place_search_empty"] = False
        return []
from app.services.pipeline.helpers.slots import (
    _build_majority_fallback_slots,
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
    dump("node_in", state.get("run_id"), {
        "node": "function_calling",
        "status": state.get("status"),
        "trigger_reason": state.get("trigger_reason"),
        "has_card": bool(state.get("maedeup_card_payload") or state.get("vote_card_payload")),
        "message_count": len(state.get("message_records", [])),
    })
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

        # next-week expansion redirect: supervisor_validation이 needs_expansion 분기로 보낸 경우.
        # date_hint를 +7일 shift해서 다음 주 GCal 슬롯을 재탐색.
        # needs_next_week_expansion flag는 여기서 즉시 소거 — 무한 루프 방지.
        if state.pop("needs_next_week_expansion", None):
            old_hint = state.get("date_hint")
            if isinstance(old_hint, str) and re.match(r"\d{4}-\d{2}-\d{2}", old_hint):
                shifted = (datetime.fromisoformat(old_hint).replace(tzinfo=timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
            else:
                # date_hint 없는 경우: 내일 기준 +7일 (다음 주 시작점)
                shifted = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=8)).strftime("%Y-%m-%d")
            state["date_hint"] = shifted
            # date_hints도 갱신 (multi-date 경로 방지 — 단일 date_hint로 진행)
            state["date_hints"] = [shifted]
            logger.info(
                "[NEXT_WEEK_EXPANSION] date_hint shifted %s → %s (room=%s)",
                old_hint,
                shifted,
                state.get("room_id"),
            )

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
            place_results = await _safe_search_place(state)
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
                place_results = await _safe_search_place(state)
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
            place_results = await _safe_search_place(state)
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
            place_results = await _safe_search_place(state)
        elif (
            state.get("intent") != "place_suggestion"
            and state.get("time_options")
            and not state.get("preference_common_times")
        ):
            # 2026-06-03 Bug 3 fix: 자연어 시간 옵션도 멤버 GCal busy를 반영해
            # 실제 교집합 가용성으로 슬롯을 만든다. 이전엔 발화자 메시지 텍스트만으로
            # available_count를 headcount(가짜)로 채워, 대화 교착 → AI 자동 개입 시
            # 전원이 가능한 교집합 시간이 아닌 슬롯을 전원 가능처럼 추천했다.
            # multi_date / preference_based 분기와 동일하게 busy_by_user 주입.
            busy_by_user = await _load_busy_by_user_for_state(state)
            state["calendar_free_slots"] = _filter_out_rejected(
                _filter_out_blocked(
                    _build_time_option_slots(state, busy_by_user=busy_by_user),
                    blocked_dates,
                ),
                rejected_dates,
            )
            state["calendar_strategy"] = "natural_language_time_options"
            place_results = await _safe_search_place(state)
        else:
            free_slots, place_results = await asyncio.gather(
                get_free_slots(state),
                _safe_search_place(state),
            )
            # get_free_slots에서 이미 필터링되지만, 이중 방어.
            state["calendar_free_slots"] = _filter_out_rejected(
                _filter_out_blocked(free_slots, blocked_dates),
                rejected_dates,
            )

            # PR-Y1 (F1 fallback, spec §4.4): 전원 가능 슬롯 0개 → 가능 멤버 수 max top 3 발행.
            # PR-V1.5 (2026-05-14): F1 외 0 슬롯 reason 분기 — calendar_consent 0%, all_blocked.
            # 본 분기는 get_free_slots가 busy_by_user 존재 + 전원 가능 슬롯 부재 시.
            if not state["calendar_free_slots"]:
                busy_by_user = await _load_busy_by_user_for_state(state)

                # PR-V1.5: 0 슬롯 reason 판정 — narrator/UX 분기용.
                # 1) busy_by_user 비어있음 → 캘린더 동의 0% (consenting_users == 0).
                # 2) busy_by_user 있는데 free_slots도 비어있고 fallback 슬롯도 불가능 → 모든 시간 blocked.
                if not busy_by_user:
                    state["zero_slot_reason"] = "calendar_consent_zero"
                    logger.info(
                        "[ZERO_SLOT] calendar_consent_zero — consenting members 0"
                    )

                if busy_by_user:
                    # get_free_slots와 동일한 time_min/time_max 계산 규칙 적용.
                    date_hint = state.get("date_hint")
                    now_utc = datetime.now(timezone.utc)
                    if isinstance(date_hint, str) and re.match(r"\d{4}-\d{2}-\d{2}", date_hint):
                        hint_date = datetime.fromisoformat(date_hint).replace(tzinfo=timezone.utc)
                        time_min = hint_date.replace(hour=0, minute=0, second=0, microsecond=0)
                        time_max = time_min + timedelta(days=1)
                    else:
                        time_min = now_utc.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                        time_max = time_min + timedelta(days=14)

                    fallback_slots = _build_majority_fallback_slots(
                        busy_by_user=busy_by_user,
                        time_min=time_min,
                        time_max=time_max,
                        blocked_dates=blocked_dates,
                        rejected_dates=rejected_dates,
                        preferred_times=state.get("preference_common_times") or [],
                    )
                    if fallback_slots:
                        state["calendar_free_slots"] = fallback_slots
                        state["calendar_strategy"] = "majority_fallback"
                        total_members = len(busy_by_user)
                        max_available = max(
                            int(s.get("available_count") or 0) for s in fallback_slots
                        )
                        state["blocker_notification_payload"] = {
                            "type": "f1_fallback",
                            "reason": "no_full_slot",
                            "missing_count": max(total_members - max_available, 0),
                            "total_count": total_members,
                            "max_available_count": max_available,
                        }
                    else:
                        # PR-V1.5: busy_by_user 있고 fallback도 0개 → 모든 시간 blocked.
                        # date_hints가 전부 rejected_dates와 겹쳤거나, blocked_dates가 전부 막은 경우.
                        state["zero_slot_reason"] = "all_blocked"
                        logger.info(
                            "[ZERO_SLOT] all_blocked — busy_by_user has %d members "
                            "but no fallback slots found",
                            len(busy_by_user),
                        )

            blocker_counts: dict[str, int] = {}
            if (
                state.get("calendar_strategy") != "majority_fallback"
                and free_slots
                and any(slot.get("has_conflict") for slot in free_slots)
            ):
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
        dump("node_out", state.get("run_id"), {
            "node": "function_calling",
            "status_after": state.get("status"),
            "card_type": None,
            "slot_count": len(state.get("calendar_free_slots", [])),
        })
        return state
    except Exception as exc:
        return await _handle_node_exception("function_calling", state, exc)
