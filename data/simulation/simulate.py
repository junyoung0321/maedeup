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

    반환: {scenario_id, purpose, budget, moods, time_slot, participants,
           center_lat, center_lng, location_specified, effective_center_lat, effective_center_lng}

    location_specified=True  (50%): 대화에서 특정 지역 명시 → hub를 중심으로 후보 선택
    location_specified=False (50%): 지역 미명시 → 참여자 무게중심을 중심으로 후보 선택
    """
    # 목적 선택 (가중 랜덤)
    purposes = list(PURPOSES.keys())
    weights = [PURPOSES[p]["weight"] for p in purposes]
    purpose = random.choices(purposes, weights=weights, k=1)[0]
    purpose_info = PURPOSES[purpose]

    # 참여자 (3~8명)
    n_participants = random.randint(3, 8)

    # 거점 하나 선택 (location_specified=True 시 명시 지역, False 시 참여자 분산 기준점)
    hub_row = places_df.sample(1).iloc[0]
    center_lat, center_lng = hub_row["lat"], hub_row["lng"]

    # 지역 명시 여부 결정 (50/50)
    location_specified = random.random() < 0.5

    if location_specified:
        # 특정 지역 명시: 참여자 hub 반경 5km 내
        spread_lat, spread_lng = 0.045, 0.055
    else:
        # 지역 미명시: 참여자 분산 넓음 (~10km) → 무게중심 사용
        spread_lat, spread_lng = 0.090, 0.110

    participants = []
    for _ in range(n_participants):
        dlat = random.uniform(-spread_lat, spread_lat)
        dlng = random.uniform(-spread_lng, spread_lng)
        participants.append({
            "lat": center_lat + dlat,
            "lng": center_lng + dlng,
        })

    if location_specified:
        effective_center_lat = center_lat
        effective_center_lng = center_lng
    else:
        effective_center_lat = float(np.mean([p["lat"] for p in participants]))
        effective_center_lng = float(np.mean([p["lng"] for p in participants]))

    # 예산
    budget = random.randint(*purpose_info["budget_range"])

    # mood 요청 (1~3개)
    n_moods = random.randint(1, 3)
    moods = random.sample(MOOD_POOL, k=n_moods)

    # 시간대 (저녁 0.5, 점심 0.3, 심야 0.2)
    time_slot = random.choices(["저녁", "점심", "심야"], weights=[0.5, 0.3, 0.2], k=1)[0]

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
        "location_specified": location_specified,
        "effective_center_lat": effective_center_lat,
        "effective_center_lng": effective_center_lng,
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
    center_lat = scenario.get("effective_center_lat", scenario["center_lat"])
    center_lng = scenario.get("effective_center_lng", scenario["center_lng"])

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

    # price_match 제거: price_level이 항상 2(상수)였으므로 budget>=15000 여부만 판단 → 무의미
    # (2026-04-25 제거)

    # hour_suitability
    time_slot = scenario["time_slot"]
    cat = candidate["category_depth1"]
    hour_suit = HOUR_SUITABILITY.get(time_slot, {}).get(cat, 0.5)

    # near_station: 선택 중심(명시 지역 or 참여자 무게중심) 1.5km 내면 1
    center_dist = haversine_km(
        scenario.get("effective_center_lat", scenario["center_lat"]),
        scenario.get("effective_center_lng", scenario["center_lng"]),
        place_lat, place_lng
    )
    near_station = 1 if center_dist < 1.5 else 0

    return {
        "avg_distance_km": round(avg_dist, 3),
        "max_distance_km": round(max_dist, 3),
        "fairness_score": round(fairness, 3),
        "category_match": cat_match,
        "mood_match_count": round(mood_match, 3),
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

    # match_score: 3개 시나리오 부합 요소 평균 (price_match 제거)
    cat = float(features["category_match"])
    mood = min(float(features["mood_match_count"]), 1.0)
    time_ = float(features.get("hour_suitability", 0.5))
    match_score = (cat + mood + time_) / 3.0

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

    return max(0, min(7, round(raw * 7)))


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
                # 8 고정 feature (price_level 제거: std=0, mood_group/vibe/budget 제거: v2 gain<21)
                # mood_group(79.8%=1), mood_vibe(78.4%=1), mood_budget(86.9%=1) → 분산 없어 식별력 없음
                "rating_norm": cand["rating_norm"],
                "review_count_log": cand["review_count_log"],
                "blog_count_log": cand["blog_count_log"],
                "mood_quiet": cand["mood_quiet"],
                "mood_private": cand["mood_private"],
                # is_chain 제거: 키워드 커버리지 3.1% → 상수에 가까움, v2 gain=6 (2026-04-26)
                # category_depth1 제거: depth2에 대분류 정보 포함됨, v2 gain=29 (2026-04-26)
                "category_depth2": cand["category_depth2"],
                # 8 시나리오 의존 feature
                **scen_features,
                # 4 감성 feature
                "food_sentiment": cand["food_sentiment"],
                "mood_sentiment": cand["mood_sentiment"],
                "svc_sentiment": cand["svc_sentiment"],
                "price_sentiment": cand["price_sentiment"],
                # sentiment_confidence 제거: v2 gain=39 (rating_norm 대비 8%), r=0.554 (2026-04-25 제거)
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
