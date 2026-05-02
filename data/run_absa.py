"""ABSA 속성 추출 실행 스크립트

사용법:
  python run_absa.py           # 전체 실행
  python run_absa.py --test    # 샘플 테스트
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
    parser = argparse.ArgumentParser(description="ABSA 속성 추출")
    parser.add_argument("--test", action="store_true", help="샘플 테스트")
    args = parser.parse_args()

    from preprocessing.morpheme import extract_morphemes
    from preprocessing.negation import detect_negation
    from preprocessing.absa import extract_absa_scores

    if args.test:
        tests = [
            "음식이 정말 맛있고 분위기도 좋아요 직원도 친절합니다",
            "맛은 괜찮은데 가격이 너무 비싸요",
            "서비스가 별로였어요 음식은 맛있었는데 직원이 불친절해요",
            "조용하고 깔끔한 카페 가성비도 좋고 추천합니다",
            "맛없고 비싸고 좁아요 최악",
            "분위기는 예쁜데 음식이 밍밍해요",
        ]
        print("=== ABSA 속성 추출 테스트 ===\n")
        for text in tests:
            morphemes = extract_morphemes(text)
            morphemes_neg = detect_negation(morphemes)
            scores = extract_absa_scores(morphemes_neg)

            print(f"원문: {text}")
            for asp, score in scores.items():
                if score is not None:
                    bar = "+" * int(abs(score) * 5) if score >= 0 else "-" * int(abs(score) * 5)
                    print(f"  {asp:5s}: {score:+.2f} {bar}")
                else:
                    print(f"  {asp:5s}: (미언급)")
            print()
        return

    from preprocessing.absa import process_all_absa

    start = time.time()
    stats = process_all_absa()
    elapsed = time.time() - start

    print("\n" + "=" * 50)
    print(f"ABSA 속성 추출 완료 ({elapsed:.0f}초)")
    print(f"  장소: {stats['places']}곳")
    print(f"  리뷰: {stats['reviews']}건 (반어법 제외 {stats['sarcasm_excluded']}건)")
    print(f"  활성 장소 (3건+ 리뷰):")
    print(f"    food: {stats['active_food']}곳")
    print(f"    mood: {stats['active_mood']}곳")
    print(f"    svc:  {stats['active_svc']}곳")
    print(f"    price: {stats['active_price']}곳")
    print(f"  저장: {stats['output_path']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
