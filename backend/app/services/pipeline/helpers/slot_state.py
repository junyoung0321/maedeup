"""슬롯 state 관리 헬퍼.

원본 위치: langgraph_pipeline.py 라인 358~366 (_coerce_headcount),
  368~407 (_update_slot_state), 409~414 (_has_meaningful_slot_progress),
  853~867 (_build_flexible_time_options), 870~872 (_normalize_preferred_time),
  874~883 (_normalize_preferred_times), 885~903 (_preference_score_for_start),
  1313~1321 (_slot_snapshot).

Phase 3 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

조정 메모: _coerce_bool은 dates.py로 옮겨졌으므로 본 모듈에서 import 사용.

의존:
  - state.GraphState
  - constants: SLOT_KEYS, PREFERRED_TIME_RANGES, KST
  - dates: _coerce_bool, _is_specific_iso_date, _is_weekend
  - formatting: _infer_time_bucket
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.pipeline.constants import KST, PREFERRED_TIME_RANGES, SLOT_KEYS
from app.services.pipeline.helpers.dates import (
    _coerce_bool,
    _is_specific_iso_date,
    _is_weekend,
)
from app.services.pipeline.helpers.formatting import _infer_time_bucket
from app.services.pipeline.state import GraphState


def _coerce_headcount(value: Any) -> int | None:
    if value in (None, "", []):
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count > 0 else None


def _update_slot_state(state: GraphState, extracted: dict[str, Any]) -> None:
    previous_date_hint = state.get("date_hint")
    date_hint = extracted.get("date_hint")
    date_hints = extracted.get("date_hints")
    place_hint = extracted.get("place_hint")
    meeting_type = extracted.get("meeting_type")
    headcount = _coerce_headcount(extracted.get("headcount"))
    parsed_time_hint = extracted.get("parsed_time_hint")
    date_is_flexible = extracted.get("date_is_flexible")
    date_hint_source_text = extracted.get("date_hint_source_text")

    if date_hint not in (None, ""):
        state["date_hint"] = str(date_hint)
    if isinstance(date_hints, list) and len(date_hints) >= 2:
        state["date_hints"] = [str(d) for d in date_hints]
    if place_hint not in (None, ""):
        state["place_hint"] = str(place_hint)
    if meeting_type not in (None, ""):
        state["meeting_type"] = str(meeting_type)
    if headcount is not None:
        state["headcount"] = headcount
    if "parsed_time_hint" in extracted:
        state["parsed_time_hint"] = str(parsed_time_hint) if parsed_time_hint not in (None, "") else None
    if "date_is_flexible" in extracted:
        state["date_is_flexible"] = _coerce_bool(date_is_flexible)
    if "date_hint_source_text" in extracted:
        state["date_hint_source_text"] = (
            str(date_hint_source_text) if date_hint_source_text not in (None, "") else None
        )
    if previous_date_hint != state.get("date_hint"):
        state["time_options"] = []

    missing_slots: list[str] = []
    for key in SLOT_KEYS:
        if state.get(key) in (None, "", []):
            missing_slots.append(key)

    state["missing_slots"] = missing_slots
    state["all_slots_filled"] = not missing_slots


def _has_meaningful_slot_progress(previous_missing_slots: list[str], state: GraphState) -> bool:
    for key in previous_missing_slots:
        if state.get(key) not in (None, "", []):
            return True
    return False


def _build_flexible_time_options(state: GraphState) -> list[str]:
    if not _is_specific_iso_date(state.get("date_hint")):
        return []

    # Fix 8a (2026-05-14): 명시 시간 (parsed_time_hint + is_flexible=False) → 단일 슬롯.
    # "내일 오후 6시" 같은 입력에서 사용자 의도 그대로 vote_card에 반영.
    # Fix 7과 결합: 정확한 정수 시간이 단일 슬롯으로 카드에 노출.
    parsed_time_hint = state.get("parsed_time_hint")
    if parsed_time_hint and not state.get("date_is_flexible"):
        return [parsed_time_hint]

    # 기존 flexible 시간 → bucket-based 3개 옵션
    if not state.get("date_is_flexible"):
        return []

    bucket = _infer_time_bucket(
        state.get("date_hint_source_text"),
        state.get("parsed_time_hint"),
    )
    if bucket == "evening":
        return ["18:00", "19:00", "20:00"]
    if bucket == "morning":
        return ["09:00", "10:00", "11:00"]
    return ["13:00", "14:00", "15:00"]


def _normalize_preferred_time(value: Any) -> str:
    return str(value or "").strip().replace(" ", "")


def _normalize_preferred_times(values: list[Any] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = _normalize_preferred_time(value)
        if item in PREFERRED_TIME_RANGES and item not in seen:
            seen.add(item)
            normalized.append(item)
    return normalized


def _preference_score_for_start(start_at: datetime, pref_times: list[str]) -> int:
    if not pref_times:
        return 0
    start_kst = start_at.astimezone(KST)
    is_weekend = _is_weekend(start_kst)
    score = 0
    for pref_time in pref_times:
        normalized = _normalize_preferred_time(pref_time)
        hours = PREFERRED_TIME_RANGES.get(normalized)
        if not hours:
            continue
        if normalized.startswith("평일") and is_weekend:
            continue
        if normalized.startswith("주말") and not is_weekend:
            continue
        start_hour, end_hour = hours
        if start_hour <= start_kst.hour < end_hour:
            score += 1
    return score


def _slot_snapshot(state: GraphState) -> dict[str, Any]:
    return {
        "date_hint": state.get("date_hint"),
        "place_hint": state.get("place_hint"),
        "headcount": state.get("headcount"),
        "meeting_type": state.get("meeting_type"),
        "all_slots_filled": state.get("all_slots_filled", False),
    }
