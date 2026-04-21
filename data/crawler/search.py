"""네이버 지도 검색으로 장소 ID 목록 수집 (Playwright 기반)

allSearch API는 동적 토큰 인증 → httpx 직접 호출 불가.
Playwright로 브라우저 실제 응답을 가로채는 방식 사용.
"""

from tqdm import tqdm
from playwright.sync_api import sync_playwright

from config import HUBS, CATEGORIES
from crawler.browser import create_browser_context, search_places, _extract_places_from_search


def search_all_hubs() -> list[dict]:
    """전체 거점 × 카테고리 Playwright 검색. 중복 제거 후 반환."""
    all_places: list[dict] = []
    seen_ids: set[str] = set()

    total = sum(len(cat["keywords"]) for cat in CATEGORIES) * len(HUBS)

    with sync_playwright() as pw:
        context = create_browser_context(pw, headless=True)
        page = context.new_page()

        with tqdm(total=total, desc="검색 진행") as pbar:
            for hub in HUBS:
                for cat in CATEGORIES:
                    for keyword in cat["keywords"]:
                        try:
                            places = search_places(
                                page,
                                query=keyword,
                                lat=hub["lat"],
                                lng=hub["lng"],
                            )
                        except Exception as e:
                            print(f"  [오류] {hub['name']} / {keyword}: {e}")
                            places = []

                        for p in places:
                            pid = p.get("naver_place_id", "")
                            if pid and pid not in seen_ids and p.get("review_count", 0) > 0:
                                p["hub"] = hub["name"]
                                p["keyword"] = keyword
                                p["category_group"] = cat["name"]
                                all_places.append(p)
                                seen_ids.add(pid)

                        pbar.update(1)

        context.browser.close()

    print(f"\n총 {len(all_places)}개 장소 수집 (중복 제거 후)")
    return all_places
