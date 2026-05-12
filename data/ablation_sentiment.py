"""Ablation: 감성 피쳐 4개 제거 시 NDCG@10 영향 측정

기존 model_v2.pkl을 그대로 사용하되, 서빙 상황 3가지를 시뮬레이션:
  A. 전체 피쳐 그대로 (baseline)
  B. 감성 4개 → 0.5 고정 (현재 serving fallback 값)
  C. 감성 4개 → 0.0 고정 (중립 기준)

실제 서빙에서 임의 카카오 장소를 사용할 때 감성 피쳐 손실이
NDCG에 얼마나 영향을 주는지 측정.
"""

import os
import pickle

import numpy as np
import pandas as pd
from sklearn.metrics import ndcg_score

SPLIT_DIR = "output/training"
MODEL_PATH = "output/training/models/model_v2.pkl"

FEATURE_COLS = [
    "rating_norm", "review_count_log", "blog_count_log",
    "mood_quiet", "mood_private",
    "category_depth2",
    "avg_distance_km", "max_distance_km", "fairness_score",
    "category_match", "mood_match_count", "hour_suitability", "near_station",
    "food_sentiment", "mood_sentiment", "svc_sentiment", "price_sentiment",
]

SENTIMENT_COLS = ["food_sentiment", "mood_sentiment", "svc_sentiment", "price_sentiment"]
LABEL_COL = "relevance"
GROUP_COL = "scenario_id"


def evaluate_scenarios(df: pd.DataFrame, scores: np.ndarray, k: int = 10) -> float:
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
    return float(np.mean(ndcgs)) if ndcgs else 0.0


def run():
    test_df = pd.read_csv(os.path.join(SPLIT_DIR, "test.csv"))

    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    # A. baseline
    X_a = test_df[FEATURE_COLS].values
    scores_a = model.predict(X_a)
    ndcg_a = evaluate_scenarios(test_df, scores_a)

    # B. 감성 4개 → 0.5 (현재 serving fallback)
    df_b = test_df.copy()
    df_b[SENTIMENT_COLS] = 0.5
    X_b = df_b[FEATURE_COLS].values
    scores_b = model.predict(X_b)
    ndcg_b = evaluate_scenarios(test_df, scores_b)

    # C. 감성 4개 → 0.0
    df_c = test_df.copy()
    df_c[SENTIMENT_COLS] = 0.0
    X_c = df_c[FEATURE_COLS].values
    scores_c = model.predict(X_c)
    ndcg_c = evaluate_scenarios(test_df, scores_c)

    # 감성 피쳐 현재 gain importance
    fi = dict(zip(model.feature_name_, model.feature_importances_))
    total_gain = sum(fi.values())
    sentiment_gain = sum(fi.get(col, 0) for col in SENTIMENT_COLS)
    sentiment_gain_pct = sentiment_gain / total_gain * 100 if total_gain > 0 else 0

    print("=" * 55)
    print("Ablation: 감성 피쳐 제거 영향")
    print("=" * 55)
    print(f"\nA. 전체 피쳐 (baseline)         NDCG@10 = {ndcg_a:.4f}")
    print(f"B. 감성 4개 → 0.5 (fallback)    NDCG@10 = {ndcg_b:.4f}  (delta = {ndcg_b - ndcg_a:+.4f})")
    print(f"C. 감성 4개 → 0.0               NDCG@10 = {ndcg_c:.4f}  (delta = {ndcg_c - ndcg_a:+.4f})")

    print(f"\n감성 피쳐 Gain importance 합산: {sentiment_gain_pct:.1f}% (전체 대비)")
    print("\n감성 피쳐별 Gain importance:")
    for col in SENTIMENT_COLS:
        g = fi.get(col, 0)
        print(f"  {col:<20} {g:>6}  ({g/total_gain*100:.1f}%)")

    print("\n비감성 피쳐별 Gain importance (상위 순):")
    non_sentiment = {k: v for k, v in fi.items() if k not in SENTIMENT_COLS}
    for col, g in sorted(non_sentiment.items(), key=lambda x: -x[1]):
        print(f"  {col:<20} {g:>6}  ({g/total_gain*100:.1f}%)")

    print("\n" + "=" * 55)
    delta = ndcg_b - ndcg_a
    if abs(delta) < 0.005:
        print("판정: 감성 피쳐 영향 미미 → 제거 후 재학습 권장")
    elif abs(delta) < 0.02:
        print("판정: 감성 피쳐 영향 소폭 → 재학습 후 비교 필요")
    else:
        print("판정: 감성 피쳐 영향 유의 → 제거 시 성능 손실 주의")


if __name__ == "__main__":
    run()
