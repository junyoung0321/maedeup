"""일정 슬롯 스코어링 및 추천 모듈

get_free_slots가 반환하는 공통 가능 시간대 후보들을 모임 유형·인원·상황에 맞게
점수화하여 추천 순서를 결정한다.

사용법:
    from serving.slot_ranker import rank_slots

    slots = [
        {"start": "2026-04-16T18:00:00+09:00", "end": "2026-04-16T20:00:00+09:00"},
        {"start": "2026-04-17T12:00:00+09:00", "end": "2026-04-17T13:30:00+09:00"},
        ...
    ]
    context = {
        "meeting_type": "식사",   # 식사 / 카페 / 술자리 / 회의 / 모임
        "headcount": 5,
        "duration_hours": 1.5,   # 예상 소요 시간 (선택)
    }
    ranked = rank_slots(slots, context, top_k=3)
    # [{"start": ..., "end": ..., "score": 0.84, "rank": 1, "reasons": [...]}, ...]

스코어링 4개 차원 (각 0~1, 가중합):
  1. hour_fit    (0.40): 모임 유형별 선호 시작 시간
  2. weekday_fit (0.30): 모임 유형별 선호 요일
  3. lead_time   (0.20): 오늘부터 2~7일 사이 슬롯 선호
  4. duration_ok (0.10): 예상 소요 시간 대비 슬롯 길이 충분성
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# ── 모임 유형별 설정 ─────────────────────────────────────────────────────────

# 시간대 적합도: 시작 시간(hour) → score (0~1)
# 지정되지 않은 hour는 0.2 기본값
_HOUR_SCORES: dict[str, dict[int, float]] = {
    "식사": {
        11: 0.8, 12: 1.0, 13: 1.0, 14: 0.7,   # 점심
        18: 0.9, 19: 1.0, 20: 0.9, 21: 0.6,   # 저녁
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
    "모임": {  # 일반 모임 — 저녁 선호
        18: 0.8, 19: 1.0, 20: 1.0, 21: 0.7,
        12: 0.6, 13: 0.6,
    },
}

# 요일 적합도: weekday(0=월 ~ 6=일) → score (0~1)
_WEEKDAY_SCORES: dict[str, dict[int, float]] = {
    "식사": {0: 0.6, 1: 0.6, 2: 0.6, 3: 0.7, 4: 1.0, 5: 1.0, 6: 0.8},
    "카페": {0: 0.7, 1: 0.7, 2: 0.7, 3: 0.7, 4: 0.8, 5: 1.0, 6: 1.0},
    "술자리": {0: 0.4, 1: 0.4, 2: 0.4, 3: 0.6, 4: 1.0, 5: 1.0, 6: 0.5},
    "회의": {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 0.8, 5: 0.3, 6: 0.2},
    "모임": {0: 0.5, 1: 0.5, 2: 0.5, 3: 0.6, 4: 1.0, 5: 1.0, 6: 0.9},
}

# 모임 유형별 최소 권장 소요 시간 (hours)
_MIN_DURATION: dict[str, float] = {
    "식사": 1.5,
    "카페": 1.0,
    "술자리": 2.0,
    "회의": 1.0,
    "모임": 1.5,
}

# 스코어 가중치
_WEIGHTS = {
    "hour_fit": 0.40,
    "weekday_fit": 0.30,
    "lead_time": 0.20,
    "duration_ok": 0.10,
}


def _to_kst(dt_str: str) -> datetime:
    """ISO 8601 문자열 → KST datetime 변환."""
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def _hour_fit_score(start: datetime, meeting_type: str) -> float:
    """시작 시간 기반 적합도 (0~1)."""
    hour_map = _HOUR_SCORES.get(meeting_type, _HOUR_SCORES["모임"])
    return hour_map.get(start.hour, 0.2)


def _weekday_fit_score(start: datetime, meeting_type: str) -> float:
    """요일 기반 적합도 (0~1). 0=월요일, 6=일요일."""
    wd_map = _WEEKDAY_SCORES.get(meeting_type, _WEEKDAY_SCORES["모임"])
    return wd_map.get(start.weekday(), 0.5)


def _lead_time_score(start: datetime, now: datetime) -> float:
    """리드타임 선호 점수 (0~1).

    너무 촉박(0~1일): 0.3
    적당(2~7일): 1.0 (3일째 peak)
    조금 멈(8~14일): 0.6
    너무 멈(15일+): 0.3
    """
    days = (start.date() - now.date()).days
    if days <= 0:
        return 0.1
    if days == 1:
        return 0.4
    if days <= 3:
        return 0.8 + (days - 2) * 0.1  # 2일→0.8, 3일→0.9
    if days <= 7:
        return 1.0 - (days - 3) * 0.05  # 4일→0.95, 7일→0.80
    if days <= 14:
        return 0.6 - (days - 8) * 0.03  # 8일→0.6, 14일→0.42
    return max(0.2, 0.4 - (days - 14) * 0.02)


def _duration_ok_score(start: datetime, end: datetime, meeting_type: str, requested_hours: float | None) -> float:
    """슬롯 길이 충분성 점수 (0~1).

    요청 시간 또는 유형별 최소 시간 대비 슬롯 길이 비율로 계산.
    초과분은 diminishing return.
    """
    slot_hours = (end - start).total_seconds() / 3600
    min_h = requested_hours if requested_hours else _MIN_DURATION.get(meeting_type, 1.5)

    if slot_hours < min_h:
        return slot_hours / min_h * 0.8  # 부족 시 선형 감소
    ratio = slot_hours / min_h
    # 충분하면 1.0, 2배 이상이면 약간 감소 (너무 긴 슬롯은 선택 부담)
    return min(1.0, 1.0 - max(0, ratio - 2.0) * 0.1)


def _score_slot(
    slot: dict,
    meeting_type: str,
    duration_hours: float | None,
    now: datetime,
) -> tuple[float, list[str]]:
    """단일 슬롯 점수 계산. (score 0~1, 이유 리스트) 반환."""
    start = _to_kst(slot["start"])
    end = _to_kst(slot["end"])

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

    # 점수 근거 메시지 생성
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
    """후보 시간 슬롯을 모임 컨텍스트에 맞게 스코어링 후 정렬.

    Args:
        slots: get_free_slots 반환 형태의 리스트.
               각 dict: {"start": ISO8601, "end": ISO8601, ...}
        context: {
            "meeting_type": str,    # 식사/카페/술자리/회의/모임
            "headcount": int,       # 참여 인원 (현재 미사용, 확장 여지)
            "duration_hours": float # 예상 소요 시간 (선택)
        }
        top_k: 반환할 최대 슬롯 수
        now: 기준 현재시각 (None이면 실시간). 테스트용 오버라이드 가능.

    Returns:
        score 내림차순 정렬된 dict 리스트.
        각 항목: 원본 slot dict + {
            "score": float,
            "rank": int,
            "reasons": list[str],
            "score_breakdown": {"hour_fit": ..., "weekday_fit": ..., ...}
        }
    """
    if not slots:
        return []

    if now is None:
        now = datetime.now(tz=KST)

    meeting_type = (context.get("meeting_type") or "모임").strip()
    # 유사 표현 정규화
    _type_alias = {
        "커피": "카페", "회식": "술자리", "미팅": "회의",
    }
    meeting_type = _type_alias.get(meeting_type, meeting_type)
    if meeting_type not in _HOUR_SCORES:
        meeting_type = "모임"

    duration_hours: float | None = context.get("duration_hours")

    scored: list[tuple[float, int, dict]] = []
    for i, slot in enumerate(slots):
        try:
            score, reasons = _score_slot(slot, meeting_type, duration_hours, now)
        except (KeyError, ValueError):
            score, reasons = 0.3, []

        # 세부 점수 계산 (반환용)
        start = _to_kst(slot["start"])
        end = _to_kst(slot["end"])
        breakdown = {
            "hour_fit": round(_hour_fit_score(start, meeting_type), 3),
            "weekday_fit": round(_weekday_fit_score(start, meeting_type), 3),
            "lead_time": round(_lead_time_score(start, now), 3),
            "duration_ok": round(_duration_ok_score(start, end, meeting_type, duration_hours), 3),
        }
        scored.append((score, i, {**slot, "score": score, "reasons": reasons, "score_breakdown": breakdown}))

    scored.sort(key=lambda x: -x[0])

    results = []
    for rank_idx, (_, _, slot_dict) in enumerate(scored[:top_k], start=1):
        results.append({**slot_dict, "rank": rank_idx})

    return results
