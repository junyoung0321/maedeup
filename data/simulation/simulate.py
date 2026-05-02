"""STEP 4. 시나리오 시뮬레이션 + STEP 2. Pseudo-label 생성

4,000 시나리오 × 15 후보 = 60,000 query-doc pairs 생성.
각 pair에 24개 feature + graded relevance (0~7) 부여.

출력: output/simulation/train_data.csv
"""

import json
import math
import os
import random
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 모임 목적별 설정
PURPOSES = {
    "식사": {"category": 0, "budget_range": (10000, 30000), "weight": 0.4},
    "카페": {"category": 1, "budget_range": (5000, 12000), "weight": 0.25},
    "술자리": {"category": 2, "budget_range": (15000, 40000), "weight": 0.25},
    "회의": {"category": 3, "budget_range": (5000, 10000), "weight": 0.1},
}

# mood 키워드 풀
MOOD_POOL = ["mood_quiet", "mood_group", "mood_vibe", "mood_budget", "mood_private"]

# 숨겨진 사용자 유형 (시나리오마다 랜덤 선택, 학습 feature에는 포함 안 됨)
# 각 유형은 5개 score 차원에 대한 가중치를 가짐
USER_TYPES = {
    "foodie":      {"food": 0.35, "mood": 0.10, "dist": 0.20, "quality": 0.20, "match": 0.15},
    "atmosphere":  {"food": 0.10, "mood": 0.35, "dist": 0.20, "quality": 0.15, "match": 0.20},
    "convenience": {"food": 0.05, "mood": 0.05, "dist": 0.60, "quality": 0.10, "match": 0.20},
    "budget":      {"food": 0.15, "mood": 0.10, "dist": 0.20, "quality": 0.10, "match": 0.45},
}

# 시간대별 적합도
HOUR_SUITABILITY = {
    "점심": {0: 1.0, 1: 0.8, 2: 0.3, 3: 0.9},   # 음식점 최적
    "저녁": {0: 1.0, 1: 0.6, 2: 1.0, 3: 0.5},   # 음식+술 최적
    "심야": {0: 0.5, 1: 0.2, 2: 1.0, 3: 0.1},   # 술집 최적
}


