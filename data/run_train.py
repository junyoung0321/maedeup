"""STEP 5~6. 데이터 분할 + LGBMRanker 학습 실행

사용법:
  python run_train.py              # 분할 + v1 + v1.5 + v2 (기본)
  python run_train.py --version v1_5   # 특정 버전만
  python run_train.py --skip-split     # 분할 스킵 (기존 split 재사용)
  python run_train.py --trials 50      # Optuna trial 수 (v2)
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
    parser = argparse.ArgumentParser(description="LGBMRanker 학습")
    parser.add_argument("--version", choices=["v1", "v1_5", "v2", "all"], default="all")
    parser.add_argument("--skip-split", action="store_true", help="데이터 분할 스킵")
    parser.add_argument("--trials", type=int, default=100, help="Optuna trials (v2)")
    args = parser.parse_args()

    SPLIT_DIR = "output/training"
    MODEL_DIR = "output/training/models"

    all_results = []

    # ── STEP 5: 데이터 분할 ──
    if not args.skip_split:
        from training.split import split_by_hub
        print("\n[STEP 5] Hub 기반 데이터 분할")
        t0 = time.time()
        meta = split_by_hub()
        print(f"  완료 ({time.time()-t0:.1f}s)")
        print(f"  train: {meta['split_counts']['train']} pairs ({meta['scenario_counts']['train']} 시나리오)")
        print(f"  val:   {meta['split_counts']['val']} pairs ({meta['scenario_counts']['val']} 시나리오)")
        print(f"  test:  {meta['split_counts']['test']} pairs ({meta['scenario_counts']['test']} 시나리오)")
    else:
        print("[STEP 5] 데이터 분할 스킵 (기존 파일 사용)")

    # ── STEP 6: 학습 ──
    from training.train import train_v1, train_v1_5, train_v2, save_metrics

    versions = ["v1", "v1_5", "v2"] if args.version == "all" else [args.version]

    for version in versions:
        print(f"\n[STEP 6] {version} 학습")
        t0 = time.time()
        try:
            if version == "v1":
                result = train_v1(SPLIT_DIR, MODEL_DIR)
            elif version == "v1_5":
                result = train_v1_5(SPLIT_DIR, MODEL_DIR)
            elif version == "v2":
                result = train_v2(SPLIT_DIR, MODEL_DIR, n_trials=args.trials)
        except Exception as e:
            print(f"  [{version}] 오류: {e}")
            raise
        elapsed = time.time() - t0
        all_results.append(result)

        print(f"  완료 ({elapsed:.1f}s)")
        print(f"  NDCG@10 = {result['ndcg_at_10']:.4f}")
        if version == "v2" and "optuna" in result:
            print(f"  Optuna best = {result['optuna']['best_value']:.4f}")
            print(f"  Best params: {result['optuna']['best_params']}")

    save_metrics(all_results, MODEL_DIR)

    print("\n" + "=" * 50)
    print("학습 결과 요약")
    for r in all_results:
        fi = r.get("feature_importance", {})
        top3 = sorted(fi.items(), key=lambda x: -x[1])[:3] if fi else []
        top3_str = ", ".join(f"{k}({v})" for k, v in top3) if top3 else "-"
        print(f"  {r['version']}: NDCG@10={r['ndcg_at_10']:.4f}  top3={top3_str}")
    print(f"  모델 저장: {MODEL_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    main()
