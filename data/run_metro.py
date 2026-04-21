"""광역시 집중 수집 크롤러 — HUBS_METRO 거점만 대상으로 search+detail+review 수행.

별도 체크포인트 사용 (supplement과 충돌 없음).
수집 결과는 supplement 인프라와 동일하게 raw/*.json + supplement_place_ids.json에 append.

사용법:
  python run_metro.py               # 전체 실행
  python run_metro.py --headless
  python run_metro.py --detail-only
  python run_metro.py --review-only
  python run_metro.py --skip-detail
  python run_metro.py --skip-review
  python run_metro.py --max-reviews N
"""

import argparse
import json
import os
import time

import pandas as pd
from playwright.sync_api import sync_playwright
from tqdm import tqdm

from config import (
    CATEGORIES,
    FINAL_CSV,
    HUBS_METRO,
    OUTPUT_DIR,
    PLACE_IDS_DIR,
    RAW_DIR,
)
from crawler.browser import (
    create_browser_context,
    fetch_detail_rating_keywords,
    fetch_review_texts,
    init_detail_page,
    search_places,
)

# metro 전용 체크포인트 (supplement과 분리)
METRO_SEARCH_CHECKPOINT = os.path.join(OUTPUT_DIR, "metro_search_checkpoint.json")
METRO_ENRICHED_PATH = os.path.join(OUTPUT_DIR, "metro_enriched_ids.json")
METRO_REVIEWS_PATH = os.path.join(OUTPUT_DIR, "metro_review_ids.json")

# 수집 결과는 supplement에 append (통합 관리)
SUPPLEMENT_IDS_PATH = os.path.join(PLACE_IDS_DIR, "supplement_place_ids.json")


