"""리뷰 텍스트 확보 우선 장소 수집

전략:
  1. 검색 → review_count >= MIN_REVIEW_COUNT 필터
  2. 기존 수집된 장소 ID 스킵 (all_place_ids.json 기준)
  3. 각 장소마다 즉시 review_texts 수집 시도
  4. 리뷰 실제 확보된 장소만 저장 (빈값 버림)

사용법:
  python run_collect_with_reviews.py              # 전체
  python run_collect_with_reviews.py --test       # 대전 둔산 1거점, 맛집만
  python run_collect_with_reviews.py --headless   # headless 모드
  python run_collect_with_reviews.py --min-reviews 5  # 리뷰 5개 이상만 시도
  python run_collect_with_reviews.py --max-reviews 30 # 장소당 최대 30개 수집
"""

import argparse
import json
import os
import time
import logging
from playwright.sync_api import sync_playwright
from tqdm import tqdm

from config import HUBS, CATEGORIES, PLACE_IDS_DIR, RAW_DIR, OUTPUT_DIR
from crawler.browser import (
    create_browser_context,
    search_places,
    fetch_detail_rating_keywords,
    fetch_review_texts,
    init_detail_page,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── 확장 거점 (--extra 모드) ──────────────────────────────────────────
EXTRA_HUBS: list[dict] = [
    # 서울 추가 거점
    {"name": "서울_신촌", "lat": 37.5558, "lng": 126.9368, "radius": 1500},
    {"name": "서울_이태원", "lat": 37.5340, "lng": 126.9944, "radius": 1500},
    {"name": "서울_신림", "lat": 37.4843, "lng": 126.9293, "radius": 1500},
    {"name": "서울_노원", "lat": 37.6542, "lng": 127.0568, "radius": 1500},
    {"name": "서울_마포", "lat": 37.5545, "lng": 126.9080, "radius": 1500},
    {"name": "서울_왕십리", "lat": 37.5614, "lng": 127.0369, "radius": 1500},
    {"name": "서울_영등포", "lat": 37.5264, "lng": 126.8963, "radius": 1500},
    # 경기도
    {"name": "수원_인계동", "lat": 37.2636, "lng": 127.0286, "radius": 2000},
    {"name": "수원_광교", "lat": 37.2894, "lng": 127.0457, "radius": 2000},
    {"name": "성남_판교", "lat": 37.3943, "lng": 127.1111, "radius": 2000},
    {"name": "성남_분당", "lat": 37.3820, "lng": 127.1233, "radius": 2000},
    {"name": "용인_기흥", "lat": 37.2750, "lng": 127.1145, "radius": 2000},
    {"name": "안양_범계", "lat": 37.3940, "lng": 126.9533, "radius": 2000},
    # 전북
    {"name": "전주_객사", "lat": 35.8200, "lng": 127.1500, "radius": 2000},
    {"name": "전주_전통한옥마을", "lat": 35.8147, "lng": 127.1533, "radius": 2000},
    # 경남
    {"name": "창원_상남동", "lat": 35.2279, "lng": 128.6811, "radius": 2000},
    {"name": "창원_용호동", "lat": 35.1877, "lng": 128.6898, "radius": 2000},
    # 충청
    {"name": "청주_성안길", "lat": 36.6357, "lng": 127.4914, "radius": 2000},
    {"name": "천안_신부동", "lat": 36.8151, "lng": 127.1139, "radius": 2000},
    # 제주
    {"name": "제주_연동", "lat": 33.4996, "lng": 126.5312, "radius": 2000},
    {"name": "제주_서귀포", "lat": 33.2541, "lng": 126.5600, "radius": 2000},
    # 강원
    {"name": "강릉_교동", "lat": 37.7519, "lng": 128.8761, "radius": 2000},
    {"name": "춘천_명동", "lat": 37.8813, "lng": 127.7298, "radius": 2000},
    # 경북
    {"name": "포항_죽도시장", "lat": 36.0190, "lng": 129.3601, "radius": 2000},
    {"name": "경주_황리단길", "lat": 35.8340, "lng": 129.2113, "radius": 2000},
]

# 확장 카테고리/키워드
EXTRA_CATEGORIES: list[dict] = [
    {"name": "음식점", "keywords": [
        "삼겹살", "치킨", "초밥", "라멘", "파스타", "스테이크", "족발",
        "오마카세", "육회", "소고기", "해산물", "마라탕", "곱창", "순대국",
        "갈비", "냉면", "쌀국수", "타코", "버거", "피자",
    ]},
    {"name": "카페", "keywords": [
        "루프탑카페", "브런치", "베이커리카페", "스페셜티커피", "한옥카페",
        "뷰맛집카페", "감성카페", "테라스카페",
    ]},
    {"name": "술집", "keywords": [
        "칵테일바", "수제맥주", "사케바", "막걸리", "포차", "루프탑바",
    ]},
    {"name": "스터디", "keywords": [
        "독서실카페", "스터디룸",
    ]},
]

# 기존 수집 장소 IDs 로드 경로
ALL_PLACE_IDS_PATH = os.path.join(PLACE_IDS_DIR, "all_place_ids.json")
# 신규 수집 체크포인트
NEW_COLLECTED_IDS_PATH = os.path.join(PLACE_IDS_DIR, "new_review_collected_ids.json")
# 신규 수집 통합 index
NEW_PLACE_IDS_PATH = os.path.join(PLACE_IDS_DIR, "new_place_ids_with_reviews.json")


def load_existing_ids() -> set[str]:
    """기존 수집된 장소 ID 전체 로드 (스킵용)."""
    existing = set()

    if os.path.exists(ALL_PLACE_IDS_PATH):
        with open(ALL_PLACE_IDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for p in data:
            pid = str(p.get("naver_place_id") or p.get("id") or "")
            if pid:
                existing.add(pid)
        logger.info(f"기존 장소 ID 로드: {len(existing)}개 (스킵 대상)")

    # raw/ 디렉터리에서도 확인 (all_place_ids 누락 대응)
    if os.path.exists(RAW_DIR):
        for fname in os.listdir(RAW_DIR):
            if fname.endswith(".json"):
                existing.add(fname[:-5])

    logger.info(f"스킵 대상 총 {len(existing)}개 (IDs + raw 파일)")
    return existing


def load_checkpoint() -> set[str]:
    """이번 run의 체크포인트 로드 (중단 재개용)."""
    if os.path.exists(NEW_COLLECTED_IDS_PATH):
        with open(NEW_COLLECTED_IDS_PATH, "r", encoding="utf-8") as f:
            ids = json.load(f)
        logger.info(f"체크포인트 로드: {len(ids)}개 기처리")
        return set(ids)
    return set()


def save_checkpoint(done_ids: set[str]):
    os.makedirs(PLACE_IDS_DIR, exist_ok=True)
    with open(NEW_COLLECTED_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(list(done_ids), f)


def save_place_raw(place: dict):
    """장소 데이터를 raw/ 디렉터리에 저장."""
    os.makedirs(RAW_DIR, exist_ok=True)
    pid = place["naver_place_id"]
    path = os.path.join(RAW_DIR, f"{pid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(place, f, ensure_ascii=False, indent=2)


def append_to_new_index(places: list[dict]):
    """new_place_ids_with_reviews.json에 누적 저장."""
    os.makedirs(PLACE_IDS_DIR, exist_ok=True)
    existing = []
    if os.path.exists(NEW_PLACE_IDS_PATH):
        with open(NEW_PLACE_IDS_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing.extend(places)
    with open(NEW_PLACE_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def collect_with_reviews(
    hubs: list[dict],
    categories: list[dict],
    min_review_count: int = 5,
    max_reviews: int = 20,
    headless: bool = False,
):
    """검색 → 즉시 리뷰 수집 통합 실행."""
    existing_ids = load_existing_ids()
    done_ids = load_checkpoint()

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(PLACE_IDS_DIR, exist_ok=True)

    total_queries = sum(len(cat["keywords"]) for cat in categories) * len(hubs)
    logger.info(
        f"검색 쿼리 수: {total_queries}개 | "
        f"min_review_count={min_review_count} | max_reviews={max_reviews}"
    )

    saved_count = 0
    skipped_existing = 0
    skipped_no_review = 0
    newly_found_batch = []

    with sync_playwright() as pw:
        context = create_browser_context(pw, headless=headless)

        # 검색용 페이지
        search_page = context.new_page()
        logger.info("네이버 지도 접속 중...")
        search_page.goto("https://map.naver.com/", wait_until="networkidle", timeout=30000)
        search_page.wait_for_timeout(3000)
        logger.info("접속 완료.")

        # 리뷰/상세 수집용 페이지 (pcmap 도메인)
        detail_page = init_detail_page(context)

        with tqdm(total=total_queries, desc="검색+리뷰 수집") as pbar:
            for hub in hubs:
                for cat in categories:
                    for keyword in cat["keywords"]:
                        query = f"{hub['name'].split('_')[1]} {keyword}"
                        candidates = search_places(search_page, query, hub["lat"], hub["lng"])

                        new_in_query = 0
                        for place in candidates:
                            pid = place.get("naver_place_id", "")
                            if not pid:
                                continue

                            # 기존 수집 장소 스킵
                            if pid in existing_ids:
                                skipped_existing += 1
                                continue

                            # 이번 run에서 이미 처리한 장소 스킵
                            if pid in done_ids:
                                continue

                            # review_count 기준 필터
                            if place.get("review_count", 0) < min_review_count:
                                skipped_no_review += 1
                                done_ids.add(pid)
                                continue

                            # 상세 정보 보강 (rating + keyword_tags)
                            detail = fetch_detail_rating_keywords(detail_page, pid)
                            place["rating"] = detail.get("rating", 0.0)
                            place["keyword_tags"] = detail.get("keyword_tags", [])

                            # 리뷰 텍스트 즉시 수집
                            reviews = fetch_review_texts(detail_page, pid, max_reviews=max_reviews)

                            done_ids.add(pid)
                            existing_ids.add(pid)  # 중복 방지

                            if not reviews:
                                # 리뷰 텍스트 없으면 버림
                                skipped_no_review += 1
                                time.sleep(0.3)
                                continue

                            # 리뷰 확보 → 저장
                            place["hub"] = hub["name"]
                            place["keyword"] = keyword
                            place["category_group"] = cat["name"]
                            place["review_texts"] = reviews

                            save_place_raw(place)
                            newly_found_batch.append(place)
                            saved_count += 1
                            new_in_query += 1

                            time.sleep(0.8)

                        pbar.set_postfix({
                            "저장": saved_count,
                            "스킵(기존)": skipped_existing,
                            "스킵(리뷰없음)": skipped_no_review,
                            "이번쿼리": new_in_query,
                        })
                        pbar.update(1)

                        # 100개마다 체크포인트 저장
                        if saved_count > 0 and saved_count % 100 == 0:
                            save_checkpoint(done_ids)
                            append_to_new_index(newly_found_batch)
                            newly_found_batch = []

                        time.sleep(1.0)

        search_page.close()
        detail_page.close()
        context.browser.close()

    # 최종 저장
    save_checkpoint(done_ids)
    if newly_found_batch:
        append_to_new_index(newly_found_batch)

    logger.info(
        f"\n{'='*60}\n"
        f"수집 완료\n"
        f"  신규 저장 (리뷰 확보): {saved_count}곳\n"
        f"  스킵 (기존 장소):      {skipped_existing}건\n"
        f"  스킵 (리뷰 미확보):    {skipped_no_review}건\n"
        f"  결과: output/raw/<pid>.json, {NEW_PLACE_IDS_PATH}\n"
        f"{'='*60}"
    )
    return {
        "saved": saved_count,
        "skipped_existing": skipped_existing,
        "skipped_no_review": skipped_no_review,
    }


def main():
    parser = argparse.ArgumentParser(description="리뷰 텍스트 확보 우선 장소 수집")
    parser.add_argument("--test", action="store_true", help="대전 둔산 1거점, 맛집만")
    parser.add_argument("--extra", action="store_true", help="확장 거점+키워드 (신규 도시, 세부 음식 카테고리)")
    parser.add_argument("--headless", action="store_true", help="headless 모드")
    parser.add_argument(
        "--min-reviews", type=int, default=5,
        help="리뷰 수집 시도 최소 visitor review_count (기본 5)"
    )
    parser.add_argument(
        "--max-reviews", type=int, default=20,
        help="장소당 최대 리뷰 수집 개수 (기본 20)"
    )
    args = parser.parse_args()

    if args.test:
        hubs = [h for h in HUBS if h["name"] == "대전_둔산"]
        categories = [{"name": "음식점", "keywords": ["맛집"]}]
    elif args.extra:
        hubs = EXTRA_HUBS
        categories = EXTRA_CATEGORIES
    else:
        hubs = HUBS
        categories = CATEGORIES

    start = time.time()
    stats = collect_with_reviews(
        hubs=hubs,
        categories=categories,
        min_review_count=args.min_reviews,
        max_reviews=args.max_reviews,
        headless=args.headless,
    )
    elapsed = time.time() - start

    print(f"\n완료 ({elapsed:.0f}초 / {elapsed/60:.1f}분)")
    print(f"  신규 저장: {stats['saved']}곳")
    print(f"  스킵 (기존): {stats['skipped_existing']}건")
    print(f"  스킵 (리뷰없음): {stats['skipped_no_review']}건")


if __name__ == "__main__":
    main()
