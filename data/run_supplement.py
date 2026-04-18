"""보완 크롤러: 누락/편향 허브 대상으로 기존 데이터 보존하며 append 수집

사용법:
  python run_supplement.py               # 전체 실행 (search+detail+review)
  python run_supplement.py --headless    # headless 모드
  python run_supplement.py --detail-only # 상세 보강만 (기수집 supplement_place_ids.json 대상)
  python run_supplement.py --review-only # 리뷰 수집만
  python run_supplement.py --skip-detail # 검색만 (상세 스킵)
  python run_supplement.py --skip-review # 리뷰 스킵
  python run_supplement.py --max-reviews N

주의: 기존 places.csv는 덮어쓰지 않고 append. 중단 후 재실행 시 체크포인트에서 재개.
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
    HUBS,
    HUBS_ALL,
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

# 보완 크롤용 전용 파일 (run_crawl.py 체크포인트와 충돌 방지)
SUPPLEMENT_SEARCH_CHECKPOINT = os.path.join(OUTPUT_DIR, "supplement_search_checkpoint.json")
SUPPLEMENT_IDS_PATH = os.path.join(PLACE_IDS_DIR, "supplement_place_ids.json")
SUPPLEMENT_ENRICHED_PATH = os.path.join(OUTPUT_DIR, "supplement_enriched_ids.json")
SUPPLEMENT_REVIEWS_PATH = os.path.join(OUTPUT_DIR, "supplement_review_ids.json")


def get_targets() -> list[tuple[dict, list[str]]]:
    """기존 places.csv 분석 → 누락/편향 허브×카테고리 목록 반환.

    Returns:
        [(hub_dict, [missing_cat_names, ...]), ...]
    """
    all_hubs: dict[str, dict] = {h["name"]: h for h in HUBS_ALL + HUBS}
    cat_names = [c["name"] for c in CATEGORIES]

    if not os.path.exists(FINAL_CSV):
        print("places.csv 없음 → 전체 허브 수집")
        return [(h, cat_names) for h in all_hubs.values()]

    df = pd.read_csv(FINAL_CSV)
    targets = []

    for hub_name, hub_dict in all_hubs.items():
        hub_df = df[df["hub"] == hub_name]
        if len(hub_df) == 0:
            targets.append((hub_dict, cat_names[:]))
        else:
            present = (
                set(hub_df["category_group"].dropna().unique())
                if "category_group" in hub_df.columns
                else set()
            )
            missing = [c for c in cat_names if c not in present]
            if missing:
                targets.append((hub_dict, missing))

    return targets


def _save_search_checkpoint(done_pairs: set, new_places: list) -> None:
    with open(SUPPLEMENT_SEARCH_CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(list(done_pairs), f, ensure_ascii=False)
    with open(SUPPLEMENT_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(new_places, f, ensure_ascii=False, indent=2)


def run_supplement_search(
    context, targets: list[tuple[dict, list[str]]], seen_ids: set
) -> list:
    """1단계: 누락 허브×카테고리 검색. 허브×카테고리×키워드 단위 체크포인트로 중단/재개.

    Args:
        targets: get_targets() 결과
        seen_ids: 기존 places.csv + 기수집 supplement의 naver_place_id 집합
    """
    # 체크포인트 로드
    done_pairs: set[str] = set()
    if os.path.exists(SUPPLEMENT_SEARCH_CHECKPOINT):
        with open(SUPPLEMENT_SEARCH_CHECKPOINT, "r", encoding="utf-8") as f:
            done_pairs = set(json.load(f))
        print(f"검색 체크포인트 로드: {len(done_pairs)}쌍 기완료")

    # 기수집 supplement 데이터 로드
    new_places: list = []
    if os.path.exists(SUPPLEMENT_IDS_PATH):
        with open(SUPPLEMENT_IDS_PATH, "r", encoding="utf-8") as f:
            new_places = json.load(f)
        # 기수집 id도 seen에 추가
        for p in new_places:
            pid = str(p.get("naver_place_id", ""))
            if pid:
                seen_ids.add(pid)
        print(f"기수집 supplement 데이터: {len(new_places)}개")

    cat_map = {c["name"]: c for c in CATEGORIES}
    total_keywords = sum(
        len(cat_map[c]["keywords"]) for _, cats in targets for c in cats
    )

    page = context.new_page()
    print("네이버 지도 접속 중...")
    page.goto("https://map.naver.com/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    print(f"접속 완료. 보완 검색 시작. 대상 키워드 수: {total_keywords}\n")

    checkpoint_interval = 50  # 키워드 50개마다 저장

    with tqdm(total=total_keywords, desc="보완 검색") as pbar:
        processed = 0
        for hub_dict, cat_names_to_collect in targets:
            for cat_name in cat_names_to_collect:
                cat = cat_map[cat_name]
                for keyword in cat["keywords"]:
                    pair_key = f"{hub_dict['name']}|{cat_name}|{keyword}"

                    if pair_key in done_pairs:
                        pbar.update(1)
                        processed += 1
                        continue

                    # 지역명만 추출 (서울_강남 → 강남, 수원_인계동 → 인계동)
                    area = hub_dict["name"].split("_", 1)[1] if "_" in hub_dict["name"] else hub_dict["name"]
                    query = f"{area} {keyword}"
                    places = search_places(page, query, hub_dict["lat"], hub_dict["lng"])

                    new_count = 0
                    for p in places:
                        pid = str(p.get("naver_place_id", ""))
                        if pid and pid not in seen_ids:
                            p["hub"] = hub_dict["name"]
                            p["keyword"] = keyword
                            p["category_group"] = cat_name
                            new_places.append(p)
                            seen_ids.add(pid)
                            new_count += 1

                    done_pairs.add(pair_key)
                    pbar.set_postfix({"신규": new_count, "누적": len(new_places)})
                    pbar.update(1)
                    processed += 1

                    time.sleep(1)

                    if processed % checkpoint_interval == 0:
                        _save_search_checkpoint(done_pairs, new_places)

    page.close()
    _save_search_checkpoint(done_pairs, new_places)
    print(f"\n보완 검색 완료: {len(new_places)}개 신규 장소")
    return new_places


def run_supplement_detail(context, places_data: list) -> None:
    """2단계: 별점+키워드 보강. supplement 전용 체크포인트."""
    already_done: set[str] = set()
    if os.path.exists(SUPPLEMENT_ENRICHED_PATH):
        with open(SUPPLEMENT_ENRICHED_PATH, "r") as f:
            already_done = set(json.load(f))
        print(f"별점/키워드 체크포인트 로드: {len(already_done)}개 기완료")

    remaining = [
        p for p in places_data if p["naver_place_id"] not in already_done
    ]
    print(
        f"별점/키워드 보강: 전체 {len(places_data)}, 기완료 {len(already_done)}, 남은 {len(remaining)}"
    )

    if not remaining:
        print("보강 대상 없음.")
        return

    page = init_detail_page(context)
    success = empty = errors = 0

    for i, p in enumerate(tqdm(remaining, desc="별점/키워드 보강")):
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

        # raw JSON 즉시 저장 (모든 속성 포함)
        raw_path = os.path.join(RAW_DIR, f"{pid}.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)

        if (i + 1) % 100 == 0:
            with open(SUPPLEMENT_ENRICHED_PATH, "w") as f:
                json.dump(list(already_done), f)
            tqdm.write(
                f"  [checkpoint {i+1}] 성공: {success} | 빈값: {empty} | 오류: {errors}"
            )

        if (i + 1) % 200 == 0:
            try:
                page.reload(wait_until="domcontentloaded", timeout=10000)
                page.wait_for_timeout(1500)
            except Exception:
                pass

        # 1000개마다 10분 휴식 (rate-limit 방지)
        if (i + 1) % 1000 == 0:
            with open(SUPPLEMENT_ENRICHED_PATH, "w") as f:
                json.dump(list(already_done), f)
            tqdm.write(f"  [rate-limit 방지 휴식] {i+1}개 완료, 10분 대기 중...")
            time.sleep(600)
            # 페이지 새로 고침으로 세션 갱신
            try:
                page.reload(wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
            except Exception:
                pass
            tqdm.write(f"  [휴식 종료] 재개합니다.")

        time.sleep(1.5)

    with open(SUPPLEMENT_ENRICHED_PATH, "w") as f:
        json.dump(list(already_done), f)

    page.close()
    print(f"보강 완료: {success}/{len(remaining)}, 빈값 {empty}, 오류 {errors}")


def run_supplement_reviews(context, places_data: list, max_reviews: int = 20) -> None:
    """3단계: 리뷰 텍스트 수집. review_count > 0인 장소만 대상."""
    already_done: set[str] = set()
    if os.path.exists(SUPPLEMENT_REVIEWS_PATH):
        with open(SUPPLEMENT_REVIEWS_PATH, "r") as f:
            already_done = set(json.load(f))
        print(f"리뷰 체크포인트 로드: {len(already_done)}개 기완료")

    targets = [
        p
        for p in places_data
        if str(p["naver_place_id"]) not in already_done
        and p.get("review_count", 0) > 0
    ]
    total_with_reviews = sum(1 for p in places_data if p.get("review_count", 0) > 0)
    print(
        f"리뷰 수집: 전체 {len(places_data)}, review>0 {total_with_reviews}, "
        f"기완료 {len(already_done)}, 남은 {len(targets)}"
    )

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

        # raw JSON 갱신 (review_texts 추가)
        raw_path = os.path.join(RAW_DIR, f"{pid}.json")
        if os.path.exists(raw_path):
            try:
                with open(raw_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                existing["review_texts"] = reviews
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 손상된 raw 파일이면 현재 p 기반으로 덮어씀
                existing = p
                existing["review_texts"] = reviews
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        else:
            p["review_texts"] = reviews
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(p, f, ensure_ascii=False, indent=2)

        if (i + 1) % 100 == 0:
            with open(SUPPLEMENT_REVIEWS_PATH, "w") as f:
                json.dump(list(already_done), f)
            tqdm.write(f"  [checkpoint {i+1}] 수집: {collected} | 빈값: {empty}")

        if (i + 1) % 500 == 0:
            try:
                page.reload(wait_until="domcontentloaded", timeout=10000)
                page.wait_for_timeout(1000)
            except Exception:
                pass

        time.sleep(0.8)

    with open(SUPPLEMENT_REVIEWS_PATH, "w") as f:
        json.dump(list(already_done), f)

    page.close()
    print(f"리뷰 수집 완료: {collected}/{len(targets)}, 빈값 {empty}")


def append_to_csv(new_places: list) -> None:
    """신규 장소를 raw JSON과 머지 후 기존 places.csv에 append. 전체 dedup 후 저장.

    기존 CSV는 절대 덮어쓰지 않고 concat 후 naver_place_id 기준 dedup.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    if not new_places:
        print("신규 장소 없음. CSV 업데이트 스킵.")
        return

    # raw JSON에서 최신 보강 데이터 머지
    final_new = []
    for p in new_places:
        pid = str(p.get("naver_place_id", ""))
        if not pid:
            continue
        raw_path = os.path.join(RAW_DIR, f"{pid}.json")
        if os.path.exists(raw_path):
            try:
                with open(raw_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # raw에 보강 데이터 있으면 머지
                if raw.get("keyword_tags") or raw.get("rating", 0) > 0:
                    p["rating"] = raw.get("rating", p.get("rating", 0.0))
                    p["keyword_tags"] = raw.get("keyword_tags", p.get("keyword_tags", []))
                    if raw.get("review_total_verified"):
                        p["review_total_verified"] = raw["review_total_verified"]
                if raw.get("review_texts"):
                    p["review_texts"] = raw["review_texts"]
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # 손상된 raw 파일은 스킵, p 원본 그대로 사용
        final_new.append(p)

    new_df = pd.DataFrame(final_new)

    # 리스트형 컬럼 JSON 직렬화
    for col in ["keyword_tags", "menu_prices", "review_texts"]:
        if col in new_df.columns:
            new_df[col] = new_df[col].apply(
                lambda x: json.dumps(x, ensure_ascii=False)
                if isinstance(x, (list, dict))
                else x
            )

    # 기존 CSV 로드 및 합치기
    if os.path.exists(FINAL_CSV):
        existing_df = pd.read_csv(FINAL_CSV)
        existing_count = len(existing_df)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        existing_count = 0
        combined_df = new_df

    # naver_place_id 기준 dedup: 신규(뒤) 우선 → 재보강 후 최신 raw 데이터가 반영됨
    before = len(combined_df)
    combined_df = combined_df.drop_duplicates(subset="naver_place_id", keep="last")
    dupes = before - len(combined_df)

    # review_count > 0 필터
    if "review_count" in combined_df.columns:
        before_r = len(combined_df)
        combined_df = combined_df[combined_df["review_count"] > 0]
        removed_no_review = before_r - len(combined_df)
        if removed_no_review > 0:
            print(f"리뷰 0개 제거: {before_r} → {len(combined_df)}곳 ({removed_no_review}개 제거)")

    combined_df.to_csv(FINAL_CSV, index=False, encoding="utf-8-sig")
    print(
        f"CSV append 완료: 기존 {existing_count} + 신규 {len(new_df)} → "
        f"dedup 후 {len(combined_df)}곳 (중복 {dupes}개 제거)"
    )


def main():
    parser = argparse.ArgumentParser(description="보완 크롤러 (누락/편향 허브 append 수집)")
    parser.add_argument("--headless", action="store_true", help="headless 모드")
    parser.add_argument(
        "--detail-only",
        action="store_true",
        help="별점/키워드 보강만 (supplement_place_ids.json 대상)",
    )
    parser.add_argument(
        "--review-only", action="store_true", help="리뷰 수집만"
    )
    parser.add_argument(
        "--skip-detail", action="store_true", help="검색만, 상세 스킵"
    )
    parser.add_argument(
        "--skip-review", action="store_true", help="리뷰 수집 스킵"
    )
    parser.add_argument(
        "--max-reviews", type=int, default=20, help="장소당 최대 리뷰 수 (기본 20)"
    )
    args = parser.parse_args()

    os.makedirs(PLACE_IDS_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    # ── 기존 CSV에서 seen_ids 로드 (재수집 방지) ──────────────────────────────
    seen_ids: set[str] = set()
    if os.path.exists(FINAL_CSV):
        existing_df = pd.read_csv(FINAL_CSV)
        seen_ids = set(existing_df["naver_place_id"].dropna().astype(str))
        print(f"기존 places.csv 로드: {len(seen_ids)}개 장소 (재수집 방지)")

    # ── 대상 허브×카테고리 계산 ───────────────────────────────────────────────
    targets = get_targets()
    total_hubs = len(targets)
    total_combos = sum(len(cats) for _, cats in targets)
    total_keywords = sum(
        len(next(c for c in CATEGORIES if c["name"] == cat_name)["keywords"])
        for _, cats in targets
        for cat_name in cats
    )
    print(
        f"\n수집 대상: {total_hubs}개 허브, {total_combos}개 허브×카테고리 조합, "
        f"약 {total_keywords}개 키워드\n"
    )

    with sync_playwright() as pw:
        context = create_browser_context(pw, headless=args.headless)

        if args.review_only or args.detail_only:
            # 기수집 supplement 데이터 로드
            if not os.path.exists(SUPPLEMENT_IDS_PATH):
                print(f"오류: {SUPPLEMENT_IDS_PATH} 없음. 먼저 검색 단계를 실행하세요.")
                return
            with open(SUPPLEMENT_IDS_PATH, "r", encoding="utf-8") as f:
                places = json.load(f)
            print(f"기존 supplement 데이터 로드: {len(places)}곳")
        else:
            # 1단계: 검색
            places = run_supplement_search(context, targets, seen_ids)

        if not args.skip_detail and not args.review_only:
            # 2단계: 별점+키워드 보강
            run_supplement_detail(context, places)

        if not args.skip_review and not args.detail_only:
            # 3단계: 리뷰 수집
            run_supplement_reviews(context, places, max_reviews=args.max_reviews)

        context.browser.close()

    # ── 기존 CSV에 append ──────────────────────────────────────────────────────
    append_to_csv(places)

    print("\n" + "=" * 60)
    print("보완 크롤링 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