def _save_checkpoint(done_pairs: set, new_places: list) -> None:
    with open(METRO_SEARCH_CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(list(done_pairs), f, ensure_ascii=False)
    # supplement_place_ids.json에 merge (dedup)
    existing: list = []
    if os.path.exists(SUPPLEMENT_IDS_PATH):
        with open(SUPPLEMENT_IDS_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing_ids = {str(p.get("naver_place_id", "")) for p in existing}
    added = [p for p in new_places if str(p.get("naver_place_id", "")) not in existing_ids]
    merged = existing + added
    with open(SUPPLEMENT_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)


def run_metro_search(context, seen_ids: set) -> list:
    """HUBS_METRO × CATEGORIES × keywords 검색. metro 전용 체크포인트."""
    done_pairs: set[str] = set()
    if os.path.exists(METRO_SEARCH_CHECKPOINT):
        with open(METRO_SEARCH_CHECKPOINT, "r", encoding="utf-8") as f:
            done_pairs = set(json.load(f))
        print(f"metro 검색 체크포인트 로드: {len(done_pairs)}쌍 기완료")

    # 이미 수집된 metro 장소 로드 (재실행 시 이어받기)
    new_places: list = []
    if os.path.exists(SUPPLEMENT_IDS_PATH):
        with open(SUPPLEMENT_IDS_PATH, "r", encoding="utf-8") as f:
            all_sup = json.load(f)
        # metro hub 소속만 필터
        metro_hub_names = {h["name"] for h in HUBS_METRO}
        new_places = [p for p in all_sup if p.get("hub", "") in metro_hub_names]
        for p in new_places:
            seen_ids.add(str(p.get("naver_place_id", "")))
        print(f"기수집 metro 장소: {len(new_places)}개")

    cat_map = {c["name"]: c for c in CATEGORIES}
    total_keywords = sum(
        len(kws)
        for cat in CATEGORIES
        for kws in [cat["keywords"]]
    ) * len(HUBS_METRO)

    page = context.new_page()
    print("네이버 지도 접속 중...")
    page.goto("https://map.naver.com/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    print(f"접속 완료. 광역시 집중 수집 시작. 총 키워드 수: {total_keywords:,}\n")

    checkpoint_interval = 50
    processed = 0

    with tqdm(total=total_keywords, desc="metro 검색") as pbar:
        for hub in HUBS_METRO:
            for cat in CATEGORIES:
                for keyword in cat["keywords"]:
                    pair_key = f"{hub['name']}|{cat['name']}|{keyword}"

                    if pair_key in done_pairs:
                        pbar.update(1)
                        processed += 1
                        continue

                    area = hub["name"].split("_", 1)[1] if "_" in hub["name"] else hub["name"]
                    query = f"{area} {keyword}"
                    places = search_places(page, query, hub["lat"], hub["lng"])

                    new_count = 0
                    for p in places:
                        pid = str(p.get("naver_place_id", ""))
                        if pid and pid not in seen_ids:
                            p["hub"] = hub["name"]
                            p["keyword"] = keyword
                            p["category_group"] = cat["name"]
                            new_places.append(p)
                            seen_ids.add(pid)
                            new_count += 1

                    done_pairs.add(pair_key)
                    pbar.set_postfix({"허브": hub["name"], "신규": new_count, "누적": len(new_places)})
                    pbar.update(1)
                    processed += 1

                    time.sleep(1)

                    if processed % checkpoint_interval == 0:
                        _save_checkpoint(done_pairs, new_places)

    page.close()
    _save_checkpoint(done_pairs, new_places)
    print(f"\nmeto 검색 완료: {len(new_places)}개 신규 장소")
    return new_places


def run_metro_detail(context, places_data: list) -> None:
    """별점+키워드 보강. metro 전용 체크포인트."""
    already_done: set[str] = set()
    if os.path.exists(METRO_ENRICHED_PATH):
        with open(METRO_ENRICHED_PATH, "r") as f:
            already_done = set(json.load(f))
        print(f"detail 체크포인트 로드: {len(already_done)}개 기완료")

    remaining = [p for p in places_data if p["naver_place_id"] not in already_done]
    print(f"detail 보강: 전체 {len(places_data)}, 남은 {len(remaining)}")

    if not remaining:
        print("보강 대상 없음.")
        return

    page = init_detail_page(context)
    success = empty = 0

    for i, p in enumerate(tqdm(remaining, desc="detail 보강")):
        pid = p["naver_place_id"]
        detail = fetch_detail_rating_keywords(page, pid)

        p["rating"] = detail.get("rating", 0.0)
        p["keyword_tags"] = detail.get("keyword_tags", [])
        if detail.get("review_total", 0) > 0:
            p["review_total_verified"] = detail["review_total"]

        if detail.get("keyword_tags"):
            success += 1
        else:
            empty += 1

        already_done.add(pid)

        raw_path = os.path.join(RAW_DIR, f"{pid}.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)

        if (i + 1) % 100 == 0:
            with open(METRO_ENRICHED_PATH, "w") as f:
                json.dump(list(already_done), f)
            tqdm.write(f"  [checkpoint {i+1}] 성공: {success} | 빈값: {empty}")

        if (i + 1) % 200 == 0:
            try:
                page.reload(wait_until="domcontentloaded", timeout=10000)
                page.wait_for_timeout(1500)
            except Exception:
                pass

        if (i + 1) % 1000 == 0:
            with open(METRO_ENRICHED_PATH, "w") as f:
                json.dump(list(already_done), f)
            tqdm.write(f"  [rate-limit 휴식] {i+1}개 완료, 10분 대기...")
            time.sleep(600)
            try:
                page.reload(wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
            except Exception:
                pass

        time.sleep(1.5)

    with open(METRO_ENRICHED_PATH, "w") as f:
        json.dump(list(already_done), f)
    page.close()
    print(f"detail 완료: {success}/{len(remaining)}, 빈값 {empty}")


def run_metro_reviews(context, places_data: list, max_reviews: int = 20) -> None:
    """리뷰 수집. metro 전용 체크포인트."""
    already_done: set[str] = set()
    if os.path.exists(METRO_REVIEWS_PATH):
        with open(METRO_REVIEWS_PATH, "r") as f:
            already_done = set(json.load(f))
        print(f"리뷰 체크포인트 로드: {len(already_done)}개 기완료")

    targets = [
        p for p in places_data
        if str(p["naver_place_id"]) not in already_done
        and p.get("review_count", 0) > 0
    ]
    print(f"리뷰 수집: 남은 {len(targets)}개")

    if not targets:
        print("리뷰 수집 대상 없음.")
        return

    page = init_detail_page(context)
    collected = empty = 0

    for i, p in enumerate(tqdm(targets, desc="리뷰 수집")):
        pid = p["naver_place_id"]
        reviews = fetch_review_texts(page, pid, max_reviews=max_reviews)

        p["review_texts"] = reviews
        already_done.add(str(pid))

        if reviews:
            collected += 1
        else:
            empty += 1

        raw_path = os.path.join(RAW_DIR, f"{pid}.json")
        if os.path.exists(raw_path):
            try:
                with open(raw_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                existing["review_texts"] = reviews
            except Exception:
                existing = dict(p)
                existing["review_texts"] = reviews
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        else:
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(dict(p, review_texts=reviews), f, ensure_ascii=False, indent=2)

        if (i + 1) % 100 == 0:
            with open(METRO_REVIEWS_PATH, "w") as f:
                json.dump(list(already_done), f)
            tqdm.write(f"  [checkpoint {i+1}] 수집: {collected} | 빈값: {empty}")

        if (i + 1) % 500 == 0:
            try:
                page.reload(wait_until="domcontentloaded", timeout=10000)
                page.wait_for_timeout(1000)
            except Exception:
                pass

        time.sleep(0.8)

    with open(METRO_REVIEWS_PATH, "w") as f:
        json.dump(list(already_done), f)
    page.close()
    print(f"리뷰 완료: {collected}/{len(targets)}, 빈값 {empty}")


def main():
    parser = argparse.ArgumentParser(description="광역시 집중 수집 (HUBS_METRO)")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--detail-only", action="store_true")
    parser.add_argument("--review-only", action="store_true")
    parser.add_argument("--skip-detail", action="store_true")
    parser.add_argument("--skip-review", action="store_true")
    parser.add_argument("--max-reviews", type=int, default=20)
    args = parser.parse_args()

    os.makedirs(PLACE_IDS_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    # seen_ids: 기존 CSV + supplement 전체
    seen_ids: set[str] = set()
    if os.path.exists(FINAL_CSV):
        df = pd.read_csv(FINAL_CSV)
        seen_ids = set(df["naver_place_id"].dropna().astype(str))
        print(f"기존 places.csv: {len(seen_ids):,}개")
    if os.path.exists(SUPPLEMENT_IDS_PATH):
        with open(SUPPLEMENT_IDS_PATH, "r", encoding="utf-8") as f:
            sup = json.load(f)
        for p in sup:
            seen_ids.add(str(p.get("naver_place_id", "")))
        print(f"supplement 포함 총 seen: {len(seen_ids):,}개")

    metro_hub_names = {h["name"] for h in HUBS_METRO}

    with sync_playwright() as pw:
        context = create_browser_context(pw, headless=args.headless)

        if args.detail_only or args.review_only:
            # supplement에서 metro 소속만 로드
            if not os.path.exists(SUPPLEMENT_IDS_PATH):
                print(f"오류: {SUPPLEMENT_IDS_PATH} 없음.")
                return
            with open(SUPPLEMENT_IDS_PATH, "r", encoding="utf-8") as f:
                all_sup = json.load(f)
            places = [p for p in all_sup if p.get("hub", "") in metro_hub_names]
            print(f"metro 장소 로드: {len(places)}개")
        else:
            places = run_metro_search(context, seen_ids)

        if not args.skip_detail and not args.review_only:
            run_metro_detail(context, places)

        if not args.skip_review and not args.detail_only:
            run_metro_reviews(context, places, max_reviews=args.max_reviews)

        context.browser.close()

    hub_dist: dict[str, int] = {}
    for p in places:
        h = p.get("hub", "?")
        hub_dist[h] = hub_dist.get(h, 0) + 1

    print("\n=== metro 수집 완료 ===")
    print(f"총 {len(places):,}개 장소\n")
    for hub in HUBS_METRO:
        cnt = hub_dist.get(hub["name"], 0)
        print(f"  {hub['name']:20s}: {cnt:,}개")


if __name__ == "__main__":
    main()
