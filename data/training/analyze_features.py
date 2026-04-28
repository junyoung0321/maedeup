"""Feature 분석: VIF 재계산 + SHAP + Mutual Information

현재 25개 피쳐 기준으로:
1. VIF 재계산 (price_level 제거 후)
2. label_score vs sentiment_confidence 결정
3. SHAP 분석 (mean |SHAP| 순위)
4. Mutual Information
5. 제거 후보 최종 정리
"""

import json
import os
import pickle

import numpy as np
import pandas as pd

SPLIT_DIR = "output/training"
MODEL_DIR = "output/training/models"

FEATURE_COLS = [
    "rating_norm", "review_count_log", "blog_count_log",
    "mood_quiet", "mood_group", "mood_vibe", "mood_budget", "mood_private",
    "is_chain", "category_depth1", "category_depth2",
    "avg_distance_km", "max_distance_km", "fairness_score",
    "category_match", "mood_match_count", "price_match",
    "hour_suitability", "near_station",
    "food_sentiment", "mood_sentiment", "svc_sentiment", "price_sentiment",
    "sentiment_confidence", "label_score",
]

LABEL_COL = "relevance"
GROUP_COL = "scenario_id"


def _load_all():
    train = pd.read_csv(os.path.join(SPLIT_DIR, "train.csv"))
    val = pd.read_csv(os.path.join(SPLIT_DIR, "val.csv"))
    test = pd.read_csv(os.path.join(SPLIT_DIR, "test.csv"))
    return train, val, test


