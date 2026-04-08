import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.search import build_search_url, parse_search_results


def test_build_search_url_contains_query():
    url = build_search_url("맛집", lat=37.4979, lng=127.0276)
    assert "127.0276" in url
    assert "37.4979" in url


def test_parse_search_results_extracts_place_ids():
    mock_response = {
        "result": {
            "place": {
                "list": [
                    {"id": "1234567890", "name": "테스트식당", "x": "127.0276", "y": "37.4979", "category": ["음식점"]},
                    {"id": "9876543210", "name": "테스트카페", "x": "127.0280", "y": "37.4980", "category": ["카페"]},
                ]
            }
        }
    }
    places = parse_search_results(mock_response)
    assert len(places) == 2
    assert places[0]["id"] == "1234567890"
    assert places[0]["name"] == "테스트식당"


def test_parse_search_results_handles_empty():
    assert parse_search_results({}) == []
    assert parse_search_results({"result": {}}) == []
    assert parse_search_results({"result": {"place": {}}}) == []
