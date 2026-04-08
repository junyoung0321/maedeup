"""네이버 장소 상세 정보 조회 (내부 API)"""

import json
import os
import httpx
from tqdm import tqdm

from config import RAW_DIR
from crawler.utils import get_headers, rate_limit_sleep, fetch_with_retry


# 네이버 플레이스 상세 API
DETAIL_URL_TEMPLATE = "https://map.naver.com/v5/api/sites/summary/{place_id}?lang=ko"


def build_detail_url(place_id: str) -> str:
    """장소 상세 API URL 생성"""
    return DETAIL_URL_TEMPLATE.format(place_id=place_id)


def parse_detail_response(data: dict) -> dict:
    """API 응답에서 필요한 필드만 추출하여 정규화된 dict 반환"""
    keywords = data.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]

    menu_info = data.get("menuInfo", [])
    menu_prices = []
    for item in menu_info:
        if isinstance(item, dict):
            menu_prices.append({
                "name": item.get("name", ""),
                "price": item.get("price", ""),
            })

    return {
        "naver_place_id": str(data.get("id", "")),
        "place_name": data.get("name", ""),
        "category": data.get("category", ""),
        "address": data.get("roadAddress", "") or data.get("address", ""),
        "lat": float(data.get("y", 0)),
        "lng": float(data.get("x", 0)),
        "rating": float(data.get("visitorReviewScore", 0) or 0),
        "review_count": int(data.get("reviewCount", 0) or 0),
        "blog_review_count": int(data.get("blogReviewCount", 0) or 0),
        "keyword_tags": keywords,
        "menu_prices": menu_prices,
        "business_hours": data.get("businessHours", "") or "",
    }


def fetch_place_detail(client: httpx.Client, place_id: str) -> dict | None:
    """장소 ID로 상세 정보 조회"""
    url = build_detail_url(place_id)
    resp = fetch_with_retry(client, "GET", url)
    if resp is None:
        return None
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return None
    return parse_detail_response(data)


def fetch_all_details(place_ids: list[str]) -> list[dict]:
    """전체 장소 ID에 대해 상세 정보 수집"""
    results = []
    failed = []

    with httpx.Client(timeout=30) as client:
        for pid in tqdm(place_ids, desc="상세 수집"):
            detail = fetch_place_detail(client, pid)
            if detail:
                results.append(detail)
                raw_path = os.path.join(RAW_DIR, f"{pid}.json")
                os.makedirs(RAW_DIR, exist_ok=True)
                with open(raw_path, "w", encoding="utf-8") as f:
                    json.dump(detail, f, ensure_ascii=False, indent=2)
            else:
                failed.append(pid)
            rate_limit_sleep()

    print(f"\n수집 완료: {len(results)}곳 성공, {len(failed)}곳 실패")
    if failed:
        print(f"실패 ID: {failed[:10]}{'...' if len(failed) > 10 else ''}")
    return results
