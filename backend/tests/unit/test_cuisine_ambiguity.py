"""PR-V1.5 / S18 (§6.16) — cuisine 다중 충돌 ambiguity 검증.

`_detect_cuisine_type`: 시그니처 변경 (str | None → list[str]).
다중 매칭 시 모두 반환, place_recommendation narrator가 분기.
"""
from __future__ import annotations

from app.services.pipeline.helpers.places import _detect_cuisine_type


def test_single_cuisine_returns_one_element_list():
    """단일 cuisine 발화 → list[str] 1개 원소."""
    result = _detect_cuisine_type("강남 한식 추천")
    assert isinstance(result, list)
    assert result == ["한식"]


def test_multiple_cuisines_returned_in_list():
    """'한식 일식' 발화 → 두 cuisine 모두 list."""
    result = _detect_cuisine_type("한식 일식 둘 다 좋아")
    assert isinstance(result, list)
    assert "한식" in result
    assert "일식" in result


def test_no_cuisine_returns_empty_list():
    """cuisine 미언급 → 빈 list."""
    result = _detect_cuisine_type("강남에서 모임")
    assert result == []


def test_empty_text_returns_empty_list():
    """빈 입력 → 빈 list."""
    assert _detect_cuisine_type("") == []
    assert _detect_cuisine_type(None) == []  # type: ignore[arg-type]


def test_duplicate_cuisine_keywords_unique():
    """'한식 한정식' 양쪽 모두 한식 매칭 → 중복 제거 1개만."""
    result = _detect_cuisine_type("한식 한정식 추천")
    assert result.count("한식") == 1


def test_cuisine_with_synonyms_picks_up_all():
    """'중식 일식' → 둘 다 추출."""
    result = _detect_cuisine_type("중식이랑 일식 중 골라줘")
    assert "중식" in result
    assert "일식" in result
    assert len(result) == 2
