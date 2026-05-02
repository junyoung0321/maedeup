"""STEP 6. LGBMRanker 학습

v1:   가중합 스코어링 (baseline, ML 없음)
v1_5: LGBMRanker 소규모 (trees=50, Train/Test 2분할)
v2:   LGBMRanker 풀 (trees=200, Optuna 100회, Train/Val/Test 3분할)

출력: output/training/models/
  model_v1_scoring.json    (가중치 dict)
  model_v1_5.pkl
  model_v2.pkl
  metrics.json
"""

import json
import logging
import os
import pickle
import time

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    # 고정 12개
    "rating_norm", "review_count_log", "blog_count_log", "price_level",
    "mood_quiet", "mood_group", "mood_vibe", "mood_budget", "mood_private",
    "is_chain", "category_depth1", "category_depth2",
    # 시나리오 의존 8개
    "avg_distance_km", "max_distance_km", "fairness_score",
    "category_match", "mood_match_count", "price_match",
    "hour_suitability", "near_station",
    # 감성 4개
    "food_sentiment", "mood_sentiment", "svc_sentiment", "price_sentiment",
    # 긍부정 2개
    "sentiment_confidence", "label_score",
]

LABEL_COL = "relevance"
GROUP_COL = "scenario_id"


def _load_split(split_dir: str, split: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(split_dir, f"{split}.csv"))


def _make_groups(df: pd.DataFrame) -> np.ndarray:
    """scenario_id 기준 group sizes (LGBMRanker 입력용)."""
    return df.groupby(GROUP_COL, sort=False).size().values


def _ndcg_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int = 10) -> float:
    """Scenario 단위 NDCG@k 평균."""
    from sklearn.metrics import ndcg_score
    return float(ndcg_score([y_true], [y_score], k=k))


def evaluate_scenarios(df: pd.DataFrame, scores: np.ndarray, k: int = 10) -> dict:
    """시나리오 단위 NDCG@k 평균."""
    df = df.copy()
    df["_score"] = scores
    ndcgs = []
    for _, grp in df.groupby(GROUP_COL, sort=False):
        if grp[LABEL_COL].max() == 0:
            continue
        try:
            from sklearn.metrics import ndcg_score
            n = float(ndcg_score([grp[LABEL_COL].values], [grp["_score"].values], k=k))
            ndcgs.append(n)
        except Exception:
            pass
    return {"ndcg_at_10": float(np.mean(ndcgs)) if ndcgs else 0.0, "n_scenarios": len(ndcgs)}


# ── v1: 가중합 스코어링 ──────────────────────────────────────────────────────
V1_WEIGHTS = {
    "rating_norm":       0.20,
    "fairness_score":    0.15,
    "avg_distance_km":   -0.15,   # 거리 역방향
    "review_count_log":  0.10,
    "category_match":    0.15,
    "mood_match_count":  0.10,
    "food_sentiment":    0.05,
    "mood_sentiment":    0.05,
    "price_match":       0.05,
}


def train_v1(
    split_dir: str = "output/training",
    model_dir: str = "output/training/models",
) -> dict:
    """v1: 가중합 scoring — 학습 없음."""
    os.makedirs(model_dir, exist_ok=True)

    test_df = _load_split(split_dir, "test")
    scores = sum(test_df[col] * w for col, w in V1_WEIGHTS.items() if col in test_df.columns)
    metrics = evaluate_scenarios(test_df, scores.values)

    # 가중치 저장
    with open(os.path.join(model_dir, "model_v1_scoring.json"), "w") as f:
        json.dump(V1_WEIGHTS, f, indent=2)

    logger.info(f"v1 NDCG@10={metrics['ndcg_at_10']:.4f} ({metrics['n_scenarios']} 시나리오)")
    return {"version": "v1", **metrics}


