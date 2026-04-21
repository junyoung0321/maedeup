"""형태소 분석 실행 스크립트

사용법:
  python run_morpheme.py           # 전체 실행
  python run_morpheme.py --test    # 샘플 테스트
"""

import argparse
import json
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="형태소 분석")
    parser.add_argument("--test", action="store_true", help="샘플 테스트")
    args = parser.parse_args()

    from preprocessing.morpheme import extract_morphemes, process_all_morphemes

    if args.test:
        test_reviews = [
            "맛있는 카페에서 커피를 마셨다 분위기도 조용하고 가성비 좋아요",
            "직원이 너무 불친절해서 별로였어요 음식은 그냥 그랬고",
            "진짜 추천합니다 룸도 있고 단체모임하기 딱이에요",
            "가격 대비 양이 적어서 가성비가 별로",
            "조용한 분위기에서 공부하기 좋은 스터디카페",
        ]
        print("=== 형태소 분석 테스트 ===\n")
        for text in test_reviews:
            morphemes = extract_morphemes(text)
            forms = [f"{m['form']}({m['tag']})" for m in morphemes]
            print(f"원문: {text}")
            print(f"형태소: {' '.join(forms)}\n")
        return

    start = time.time()
    stats = process_all_morphemes()
    elapsed = time.time() - start

    print("\n" + "=" * 50)
    print(f"형태소 분석 완료 ({elapsed:.0f}초)")
    print(f"  장소: {stats['places']}곳")
    print(f"  리뷰: {stats['reviews']}건")
    print(f"  형태소: {stats['morphemes']}개 (리뷰당 {stats['avg_per_review']}개)")
    print(f"  저장: {stats['output_path']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
