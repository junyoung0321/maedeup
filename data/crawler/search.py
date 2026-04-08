"""네이버 지도 검색으로 장소 ID 목록 수집"""

import json
import urllib.parse
import httpx
from tqdm import tqdm

from config import HUBS, CATEGORIES, SEARCH_RESULT_LIMIT, PLACE_IDS_DIR
from crawler.utils import get_headers, rate_limit_sleep, fetch_with_retry


SEARCH_URL = "https://map.naver.com/v5/api/search"


def build_search_url(query: str, lat: float, lng: float) -> str:
    """네이버 지도 검색 URL 생성"""
    params = {
        "caller": "pcweb",
        "query": query,
        "type": "all",
        "searchCoord": f"{lng};{lat}",
        "page": "1",
        "displayCount": str(SEARCH_RESULT_LIMIT),
    }
    return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"


def parse_search_results(data: dict) -> list[dict]:
    """검색 응답에서 장소 ID/이름/좌표/카테고리 추출"""
    places = []
    try:
        place_list = data.get("result", {}).get("place", {}).get("list", [])
        for item in place_list:
            places.append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "x": item.get("x", ""),
                "y": item.get("y", ""),
                "category": item.get("category", []),
            })
    except (KeyError, TypeError):
        pass
    return places


def search_hub_category(
    client: httpx.Client,
    hub: dict,
    keyword: str,
) -> list[dict]:
    """하나의 거점 + 키워드 조합으로 장소 검색"""
    url = build_search_url(keyword, hub["lat"], hub["lng"])
    resp = fetch_with_retry(client, "GET", url)
    if resp is None:
        return []
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return []
    places = parse_search_results(data)
    for p in places:
        p["hub"] = hub["name"]
        p["keyword"] = keyword
    return places


def search_all_hubs() -> list[dict]:
    """전체 거점 × 카테고리 검색 실행. 중복 제거 후 반환."""
    all_places = []
    seen_ids: set[str] = set()

    total = sum(len(cat["keywords"]) for cat in CATEGORIES) * len(HUBS)

    with httpx.Client(timeout=30) as client:
        with tqdm(total=total, desc="검색 진행") as pbar:
            for hub in HUBS:
                for cat in CATEGORIES:
                    for keyword in cat["keywords"]:
                        places = search_hub_category(client, hub, keyword)
                        for p in places:
                            if p["id"] not in seen_ids:
                                p["category_group"] = cat["name"]
                                all_places.append(p)
                                seen_ids.add(p["id"])
                        rate_limit_sleep()
                        pbar.update(1)

    print(f"\n총 {len(all_places)}개 장소 수집 (중복 제거 후)")
    return all_places