# ── v1.5: LGBMRanker 소규모 ───────────────────────────────────────────────────
def train_v1_5(
    split_dir: str = "output/training",
    model_dir: str = "output/training/models",
) -> dict:
    """v1.5: LGBMRanker (train+val 합쳐서 학습, test 평가)."""
    import lightgbm as lgb

    os.makedirs(model_dir, exist_ok=True)

    train_df = _load_split(split_dir, "train")
    val_df = _load_split(split_dir, "val")
    test_df = _load_split(split_dir, "test")

    # train+val → 학습
    fit_df = pd.concat([train_df, val_df], ignore_index=True)
    X_fit = fit_df[FEATURE_COLS].values
    y_fit = fit_df[LABEL_COL].values
    g_fit = _make_groups(fit_df)

    X_test = test_df[FEATURE_COLS].values
    y_test = test_df[LABEL_COL].values

    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [10],
        "n_estimators": 50,
        "num_leaves": 31,
        "learning_rate": 0.1,
        "min_child_samples": 20,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
        "verbose": -1,
    }

    model = lgb.LGBMRanker(**params)
    t0 = time.time()
    model.fit(X_fit, y_fit, group=g_fit, feature_name=FEATURE_COLS)
    logger.info(f"v1.5 학습 완료 ({time.time()-t0:.1f}s)")

    test_scores = model.predict(X_test)
    metrics = evaluate_scenarios(test_df, test_scores)

    # Feature importance
    fi = dict(zip(FEATURE_COLS, model.feature_importances_))
    top_features = sorted(fi.items(), key=lambda x: -x[1])[:10]
    logger.info(f"Top features: {top_features[:5]}")

    # 저장
    with open(os.path.join(model_dir, "model_v1_5.pkl"), "wb") as f:
        pickle.dump(model, f)

    logger.info(f"v1.5 NDCG@10={metrics['ndcg_at_10']:.4f} ({metrics['n_scenarios']} 시나리오)")
    return {"version": "v1_5", **metrics, "feature_importance": fi}


# ── v2: LGBMRanker + Optuna ───────────────────────────────────────────────────
def train_v2(
    split_dir: str = "output/training",
    model_dir: str = "output/training/models",
    n_trials: int = 100,
) -> dict:
    """v2: LGBMRanker + Optuna 하이퍼파라미터 튜닝."""
    import lightgbm as lgb
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    os.makedirs(model_dir, exist_ok=True)

    train_df = _load_split(split_dir, "train")
    val_df = _load_split(split_dir, "val")
    test_df = _load_split(split_dir, "test")

    X_train = train_df[FEATURE_COLS].values
    y_train = train_df[LABEL_COL].values
    g_train = _make_groups(train_df)

    X_val = val_df[FEATURE_COLS].values
    y_val = val_df[LABEL_COL].values
    g_val = _make_groups(val_df)

    X_test = test_df[FEATURE_COLS].values

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
            callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(-1)],
        )
        val_scores = model.predict(X_val)
        m = evaluate_scenarios(val_df, val_scores)
        return m["ndcg_at_10"]

    logger.info(f"Optuna 튜닝 시작 ({n_trials} trials)...")
    t0 = time.time()
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    logger.info(f"튜닝 완료 ({time.time()-t0:.1f}s), best NDCG@10={study.best_value:.4f}")

    # 최적 파라미터로 재학습
    best_params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [10],
        "random_state": 42,
        "verbose": -1,
        **study.best_params,
    }

    # train+val 합쳐서 최종 학습
    fit_df = pd.concat([train_df, val_df], ignore_index=True)
    X_fit = fit_df[FEATURE_COLS].values
    y_fit = fit_df[LABEL_COL].values
    g_fit = _make_groups(fit_df)

    final_model = lgb.LGBMRanker(**best_params)
    final_model.fit(X_fit, y_fit, group=g_fit, feature_name=FEATURE_COLS)

    # Test 평가
    test_scores = final_model.predict(X_test)
    metrics = evaluate_scenarios(test_df, test_scores)

    # Feature importance
    fi = dict(zip(FEATURE_COLS, final_model.feature_importances_))
    top_features = sorted(fi.items(), key=lambda x: -x[1])[:10]
    logger.info(f"Top features: {top_features[:5]}")

    # 저장
    with open(os.path.join(model_dir, "model_v2.pkl"), "wb") as f:
        pickle.dump(final_model, f)

    optuna_results = {
        "best_value": study.best_value,
        "best_params": study.best_params,
        "n_trials": n_trials,
    }
    with open(os.path.join(model_dir, "optuna_v2.json"), "w") as f:
        json.dump(optuna_results, f, indent=2)

    logger.info(f"v2 NDCG@10={metrics['ndcg_at_10']:.4f} ({metrics['n_scenarios']} 시나리오)")
    return {"version": "v2", **metrics, "optuna": optuna_results, "feature_importance": fi}


def save_metrics(results: list[dict], model_dir: str = "output/training/models"):
    os.makedirs(model_dir, exist_ok=True)
    with open(os.path.join(model_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=lambda x: float(x) if isinstance(x, (np.floating, np.integer)) else x)
    logger.info(f"메트릭 저장: {model_dir}/metrics.json")
