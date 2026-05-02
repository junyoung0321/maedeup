"""기존 raw 파일에 review_texts 추가 (review_texts 없는 장소만 처리)

run_search.py + run_detail.py 경로로 수집된 장소들은 review_texts가 없음.
이 스크립트는 review_count > 0이지만 review_texts가 없는 raw 파일에
getVisitorReviews GraphQL로 텍스트를 수집하여 업데이트.

사용법:
  python run_add_reviews.py                    # 전체 (약 3,000개)
  python run_add_reviews.py --test 20          # 20개만 테스트
  python run_add_reviews.py --max-reviews 20  # 장소당 최대 리뷰 수 (기본 20)
  python run_add_reviews.py --headless         # headless 모드
"""

import argparse
import json
import os
import time
import logging
from playwright.sync_api import sync_playwright
from tqdm import tqdm

from config import RAW_DIR
from crawler.browser import create_browser_context, init_detail_page, fetch_review_texts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

CHECKPOINT_PATH = "output/place_ids/add_reviews_checkpoint.json"


def load_checkpoint() -> set[str]:
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_checkpoint(done: set[str]):
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(list(done), f)


def find_targets(limit: int = 0) -> list[str]:
    """review_texts 없고 review_count > 0인 raw 파일 pid 목록."""
    targets = []
    for fname in os.listdir(RAW_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(RAW_DIR, fname)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if not d.get("review_texts") and d.get("review_count", 0) > 0:
            targets.append(fname.replace(".json", ""))
        if limit and len(targets) >= limit:
            break
    return targets


def main():
    parser = argparse.ArgumentParser(description="기존 raw 파일에 review_texts 추가")
    parser.add_argument("--test", type=int, default=0, metavar="N", help="N개만 처리")
    parser.add_argument("--max-reviews", type=int, default=20, help="장소당 최대 리뷰 수 (기본 20)")
    parser.add_argument("--headless", action="store_true", help="headless 모드")
    args = parser.parse_args()

    targets = find_targets(limit=args.test)
    done = load_checkpoint()

    todo = [pid for pid in targets if pid not in done]
    logger.info(f"대상: {len(targets)}개 | 기처리: {len(done)}개 | 잔여: {len(todo)}개")

    if not todo:
        print("처리할 장소 없음.")
        return

    saved = 0
    skipped_empty = 0

    with sync_playwright() as pw:
        ctx = create_browser_context(pw, headless=args.headless)
        page = init_detail_page(ctx)
        page.set_default_timeout(30000)

        with tqdm(total=len(todo), desc="리뷰 텍스트 추가") as pbar:
            for pid in todo:
                path = os.path.join(RAW_DIR, f"{pid}.json")
                try:
                    reviews = fetch_review_texts(page, pid, max_reviews=args.max_reviews)
                except Exception as e:
                    logger.warning(f"[오류] {pid}: {e}")
                    done.add(pid)
                    pbar.update(1)
                    continue

                done.add(pid)

                if not reviews:
                    skipped_empty += 1
                    pbar.update(1)
                    time.sleep(0.3)
                    continue

                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                data["review_texts"] = reviews
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                saved += 1
                pbar.set_postfix({"저장": saved, "빈리뷰": skipped_empty})
                pbar.update(1)

                if saved % 200 == 0:
                    save_checkpoint(done)

                time.sleep(0.5)

        ctx.browser.close()

    save_checkpoint(done)
    print(f"\n완료: 추가 {saved}개 | 리뷰 없음(스킵) {skipped_empty}개")


if __name__ == "__main__":
    main()
