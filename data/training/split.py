"""STEP 5. Hub 기반 Train/Val/Test 분할

같은 hub의 장소가 train/test 양쪽에 들어가지 않도록 hub 단위로 분리.
- Train 70%: LGBMRanker 학습
- Val   10%: early stopping / Optuna 튜닝
- Test  20%: 최종 NDCG@10 평가 (단 1회)

출력:
- output/training/train.csv
- output/training/val.csv
- output/training/test.csv
- output/training/split_meta.json
"""

import json
import logging
import os
import random
from collections import Counter

import pandas as pd

logger = logging.getLogger(__name__)


def split_by_hub(
    train_data_path: str = "output/simulation/train_data.csv",
    features_path: str = "output/features/place_features.csv",
    output_dir: str = "output/training",
    train_ratio: float = 0.70,
    val_ratio: float = 0.10,
    seed: int = 42,
) -> dict:
    """Hub 기준 시나리오 분할."""
    os.makedirs(output_dir, exist_ok=True)
    random.seed(seed)

    # 데이터 로드
    train_df = pd.read_csv(train_data_path)
    feat_df = pd.read_csv(features_path)[["naver_place_id", "hub"]]
    logger.info(f"train_data: {len(train_df)} pairs, {train_df.scenario_id.nunique()} 시나리오")

    # place_id → hub 매핑
    place_hub = dict(zip(feat_df["naver_place_id"].astype(str), feat_df["hub"]))

    # 시나리오별 dominant hub
    train_df["_hub"] = train_df["naver_place_id"].astype(str).map(place_hub).fillna("unknown")
    scenario_hub = (
        train_df.groupby("scenario_id")["_hub"]
        .apply(lambda x: Counter(x).most_common(1)[0][0])
        .reset_index()
        .rename(columns={"_hub": "dominant_hub"})
    )
    logger.info(f"고유 hub: {scenario_hub.dominant_hub.nunique()}개")

    # Hub별 시나리오 수 (많은 순 정렬)
    hub_counts = scenario_hub.groupby("dominant_hub").size().sort_values(ascending=False)
    total_scenarios = len(scenario_hub)

    # Greedy 할당: 목표 비율 달성 위해 큰 hub부터 순서대로 train/val/test 채움
    target_train = total_scenarios * train_ratio
    target_val = total_scenarios * val_ratio

    train_hubs, val_hubs, test_hubs = set(), set(), set()
    train_cnt = val_cnt = 0

    for hub, cnt in hub_counts.items():
        if train_cnt < target_train:
            train_hubs.add(hub)
            train_cnt += cnt
        elif val_cnt < target_val:
            val_hubs.add(hub)
            val_cnt += cnt
        else:
            test_hubs.add(hub)

    logger.info(f"Hub 분할: train={len(train_hubs)}, val={len(val_hubs)}, test={len(test_hubs)}")

    # 시나리오 → split 할당
    scenario_hub["split"] = scenario_hub["dominant_hub"].apply(
        lambda h: "train" if h in train_hubs else ("val" if h in val_hubs else "test")
    )
    scenario_split = dict(zip(scenario_hub["scenario_id"], scenario_hub["split"]))

    # train_df에 split 적용
    train_df["split"] = train_df["scenario_id"].map(scenario_split)

    # 저장
    feature_cols = [c for c in train_df.columns if c not in ("scenario_id", "naver_place_id", "_hub", "split")]

    for split_name in ("train", "val", "test"):
        sub = train_df[train_df["split"] == split_name].copy()
        sub = sub.drop(columns=["_hub", "split"])
        path = os.path.join(output_dir, f"{split_name}.csv")
        sub.to_csv(path, index=False)
        logger.info(f"  {split_name}: {len(sub)} pairs, {sub.scenario_id.nunique()} 시나리오 → {path}")

    # 메타 저장
    meta = {
        "total_pairs": len(train_df),
        "total_scenarios": train_df.scenario_id.nunique(),
        "train_hubs": sorted(train_hubs),
        "val_hubs": sorted(val_hubs),
        "test_hubs": sorted(test_hubs),
        "split_counts": {
            s: int((train_df["split"] == s).sum()) for s in ("train", "val", "test")
        },
        "scenario_counts": {
            s: int((scenario_hub["split"] == s).sum()) for s in ("train", "val", "test")
        },
    }
    with open(os.path.join(output_dir, "split_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    logger.info(
        f"분할 완료: train={meta['split_counts']['train']}, "
        f"val={meta['split_counts']['val']}, test={meta['split_counts']['test']}"
    )
    return meta
