import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.detail import build_detail_url, parse_detail_response


def test_build_detail_url_contains_place_id():
    url = build_detail_url("1234567890")
    assert "1234567890" in url


def test_parse_detail_response_extracts_fields():
    mock_data = {
        "id": "1234567890",
        "name": "테스트식당",
        "category": "음식점 > 한식 > 국밥",
        "roadAddress": "서울 강남구 테헤란로 1",
        "x": "127.0276",
        "y": "37.4979",
        "reviewCount": 150,
        "blogReviewCount": 45,
        "visitorReviewScore": 4.3,
        "keywords": ["분위기좋은", "단체모임"],
        "menuInfo": [
            {"name": "된장찌개", "price": "8000"},
            {"name": "김치찌개", "price": "9000"},
        ],
        "businessHours": "매일 11:00 - 22:00",
    }
    result = parse_detail_response(mock_data)
    assert result["naver_place_id"] == "1234567890"
    assert result["place_name"] == "테스트식당"
    assert result["rating"] == 4.3
    assert result["review_count"] == 150
    assert result["blog_review_count"] == 45
    assert "분위기좋은" in result["keyword_tags"]
    assert result["menu_prices"][0]["name"] == "된장찌개"
    assert result["business_hours"] == "매일 11:00 - 22:00"


def test_parse_detail_response_handles_missing_fields():
    result = parse_detail_response({"id": "999", "name": "빈가게"})
    assert result["naver_place_id"] == "999"
    assert result["rating"] == 0
    assert result["review_count"] == 0
    assert result["keyword_tags"] == []
    assert result["menu_prices"] == []
