"""Unit tests for app.services.pipeline.helpers.preference_toggle.

PR-Z1 (2026-05-14) — Q7-c 차단 조건 + preference_source 라벨 계산.

Q7-c false 조건: C1 ∨ C3 ∨ C4 (게스트 C2 제외).
"""
from __future__ import annotations

from app.services.pipeline.helpers.preference_toggle import (
    compute_preference_source,
    compute_preference_toggle_enabled,
)


def _make_state(
    *,
    home_base: str | None = "서울 강남",
    prefs: dict | None = None,
    preference_source: str | None = None,
) -> dict:
    """GraphState-like dict factory. dict는 TypedDict의 런타임 표현."""
    if prefs is None:
        prefs = {
            "food_preferences": ["한식"],
            "food_restrictions": None,
            "liked_areas": None,
            "disliked_areas": None,
            "transport_mode": None,
            "time_preference": None,
            "share_food_data": True,
            "share_location_data": True,
            "share_schedule_data": True,
            "is_guest": False,
        }
    state: dict = {
        "requester_home_base": home_base,
        "requester_preferences": prefs,
    }
    if preference_source is not None:
        state["preference_source"] = preference_source
    return state


# ---------------------------------------------------------------------------
# compute_preference_toggle_enabled — Q7-c 차단 조건
# ---------------------------------------------------------------------------


def test_toggle_enabled_true_default():
    """정상 케이스 — home_base 있고 share_*_data 전부 True면 토글 가능."""
    state = _make_state()
    assert compute_preference_toggle_enabled(state) is True


def test_toggle_disabled_when_share_food_false():
    """C1: share_food_data=False → 토글 차단."""
    state = _make_state(prefs={
        "food_preferences": None,
        "food_restrictions": None,
        "liked_areas": None,
        "disliked_areas": None,
        "transport_mode": None,
        "time_preference": None,
        "share_food_data": False,  # ← C1
        "share_location_data": True,
        "share_schedule_data": True,
        "is_guest": False,
    })
    assert compute_preference_toggle_enabled(state) is False


def test_toggle_disabled_when_share_location_false():
    """C1: share_location_data=False → 토글 차단."""
    state = _make_state(prefs={
        "food_preferences": None,
        "food_restrictions": None,
        "liked_areas": None,
        "disliked_areas": None,
        "transport_mode": None,
        "time_preference": None,
        "share_food_data": True,
        "share_location_data": False,  # ← C1
        "share_schedule_data": True,
        "is_guest": False,
    })
    assert compute_preference_toggle_enabled(state) is False


def test_toggle_disabled_when_share_schedule_false():
    """C1: share_schedule_data=False → 토글 차단."""
    state = _make_state(prefs={
        "food_preferences": None,
        "food_restrictions": None,
        "liked_areas": None,
        "disliked_areas": None,
        "transport_mode": None,
        "time_preference": None,
        "share_food_data": True,
        "share_location_data": True,
        "share_schedule_data": False,  # ← C1
        "is_guest": False,
    })
    assert compute_preference_toggle_enabled(state) is False


def test_toggle_disabled_when_no_home_base_and_no_prefs():
    """C4: requester_home_base AND requester_preferences 모두 None → 차단."""
    state = _make_state(home_base=None, prefs=None)
    assert compute_preference_toggle_enabled(state) is False


def test_toggle_enabled_when_home_base_only():
    """C4 회피: home_base만 있어도 (prefs=None) 토글 가능."""
    state = _make_state(home_base="서울 강남", prefs=None)
    assert compute_preference_toggle_enabled(state) is True


def test_toggle_enabled_for_guest_with_prefs():
    """Q7-c C2 제외 — 게스트라도 본인 prefs 입력했다면 토글 가능."""
    state = _make_state(prefs={
        "food_preferences": ["한식"],
        "food_restrictions": None,
        "liked_areas": None,
        "disliked_areas": None,
        "transport_mode": None,
        "time_preference": None,
        "share_food_data": True,
        "share_location_data": True,
        "share_schedule_data": True,
        "is_guest": True,  # ← 게스트
    })
    assert compute_preference_toggle_enabled(state) is True


# ---------------------------------------------------------------------------
# compute_preference_source
# ---------------------------------------------------------------------------


def test_compute_source_defaults_to_group():
    """preference_source 미지정 → "group"."""
    state = _make_state()
    assert compute_preference_source(state) == "group"


def test_compute_source_speaker_when_explicit():
    """refresh 라우트가 "speaker" 명시 → "speaker" 그대로."""
    state = _make_state(preference_source="speaker")
    assert compute_preference_source(state) == "speaker"


def test_compute_source_group_when_explicit():
    """refresh 라우트가 "group" 명시 → "group" 그대로."""
    state = _make_state(preference_source="group")
    assert compute_preference_source(state) == "group"


def test_compute_source_invalid_falls_back_to_group():
    """알 수 없는 값은 기본 "group"으로 fallback."""
    state = _make_state(preference_source="unknown")
    assert compute_preference_source(state) == "group"
