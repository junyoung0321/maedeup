"""PR-V1.5 / S20 (Q4=A) — 점수 통합 공식 0.4·ML + 0.3·Gemini + 0.3·거리 검증.

`_compute_final_score` + `_sort_by_final_score` (F8 tiebreaker).
"""
from __future__ import annotations

from app.services.pipeline.nodes.place import (
    _compute_final_score,
    _sort_by_final_score,
)


def test_compute_final_score_all_components_present():
    """ml=1, gemini=1, distance=1 → final = 1.0."""
    item = {"ml_score": 1.0, "gemini_score": 1.0, "distance_score": 1.0}
    assert _compute_final_score(item) == 1.0


def test_compute_final_score_weighting_ml_dominates():
    """ml만 1, 나머지 0 → final = 0.4."""
    item = {"ml_score": 1.0, "gemini_score": 0.0, "distance_score": 0.0}
    assert _compute_final_score(item) == 0.4


def test_compute_final_score_weighting_gemini_only():
    """gemini만 1, 나머지 0 → final = 0.3."""
    item = {"ml_score": 0.0, "gemini_score": 1.0, "distance_score": 0.0}
    assert _compute_final_score(item) == 0.3


def test_compute_final_score_weighting_distance_only():
    """distance만 1 → final = 0.3."""
    item = {"ml_score": 0.0, "gemini_score": 0.0, "distance_score": 1.0}
    assert _compute_final_score(item) == 0.3


def test_compute_final_score_missing_keys_treated_as_zero():
    """누락 key는 0으로 처리."""
    item = {"distance_score": 0.5}
    assert _compute_final_score(item) == 0.15  # 0.3 * 0.5


def test_compute_final_score_invalid_values_handled():
    """비숫자 값은 0으로 처리."""
    item = {"ml_score": "bad", "gemini_score": None, "distance_score": 0.5}
    assert _compute_final_score(item) == 0.15  # 0.3 * 0.5


def test_compute_final_score_ml_first_case():
    """ML 1위 + Gemini 낮음 + 거리 낮음 → ML 가중치 우세."""
    item = {"ml_score": 0.9, "gemini_score": 0.2, "distance_score": 0.2}
    expected = round(0.4 * 0.9 + 0.3 * 0.2 + 0.3 * 0.2, 4)  # 0.36 + 0.06 + 0.06 = 0.48
    assert _compute_final_score(item) == expected


def test_compute_final_score_distance_first_case():
    """거리 1위 + ML 낮음 → 거리만으로는 ML보다 가중치 작음 (0.3 < 0.4)."""
    ml_heavy = {"ml_score": 1.0, "gemini_score": 0.0, "distance_score": 0.0}
    distance_heavy = {"ml_score": 0.0, "gemini_score": 0.0, "distance_score": 1.0}
    assert _compute_final_score(ml_heavy) > _compute_final_score(distance_heavy)


def test_compute_final_score_gemini_first_case():
    """Gemini 1위 + ML 0 → final = 0.3."""
    item = {"ml_score": 0.0, "gemini_score": 1.0, "distance_score": 0.0}
    assert _compute_final_score(item) == 0.3


# ---------------------------------------------------------------------------
# F8 tiebreaker — _sort_by_final_score
# ---------------------------------------------------------------------------


def test_sort_by_final_score_descending():
    """final_score 내림차순 정렬."""
    items = [
        {"place_id": "a", "final_score": 0.3, "distance_m": 100},
        {"place_id": "b", "final_score": 0.8, "distance_m": 100},
        {"place_id": "c", "final_score": 0.5, "distance_m": 100},
    ]
    out = _sort_by_final_score(items)
    assert [p["place_id"] for p in out] == ["b", "c", "a"]


def test_sort_by_final_score_tiebreak_by_distance():
    """final 동률 → distance_m 오름차순 (가까운 순)."""
    items = [
        {"place_id": "a", "final_score": 0.5, "distance_m": 200},
        {"place_id": "b", "final_score": 0.5, "distance_m": 100},
        {"place_id": "c", "final_score": 0.5, "distance_m": 300},
    ]
    out = _sort_by_final_score(items)
    assert [p["place_id"] for p in out] == ["b", "a", "c"]


def test_sort_by_final_score_tiebreak_by_place_id():
    """final + distance 둘 다 동률 → place_id 사전순."""
    items = [
        {"place_id": "zzz", "final_score": 0.5, "distance_m": 100},
        {"place_id": "aaa", "final_score": 0.5, "distance_m": 100},
        {"place_id": "mmm", "final_score": 0.5, "distance_m": 100},
    ]
    out = _sort_by_final_score(items)
    assert [p["place_id"] for p in out] == ["aaa", "mmm", "zzz"]


def test_sort_by_final_score_handles_missing_fields():
    """final_score / distance_m 누락도 결정적 처리."""
    items = [
        {"place_id": "a"},
        {"place_id": "b", "final_score": 0.5, "distance_m": 100},
    ]
    out = _sort_by_final_score(items)
    assert out[0]["place_id"] == "b"
