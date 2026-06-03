"""
Unit tests for _build_time_option_slots — 자연어 시간 옵션 슬롯의 멤버 가용성 교집합.

2026-06-03 Bug 3: 대화 교착 → AI 자동 개입으로 시간을 추천할 때, 대화에 자연어
시간 표현이 있으면 natural_language_time_options 경로(_build_time_option_slots)를
타는데, 이 함수가 멤버 캘린더 busy를 전혀 반영하지 않고 available_count를
headcount로 가짜로 채웠다. 그 결과 "전원이 가능한 교집합 시간"이 아닌 슬롯도
전원 가능처럼 추천됐다. _build_multi_date_slots / _build_preference_time_slots와
동일하게 busy_by_user를 반영해 실제 가용성으로 계산·정렬해야 한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.pipeline.helpers.slots import _build_time_option_slots

KST = timezone(timedelta(hours=9))


def _state():
    return {
        "date_hint": "2026-05-30",  # 토
        "time_options": ["13:00", "14:00", "15:00"],
        "headcount": 3,
    }


def _busy(h_start: int, m_start: int, h_end: int, m_end: int):
    base = datetime(2026, 5, 30, tzinfo=KST)
    return {
        "start": base.replace(hour=h_start, minute=m_start),
        "end": base.replace(hour=h_end, minute=m_end),
    }


def test_no_busy_data_preserves_headcount_and_order():
    """busy 데이터 없으면(캘린더 동의 0 등) 기존 동작 유지 — 전 슬롯 headcount, 시간순."""
    slots = _build_time_option_slots(_state(), busy_by_user=None)
    assert [s["start_at"][11:16] for s in slots] == ["13:00", "14:00", "15:00"]
    assert all(s["available_count"] == 3 for s in slots)
    assert all(s["has_conflict"] is False for s in slots)


def test_busy_data_reflected_as_real_availability_and_ranked():
    """멤버 busy를 반영: 가능 인원수 정확 + 전원 가능 슬롯이 먼저 추천(교집합 우선)."""
    busy_by_user = {
        "A": [_busy(13, 0, 13, 30)],   # 13:00 슬롯(13~14)만 겹침
        "B": [_busy(13, 30, 14, 30)],  # 13:00·14:00 슬롯 겹침
        "C": [],                        # 항상 가능
    }
    slots = _build_time_option_slots(_state(), busy_by_user=busy_by_user)

    by_time = {s["start_at"][11:16]: s for s in slots}
    # 13:00 — A,B 불가 → 1명 가능
    assert by_time["13:00"]["available_count"] == 1
    assert by_time["13:00"]["has_conflict"] is True
    assert len(by_time["13:00"]["unavailable_users"]) == 2
    # 14:00 — B 불가 → 2명 가능
    assert by_time["14:00"]["available_count"] == 2
    assert len(by_time["14:00"]["unavailable_users"]) == 1
    # 15:00 — 전원 가능 → 3명
    assert by_time["15:00"]["available_count"] == 3
    assert by_time["15:00"]["has_conflict"] is False

    # 교집합 우선 정렬: 전원 가능한 15:00이 첫 추천이어야 한다.
    assert slots[0]["start_at"][11:16] == "15:00"
    assert slots[0]["available_count"] == 3
