"""PR-V1.5 / F1 외 0 슬롯 reason 분기 검증.

`function_calling` 노드가 calendar_free_slots == [] 일 때 zero_slot_reason
필드를 박는지 검증. narrator 분기는 vote_card_creation 노드가 사용.

zero_slot_reason 값:
  - "calendar_consent_zero": busy_by_user가 비어있음 (consenting members 0)
  - "all_blocked": busy_by_user는 있는데 fallback도 0개 (모든 시간 blocked)
  - None: 정상 슬롯 발견 또는 그 외.

본 테스트는 GraphState 헬퍼 로직만 검증 — 전체 노드 호출은 integration
테스트 (test_f1_fallback_pipeline 류)에서 다룸.
"""
from __future__ import annotations


def test_state_default_zero_slot_reason_is_none():
    """_default_state 결과의 zero_slot_reason은 초기값 None."""
    # GraphState는 TypedDict라 runtime엔 dict — _default_state 결과를 확인.
    from app.services.pipeline.state import _default_state

    state = _default_state(
        room_id="1",
        db=None,  # type: ignore[arg-type]
        messages=[],
    )
    assert state.get("zero_slot_reason") is None


def test_state_default_rejected_places_is_empty_list():
    """rejected_places 초기값은 빈 list (S16)."""
    from app.services.pipeline.state import _default_state

    state = _default_state(
        room_id="1",
        db=None,  # type: ignore[arg-type]
        messages=[],
    )
    assert state.get("rejected_places") == []


def test_state_default_place_search_empty_is_false():
    """place_search_empty 초기값은 False (§6.15)."""
    from app.services.pipeline.state import _default_state

    state = _default_state(
        room_id="1",
        db=None,  # type: ignore[arg-type]
        messages=[],
    )
    assert state.get("place_search_empty") is False
