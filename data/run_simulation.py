"""시나리오 시뮬레이션 + Pseudo-label 생성 실행

사용법:
  python run_simulation.py                # 전체 (4000 시나리오)
  python run_simulation.py --test         # 10 시나리오 테스트
  python run_simulation.py -n 1000       # 1000 시나리오
"""

import argparse
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="시나리오 시뮬레이션")
    parser.add_argument("--test", action="store_true", help="10 시나리오 테스트")
    parser.add_argument("-n", type=int, default=4000, help="시나리오 수 (기본 4000)")
    args = parser.parse_args()

    from simulation.simulate import run_simulation

    n = 10 if args.test else args.n

    start = time.time()
    stats = run_simulation(n_scenarios=n)
    elapsed = time.time() - start

    print("\n" + "=" * 50)
    print(f"시뮬레이션 완료 ({elapsed:.1f}초)")
    print(f"  시나리오: {stats['scenarios']}개")
    print(f"  Query-Doc Pairs: {stats['pairs']}개")
    print(f"  빈 시나리오: {stats['empty_scenarios']}개")
    print(f"  Relevance 분포:")
    for score, count in sorted(stats["relevance_dist"].items()):
        pct = count / stats["pairs"] * 100
        bar = "#" * int(pct / 2)
        print(f"    {score}: {count:>6} ({pct:5.1f}%) {bar}")
    print(f"  저장: {stats['output_path']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
