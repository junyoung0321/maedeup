"""일정 슬롯 스코어링 및 추천 모듈

get_free_slots가 반환하는 공통 가능 시간대 후보들을 모임 유형·인원·상황에 맞게
점수화하여 추천 순서를 결정한다.

슬롯 키: "start"/"end" 또는 "start_at"/"end_at" 모두 허용.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

_HOUR_SCORES: dict[str, dict[int, float]] = {
    "식사": {
        11: 0.8, 12: 1.0, 13: 1.0, 14: 0.7,
        18: 0.9, 19: 1.0, 20: 0.9, 21: 0.6,
    },
    "카페": {
        10: 0.7, 11: 0.9, 12: 0.8, 13: 0.8,
        14: 1.0, 15: 1.0, 16: 0.9, 17: 0.7,
    },
    "술자리": {
        18: 0.6, 19: 0.9, 20: 1.0, 21: 1.0, 22: 0.8,
    },
    "회의": {
        9: 0.9, 10: 1.0, 11: 1.0, 14: 1.0, 15: 1.0, 16: 0.8,
    },
    "모임": {
        18: 0.8, 19: 1.0, 20: 1.0, 21: 0.7,
        12: 0.6, 13: 0.6,
    },
}

_WEEKDAY_SCORES: dict[str, dict[int, float]] = {
    "식사": {0: 0.6, 1: 0.6, 2: 0.6, 3: 0.7, 4: 1.0, 5: 1.0, 6: 0.8},
    "카페": {0: 0.7, 1: 0.7, 2: 0.7, 3: 0.7, 4: 0.8, 5: 1.0, 6: 1.0},
    "술자리": {0: 0.4, 1: 0.4, 2: 0.4, 3: 0.6, 4: 1.0, 5: 1.0, 6: 0.5},
    "회의": {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 0.8, 5: 0.3, 6: 0.2},
    "모임": {0: 0.5, 1: 0.5, 2: 0.5, 3: 0.6, 4: 1.0, 5: 1.0, 6: 0.9},
}

_MIN_DURATION: dict[str, float] = {
    "식사": 1.5,
    "카페": 1.0,
    "술자리": 2.0,
    "회의": 1.0,
    "모임": 1.5,
}

_WEIGHTS = {
    "hour_fit": 0.40,
    "weekday_fit": 0.30,
    "lead_time": 0.20,
    "duration_ok": 0.10,
}

_TYPE_ALIAS = {
    "커피": "카페", "회식": "술자리", "미팅": "회의",
    "맛집": "식사", "밥": "식사", "점심": "식사", "저녁": "식사",
}


def _to_kst(dt_str: str) -> datetime:
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def _slot_start_end(slot: dict) -> tuple[datetime, datetime]:
    start_str = slot.get("start") or slot.get("start_at", "")
    end_str = slot.get("end") or slot.get("end_at", "")
    return _to_kst(start_str), _to_kst(end_str)


def _hour_fit_score(start: datetime, meeting_type: str) -> float:
    hour_map = _HOUR_SCORES.get(meeting_type, _HOUR_SCORES["모임"])
    return hour_map.get(start.hour, 0.2)


def _weekday_fit_score(start: datetime, meeting_type: str) -> float:
    wd_map = _WEEKDAY_SCORES.get(meeting_type, _WEEKDAY_SCORES["모임"])
    return wd_map.get(start.weekday(), 0.5)


def _lead_time_score(start: datetime, now: datetime) -> float:
    days = (start.date() - now.date()).days
    if days <= 0:
        return 0.1
    if days == 1:
        return 0.4
    if days <= 3:
        return 0.8 + (days - 2) * 0.1
    if days <= 7:
        return 1.0 - (days - 3) * 0.05
    if days <= 14:
        return 0.6 - (days - 8) * 0.03
    return max(0.2, 0.4 - (days - 14) * 0.02)


def _duration_ok_score(start: datetime, end: datetime, meeting_type: str, requested_hours: float | None) -> float:
    slot_hours = (end - start).total_seconds() / 3600
    min_h = requested_hours if requested_hours else _MIN_DURATION.get(meeting_type, 1.5)
    if slot_hours < min_h:
        return slot_hours / min_h * 0.8
    ratio = slot_hours / min_h
    return min(1.0, 1.0 - max(0, ratio - 2.0) * 0.1)


def _score_slot(
    slot: dict,
    meeting_type: str,
    duration_hours: float | None,
    now: datetime,
) -> tuple[float, list[str]]:
    start, end = _slot_start_end(slot)

    hour_fit = _hour_fit_score(start, meeting_type)
    weekday_fit = _weekday_fit_score(start, meeting_type)
    lead_time = _lead_time_score(start, now)
    duration_ok = _duration_ok_score(start, end, meeting_type, duration_hours)

    score = (
        _WEIGHTS["hour_fit"] * hour_fit
        + _WEIGHTS["weekday_fit"] * weekday_fit
        + _WEIGHTS["lead_time"] * lead_time
        + _WEIGHTS["duration_ok"] * duration_ok
    )

    reasons: list[str] = []
    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
    wd = weekday_names[start.weekday()]
    h = start.hour
    ampm = "오전" if h < 12 else "오후"
    h12 = h if h <= 12 else h - 12

    if hour_fit >= 0.9:
        reasons.append(f"{meeting_type} 모임에 최적인 {ampm} {h12}시")
    elif hour_fit >= 0.6:
        reasons.append(f"{meeting_type} 모임에 적합한 시간대")

    if weekday_fit >= 0.9:
        reasons.append(f"{wd}요일 최선호")
    elif weekday_fit >= 0.7:
        reasons.append(f"{wd}요일 선호")

    days_away = (start.date() - now.date()).days
    if 2 <= days_away <= 5:
        reasons.append(f"{days_away}일 후 (여유 있는 일정)")
    elif days_away == 1:
        reasons.append("내일 (촉박한 일정)")

    slot_h = (end - start).total_seconds() / 3600
    min_h = duration_hours or _MIN_DURATION.get(meeting_type, 1.5)
    if slot_h >= min_h:
        reasons.append(f"충분한 시간 ({slot_h:.1f}h)")

    return round(score, 4), reasons


def rank_slots(
    slots: list[dict],
    context: dict,
    top_k: int = 5,
    now: datetime | None = None,
) -> list[dict]:
    """후보 슬롯을 모임 컨텍스트에 맞게 스코어링 후 정렬.

    슬롯 키: "start"/"end" 또는 "start_at"/"end_at" 모두 허용.
    """
    if not slots:
        return []

    if now is None:
        now = datetime.now(tz=KST)

    meeting_type = (context.get("meeting_type") or "모임").strip()
    meeting_type = _TYPE_ALIAS.get(meeting_type, meeting_type)
    if meeting_type not in _HOUR_SCORES:
        meeting_type = "모임"

    duration_hours: float | None = context.get("duration_hours")

    scored: list[tuple[float, int, dict]] = []
    for i, slot in enumerate(slots):
        try:
            score, reasons = _score_slot(slot, meeting_type, duration_hours, now)
            start, end = _slot_start_end(slot)
            breakdown = {
                "hour_fit": round(_hour_fit_score(start, meeting_type), 3),
                "weekday_fit": round(_weekday_fit_score(start, meeting_type), 3),
                "lead_time": round(_lead_time_score(start, now), 3),
                "duration_ok": round(_duration_ok_score(start, end, meeting_type, duration_hours), 3),
            }
        except (KeyError, ValueError):
            score, reasons, breakdown = 0.3, [], {}

        scored.append((score, i, {**slot, "score": score, "reasons": reasons, "score_breakdown": breakdown}))

    scored.sort(key=lambda x: -x[0])

    return [
        {**slot_dict, "rank": rank_idx}
        for rank_idx, (_, _, slot_dict) in enumerate(scored[:top_k], start=1)
    ]
