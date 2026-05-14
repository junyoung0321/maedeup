"""PR-V1.5 / S16 (§6.15) — rejected_places 누적 + 필터 검증.

거부 발화에서 장소 추출 후 다음 추천에서 제외되는지 단위 테스트.
"""
from __future__ import annotations

from app.services.pipeline.helpers.places import _filter_out_rejected_places
from app.services.pipeline.nodes.entity import _pattern_extract_entities


def test_pattern_extracts_rejected_place_with_malgo():
    """'강남 말고' → rejected_places에 '강남' 추가."""
    result = _pattern_extract_entities("강남 말고 다른 데로 가자")
    assert isinstance(result.get("rejected_places"), list)
    assert any(rp["place"] == "강남" for rp in result["rejected_places"])


def test_pattern_extracts_rejected_place_with_byello():
    """'홍대는 별로' → rejected_places에 '홍대' 추가."""
    result = _pattern_extract_entities("홍대는 별로야")
    assert any(rp["place"] == "홍대" for rp in result["rejected_places"])


def test_pattern_extracts_rejected_place_with_ppaego():
    """'역삼 빼고' → rejected_places에 '역삼' 추가."""
    result = _pattern_extract_entities("역삼 빼고 다른 곳")
    assert any(rp["place"] == "역삼" for rp in result["rejected_places"])


def test_pattern_extracts_multiple_rejected_places():
    """'강남 말고 홍대는 별로' → 두 장소 모두 추출."""
    result = _pattern_extract_entities("강남 말고, 홍대는 별로야")
    places = {rp["place"] for rp in result["rejected_places"]}
    assert "강남" in places
    assert "홍대" in places


def test_pattern_no_rejected_when_just_preference():
    """'강남이 좋아' → 거부 아님 → rejected_places 비어있어야 함."""
    result = _pattern_extract_entities("강남이 좋아")
    assert result["rejected_places"] == []


def test_filter_out_rejected_places_removes_matches():
    """rejected_places에 있는 키워드와 name/address가 겹치면 제외."""
    places = [
        {"place_id": "1", "name": "강남식당", "address": "서울 강남구"},
        {"place_id": "2", "name": "홍대맛집", "address": "서울 마포구 홍대"},
        {"place_id": "3", "name": "이태원 카페", "address": "서울 용산구"},
    ]
    rejected = [{"place": "강남", "user": None, "reason": None}]
    out = _filter_out_rejected_places(places, rejected)
    place_ids = {p["place_id"] for p in out}
    assert "1" not in place_ids
    assert "2" in place_ids
    assert "3" in place_ids


def test_filter_out_rejected_places_empty_rejection_passthrough():
    """rejected_places가 비면 입력 그대로 반환."""
    places = [{"place_id": "1", "name": "강남식당", "address": ""}]
    out = _filter_out_rejected_places(places, [])
    assert out == places


def test_filter_out_rejected_places_matches_address_only():
    """name에 없어도 address에 거부 키워드면 제외."""
    places = [
        {"place_id": "1", "name": "동네식당", "address": "서울 마포구 홍대로 1"},
    ]
    rejected = [{"place": "홍대", "user": None, "reason": None}]
    out = _filter_out_rejected_places(places, rejected)
    assert out == []
