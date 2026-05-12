"""Kakao Local Search API 기반 후보 장소 실시간 조회"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

KAKAO_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
_CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"
_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

# purpose_cat → Kakao 검색 전략
_SEARCH_CONFIG: dict[int, dict] = {
    0: {"type": "category", "code": "FD6"},       # 식사 → 음식점
    1: {"type": "category", "code": "CE7"},       # 카페 → 카페,디저트
    2: {"type": "keyword",  "query": "주점"},     # 술자리 → 주점 키워드
    3: {"type": "category", "code": "CE7"},       # 회의 → 카페
}

_CODE_TO_DEPTH1: dict[str, int] = {
    "FD6": 0,  # 음식점
    "CE7": 1,  # 카페,디저트
}

# category_name 내 키워드로 술집(2) 판별 (FD6 안에 주점 있음)
_DEPTH1_KW: dict[str, int] = {
    "카페": 1, "디저트": 1,
    "술집": 2, "바": 2, "주점": 2, "bar": 2,
}


def _extract_depth1(code: str, category_name: str) -> int:
    base = _CODE_TO_DEPTH1.get(code)
    if base is not None:
        if base == 0:  # FD6 안에 술집 있을 수 있음
            low = category_name.lower()
            for kw, d1 in _DEPTH1_KW.items():
                if kw in low:
                    return d1
        return base
    low = category_name.lower()
    for kw, d1 in _DEPTH1_KW.items():
        if kw in low:
            return d1
    return 0  # 기본: 음식점


def _api_call(url: str, params: dict) -> tuple[list[dict], dict]:
    if not KAKAO_API_KEY:
        raise EnvironmentError("KAKAO_REST_API_KEY 환경변수가 설정되지 않았습니다.")
    try:
        r = requests.get(
            url,
            headers={"Authorization": f"KakaoAK {KAKAO_API_KEY}"},
            params=params,
            timeout=5,
        )
        r.raise_for_status()
        body = r.json()
        return body.get("documents", []), body.get("meta", {})
    except Exception as e:
        logger.warning(f"Kakao API 오류: {e}")
        return [], {}


def _parse_doc(doc: dict) -> dict:
    code = doc.get("category_group_code", "")
    cat_name = doc.get("category_name", "")
    return {
        "kakao_place_id": doc.get("id", ""),
        "place_name": doc.get("place_name", ""),
        "lat": float(doc.get("y", 0)),
        "lng": float(doc.get("x", 0)),
        "category_name": cat_name,
        "category_depth1": _extract_depth1(code, cat_name),
    }


def search_places(
    lat: float,
    lng: float,
    purpose_cat: int,
    radius_m: int = 3000,
    max_results: int = 45,
) -> list[dict]:
    """Kakao Local API로 후보 장소 검색.

    Args:
        lat, lng:    검색 중심 좌표
        purpose_cat: 0=식사, 1=카페, 2=술자리, 3=회의
        radius_m:    검색 반경 (최대 20000m)
        max_results: 최대 반환 수 (API 1페이지=15개, 최대 45페이지)

    Returns:
        [{kakao_place_id, place_name, lat, lng, category_name, category_depth1}, ...]
    """
    config = _SEARCH_CONFIG.get(purpose_cat, _SEARCH_CONFIG[0])
    results: list[dict] = []
    pages = (min(max_results, 675) + 14) // 15  # 올림 나눗셈

    for page in range(1, min(pages, 45) + 1):
        base_params = {
            "y": lat,
            "x": lng,
            "radius": min(radius_m, 20000),
            "size": 15,
            "page": page,
            "sort": "distance",
        }
        if config["type"] == "category":
            url = _CATEGORY_URL
            params = {"category_group_code": config["code"], **base_params}
        else:
            url = _KEYWORD_URL
            params = {"query": config["query"], **base_params}

        docs, meta = _api_call(url, params)
        results.extend(_parse_doc(doc) for doc in docs)

        if meta.get("is_end", True) or len(results) >= max_results:
            break

    logger.info(f"Kakao 장소 검색: {len(results)}곳 (purpose_cat={purpose_cat}, r={radius_m}m)")
    return results[:max_results]
