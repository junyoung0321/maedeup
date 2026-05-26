"""Q7 hybrid 토글 메타 계산 — vote_card / place 페이로드용.

PR-Z1 (2026-05-14, 결정 Q7=B + Q7-c).
PR-V1.5 (2026-05-14): Q7-c C3 lightweight 비교 추가.

`preference_source` ("group" | "speaker") 와 `preference_toggle_enabled` (bool)
두 값은 추천 카드 페이로드에 그대로 박혀 프론트가 토글 UI를 그릴 때 사용.

Q7-c 차단 조건 (false 처리):
  - C1: 발화자 share_*_data 어느 하나라도 False
  - C2: 게스트 — 본 PR에서는 차단 안 함 (decision: 게스트도 본인 prefs 입력했다면 가능)
  - C3: 그룹·speaker 결과 동일 — PR-V1.5 lightweight 비교
        (food_preferences 교집합 ≥ 70% AND home_base ≈ 그룹 다수결 → 동일로 간주, 토글 false)
  - C4: requester_home_base AND requester_preferences 모두 None
"""
from __future__ import annotations

from typing import Any

from app.services.pipeline.state import GraphState


def _lightweight_speaker_matches_group(state: GraphState) -> bool:
    """PR-V1.5 / Q7-c C3 lightweight 비교.

    발화자(requester) 선호가 그룹 다수결과 "유사"하면 토글 의미 없음 → True.
    비교 키:
      1. home_base: requester_home_base == default_place_hint (그룹 다수결 hint)
      2. food_preferences: requester food_preferences vs preference_common_foods
         (state에 있을 때만; 교집합 / union ≥ 70%면 유사).

    note: 정확한 그룹 평균 계산은 추가 DB query 필요 → 본 PR은 이미 state에
    주입된 값만 사용해 비용 0으로 비교 (lightweight). 두 시그널 모두 일치할
    때만 "동일" 판정 — false positive 보수적.
    """
    prefs: dict[str, Any] | None = state.get("requester_preferences")
    requester_home: str | None = state.get("requester_home_base")
    group_home: str | None = state.get("default_place_hint")

    # 1. home_base 비교 — 둘 다 있어야 비교 가능.
    home_matches = (
        isinstance(requester_home, str)
        and isinstance(group_home, str)
        and requester_home.strip()
        and group_home.strip()
        and requester_home.strip() == group_home.strip()
    )
    if not home_matches:
        return False

    # 2. food_preferences 비교 — refresh route의 _load_group_preference_context
    #    (Codex P2 fix, 2026-05-15)가 default_place_hint + preference_common_foods
    #    둘 다 주입. 두 값 모두 list 형태로 존재할 때만 70% 교집합 검사.
    speaker_foods = (prefs or {}).get("food_preferences") if prefs else None
    group_foods = state.get("preference_common_foods")
    if not isinstance(speaker_foods, list) or not speaker_foods:
        return False
    if not isinstance(group_foods, list) or not group_foods:
        return False
    speaker_set = {str(f).strip() for f in speaker_foods if f}
    group_set = {str(f).strip() for f in group_foods if f}
    if not speaker_set or not group_set:
        return False
    intersection = speaker_set & group_set
    union = speaker_set | group_set
    if not union:
        return False
    overlap_ratio = len(intersection) / len(union)
    return overlap_ratio >= 0.70


def compute_preference_toggle_enabled(state: GraphState) -> bool:
    """Q7-c: false 조건 = C1 ∨ C3 ∨ C4 (게스트 C2 제외).

    C0 (feature flag): 운영자가 PREFERENCE_TOGGLE_ENABLED=false 설정 시 항상 false.
        시연 시나리오에 포함하기 애매한 경우 옵션 B (UI dormant) 로 활용.
    C1: 발화자의 share_*_data 어느 하나라도 False
    C3: 그룹·speaker 결과 동일 — PR-V1.5 lightweight 비교 (home_base + food prefs)
    C4: requester_home_base AND requester_preferences 모두 None
    """
    # C0: feature flag — 운영 환경변수로 토글 자체를 dormant 시킬 수 있음.
    # (frontend 의 ScheduleRecommendationCard / PlaceRecommendationCard 는 이 값이
    # false 면 토글 UI 안 렌더 → ACT 5.5 시연 항목 skip 가능)
    import os
    if os.getenv("PREFERENCE_TOGGLE_ENABLED", "true").lower() in ("false", "0", "no"):
        return False

    prefs: dict[str, Any] | None = state.get("requester_preferences")
    home_base = state.get("requester_home_base")

    # C4: requester 본인 정보 부재
    if not home_base and not prefs:
        return False

    # C1: share_*_data 어느 하나라도 False면 그룹 vs 발화자 비교 불가 (private leak 방지)
    if prefs:
        if not prefs.get("share_food_data", True):
            return False
        if not prefs.get("share_location_data", True):
            return False
        if not prefs.get("share_schedule_data", True):
            return False

    # PR-V1.5 / C3: lightweight 비교 — home_base + food 교집합 ≥ 70%면 동일로 간주.
    if _lightweight_speaker_matches_group(state):
        return False

    return True


def compute_preference_source(state: GraphState) -> str:
    """현재 페이로드의 preference_source 라벨.

    refresh 라우트가 state["preference_source"]를 명시했으면 그 값,
    아니면 기본 "group".
    """
    source = state.get("preference_source")
    if source in ("group", "speaker"):
        return source
    return "group"
