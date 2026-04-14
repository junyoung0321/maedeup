"""Playwright 기반 네이버 지도 크롤러 — 브라우저 API 응답 가로채기

전략:
  1. 검색 응답 (allSearch) → 기본 데이터 90% 확보
     (이름, 카테고리, 주소, 좌표, 리뷰수, 메뉴, 영업시간)
  2. 상세 페이지 GraphQL 응답 → 별점 + 키워드 태그 + 리뷰 텍스트 보강
"""

import json
import re
from playwright.sync_api import Page, BrowserContext


NAVER_MAP_URL = "https://map.naver.com/p/search/{query}"


def create_browser_context(playwright, headless: bool = False) -> BrowserContext:
    """브라우저 컨텍스트 생성. headless=False면 captcha 수동 해결 가능."""
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="ko-KR",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    return context


def search_places(page: Page, query: str, lat: float, lng: float) -> list[dict]:
    """네이버 지도에서 검색 후 API 응답을 가로채서 장소 목록 추출.
    ?c={lng},{lat},15,0,0,0,dh 파라미터로 거점 중심 검색.
    검색 응답에 메뉴, 영업시간, 리뷰수 등 대부분의 데이터가 포함됨."""
    captured_data = []

    def handle_response(response):
        if "allSearch" in response.url and response.status == 200:
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    captured_data.append(response.json())
            except Exception:
                pass

    page.on("response", handle_response)

    # ?c={lng},{lat},zoom,0,0,0,dh → 지도 중심 좌표 설정
    import urllib.parse
    encoded_query = urllib.parse.quote(query)
    url = f"https://map.naver.com/p/search/{encoded_query}?c={lng},{lat},15,0,0,0,dh"
    try:
        page.goto(url, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
    except Exception as e:
        # networkidle 타임아웃은 무시 — 응답은 이미 캡처됨
        if "allSearch" not in str(e):
            pass

    page.remove_listener("response", handle_response)

    places = []
    for data in captured_data:
        extracted = _extract_places_from_search(data)
        places.extend(extracted)

    return places


def _extract_places_from_search(data: dict) -> list[dict]:
    """검색 API 응답에서 장소 정보를 최대한 추출"""
    places = []
    try:
        place_list = data.get("result", {}).get("place", {}).get("list", [])
    except (AttributeError, TypeError):
        return places

    for item in place_list:
        # 메뉴 파싱: "메뉴명 가격 | 메뉴명 가격 | ..." 형태
        menu_prices = _parse_menu_info(item.get("menuInfo", ""))

        # 카테고리: 리스트 또는 문자열
        category = item.get("category", "")
        if isinstance(category, list):
            category = " > ".join(category)

        places.append({
            "naver_place_id": str(item.get("id", "")),
            "place_name": item.get("name", ""),
            "category": category,
            "address": item.get("roadAddress", "") or item.get("address", ""),
            "lat": float(item.get("y", 0) or 0),
            "lng": float(item.get("x", 0) or 0),
            "review_count": int(item.get("placeReviewCount", 0) or 0),
            "blog_review_count": int(item.get("reviewCount", 0) or 0),
            "menu_prices": menu_prices,
            "business_hours": item.get("bizhourInfo", "") or "",
            # 별점과 키워드는 검색 응답에 없음 → 상세에서 보강
            "rating": 0.0,
            "keyword_tags": [],
        })

    return places


def _parse_menu_info(menu_str: str) -> list[dict]:
    """네이버 검색 응답의 menuInfo 문자열 파싱.
    형태: '(카테고리)메뉴명 가격 | 메뉴명 가격 | ...'"""
    if not menu_str:
        return []

    menus = []
    for part in menu_str.split(" | "):
        part = part.strip()
        # (카테고리) 제거
        part = re.sub(r"\([^)]*\)", "", part).strip()
        # 가격 분리: 마지막 숫자+콤마 패턴
        match = re.match(r"(.+?)\s+([\d,]+)$", part)
        if match:
            menus.append({
                "name": match.group(1).strip(),
                "price": match.group(2).replace(",", ""),
            })
        elif part:
            menus.append({"name": part, "price": ""})

    return menus


def fetch_detail_rating_keywords(page: Page, place_id: str) -> dict:
    """JS fetch로 GraphQL 직접 호출 → 별점 + 키워드(themes) 추출.
    page는 pcmap.place.naver.com 도메인에 이미 진입해 있어야 함.
    반환: {"rating": float, "keyword_tags": list[str], "review_total": int}
    """
    result = {"rating": 0.0, "keyword_tags": [], "review_total": 0}

    gql_query = (
        "query getVisitorReviewStats($input: VisitorReviewStatsInput) {"
        "  visitorReviewStats(input: $input) {"
        "    id"
        "    review { avgRating totalCount }"
        "    analysis { themes { code label count } }"
        "  }"
        "}"
    )
    payload = json.dumps([{
        "operationName": "getVisitorReviewStats",
        "variables": {"input": {"businessId": place_id, "businessType": "restaurant"}},
        "query": gql_query,
    }])

    try:
        resp = page.evaluate("""async (args) => {
            const [pid, payload] = args;
            const resp = await fetch('https://pcmap-api.place.naver.com/place/graphql', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: payload,
            });
            return { status: resp.status, body: await resp.text() };
        }""", [place_id, payload])
    except Exception as e:
        print(f"  [js fetch error] {place_id}: {e}")
        return result

    if resp.get("status") != 200:
        return result

    try:
        data = json.loads(resp["body"])
    except (json.JSONDecodeError, KeyError):
        return result

    entries = data if isinstance(data, list) else [data]
    for entry in entries:
        stats = (entry.get("data") or {}).get("visitorReviewStats") or {}

        # 별점
        review = stats.get("review") or {}
        avg = review.get("avgRating", 0)
        if avg and result["rating"] == 0.0:
            result["rating"] = float(avg)
        total = review.get("totalCount", 0)
        if total:
            result["review_total"] = int(total)

        # 키워드 themes
        themes = (stats.get("analysis") or {}).get("themes") or []
        for theme in themes:
            if not isinstance(theme, dict):
                continue
            label = theme.get("label", "")
            if label and label not in result["keyword_tags"]:
                result["keyword_tags"].append(label)

    return result


def fetch_review_texts(page: Page, place_id: str, max_reviews: int = 20) -> list[str]:
    """JS fetch로 방문자 리뷰 본문을 수집. ABSA 감성분석 입력용.
    page는 pcmap.place.naver.com 도메인에 이미 진입해 있어야 함.
    businessType: 'restaurant' 1차 시도 → 결과 없으면 'place' 폴백.
    반환: 리뷰 본문 리스트 (최대 max_reviews건)
    """

    def _fetch_pages(business_type: str) -> list[str]:
        collected = []
        page_size = 20
        pages_needed = (max_reviews + page_size - 1) // page_size

        for pg in range(1, pages_needed + 1):
            payload = json.dumps([{
                "operationName": "getVisitorReviews",
                "variables": {
                    "input": {
                        "businessId": place_id,
                        "businessType": business_type,
                        "size": page_size,
                        "page": pg,
                        "includeContent": True,
                    }
                },
                "query": (
                    "query getVisitorReviews($input: VisitorReviewsInput) {"
                    "  visitorReviews(input: $input) {"
                    "    items { body }"
                    "    total"
                    "  }"
                    "}"
                ),
            }])

            try:
                resp = page.evaluate("""async (payload) => {
                    const controller = new AbortController();
                    const timer = setTimeout(() => controller.abort(), 10000);
                    try {
                        const r = await fetch('https://pcmap-api.place.naver.com/place/graphql', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: payload,
                            signal: controller.signal,
                        });
                        clearTimeout(timer);
                        return { status: r.status, body: await r.text() };
                    } catch(e) {
                        clearTimeout(timer);
                        return { status: -1, body: '' };
                    }
                }""", payload)
            except Exception:
                break

            if resp.get("status") != 200:
                break

            try:
                data = json.loads(resp["body"])
            except (json.JSONDecodeError, KeyError):
                break

            items = (
                data[0].get("data", {}).get("visitorReviews", {}).get("items", [])
                if isinstance(data, list) and data
                else []
            )

            for item in items:
                body = (item.get("body") or "").strip()
                if body:
                    collected.append(body)

            if len(items) < page_size:
                break

        return collected

    # 1차: restaurant
    reviews = _fetch_pages("restaurant")
    # 2차 폴백: place (카페/술집/스터디 등)
    if not reviews:
        reviews = _fetch_pages("place")

    return reviews[:max_reviews]


def init_detail_page(context: BrowserContext) -> Page:
    """보강용 페이지를 pcmap 도메인에 진입시켜 반환.
    이후 fetch_detail_rating_keywords에서 JS fetch 사용 가능."""
    page = context.new_page()
    page.goto(
        "https://pcmap.place.naver.com/place/1/home",
        wait_until="domcontentloaded",
        timeout=15000,
    )
    page.wait_for_timeout(1000)
    return page


def fetch_detail_rating_keywords_api(
    client, place_id: str, headers: dict
) -> dict:
    """httpx로 별점 + 키워드 추출 (Playwright 불필요, 훨씬 빠름).
    1) Summary API → rating
    2) GraphQL POST → keyword_tags
    반환: {"rating": float, "keyword_tags": list[str]}"""
    result = {"rating": 0.0, "keyword_tags": []}

    # ── 1) Summary API: rating ──
    try:
        resp = client.get(
            f"https://map.naver.com/v5/api/sites/summary/{place_id}?lang=ko",
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            result["rating"] = float(data.get("visitorReviewScore", 0) or 0)
            kw = data.get("keywords", [])
            if isinstance(kw, list):
                result["keyword_tags"] = [k for k in kw if k]
    except Exception:
        pass

    # ── 2) GraphQL: keyword_tags (visitor review analysis) ──
    if not result["keyword_tags"]:
        try:
            gql_headers = {
                **headers,
                "Content-Type": "application/json",
                "Referer": f"https://pcmap.place.naver.com/place/{place_id}/home",
            }
            payload = [
                {
                    "operationName": "getVisitorReviewStats",
                    "variables": {
                        "input": {
                            "businessId": place_id,
                            "businessType": "restaurant",
                        }
                    },
                    "query": (
                        "query getVisitorReviewStats($input: VisitorReviewStatsInput) {"
                        "  visitorReviewStats(input: $input) {"
                        "    id"
                        "    analysis { keywords { text count } }"
                        "    review { keywords { text count } }"
                        "  }"
                        "}"
                    ),
                }
            ]
            gql_resp = client.post(
                "https://pcmap-api.place.naver.com/place/graphql",
                headers=gql_headers,
                json=payload,
            )
            if gql_resp.status_code == 200:
                gql_data = gql_resp.json()
                entries = gql_data if isinstance(gql_data, list) else [gql_data]
                for entry in entries:
                    stats = (entry.get("data") or {}).get("visitorReviewStats") or {}
                    for section_key in ("analysis", "review"):
                        section = stats.get(section_key) or {}
                        for kw in section.get("keywords", []):
                            text = kw.get("text", "") if isinstance(kw, dict) else str(kw)
                            if text and text not in result["keyword_tags"]:
                                result["keyword_tags"].append(text)
        except Exception:
            pass

    return result
