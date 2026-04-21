"""반어법·부정 탐지 실행 스크립트

사용법:
  python run_sarcasm.py           # 전체 실행
  python run_sarcasm.py --test    # 샘플 테스트
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
    parser = argparse.ArgumentParser(description="반어법·부정 탐지")
    parser.add_argument("--test", action="store_true", help="샘플 테스트")
    args = parser.parse_args()

    from preprocessing.negation import detect_negation, get_negation_summary
    from preprocessing.morpheme import extract_morphemes
    from preprocessing.sarcasm import detect_sarcasm

    if args.test:
        tests = [
            "맛있어요 분위기도 좋고 추천합니다",
            "별로였어요 맛도 없고 비싸요",
            "맛있다고 해서 갔는데 완전 실망이에요",
            "와 진짜 맛있네요 다신 안 갈듯",
            "음식은 괜찮은데 서비스가 안 좋아요",
            "분위기는 좋은데 맛은 별로",
        ]
        print("=== 반어법·부정 탐지 테스트 ===\n")
        for text in tests:
            morphemes = extract_morphemes(text)

            # 부정 탐지
            morphemes_neg = detect_negation(morphemes)
            neg = get_negation_summary(morphemes_neg)

            # 반어법 탐지
            sarc = detect_sarcasm(text, morphemes)

            print(f"원문: {text}")
            print(f"  문장감성: {sarc['sentence_label']} ({sarc['sentence_confidence']:.3f})")
            print(f"  토큰감성: {sarc['token_sentiment']}")
            if neg["has_negation"]:
                print(f"  부정어: {neg['negation_words']} → 대상: {neg['negated_targets']}")
            print(f"  반어점수: {sarc['sarcasm_score']:.3f} {'⚠ 반어법' if sarc['is_sarcastic'] else ''}")
            print()
        return

    from preprocessing.sarcasm import process_all_sarcasm

    start = time.time()
    stats = process_all_sarcasm()
    elapsed = time.time() - start

    print("\n" + "=" * 50)
    print(f"반어법·부정 탐지 완료 ({elapsed:.0f}초)")
    print(f"  장소: {stats['places']}곳")
    print(f"  리뷰: {stats['reviews']}건")
    print(f"  반어법: {stats['sarcastic']}건 ({stats['sarcastic_pct']}%)")
    print(f"  부정: {stats['negated']}건 ({stats['negated_pct']}%)")
    print(f"  저장: {stats['output_path']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
