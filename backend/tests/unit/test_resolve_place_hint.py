"""PR-V1.5 / §6.17 (F5) — `_resolve_place_hint` 4-step 분기 검증.

1. state["place_hint"] (이미 명시) — fast-path 호환.
2. default_place_hint — 그룹 다수결 (refresh 라우트가 주입).
3. requester_home_base — 발화자 home_base.
4. creator_home_base — 방장 home_base (legacy).
5. None ("") — 검색 skip.
"""
from __future__ import annotations

from app.services.pipeline.helpers.places import _resolve_place_hint


def test_step1_returns_explicit_place_hint():
    """Step 1: place_hint 명시 → 그대로 반환."""
    state: dict = {"place_hint": "강남"}
    assert _resolve_place_hint(state) == "강남"


def test_step2_falls_back_to_default_place_hint():
    """Step 2: place_hint 없음 + default_place_hint 있음 → default 사용."""
    state: dict = {"default_place_hint": "홍대"}
    result = _resolve_place_hint(state)
    assert result == "홍대"
    # state에도 캐시
    assert state["place_hint"] == "홍대"


def test_step3_falls_back_to_requester_home_base():
    """Step 3: place_hint·default 없음 + requester_home_base 있음 → 발화자 home."""
    state: dict = {
        "default_place_hint": "",
        "requester_home_base": "역삼동",
    }
    result = _resolve_place_hint(state)
    assert result == "역삼동"
    assert state["place_hint"] == "역삼동"


def test_step4_falls_back_to_creator_home_base():
    """Step 4: 위 셋 다 없음 + creator_home_base 있음 → 방장 home (legacy)."""
    state: dict = {"creator_home_base": "이태원"}
    result = _resolve_place_hint(state)
    assert result == "이태원"


def test_step5_returns_empty_when_all_missing():
    """Step 5: 모두 없음 → 빈 문자열."""
    state: dict = {}
    assert _resolve_place_hint(state) == ""


def test_priority_order_default_over_requester():
    """우선순위: default_place_hint > requester_home_base."""
    state: dict = {
        "default_place_hint": "강남",
        "requester_home_base": "홍대",
        "creator_home_base": "이태원",
    }
    assert _resolve_place_hint(state) == "강남"


def test_priority_order_requester_over_creator():
    """우선순위: requester_home_base > creator_home_base."""
    state: dict = {
        "requester_home_base": "홍대",
        "creator_home_base": "이태원",
    }
    assert _resolve_place_hint(state) == "홍대"


def test_blank_default_skipped_to_requester():
    """default_place_hint = 공백문자만이면 step3로 진행."""
    state: dict = {
        "default_place_hint": "   ",
        "requester_home_base": "성수",
    }
    assert _resolve_place_hint(state) == "성수"


def test_place_hint_trimmed():
    """place_hint 앞뒤 공백 제거."""
    state: dict = {"place_hint": "  강남  "}
    assert _resolve_place_hint(state) == "강남"
