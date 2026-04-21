"""긍부정 레이블링 실행 스크립트

사용법:
  python run_sentiment_label.py
"""

import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def main():
    from preprocessing.sentiment_label import process_all_sentiment_labels

    start = time.time()
    stats = process_all_sentiment_labels()
    elapsed = time.time() - start

    total = stats["places"]
    print("\n" + "=" * 50)
    print(f"긍부정 레이블링 완료 ({elapsed:.1f}초)")
    print(f"  장소: {total}곳")
    print(f"  strong  (일치): {stats['strong']}곳 ({100*stats['strong']/total:.1f}%)")
    print(f"  conflict(상충): {stats['conflict']}곳 ({100*stats['conflict']/total:.1f}%)")
    print(f"  neutral (중립): {stats['neutral']}곳 ({100*stats['neutral']/total:.1f}%)")
    print(f"  unknown (평점없음): {stats['unknown']}곳 ({100*stats['unknown']/total:.1f}%)")
    print(f"  저장: {stats['output_path']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