# ── 1. VIF ───────────────────────────────────────────────────────────────────
def compute_vif(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    X = df[cols].values.astype(float)
    vif_vals = []
    for i in range(X.shape[1]):
        y = X[:, i]
        X_rest = np.delete(X, i, axis=1)
        # lstsq로 R² 계산
        coef, _, _, _ = np.linalg.lstsq(
            np.column_stack([np.ones(len(X_rest)), X_rest]), y, rcond=None
        )
        y_pred = np.column_stack([np.ones(len(X_rest)), X_rest]) @ coef
        ss_res = ((y - y_pred) ** 2).sum()
        ss_tot = ((y - y.mean()) ** 2).sum()
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        vif = 1 / (1 - r2) if r2 < 1 else float("inf")
        vif_vals.append(vif)
    return pd.DataFrame({"feature": cols, "VIF": vif_vals}).sort_values("VIF", ascending=False)


# ── 2. Correlation heatmap key pairs ─────────────────────────────────────────
def corr_analysis(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    corr = df[cols].corr().abs()
    pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            pairs.append({
                "feat1": cols[i],
                "feat2": cols[j],
                "r": round(corr.iloc[i, j], 3),
            })
    return pd.DataFrame(pairs).sort_values("r", ascending=False).head(15)


# ── 3. SHAP ───────────────────────────────────────────────────────────────────
def shap_analysis(model, X_test: np.ndarray, cols: list) -> pd.DataFrame:
    import shap
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)
    mean_abs = np.abs(shap_values).mean(axis=0)
    return (
        pd.DataFrame({"feature": cols, "mean_abs_shap": mean_abs})
        .sort_values("mean_abs_shap", ascending=False)
    )


# ── 4. Mutual Information ─────────────────────────────────────────────────────
def mi_analysis(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    from sklearn.feature_selection import mutual_info_regression
    X = df[cols].values
    y = df[LABEL_COL].values
    mi = mutual_info_regression(X, y, random_state=42)
    return (
        pd.DataFrame({"feature": cols, "MI": mi})
        .sort_values("MI", ascending=False)
    )


# ── 5. Gain importance (LightGBM) ─────────────────────────────────────────────
def gain_importance(model, cols: list) -> pd.DataFrame:
    fi = dict(zip(cols, model.feature_importances_))
    return (
        pd.DataFrame(list(fi.items()), columns=["feature", "gain"])
        .sort_values("gain", ascending=False)
    )


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
    return float(np.mean(ndcgs)) if ndcgs else 0.0


def run():
    print("=" * 60)
    print("Feature 분석 (25개 기준)")
    print("=" * 60)

    train_df, val_df, test_df = _load_all()
    fit_df = pd.concat([train_df, val_df], ignore_index=True)

    # 모델 로드 (v2)
    with open(os.path.join(MODEL_DIR, "model_v2.pkl"), "rb") as f:
        model = pickle.load(f)

    X_test = test_df[FEATURE_COLS].values

    # 현재 FEATURE_COLS vs model feature names 확인
    model_feat = model.feature_name_ if hasattr(model, "feature_name_") else FEATURE_COLS
    print(f"\n모델 feature 수: {len(model_feat)}")
    print(f"분석 feature 수: {len(FEATURE_COLS)}")
    if list(model_feat) != FEATURE_COLS:
        print("  [주의] 모델과 현재 FEATURE_COLS 불일치 - v2 재학습 필요")
    else:
        print("  [OK] 모델 feature 일치")

    # 현재 모델 성능
    test_ndcg = evaluate_scenarios(test_df, model.predict(X_test))
    print(f"\n현재 v2 test NDCG@10: {test_ndcg:.4f}")

    # ── 1. VIF (train+val 전체) ──
    print("\n" + "─" * 40)
    print("1. VIF (25개)")
    vif_df = compute_vif(fit_df, FEATURE_COLS)
    print(vif_df.to_string(index=False))

    # ── 2. 고상관 쌍 ──
    print("\n" + "─" * 40)
    print("2. 고상관 쌍 (|r| 상위 15)")
    corr_df = corr_analysis(fit_df, FEATURE_COLS)
    print(corr_df.to_string(index=False))

    # ── 3. Gain importance ──
    print("\n" + "─" * 40)
    print("3. Gain importance (v2 model)")
    if list(model_feat) == FEATURE_COLS:
        gi_df = gain_importance(model, FEATURE_COLS)
    else:
        gi_df = gain_importance(model, list(model_feat))
    print(gi_df.to_string(index=False))

    # ── 4. Mutual Information ──
    print("\n" + "─" * 40)
    print("4. Mutual Information")
    mi_df = mi_analysis(fit_df, FEATURE_COLS)
    print(mi_df.to_string(index=False))

    # ── 5. SHAP ──
    print("\n" + "─" * 40)
    print("5. SHAP (v2 model, test set)")
    try:
        import shap
        if list(model_feat) == FEATURE_COLS:
            shap_df = shap_analysis(model, X_test, FEATURE_COLS)
        else:
            shap_df = shap_analysis(model, X_test, list(model_feat))
        print(shap_df.to_string(index=False))
    except ImportError:
        print("  shap 미설치 — pip install shap")
        shap_df = None

    # ── 6. 종합 제거 후보 ──
    print("\n" + "═" * 60)
    print("종합 제거 후보 분석")
    print("─" * 60)

    # 각 기준 점수 합산 (rank-based)
    if list(model_feat) == FEATURE_COLS:
        gi_rank = gi_df.reset_index(drop=True)
        gi_rank["gi_rank"] = gi_rank["gain"].rank(ascending=True)  # 낮을수록 제거 후보

        mi_rank = mi_df.reset_index(drop=True)
        mi_rank["mi_rank"] = mi_rank["MI"].rank(ascending=True)

        summary = gi_rank[["feature", "gain", "gi_rank"]].merge(
            mi_rank[["feature", "MI", "mi_rank"]], on="feature"
        )

        vif_merge = vif_df[["feature", "VIF"]]
        summary = summary.merge(vif_merge, on="feature")

        if shap_df is not None:
            shap_rank = shap_df.copy()
            shap_rank["shap_rank"] = shap_rank["mean_abs_shap"].rank(ascending=True)
            summary = summary.merge(shap_rank[["feature", "mean_abs_shap", "shap_rank"]], on="feature")
            summary["total_rank"] = summary["gi_rank"] + summary["mi_rank"] + summary["shap_rank"]
        else:
            summary["total_rank"] = summary["gi_rank"] + summary["mi_rank"]

        summary = summary.sort_values("total_rank")
        print("\n제거 우선순위 (total_rank 낮을수록 제거 후보):")
        print(summary.to_string(index=False))

        # 임계값 기준 명확한 후보
        print("\n명확한 제거 후보 (gain < 5 AND MI < 0.01):")
        candidates = summary[(summary["gain"] < 5) | (summary["MI"] < 0.01)]
        print(candidates[["feature", "gain", "MI", "VIF"]].to_string(index=False))

    print("\n완료.")


if __name__ == "__main__":
    run()
