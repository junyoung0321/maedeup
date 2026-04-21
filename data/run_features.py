"""Feature 가공 실행 스크립트

사용법:
  python run_features.py
"""

import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def main():
    from preprocessing.features import compute_place_features

    start = time.time()
    stats = compute_place_features()
    elapsed = time.time() - start

    print("\n" + "=" * 50)
    print(f"Feature 가공 완료 ({elapsed:.1f}초)")
    print(f"  장소: {stats['places']}곳")
    print(f"  Feature: {stats['features']}개 (고정12 + 감성4)")
    print(f"  감성 활성: {stats['sentiment_active']}곳")
    print(f"  프랜차이즈: {stats['chain_count']}곳")
    print(f"  저장: {stats['output_path']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
