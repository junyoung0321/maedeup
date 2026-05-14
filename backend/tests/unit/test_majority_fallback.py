"""
Tests for `_build_majority_fallback_slots` — F1 fallback (spec §4.4).

전원 가능 슬롯이 없을 때 가능 멤버 수가 가장 많은 슬롯 top 3를 발행하는 헬퍼.

WORK_HOUR_START=9, WORK_HOUR_END=22, SLOT_MINUTES=60 (KST 09:00~22:00 정시 단위).
busy_by_user의 키는 `_user_calendar_key(user)` 형식 ("id:name") — display name 추출용.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.pipeline.constants import KST
from app.services.pipeline.helpers.slots import _build_majority_fallback_slots


def _kst_dt(date_iso: str, hour: int, minute: int = 0) -> datetime:
    """KST aware datetime helper."""
    return datetime.fromisoformat(f"{date_iso}T00:00:00").replace(
        tzinfo=KST, hour=hour, minute=minute
    )


def _utc_dt(date_iso: str, hour: int, minute: int = 0) -> datetime:
    """UTC aware datetime helper (time_min/time_max용)."""
    return datetime.fromisoformat(f"{date_iso}T00:00:00").replace(
        tzinfo=timezone.utc, hour=hour, minute=minute
    )


def test_majority_fallback_picks_top3_by_available_count():
    """4명 멤버, 각 슬롯에 최소 1명 충돌. available_count desc 정렬 + top 3 반환."""
    # 2026-05-20 (수) KST 09:00~13:00 = 4개 슬롯.
    # 09:00 → A 충돌 (3/4 가능)
    # 10:00 → A,B 충돌 (2/4)
    # 11:00 → A,B,C 충돌 (1/4)
    # 12:00 → A 충돌 (3/4)
    date = "2026-05-20"
    a_busy = [
        {"start": _kst_dt(date, 9), "end": _kst_dt(date, 13)},  # 09~12 모두 충돌
    ]
    b_busy = [
        {"start": _kst_dt(date, 10), "end": _kst_dt(date, 12)},
    ]
    c_busy = [
        {"start": _kst_dt(date, 11), "end": _kst_dt(date, 12)},
    ]
    busy_by_user = {
        "1:Alice": a_busy,
        "2:Bob": b_busy,
        "3:Carol": c_busy,
        "4:Dan": [],
    }
    # KST 09~13 = UTC 00~04
    time_min = _utc_dt(date, 0)
    time_max = _utc_dt(date, 4)

    result = _build_majority_fallback_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
    )

    assert len(result) <= 3
    # available_count desc 검증
    counts = [s["available_count"] for s in result]
    assert counts == sorted(counts, reverse=True)
    # top 1은 가능 인원 3명 (09시 또는 12시)
    assert result[0]["available_count"] == 3
    assert result[0]["total_count"] == 4
    # unavailable_users는 display name 리스트
    assert isinstance(result[0]["unavailable_users"], list)


def test_majority_fallback_tie_sorted_by_start_at():
    """가능 멤버 수 동률 → start_at 오름차순."""
    date = "2026-05-21"
    # 4명 모두 어느 슬롯에서도 한 명씩만 충돌 (가능 = 3) → 모든 슬롯이 available=3 동률.
    # KST 09:00 → A 충돌, 10:00 → B, 11:00 → C, 12:00 → D, 13:00 → A — 모두 가능 3명.
    busy_by_user = {
        "1:A": [
            {"start": _kst_dt(date, 9), "end": _kst_dt(date, 10)},
            {"start": _kst_dt(date, 13), "end": _kst_dt(date, 14)},
        ],
        "2:B": [{"start": _kst_dt(date, 10), "end": _kst_dt(date, 11)}],
        "3:C": [{"start": _kst_dt(date, 11), "end": _kst_dt(date, 12)}],
        "4:D": [{"start": _kst_dt(date, 12), "end": _kst_dt(date, 13)}],
    }
    time_min = _utc_dt(date, 0)
    time_max = _utc_dt(date, 5)  # KST 09~14, 5개 슬롯

    result = _build_majority_fallback_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
    )

    assert len(result) == 3  # top 3
    # 모두 동률
    assert all(s["available_count"] == 3 for s in result)
    # start_at 오름차순 (시간 빠른 순)
    start_ats = [s["start_at"] for s in result]
    assert start_ats == sorted(start_ats)


def test_majority_fallback_respects_blocked_rejected():
    """blocked_dates에 포함된 날짜는 후보 풀에서 제외."""
    blocked_date = "2026-05-22"
    open_date = "2026-05-23"
    busy_by_user = {
        "1:A": [],
        "2:B": [{"start": _kst_dt(blocked_date, 9), "end": _kst_dt(blocked_date, 10)}],
        # open_date는 모두 가능 (전원 가능 슬롯 → 그래도 후보로 들어와도 OK, blocked만 거름)
    }
    time_min = _utc_dt(blocked_date, 0)
    # 22일 09~12 KST + 23일 09~12 KST 모두 스캔
    time_max = _utc_dt(open_date, 4)

    result = _build_majority_fallback_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
        blocked_dates={blocked_date},
    )

    # blocked_date의 슬롯은 모두 제외됨
    for slot in result:
        assert not slot["start_at"].startswith(blocked_date)

    # rejected_dates 검증
    rejected = [{"date": open_date}]
    result2 = _build_majority_fallback_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
        rejected_dates=rejected,
    )
    for slot in result2:
        assert not slot["start_at"].startswith(open_date)


def test_majority_fallback_empty_when_no_users():
    """busy_by_user 빈 dict → 빈 리스트."""
    result = _build_majority_fallback_slots(
        busy_by_user={},
        time_min=_utc_dt("2026-05-20", 0),
        time_max=_utc_dt("2026-05-20", 12),
    )
    assert result == []
