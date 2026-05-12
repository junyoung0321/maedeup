"""감성 피쳐 4개 제외 재학습 — NDCG@10 비교

baseline (model_v2.pkl, 17피쳐): 0.9073
이 스크립트: 13피쳐로 Optuna 50회 재학습 후 비교
"""

import json
import logging
import os
import pickle
import time

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SPLIT_DIR = "output/training"
MODEL_DIR = "output/training/models"

FEATURE_COLS_NO_SENTIMENT = [
    "rating_norm", "review_count_log", "blog_count_log",
    "mood_quiet", "mood_private",
    "category_depth2",
    "avg_distance_km", "max_distance_km", "fairness_score",
    "category_match", "mood_match_count", "hour_suitability", "near_station",
]

CAT_FEATURES = ["category_depth2"]
LABEL_COL = "relevance"
GROUP_COL = "scenario_id"
BASELINE_NDCG = 0.9073


def _make_groups(df):
    return df.groupby(GROUP_COL, sort=False).size().values


def evaluate_scenarios(df, scores, k=10):
    from sklearn.metrics import ndcg_score
    df = df.copy()
    df["_score"] = scores
    ndcgs = []
    for _, grp in df.groupby(GROUP_COL, sort=False):
        if grp[LABEL_COL].max() == 0:
            continue
        try:
            n = float(ndcg_score([grp[LABEL_COL].values], [grp["_score"].values], k=k))
            ndcgs.append(n)
        except Exception:
            pass
    return float(np.mean(ndcgs)) if ndcgs else 0.0, len(ndcgs)


def run():
    import lightgbm as lgb
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    os.makedirs(MODEL_DIR, exist_ok=True)

    train_df = pd.read_csv(os.path.join(SPLIT_DIR, "train.csv"))
    val_df = pd.read_csv(os.path.join(SPLIT_DIR, "val.csv"))
    test_df = pd.read_csv(os.path.join(SPLIT_DIR, "test.csv"))

    X_train = train_df[FEATURE_COLS_NO_SENTIMENT].values
    y_train = train_df[LABEL_COL].values
    g_train = _make_groups(train_df)

    X_val = val_df[FEATURE_COLS_NO_SENTIMENT].values
    y_val = val_df[LABEL_COL].values
    g_val = _make_groups(val_df)

    X_test = test_df[FEATURE_COLS_NO_SENTIMENT].values

    def objective(trial):
        params = {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [10],
            "n_estimators": trial.suggest_int("n_estimators", 100, 400),
            "num_leaves": trial.suggest_int("num_leaves", 15, 63),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 50),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "random_state": 42,
            "verbose": -1,
        }
        model = lgb.LGBMRanker(**params)
        model.fit(
            X_train, y_train, group=g_train,
            eval_set=[(X_val, y_val)], eval_group=[g_val],
            eval_at=[10],
            feature_name=FEATURE_COLS_NO_SENTIMENT,
            categorical_feature=CAT_FEATURES,
            callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(-1)],
        )
        val_scores = model.predict(X_val)
        ndcg, _ = evaluate_scenarios(val_df, val_scores)
        return ndcg

    logger.info("Optuna 50회 튜닝 시작...")
    t0 = time.time()
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=50, show_progress_bar=True)
    elapsed = time.time() - t0
    logger.info(f"튜닝 완료 ({elapsed:.1f}s), best val NDCG@10={study.best_value:.4f}")

    # 최적 파라미터로 train+val 합쳐 재학습
    best_params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [10],
        "random_state": 42,
        "verbose": -1,
        **study.best_params,
    }
    fit_df = pd.concat([train_df, val_df], ignore_index=True)
    X_fit = fit_df[FEATURE_COLS_NO_SENTIMENT].values
    y_fit = fit_df[LABEL_COL].values
    g_fit = _make_groups(fit_df)

    final_model = lgb.LGBMRanker(**best_params)
    final_model.fit(X_fit, y_fit, group=g_fit,
                    feature_name=FEATURE_COLS_NO_SENTIMENT,
                    categorical_feature=CAT_FEATURES)

    test_scores = final_model.predict(X_test)
    ndcg_new, n_scen = evaluate_scenarios(test_df, test_scores)

    # Feature importance
    fi = dict(zip(FEATURE_COLS_NO_SENTIMENT, final_model.feature_importances_))
    total_gain = sum(fi.values())

    print("\n" + "=" * 55)
    print("재학습 결과 (감성 피쳐 제외, 13개)")
    print("=" * 55)
    print(f"\nbaseline (17피쳐)  NDCG@10 = {BASELINE_NDCG:.4f}")
    print(f"재학습  (13피쳐)  NDCG@10 = {ndcg_new:.4f}  (delta = {ndcg_new - BASELINE_NDCG:+.4f})")
    print(f"평가 시나리오 수: {n_scen}")
    print(f"\nOptuna best val NDCG@10: {study.best_value:.4f}")
    print(f"best params: {study.best_params}")

    print("\nFeature Importance (13개):")
    for col, g in sorted(fi.items(), key=lambda x: -x[1]):
        print(f"  {col:<22} {g:>6}  ({g/total_gain*100:.1f}%)")

    print("\n" + "=" * 55)
    delta = ndcg_new - BASELINE_NDCG
    if delta >= -0.005:
        print("판정: 감성 피쳐 제거 후에도 성능 유지 → 제거 확정 권장")
    elif delta >= -0.02:
        print("판정: 소폭 하락 — 커버리지 이득 고려 시 제거 허용 가능")
    else:
        print("판정: 유의미한 성능 하락 → 감성 피쳐 유지 재고")

    # 모델 저장
    model_path = os.path.join(MODEL_DIR, "model_v2_no_sentiment.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(final_model, f)
    logger.info(f"\n모델 저장: {model_path}")

    results = {
        "baseline_ndcg": BASELINE_NDCG,
        "new_ndcg": ndcg_new,
        "delta": ndcg_new - BASELINE_NDCG,
        "feature_cols": FEATURE_COLS_NO_SENTIMENT,
        "optuna_best_val": study.best_value,
        "best_params": study.best_params,
        "feature_importance": fi,
    }
    with open(os.path.join(MODEL_DIR, "ablation_no_sentiment.json"), "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    run()
