"""Playwright 기반 네이버 지도 크롤러 실행

사용법:
  python run_crawl.py                  # 전체 실행 (headed 모드)
  python run_crawl.py --test           # 대전 1거점 테스트
  python run_crawl.py --headless       # headless 모드
  python run_crawl.py --detail-only    # 별점/키워드 보강만
  python run_crawl.py --skip-detail    # 검색만 (상세 스킵)
"""

import argparse
import json
import os
import time
import pandas as pd
from playwright.sync_api import sync_playwright
from tqdm import tqdm

from config import HUBS, CATEGORIES, PLACE_IDS_DIR, RAW_DIR, FINAL_CSV, OUTPUT_DIR
from crawler.browser import (
    create_browser_context,
    search_places,
    fetch_detail_rating_keywords,
    fetch_review_texts,
    init_detail_page,
)


def run_search(context, hubs, categories):
    """1단계: 거점×카테고리 검색 → 장소 기본 데이터 수집"""
    page = context.new_page()
    all_places = []
    seen_ids = set()

    print("네이버 지도 접속 중...")
    page.goto("https://map.naver.com/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    print("접속 완료. 검색 시작.\n")

    total = sum(len(cat["keywords"]) for cat in categories) * len(hubs)

    with tqdm(total=total, desc="검색 진행") as pbar:
        for hub in hubs:
            for cat in categories:
                for keyword in cat["keywords"]:
                    query = f"{hub['name'].split('_')[1]} {keyword}"
                    places = search_places(page, query, hub["lat"], hub["lng"])

                    new_count = 0
                    for p in places:
                        pid = p.get("naver_place_id", "")
                        if pid and pid not in seen_ids:
                            p["hub"] = hub["name"]
                            p["keyword"] = keyword
                            p["category_group"] = cat["name"]
                            all_places.append(p)
                            seen_ids.add(pid)
                            new_count += 1

                    pbar.set_postfix({"신규": new_count, "누적": len(all_places)})
                    pbar.update(1)
                    time.sleep(1)

    page.close()
    print(f"\n검색 완료: 총 {len(all_places)}곳 (중복 제거)")
    return all_places


def run_detail_enrichment(context, places_data):
    """2단계: pcmap 도메인에서 JS fetch → GraphQL로 별점 + 키워드 보강.
    기존 체크포인트는 리셋하고 전체 재시도 (이전 보강은 파싱 실패였으므로)."""
    enriched_path = os.path.join(OUTPUT_DIR, "enriched_ids_v2.json")

    already_done = set()
    if os.path.exists(enriched_path):
        with open(enriched_path, "r") as f:
            already_done = set(json.load(f))
        print(f"v2 체크포인트 로드: {len(already_done)}개 기완료")

    remaining = [p for p in places_data if p["naver_place_id"] not in already_done]
    print(f"별점/키워드 보강: 전체 {len(places_data)}, 기완료 {len(already_done)}, 남은 {len(remaining)}")

    if not remaining:
        print("보강할 대상 없음.")
        return

    # pcmap 도메인 진입 (JS fetch용)
    page = init_detail_page(context)

    success = 0
    empty = 0
    errors = 0

    for i, p in enumerate(tqdm(remaining, desc="별점/키워드 보강 (v2)")):
        pid = p["naver_place_id"]
        detail = fetch_detail_rating_keywords(page, pid)

        p["rating"] = detail.get("rating", 0.0)
        p["keyword_tags"] = detail.get("keyword_tags", [])
        if detail.get("review_total", 0) > 0:
            p["review_total_verified"] = detail["review_total"]

        if detail["keyword_tags"]:
            success += 1
        elif detail.get("review_total", 0) == 0 and detail["rating"] == 0.0:
            empty += 1
        else:
            errors += 1

        already_done.add(pid)

        # raw JSON 즉시 저장
        raw_path = os.path.join(RAW_DIR, f"{pid}.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)

        # 100건마다 체크포인트
        if (i + 1) % 100 == 0:
            with open(enriched_path, "w") as f:
                json.dump(list(already_done), f)
            tqdm.write(
                f"  [checkpoint {i+1}] 성공: {success} | 빈값: {empty} | 오류: {errors}"
            )

        # 세션 유지를 위해 500건마다 페이지 리프레시
        if (i + 1) % 500 == 0:
            try:
                page.reload(wait_until="domcontentloaded", timeout=10000)
                page.wait_for_timeout(1000)
            except Exception:
                pass

        time.sleep(0.8)

    # 최종 저장
    with open(enriched_path, "w") as f:
        json.dump(list(already_done), f)

    page.close()
    print(f"보강 완료: 키워드 확보 {success}/{len(remaining)}, 빈값 {empty}, 오류 {errors}")


def run_review_collection(context, places_data, max_reviews=20):
    """3단계: 리뷰 텍스트 수집 (ABSA 감성분석 입력용).
    review_count > 0인 장소만 대상. 체크포인트 기반 중단/재개."""
    checkpoint_path = os.path.join(OUTPUT_DIR, "review_collected_ids.json")

    already_done = set()
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r") as f:
            already_done = set(json.load(f))
        print(f"리뷰 체크포인트 로드: {len(already_done)}개 기완료")

    # review_count > 0인 장소만 대상
    targets = [
        p for p in places_data
        if p["naver_place_id"] not in already_done
        and p.get("review_count", 0) > 0
    ]
    print(f"리뷰 수집: 전체 {len(places_data)}, 대상(review>0) {sum(1 for p in places_data if p.get('review_count',0)>0)}, 기완료 {len(already_done)}, 남은 {len(targets)}")

    if not targets:
        print("리뷰 수집 대상 없음.")
        return

    page = init_detail_page(context)

    collected = 0
    empty = 0

    for i, p in enumerate(tqdm(targets, desc="리뷰 수집")):
        pid = p["naver_place_id"]
        reviews = fetch_review_texts(page, pid, max_reviews=max_reviews)

        p["review_texts"] = reviews
        already_done.add(pid)

        if reviews:
            collected += 1
        else:
            empty += 1

        # raw JSON 즉시 저장
        raw_path = os.path.join(RAW_DIR, f"{pid}.json")
        if os.path.exists(raw_path):
            with open(raw_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing["review_texts"] = reviews
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        else:
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(p, f, ensure_ascii=False, indent=2)

        # 100건마다 체크포인트
        if (i + 1) % 100 == 0:
            with open(checkpoint_path, "w") as f:
                json.dump(list(already_done), f)
            tqdm.write(
                f"  [checkpoint {i+1}] 수집: {collected} | 빈값: {empty}"
            )

        # 500건마다 페이지 리프레시
        if (i + 1) % 500 == 0:
            try:
                page.reload(wait_until="domcontentloaded", timeout=10000)
                page.wait_for_timeout(1000)
            except Exception:
                pass

        time.sleep(0.8)

    with open(checkpoint_path, "w") as f:
        json.dump(list(already_done), f)

    page.close()
    print(f"리뷰 수집 완료: {collected}/{len(targets)} 수집, {empty} 빈값")


def save_results(places_data):
    """raw JSON에서 보강 데이터를 읽어 최종 CSV 생성.
    raw JSON이 이미 보강된 데이터를 가지고 있으면 그것을 우선 사용."""
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # raw JSON에서 보강된 데이터 머지
    final_places = []
    for p in places_data:
        pid = p.get("naver_place_id", "")
        if pid:
            raw_path = os.path.join(RAW_DIR, f"{pid}.json")
            if os.path.exists(raw_path):
                with open(raw_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # raw에 보강 데이터가 있으면 머지
                if raw.get("keyword_tags") or raw.get("rating", 0) > 0:
                    p["rating"] = raw.get("rating", p.get("rating", 0.0))
                    p["keyword_tags"] = raw.get("keyword_tags", p.get("keyword_tags", []))
                    if raw.get("review_total_verified"):
                        p["review_total_verified"] = raw["review_total_verified"]
            # raw JSON 갱신 (머지된 데이터로)
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(p, f, ensure_ascii=False, indent=2)
        final_places.append(p)

    # CSV 변환
    df = pd.DataFrame(final_places)
    for col in ["keyword_tags", "menu_prices"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x
            )

    if "naver_place_id" in df.columns:
        df = df.drop_duplicates(subset="naver_place_id")

    if "review_count" in df.columns:
        before = len(df)
        df = df[df["review_count"] > 0]
        print(f"리뷰 0개 제거: {before} → {len(df)}곳")

    df.to_csv(FINAL_CSV, index=False, encoding="utf-8-sig")
    print(f"CSV 저장: {FINAL_CSV} ({len(df)}곳)")


def main():
    parser = argparse.ArgumentParser(description="네이버 지도 장소 크롤러")
    parser.add_argument("--test", action="store_true", help="대전 1거점 테스트")
    parser.add_argument("--headless", action="store_true", help="headless 모드")
    parser.add_argument("--detail-only", action="store_true", help="별점/키워드 보강만")
    parser.add_argument("--skip-detail", action="store_true", help="검색만 (상세 스킵)")
    parser.add_argument("--review-only", action="store_true", help="리뷰 텍스트 수집만")
    parser.add_argument("--skip-review", action="store_true", help="리뷰 수집 스킵")
    parser.add_argument("--max-reviews", type=int, default=20, help="장소당 최대 리뷰 수 (기본 20)")
    args = parser.parse_args()

    os.makedirs(PLACE_IDS_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    if args.test:
        hubs = [h for h in HUBS if h["name"] == "대전_둔산"]
        categories = [{"name": "음식점", "keywords": ["맛집"]}]
    else:
        hubs = HUBS
        categories = CATEGORIES

    ids_path = os.path.join(PLACE_IDS_DIR, "all_place_ids.json")

    with sync_playwright() as pw:
        context = create_browser_context(pw, headless=args.headless)

        if args.review_only or args.detail_only:
            with open(ids_path, "r", encoding="utf-8") as f:
                places = json.load(f)
            print(f"기존 데이터 로드: {len(places)}곳")
        else:
            # 1단계: 검색 → 기본 데이터 수집
            places = run_search(context, hubs, categories)
            with open(ids_path, "w", encoding="utf-8") as f:
                json.dump(places, f, ensure_ascii=False, indent=2)
            print(f"장소 데이터 저장: {ids_path}")

        if not args.skip_detail and not args.review_only:
            # 2단계: 별점 + 키워드 보강
            run_detail_enrichment(context, places)

        if not args.skip_review and not args.detail_only:
            # 3단계: 리뷰 텍스트 수집
            run_review_collection(context, places, max_reviews=args.max_reviews)

        context.browser.close()

    # 최종 저장
    save_results(places)

    print("\n" + "=" * 60)
    print("크롤링 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
