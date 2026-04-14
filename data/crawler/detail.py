"""네이버 장소 상세 정보 조회 (Playwright GraphQL 배치)

v5/api/sites/summary 폐기 → pcmap-api GraphQL로 대체.
avgRating + keyword_tags를 JS Promise.all 배치로 수집.
"""

import json
import os
import math
from tqdm import tqdm
from playwright.sync_api import sync_playwright

from config import RAW_DIR
from crawler.browser import create_browser_context, init_detail_page


GQL_QUERY = (
    "query getVisitorReviewStats($input: VisitorReviewStatsInput) {"
    "  visitorReviewStats(input: $input) {"
    "    id"
    "    review { avgRating totalCount }"
    "    analysis { themes { code label count } }"
    "  }"
    "}"
)

BATCH_SIZE = 20  # JS Promise.all 배치 크기


def _batch_fetch_ratings(page, place_ids: list[str]) -> dict[str, dict]:
    """place_ids 배치를 JS Promise.all로 병렬 GraphQL 호출.
    반환: {place_id: {"rating": float, "keyword_tags": list, "review_total": int}}
    """
    results = page.evaluate(
        """async (args) => {
            const [pids, query] = args;

            async function fetchStats(pid, businessType) {
                const controller = new AbortController();
                const timer = setTimeout(() => controller.abort(), 10000);
                try {
                    const r = await fetch('https://pcmap-api.place.naver.com/place/graphql', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify([{
                            operationName: 'getVisitorReviewStats',
                            variables: { input: { businessId: pid, businessType } },
                            query,
                        }]),
                        signal: controller.signal,
                    });
                    clearTimeout(timer);
                    return { status: r.status, body: await r.text() };
                } catch(e) {
                    clearTimeout(timer);
                    return { status: -1, body: '' };
                }
            }

            const responses = await Promise.all(pids.map(async (pid) => {
                // 1차: restaurant
                let res = await fetchStats(pid, 'restaurant');
                if (res.status === 200) {
                    try {
                        const data = JSON.parse(res.body);
                        const rating = data[0]?.data?.visitorReviewStats?.review?.avgRating;
                        if (rating && rating > 0) return { pid, status: 200, body: res.body };
                    } catch(e) {}
                }
                // 2차 폴백: place
                res = await fetchStats(pid, 'place');
                return { pid, status: res.status, body: res.body };
            }));
            return responses;
        }""",
        [place_ids, GQL_QUERY],
    )

    out = {}
    for r in results:
        pid = r["pid"]
        if r["status"] != 200:
            out[pid] = {"rating": 0.0, "keyword_tags": [], "review_total": 0}
            continue
        try:
            data = json.loads(r["body"])
            stats = (data[0].get("data") or {}).get("visitorReviewStats") or {}
            review = stats.get("review") or {}
            themes = (stats.get("analysis") or {}).get("themes") or []
            keywords = [
                t.get("label", "") for t in themes
                if isinstance(t, dict) and t.get("label")
            ]
            out[pid] = {
                "rating": float(review.get("avgRating", 0) or 0),
                "keyword_tags": keywords,
                "review_total": int(review.get("totalCount", 0) or 0),
            }
        except Exception:
            out[pid] = {"rating": 0.0, "keyword_tags": [], "review_total": 0}
    return out


def enrich_with_ratings(places: list[dict]) -> list[dict]:
    """장소 목록에 rating/keyword_tags 추가. rating > 0인 장소만 반환."""
    place_ids = [p.get("naver_place_id", p.get("id", "")) for p in places]
    n_batches = math.ceil(len(place_ids) / BATCH_SIZE)

    enriched = {}

    with sync_playwright() as pw:
        ctx = create_browser_context(pw, headless=True)
        detail_page = init_detail_page(ctx)
        detail_page.set_default_timeout(30000)  # evaluate 타임아웃 30s

        with tqdm(total=n_batches, desc="별점 수집") as pbar:
            for i in range(n_batches):
                batch = place_ids[i * BATCH_SIZE: (i + 1) * BATCH_SIZE]
                batch = [pid for pid in batch if pid]
                if not batch:
                    pbar.update(1)
                    continue
                try:
                    batch_result = _batch_fetch_ratings(detail_page, batch)
                    enriched.update(batch_result)
                except Exception as e:
                    print(f"  [배치 오류] batch {i}: {e}")
                pbar.update(1)

        ctx.browser.close()

    # 원본 장소에 rating/keyword_tags 병합
    results = []
    for p in places:
        pid = p.get("naver_place_id", p.get("id", ""))
        extra = enriched.get(pid, {"rating": 0.0, "keyword_tags": [], "review_total": 0})
        merged = {
            "naver_place_id": pid,
            "place_name": p.get("place_name", p.get("name", "")),
            "category": p.get("category", ""),
            "address": p.get("address", ""),
            "lat": float(p.get("lat", 0) or 0),
            "lng": float(p.get("lng", 0) or 0),
            "rating": extra["rating"],
            "review_count": int(p.get("review_count", extra.get("review_total", 0)) or 0),
            "blog_review_count": int(p.get("blog_review_count", 0) or 0),
            "keyword_tags": extra["keyword_tags"],
            "menu_prices": p.get("menu_prices", []),
            "business_hours": p.get("business_hours", ""),
        }
        results.append(merged)

    return results


def save_raw(places: list[dict]) -> None:
    """장소 목록을 RAW_DIR에 개별 JSON 파일로 저장."""
    os.makedirs(RAW_DIR, exist_ok=True)
    for p in places:
        pid = p.get("naver_place_id", "")
        if not pid:
            continue
        path = os.path.join(RAW_DIR, f"{pid}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
