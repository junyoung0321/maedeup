"""place_recommendation narrator 문구 분기 (free-use audit 2026-06-03).

빈 장소 카드 가드와 함께: 추천 0건이면 카드를 발행하지 않으므로 narrator도
"아래 카드를 확인" 이 아니라 "다른 지역 알려주세요" 를 내보내야 한다.
"""
from __future__ import annotations

from app.services.pipeline.nodes.place import _build_place_narrator


def test_zero_count_guides_to_other_region_not_card():
    # 회귀: 0건 → 카드 없음 → "아래 카드 확인" 문구가 나오면 안 됨.
    msg = _build_place_narrator(hint="강남역", count=0, cuisines=[], kakao_error=False)
    assert "다른 지역" in msg
    assert "아래 카드" not in msg


def test_positive_count_points_to_card():
    msg = _build_place_narrator(hint="강남역", count=3, cuisines=[], kakao_error=False)
    assert "3개" in msg
    assert "아래 카드" in msg


def test_kakao_error_with_zero_count_takes_priority():
    msg = _build_place_narrator(hint="강남역", count=0, cuisines=["한식", "일식"],
                                kakao_error=True)
    assert "일시적으로 불가" in msg
    # 장애 문구가 최우선 — cuisine/지역 안내로 오염되지 않음.
    assert "다른 지역" not in msg
    assert "추천 중이에요" not in msg


def test_multi_cuisine_prefix_with_results():
    msg = _build_place_narrator(hint="강남역", count=2, cuisines=["한식", "중식"],
                                kakao_error=False)
    assert "한식·중식" in msg
    assert "2개" in msg
