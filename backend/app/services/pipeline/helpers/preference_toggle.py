"""Q7 hybrid 토글 메타 계산 — vote_card / place 페이로드용.

PR-Z1 (2026-05-14, 결정 Q7=B + Q7-c).

`preference_source` ("group" | "speaker") 와 `preference_toggle_enabled` (bool)
두 값은 추천 카드 페이로드에 그대로 박혀 프론트가 토글 UI를 그릴 때 사용.

Q7-c 차단 조건 (false 처리):
  - C1: 발화자 share_*_data 어느 하나라도 False
  - C2: 게스트 — 본 PR에서는 차단 안 함 (decision: 게스트도 본인 prefs 입력했다면 가능)
  - C3: 그룹·speaker 결과 동일 — 본 PR은 휴리스틱 True (후속 PR에서 정확한 비교)
  - C4: requester_home_base AND requester_preferences 모두 None
"""
from __future__ import annotations

from typing import Any

from app.services.pipeline.state import GraphState


def compute_preference_toggle_enabled(state: GraphState) -> bool:
    """Q7-c: false 조건 = C1 ∨ C3 ∨ C4 (게스트 C2 제외).

    C1: 발화자의 share_*_data 어느 하나라도 False
    C3: 그룹·speaker 결과 동일 — 본 PR에서는 단순 True (후속 PR에서 정확한 비교)
    C4: requester_home_base AND requester_preferences 모두 None
    """
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

    # C3: 후속 PR에서 그룹/speaker 결과 동일성 비교 — 본 PR 휴리스틱 True
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
