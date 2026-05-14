"""
Integration tests — F1 fallback (PR-Y1).

`function_calling` 노드가 전원 가능 슬롯 0개일 때 majority_fallback 전략으로 분기,
`vote_card_creation`이 단일 슬롯 skip을 우회하고 narrator를 발행하는지 검증.

외부 의존 (Google Calendar / Kakao / DB pending meeting)은 monkeypatch로 격리.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.pipeline.constants import KST
from app.services.pipeline.nodes import function_call as fc_module
from app.services.pipeline.nodes import vote_card as vc_module


def _kst_dt(date_iso: str, hour: int) -> datetime:
    return datetime.fromisoformat(f"{date_iso}T00:00:00").replace(
        tzinfo=KST, hour=hour
    )


def _base_state(db: Any) -> dict[str, Any]:
    """function_calling이 else 분기에 진입할 최소 state."""
    return {
        "room_id": "10",
        "db": db,
        "status": "intent_classified",
        "intent": "scheduling",
        "calendar_free_slots": [],
        "place_search_results": [],
        "blocker_notification_payload": None,
        "calendar_strategy": None,
        "preference_common_times": [],
        "rejected_dates": [],
        "date_hints": [],
        "date_hint": "2026-05-20",
        "is_location_first": False,
        "time_options": [],
        "place_hint": None,
        "message_records": [],
        "seen_message_ids": [],
        "new_assistant_messages": [],
        "headcount": 4,
        "viewer_user_id": None,
    }


@pytest.mark.asyncio
async def test_function_call_triggers_majority_fallback(monkeypatch):
    """
    get_free_slots가 빈 리스트 반환 + busy_by_user는 살아있는 상황 →
    state["calendar_strategy"] == "majority_fallback", calendar_free_slots 길이 ≤ 3,
    blocker_notification_payload type == "f1_fallback".
    """
    date = "2026-05-20"

    # 모든 슬롯에 최소 1명 충돌하도록 4명 busy 구성 (전원 가능 슬롯 0개).
    busy_by_user = {
        "1:Alice": [
            {"start": _kst_dt(date, 9), "end": _kst_dt(date, 22)},
        ],
        "2:Bob": [{"start": _kst_dt(date, 10), "end": _kst_dt(date, 11)}],
        "3:Carol": [{"start": _kst_dt(date, 12), "end": _kst_dt(date, 13)}],
        "4:Dan": [],
    }

    async def _fake_get_free_slots(state):
        return []

    async def _fake_search_place(state):
        return []

    async def _fake_load_blocked(room_pk):
        return set()

    async def _fake_load_busy(state):
        return busy_by_user

    monkeypatch.setattr(fc_module, "get_free_slots", _fake_get_free_slots)
    monkeypatch.setattr(fc_module, "search_place", _fake_search_place)
    monkeypatch.setattr(fc_module, "_load_blocked_dates", _fake_load_blocked)
    monkeypatch.setattr(fc_module, "_load_busy_by_user_for_state", _fake_load_busy)

    state = _base_state(db=SimpleNamespace())

    result = await fc_module.function_calling(state)

    assert result["calendar_strategy"] == "majority_fallback"
    slots = result["calendar_free_slots"]
    assert 1 <= len(slots) <= 3
    # available_count desc 정렬
    counts = [s["available_count"] for s in slots]
    assert counts == sorted(counts, reverse=True)

    payload = result["blocker_notification_payload"]
    assert payload is not None
    assert payload["type"] == "f1_fallback"
    assert payload["reason"] == "no_full_slot"
    assert payload["total_count"] == 4
    assert payload["missing_count"] >= 1


@pytest.mark.asyncio
async def test_function_call_no_fallback_when_busy_empty(monkeypatch):
    """busy_by_user가 비어있으면 (캘린더 미연동 0%) F1 fallback도 발동 안 함 — 별도 PR 영역."""
    async def _fake_get_free_slots(state):
        return []

    async def _fake_search_place(state):
        return []

    async def _fake_load_blocked(room_pk):
        return set()

    async def _fake_load_busy(state):
        return {}

    monkeypatch.setattr(fc_module, "get_free_slots", _fake_get_free_slots)
    monkeypatch.setattr(fc_module, "search_place", _fake_search_place)
    monkeypatch.setattr(fc_module, "_load_blocked_dates", _fake_load_blocked)
    monkeypatch.setattr(fc_module, "_load_busy_by_user_for_state", _fake_load_busy)

    state = _base_state(db=SimpleNamespace())
    result = await fc_module.function_calling(state)

    assert result["calendar_strategy"] != "majority_fallback"
    assert result["calendar_free_slots"] == []


@pytest.mark.asyncio
async def test_vote_card_creation_skips_skip_for_majority_fallback(monkeypatch):
    """
    majority_fallback 상태에서 vote_card_creation 호출 → 단일 슬롯이 아니어도 카드 발행되며,
    narrator에 "전원 가능한 시간이 없어" 포함.
    """
    emitted_messages: list[str] = []

    async def _fake_emit(room_id, db, content, state, *, shared=False):
        emitted_messages.append(content)

    # AsyncSessionLocal context manager mock
    class _FakeSession:
        async def __aenter__(self):
            return SimpleNamespace()

        async def __aexit__(self, *a):
            return False

    def _fake_session_factory():
        return _FakeSession()

    monkeypatch.setattr(vc_module, "_emit_assistant_message", _fake_emit)
    monkeypatch.setattr(vc_module, "AsyncSessionLocal", _fake_session_factory)

    # state — calendar_free_slots에 3개 슬롯, meeting_id는 슬롯에 직접 박아 DB 우회.
    slot_template = {
        "slot_id": "majority-slot-1",
        "label": "5/20 (수) 09:00",
        "start_at": "2026-05-20T09:00:00+09:00",
        "end_at": "2026-05-20T10:00:00+09:00",
        "is_holiday": False,
        "holiday_name": None,
        "is_weekend": False,
        "available_count": 3,
        "total_count": 4,
        "unavailable_users": ["Alice"],
        "meeting_id": 999,  # DB 우회 — _ensure_pending_meeting_id 안 타게.
    }
    slot2 = {**slot_template, "slot_id": "majority-slot-2", "available_count": 2,
             "start_at": "2026-05-20T10:00:00+09:00"}
    slot3 = {**slot_template, "slot_id": "majority-slot-3", "available_count": 2,
             "start_at": "2026-05-20T11:00:00+09:00"}

    state: dict[str, Any] = {
        "room_id": "10",
        "db": SimpleNamespace(),
        "status": "functions_called",
        "calendar_free_slots": [slot_template, slot2, slot3],
        "calendar_strategy": "majority_fallback",
        "date_hint": "2026-05-20",
        "preference_common_times": [],
        "rejected_dates": [],
        "headcount": 4,
        "meeting_type": "모임",
        "blocker_notification_payload": {
            "type": "f1_fallback",
            "reason": "no_full_slot",
            "missing_count": 1,
            "total_count": 4,
            "max_available_count": 3,
        },
        "message_records": [],
        "seen_message_ids": [],
        "new_assistant_messages": [],
        "viewer_user_id": None,
    }

    result = await vc_module.vote_card_creation(state)

    # 단일 슬롯 skip을 우회했어야 함 — vote_card_payload가 발행됨.
    assert result["status"] == "vote_card_created"
    payload = result.get("vote_card_payload")
    assert payload is not None
    assert payload["calendar_strategy"] == "majority_fallback"
    # time_options에 available_count / unavailable_users 포함
    assert len(payload["time_options"]) == 3
    first_option = payload["time_options"][0]
    assert "available_count" in first_option
    assert "total_count" in first_option
    assert "unavailable_users" in first_option

    # narrator 검증
    assert emitted_messages, "narrator 메시지가 emit되지 않았습니다"
    assert any("전원 가능한 시간이 없어" in msg for msg in emitted_messages)
