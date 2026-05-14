"""Unit tests for app.services.pipeline.helpers.preference_toggle.

PR-Z1 (2026-05-14) — Q7-c 차단 조건 + preference_source 라벨 계산.

Q7-c false 조건: C1 ∨ C3 ∨ C4 (게스트 C2 제외).
"""
from __future__ import annotations

from app.services.pipeline.helpers.preference_toggle import (
    compute_preference_source,
    compute_preference_toggle_enabled,
)


# SENTINEL: kwargs 미지정(default 적용) vs 명시적 None 전달을 구분하기 위한 마커.
# `_make_state(prefs=None)`처럼 None을 명시한 호출이 default 값으로 덮어쓰여지지
# 않도록 한다 (C4 차단 조건 테스트가 prefs=None을 그대로 전달해야 한다).
_SENTINEL: object = object()


def _make_state(
    *,
    home_base: str | object = _SENTINEL,
    prefs: dict | None | object = _SENTINEL,
    preference_source: str | None = None,
) -> dict:
    """GraphState-like dict factory. dict는 TypedDict의 런타임 표현.

    home_base / prefs는 _SENTINEL일 때만 default를 적용하므로, 호출자가
    `home_base=None` 또는 `prefs=None`을 명시하면 그 값이 그대로 state에 들어간다.
    """
    if home_base is _SENTINEL:
        home_base = "서울 강남"
    if prefs is _SENTINEL:
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


# ---------------------------------------------------------------------------
# PR-V1.5 / Q7-c C3 — lightweight 비교 (home_base + food prefs)
# ---------------------------------------------------------------------------


def _make_state_with_group(
    *,
    home_base: str | object = _SENTINEL,
    speaker_foods: list[str] | None = None,
    group_home: str | None = None,
    group_foods: list[str] | None = None,
) -> dict:
    """그룹 컨텍스트가 포함된 state factory.

    home_base는 SENTINEL일 때만 default("서울 강남")를 적용한다 (None 명시 가능).
    """
    if home_base is _SENTINEL:
        home_base = "서울 강남"
    state = _make_state(
        home_base=home_base,
        prefs={
            "food_preferences": speaker_foods,
            "food_restrictions": None,
            "liked_areas": None,
            "disliked_areas": None,
            "transport_mode": None,
            "time_preference": None,
            "share_food_data": True,
            "share_location_data": True,
            "share_schedule_data": True,
            "is_guest": False,
        },
    )
    if group_home is not None:
        state["default_place_hint"] = group_home
    if group_foods is not None:
        state["preference_common_foods"] = group_foods
    return state


def test_c3_lightweight_same_home_same_food_disables_toggle():
    """C3: home_base 일치 + food 70% 이상 일치 → 토글 비활성."""
    state = _make_state_with_group(
        home_base="서울 강남",
        speaker_foods=["한식", "일식"],
        group_home="서울 강남",
        group_foods=["한식", "일식"],
    )
    assert compute_preference_toggle_enabled(state) is False


def test_c3_lightweight_different_home_keeps_toggle_enabled():
    """C3: home_base 불일치 → C3 비교 통과 못 함 → 토글 활성 유지."""
    state = _make_state_with_group(
        home_base="서울 강남",
        speaker_foods=["한식", "일식"],
        group_home="서울 홍대",
        group_foods=["한식", "일식"],
    )
    assert compute_preference_toggle_enabled(state) is True


def test_c3_lightweight_low_overlap_food_keeps_toggle_enabled():
    """C3: food 교집합 적음 (< 70%) → 토글 활성 유지."""
    state = _make_state_with_group(
        home_base="서울 강남",
        speaker_foods=["한식"],
        group_home="서울 강남",
        group_foods=["일식", "중식", "양식"],  # 교집합 0
    )
    assert compute_preference_toggle_enabled(state) is True


def test_c3_lightweight_missing_group_foods_keeps_toggle_enabled():
    """C3: group foods 없음 → 보수적으로 토글 활성 유지."""
    state = _make_state_with_group(
        home_base="서울 강남",
        speaker_foods=["한식", "일식"],
        group_home="서울 강남",
        # group_foods 미설정 → 비교 못 함
    )
    assert compute_preference_toggle_enabled(state) is True


def test_c3_lightweight_missing_group_home_keeps_toggle_enabled():
    """Codex P2 회귀 가드 (2026-05-15): group home_base가 None이면 C3 발동 안 함.

    refresh route가 group context를 빠뜨리는 (수정 전) 동작과 동치 — 이 상태에서
    C3가 절대 발동하지 않아야 함 (False positive 방지). 본 테스트는 P2 수정이
    들어간 뒤에도 C3 가드가 보수적임을 보장.
    """
    state = _make_state_with_group(
        home_base="서울 강남",
        speaker_foods=["한식", "일식"],
        # group_home 미설정 → 비교 못 함
        group_foods=["한식", "일식"],
    )
    assert compute_preference_toggle_enabled(state) is True


def test_c3_lightweight_empty_group_lists_keeps_toggle_enabled():
    """Codex P2 회귀 가드: group list가 빈 list여도 보수적으로 토글 활성 유지."""
    state = _make_state_with_group(
        home_base="서울 강남",
        speaker_foods=["한식"],
        group_home="서울 강남",
        group_foods=[],  # 빈 list — list이긴 하지만 비교 불가
    )
    assert compute_preference_toggle_enabled(state) is True
