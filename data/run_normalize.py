"""노이즈 정규화 실행 스크립트

사용법:
  python run_normalize.py                    # 전체 실행 (띄어쓰기 교정 포함)
  python run_normalize.py --no-spacing       # 띄어쓰기 교정 스킵 (빠름)
  python run_normalize.py --test             # 5곳만 테스트
  python run_normalize.py --min-length 5     # 최소 길이 변경 (기본 10)
"""

import argparse
import json
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="리뷰 노이즈 정규화")
    parser.add_argument("--no-spacing", action="store_true", help="띄어쓰기 교정 스킵")
    parser.add_argument("--test", action="store_true", help="5곳만 테스트")
    parser.add_argument("--min-length", type=int, default=10, help="최소 리뷰 길이 (기본 10)")
    args = parser.parse_args()

    from preprocessing.normalize import (
        normalize_review,
        process_all_reviews,
    )

    if args.test:
        # 테스트 모드: 샘플 리뷰로 정규화 확인
        test_reviews = [
            "맛있어요ㅋㅋㅋㅋㅋ 분위기도 좋고요!!!",
            "진짜진짜진짜 맛있었어요ㅠㅠㅠㅠ",
            "가성비최고 메뉴도다양하고 직원분도친절해요",
            "ㅎ",
            "좋아요",
            "분위기가너무좋아서데이트하기딱이에요음식도맛있고서비스도좋았어요",
            "별로였어요\n맛도 그냥그렇고\n가격만 비싸요",
        ]
        print("=== 노이즈 정규화 테스트 ===\n")
        for raw in test_reviews:
            norm = normalize_review(raw, use_spacing=not args.no_spacing)
            status = "유지" if len(norm) >= args.min_length else "필터"
            print(f"[{status}] ({len(raw):>3}→{len(norm):>3}자)")
            print(f"  원본: {raw}")
            print(f"  정규: {norm}\n")
        return

    # 전체 실행
    start = time.time()
    stats = process_all_reviews(
        raw_dir="output/raw",
        output_path="output/preprocessed/normalized_reviews.json",
        min_length=args.min_length,
        use_spacing=not args.no_spacing,
    )
    elapsed = time.time() - start

    print("\n" + "=" * 50)
    print(f"노이즈 정규화 완료 ({elapsed:.0f}초)")
    print(f"  장소: {stats['places']}곳")
    print(f"  리뷰: {stats['raw_reviews']} → {stats['kept_reviews']}건")
    print(f"  필터: {stats['filtered']}건 ({args.min_length}자 미만)")
    print(f"  저장: {stats['output_path']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