def haversine_km(lat1, lng1, lat2, lng2):
    """두 좌표 간 거리 (km)."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def generate_scenario(places_df: pd.DataFrame, scenario_id: int) -> dict:
    """단일 시나리오 생성.
    반환: {scenario_id, purpose, budget, moods, time_slot, participants: [{lat, lng}]}
    """
    # 목적 선택 (가중 랜덤)
    purposes = list(PURPOSES.keys())
    weights = [PURPOSES[p]["weight"] for p in purposes]
    purpose = random.choices(purposes, weights=weights, k=1)[0]
    purpose_info = PURPOSES[purpose]

    # 참여자 (3~8명)
    n_participants = random.randint(3, 8)

    # 거점 하나 선택 → 참여자 위치는 거점 중심 반경 5km 내
    hub_row = places_df.sample(1).iloc[0]
    center_lat, center_lng = hub_row["lat"], hub_row["lng"]

    participants = []
    for _ in range(n_participants):
        dlat = random.uniform(-0.045, 0.045)  # ~5km
        dlng = random.uniform(-0.055, 0.055)
        participants.append({
            "lat": center_lat + dlat,
            "lng": center_lng + dlng,
        })

    # 예산
    budget = random.randint(*purpose_info["budget_range"])

    # mood 요청 (1~3개)
    n_moods = random.randint(1, 3)
    moods = random.sample(MOOD_POOL, k=n_moods)

    # 시간대
    time_slot = random.choice(["점심", "저녁", "심야"])

    # 숨겨진 사용자 유형 (label 생성에만 사용, 학습 feature 제외)
    user_type = random.choice(list(USER_TYPES.keys()))

    return {
        "scenario_id": scenario_id,
        "purpose": purpose,
        "purpose_cat": purpose_info["category"],
        "budget": budget,
        "moods": moods,
        "time_slot": time_slot,
        "participants": participants,
        "center_lat": center_lat,
        "center_lng": center_lng,
        "user_type": user_type,
    }


def select_candidates(
    places_df: pd.DataFrame,
    scenario: dict,
    n_candidates: int = 15,
    n_hard_negatives: int = 3,
) -> pd.DataFrame:
    """후보 장소 샘플링.

    - (n_candidates - n_hard_negatives)개: 중심 반경 3km 내 근거리
    - n_hard_negatives개: 4~8km 원거리 (label-0 유도용 hard negative)
    """
    center_lat = scenario["center_lat"]
    center_lng = scenario["center_lng"]

    # ── 근거리 후보 (3km 이내) ──────────────────────────
    lat_near = 0.027   # ~3km
    lng_near = 0.036
    mask_near = (
        (places_df["lat"].between(center_lat - lat_near, center_lat + lat_near)) &
        (places_df["lng"].between(center_lng - lng_near, center_lng + lng_near))
    )
    nearby = places_df[mask_near]

    if len(nearby) < 5:
        lat_near *= 2
        lng_near *= 2
        mask_near = (
            (places_df["lat"].between(center_lat - lat_near, center_lat + lat_near)) &
            (places_df["lng"].between(center_lng - lng_near, center_lng + lng_near))
        )
        nearby = places_df[mask_near]

    if len(nearby) == 0:
        return pd.DataFrame()

    # ── 원거리 후보 (4~8km, hard negative) ──────────────
    # lat 4km≈0.036, 8km≈0.072 / lng 4km≈0.045, 8km≈0.090
    lat_far_inner, lat_far_outer = 0.036, 0.072
    lng_far_inner, lng_far_outer = 0.045, 0.090
    mask_far = (
        ~mask_near &
        (places_df["lat"].between(center_lat - lat_far_outer, center_lat + lat_far_outer)) &
        (places_df["lng"].between(center_lng - lng_far_outer, center_lng + lng_far_outer))
    )
    far = places_df[mask_far]

    n_near = min(n_candidates - n_hard_negatives, len(nearby))
    n_far = min(n_hard_negatives, len(far))

    parts = [nearby.sample(n=n_near)]
    if n_far > 0:
        parts.append(far.sample(n=n_far))
    return pd.concat(parts)


def compute_scenario_features(candidate: pd.Series, scenario: dict) -> dict:
    """시나리오 의존 feature 8개 계산."""
    participants = scenario["participants"]
    place_lat, place_lng = candidate["lat"], candidate["lng"]

    # 거리 계산
    distances = [
        haversine_km(p["lat"], p["lng"], place_lat, place_lng)
        for p in participants
    ]
    avg_dist = np.mean(distances)
    max_dist = np.max(distances)
    dist_std = np.std(distances)
    fairness = 1.0 / (dist_std + 1)

    # category_match: 목적과 카테고리 일치
    cat_match = 1 if candidate["category_depth1"] == scenario["purpose_cat"] else 0

    # mood_match_count: 요청 mood 중 일치 비율
    requested_moods = scenario["moods"]
    matched = sum(1 for m in requested_moods if candidate.get(m, 0) == 1)
    mood_match = matched / len(requested_moods) if requested_moods else 0

    # price_match: 예산 내 여부
    price_level = candidate["price_level"]
    budget = scenario["budget"]
    # price_level 1~4 → 대략적 가격대
    price_ranges = {1: 8000, 2: 15000, 3: 30000, 4: 50000}
    est_price = price_ranges.get(price_level, 15000)
    price_match = 1 if est_price <= budget else 0

    # hour_suitability
    time_slot = scenario["time_slot"]
    cat = candidate["category_depth1"]
    hour_suit = HOUR_SUITABILITY.get(time_slot, {}).get(cat, 0.5)

    # near_station: 간소화 (도심 거점 1.5km 내면 1)
    center_dist = haversine_km(
        scenario["center_lat"], scenario["center_lng"],
        place_lat, place_lng
    )
    near_station = 1 if center_dist < 1.5 else 0

    return {
        "avg_distance_km": round(avg_dist, 3),
        "max_distance_km": round(max_dist, 3),
        "fairness_score": round(fairness, 3),
        "category_match": cat_match,
        "mood_match_count": round(mood_match, 3),
        "price_match": price_match,
        "hour_suitability": round(hour_suit, 3),
        "near_station": near_station,
        # label 계산 전용 (학습 feature 제외)
        "_center_dist_km": round(center_dist, 3),
    }


def compute_pseudo_label(features: dict, user_type: str) -> int:
    """STEP 2: Pseudo-label (graded relevance 0~7).

    숨겨진 사용자 유형(user_type)별로 5개 score 차원을 다르게 가중합.
    → 동일 feature 조합도 user_type에 따라 label이 달라져 모델이 완벽 재현 불가.

    5개 차원:
    - dist:    거리 기반 (avg_distance → 0~1 연속값)
    - match:   시나리오 부합도 (category/mood/price/time 평균)
    - quality: 평점 정규화 (rating_norm)
    - food:    음식 감성 (food_sentiment, 0이면 중립 0.5 처리)
    - mood:    분위기 감성 (mood_sentiment, 0이면 중립 0.5 처리)

    raw score [0,1] → 0~7 변환 (int(raw * 8), clip)
    + 소량 노이즈 (gaussian σ=0.04 → ±0.3 label 변동 수준)
    """
    w = USER_TYPES[user_type]

    # dist_score: 5km 기준 선형 감소 (참여자→place 평균 거리 기반)
    dist = features["avg_distance_km"]
    dist_score = max(0.0, 1.0 - dist / 5.0)

    # match_score: 4개 시나리오 부합 요소 평균
    cat = float(features["category_match"])
    mood = min(float(features["mood_match_count"]), 1.0)
    price = float(features.get("price_match", 0))
    time_ = float(features.get("hour_suitability", 0.5))
    match_score = (cat + mood + price + time_) / 4.0

    # quality_score: 평점 정규화
    quality_score = float(features["rating_norm"])

    # 감성 score: percentile rank 기반 (0.0이면 데이터 없음 → 중립 0.5)
    food_raw = float(features.get("food_sentiment", 0.0))
    food_score = food_raw if food_raw != 0.0 else 0.5

    mood_raw = float(features.get("mood_sentiment", 0.0))
    mood_score = mood_raw if mood_raw != 0.0 else 0.5

    # 가중합
    raw = (
        w["dist"]    * dist_score +
        w["match"]   * match_score +
        w["quality"] * quality_score +
        w["food"]    * food_score +
        w["mood"]    * mood_score
    )

    # 가우시안 노이즈 (σ=0.10): 현실적 선호 불확실성 반영
    raw += random.gauss(0, 0.10)
    raw = max(0.0, min(1.0, raw))

    return max(0, min(7, int(raw * 8)))


def run_simulation(
    features_path: str = "output/features/place_features.csv",
    output_path: str = "output/simulation/train_data.csv",
    n_scenarios: int = 4000,
    n_candidates: int = 15,
    seed: int = 42,
):
    """전체 시뮬레이션 실행."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    random.seed(seed)
    np.random.seed(seed)

    # 장소 데이터 로드
    places_df = pd.read_csv(features_path)
    logger.info(f"장소 로드: {len(places_df)}곳")

    all_rows = []
    empty_scenarios = 0

    for i in range(n_scenarios):
        scenario = generate_scenario(places_df, i)
        candidates = select_candidates(places_df, scenario, n_candidates)

        if candidates.empty:
            empty_scenarios += 1
            continue

        for _, cand in candidates.iterrows():
            # 시나리오 의존 feature
            scen_features = compute_scenario_features(cand, scenario)

            # 전체 feature 합치기
            row = {
                "scenario_id": scenario["scenario_id"],
                "naver_place_id": cand["naver_place_id"],
                # 12 고정 feature
                "rating_norm": cand["rating_norm"],
                "review_count_log": cand["review_count_log"],
                "blog_count_log": cand["blog_count_log"],
                "price_level": cand["price_level"],
                "mood_quiet": cand["mood_quiet"],
                "mood_group": cand["mood_group"],
                "mood_vibe": cand["mood_vibe"],
                "mood_budget": cand["mood_budget"],
                "mood_private": cand["mood_private"],
                "is_chain": cand["is_chain"],
                "category_depth1": cand["category_depth1"],
                "category_depth2": cand["category_depth2"],
                # 8 시나리오 의존 feature
                **scen_features,
                # 4 감성 feature
                "food_sentiment": cand["food_sentiment"],
                "mood_sentiment": cand["mood_sentiment"],
                "svc_sentiment": cand["svc_sentiment"],
                "price_sentiment": cand["price_sentiment"],
                # 2 긍부정 레이블 feature
                "sentiment_confidence": cand["sentiment_confidence"],
                "label_score": cand["label_score"],
            }

            # Pseudo-label (user_type, _center_dist_km은 학습 row에 포함 안 됨)
            row["relevance"] = compute_pseudo_label(row, scenario["user_type"])
            row.pop("_center_dist_km", None)
            all_rows.append(row)

        if (i + 1) % 500 == 0:
            logger.info(f"  [{i+1}/{n_scenarios}] pairs: {len(all_rows)}")

    df = pd.DataFrame(all_rows)
    df.to_csv(output_path, index=False)

    logger.info(
        f"시뮬레이션 완료: {n_scenarios - empty_scenarios} 시나리오, "
        f"{len(df)} pairs, 빈 시나리오 {empty_scenarios}"
    )

    # relevance 분포
    rel_dist = df["relevance"].value_counts().sort_index()
    logger.info(f"Relevance 분포:\n{rel_dist.to_string()}")

    return {
        "scenarios": n_scenarios - empty_scenarios,
        "pairs": len(df),
        "empty_scenarios": empty_scenarios,
        "relevance_dist": rel_dist.to_dict(),
        "output_path": output_path,
    }
