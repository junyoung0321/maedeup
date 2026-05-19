"""ML 서빙 모듈 — LGBMRanker(model_v2_no_sentiment.pkl) 기반 장소 추천

사용법:
    from serving.ranker import rank

    candidates = [
        {
            "place_name": "카페베네 홍대점",
            "lat": 37.556,
            "lng": 126.923,
        },
        ...
    ]

    scenario = {
        "purpose": "카페",
        "purpose_cat": 1,          # PURPOSES[purpose]["category"]
        "budget": 8000,
        "moods": ["mood_quiet", "mood_vibe"],
        "time_slot": "점심",
        "participants": [{"lat": 37.55, "lng": 126.92}, ...],
        "center_lat": 37.555,
        "center_lng": 126.921,
    }

    results = rank(candidates, scenario, top_k=5)
    # [{"place_name": ..., "score": 0.87, "rank": 1}, ...]
"""

import os
import pickle
import logging
from functools import lru_cache
from typing import Optional

import numpy as np
import pandas as pd

from simulation.simulate import compute_scenario_features

logger = logging.getLogger(__name__)

# 학습에 사용된 feature 순서 (retrain_no_sentiment.py의 FEATURE_COLS와 동일해야 함)
FEATURE_COLS = [
    # 정량 3개
    "rating_norm", "review_count_log", "blog_count_log",
    # mood 2개
    "mood_quiet", "mood_private",
    # 고정 1개
    "category_depth2",
    # 거리/공정성 3개
    "avg_distance_km", "max_distance_km", "fairness_score",
    # 시나리오 매칭 4개
    "category_match", "mood_match_count", "hour_suitability", "near_station",
]

# 고정 feature 기본값 (카카오 API 장소 fallback)
# mood_group/vibe/budget은 FEATURE_COLS 제외지만 compute_scenario_features(mood_match_count)에 필요
# category_depth1은 FEATURE_COLS 제외지만 compute_scenario_features(category_match, hour_suitability)에 필요
_FIXED_DEFAULTS = {
    "rating_norm": 0.7,
    "review_count_log": 0.3,
    "blog_count_log": 0.2,
    "mood_quiet": 0,
    "mood_group": 0,
    "mood_vibe": 0,
    "mood_budget": 0,
    "mood_private": 0,
    "category_depth1": 0,
    "category_depth2": -1,
}

_MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "output", "training", "models", "model_v2_no_sentiment.pkl",
)
_FEATURES_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "output", "features", "place_features.csv",
)
_KAKAO_MAP_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "output", "kakao_map.csv",
)


@lru_cache(maxsize=1)
def _load_model():
    """model_v2.pkl 싱글톤 로드."""
    path = os.path.normpath(_MODEL_PATH)
    with open(path, "rb") as f:
        model = pickle.load(f)
    logger.info(f"LGBMRanker 로드: {path}")
    return model


@lru_cache(maxsize=1)
def _load_kakao_bridge() -> dict[str, str]:
    """kakao_map.csv → {kakao_place_id: naver_place_id} 역방향 인덱스."""
    path = os.path.normpath(_KAKAO_MAP_PATH)
    if not os.path.exists(path):
        logger.warning("kakao_map.csv 없음 — 브릿지 비활성화")
        return {}
    df = pd.read_csv(path, dtype={"naver_place_id": str, "kakao_place_id": str})
    df = df.dropna(subset=["kakao_place_id"])
    bridge = dict(zip(df["kakao_place_id"], df["naver_place_id"]))
    logger.info(f"Kakao bridge 로드: {len(bridge):,}개 매핑")
    return bridge


@lru_cache(maxsize=1)
def _load_place_features() -> pd.DataFrame:
    """place_features.csv 싱글톤 로드. naver_place_id → Series 인덱스."""
    path = os.path.normpath(_FEATURES_PATH)
    df = pd.read_csv(path, dtype={"naver_place_id": str})
    df = df.set_index("naver_place_id")
    logger.info(f"place_features 로드: {len(df)}곳 ({path})")
    return df


def _get_fixed_features(naver_place_id: Optional[str], place_row: Optional[pd.Series] = None) -> dict:
    """place_features에서 고정 feature를 조회. 미등록이면 기본값 사용."""
    fixed_cols = [
        "rating_norm", "review_count_log", "blog_count_log",
        "mood_quiet", "mood_group", "mood_vibe", "mood_budget", "mood_private",
        "category_depth1", "category_depth2",
    ]

    if place_row is not None:
        return {col: place_row.get(col, _FIXED_DEFAULTS[col]) for col in fixed_cols}

    features_df = _load_place_features()
    if naver_place_id and naver_place_id in features_df.index:
        row = features_df.loc[naver_place_id]
        return {col: row.get(col, _FIXED_DEFAULTS[col]) for col in fixed_cols}

    # fallback: 기본값
    logger.debug(f"place_features 미등록: {naver_place_id}, 기본값 사용")
    return {col: _FIXED_DEFAULTS[col] for col in fixed_cols}


def build_features(candidates: list[dict], scenario: dict) -> pd.DataFrame:
    """후보 장소 리스트 + 시나리오 → 17-feature DataFrame.

    Args:
        candidates: 후보 장소 리스트. 각 dict는 최소 {"lat": float, "lng": float} 필요.
                    "naver_place_id"가 있으면 place_features.csv 조회.
        scenario: generate_scenario() 반환 형태의 dict.
                  participants, center_lat/lng, purpose_cat, moods, budget, time_slot 필수.

    Returns:
        FEATURE_COLS 순서의 DataFrame (len == len(candidates))
    """
    bridge = _load_kakao_bridge()
    rows = []
    for cand in candidates:
        # naver_place_id 확정: 직접 제공 → kakao_place_id 브릿지 순으로 조회
        naver_id = str(cand.get("naver_place_id", "")) or None
        if not naver_id:
            kakao_id = str(cand.get("kakao_place_id", "")) or None
            if kakao_id:
                naver_id = bridge.get(kakao_id)
        fixed_feat = _get_fixed_features(naver_id)

        # compute_scenario_features는 lat/lng + category_depth1/price_level/mood flags 필요
        # → candidate dict + fixed feature를 합쳐 Series 생성
        merged = {**fixed_feat, **cand}  # cand의 lat/lng가 고정값을 덮어씀
        cand_series = pd.Series(merged)

        # 시나리오 의존 feature 8개 계산
        scen_feat = compute_scenario_features(cand_series, scenario)
        scen_feat.pop("_center_dist_km", None)

        row = {**fixed_feat, **scen_feat}
        rows.append(row)

    df = pd.DataFrame(rows, columns=FEATURE_COLS)
    return df


def rank(
    candidates: list[dict],
    scenario: dict,
    top_k: int = 5,
) -> list[dict]:
    """후보 장소를 LGBMRanker + Two-Tower 하이브리드로 스코어링해 상위 top_k개 반환.

    브릿지 매핑된 장소: LGBMRanker 0.8 + Two-Tower 0.2
    미매핑 장소:        LGBMRanker 0.3 + Two-Tower 0.7

    Args:
        candidates: 후보 장소 리스트 (place_name, lat, lng, kakao_place_id 등 포함)
        scenario: 시나리오 dict
        top_k: 반환할 장소 수

    Returns:
        score 내림차순 정렬된 dict 리스트.
        각 항목: 원본 candidate dict + {"score": float, "rank": int, "ml_ranked": True}
    """
    if not candidates:
        return []

    model = _load_model()
    feat_df = build_features(candidates, scenario)

    # LGBMRanker.predict → relevance 예측값
    lgbm_raw = model.predict(feat_df)
    s_min, s_max = lgbm_raw.min(), lgbm_raw.max()
    lgbm_norm = (lgbm_raw - s_min) / (s_max - s_min) if s_max > s_min else np.full(len(lgbm_raw), 0.5)

    # 브릿지 매핑 여부 판별
    bridge = _load_kakao_bridge()
    is_mapped = np.zeros(len(candidates), dtype=bool)
    for i, cand in enumerate(candidates):
        naver_id = str(cand.get("naver_place_id", "")) or None
        if naver_id:
            is_mapped[i] = True
        else:
            kakao_id = str(cand.get("kakao_place_id", "")) or None
            if kakao_id and kakao_id in bridge:
                is_mapped[i] = True

    # Two-Tower 스코어 (로드 실패 시 0.5 폴백)
    tt_scores = np.full(len(candidates), 0.5)
    try:
        from serving.two_tower import score_places as tt_score_places
        raw_tt = np.array(tt_score_places(scenario, candidates))
        tt_min, tt_max = raw_tt.min(), raw_tt.max()
        tt_scores = (raw_tt - tt_min) / (tt_max - tt_min) if tt_max > tt_min else np.full(len(raw_tt), 0.5)
    except Exception as e:
        logger.warning(f"Two-Tower 비활성화: {e}")

    # 하이브리드 최종 점수
    lgbm_w = np.where(is_mapped, 0.8, 0.3)
    tt_w = 1.0 - lgbm_w
    final_scores = lgbm_w * lgbm_norm + tt_w * tt_scores

    # 정렬 및 top_k 선택
    order = np.argsort(-final_scores)
    results = []
    for rank_idx, cand_idx in enumerate(order[:top_k], start=1):
        result = {
            **candidates[cand_idx],
            "score": round(float(final_scores[cand_idx]), 4),
            "rank": rank_idx,
            "ml_ranked": True,
            "bridge_mapped": bool(is_mapped[cand_idx]),
        }
        results.append(result)

    return results


# ── LangGraph 연동 헬퍼 ─────────────────────────────────────────────────────

# meeting_type → (purpose, purpose_cat, default_budget)
_MEETING_TYPE_MAP = {
    "식사": ("식사", 0, 20000),
    "카페": ("카페", 1, 8000),
    "커피": ("카페", 1, 8000),
    "술자리": ("술자리", 2, 25000),
    "회식": ("술자리", 2, 25000),
    "회의": ("회의", 3, 7000),
    "미팅": ("회의", 3, 7000),
    "모임": ("식사", 0, 20000),
}

# date_hint 시간대 추론 (오전/오후/저녁/심야)
def _infer_time_slot(date_hint: str | None) -> str:
    if not date_hint:
        return "저녁"
    dh = date_hint.lower()
    for kw in ("심야", "자정", "새벽"):
        if kw in dh:
            return "심야"
    for kw in ("저녁", "야", "밤", "pm", "오후"):
        if kw in dh:
            return "저녁"
    return "점심"


def build_scenario_from_state(state: dict) -> dict:
    """LangGraph GraphState → ranker scenario dict 변환.

    state에 없는 값(budget, moods, participants 좌표)은 합리적 기본값으로 채움.
    place_search_results의 첫 번째 장소 좌표를 center로 사용.
    """
    meeting_type = (state.get("meeting_type") or "모임").strip()
    purpose, purpose_cat, default_budget = _MEETING_TYPE_MAP.get(
        meeting_type, ("식사", 0, 20000)
    )

    # center 좌표: place_search_results 첫 번째 장소 또는 서울 중심
    places = state.get("place_search_results") or []
    if places and places[0].get("lat") and places[0].get("lng"):
        center_lat = float(places[0]["lat"])
        center_lng = float(places[0]["lng"])
    else:
        center_lat, center_lng = 37.5665, 126.9780  # 서울시청

    # participants: headcount 기반 더미 좌표 (center ± 0.01~0.03도)
    headcount = max(2, int(state.get("headcount") or 4))
    import random as _random
    _random.seed(42)
    participants = [
        {
            "lat": center_lat + _random.uniform(-0.025, 0.025),
            "lng": center_lng + _random.uniform(-0.030, 0.030),
        }
        for _ in range(headcount)
    ]

    return {
        "purpose": purpose,
        "purpose_cat": purpose_cat,
        "budget": default_budget,
        "moods": [],
        "time_slot": _infer_time_slot(state.get("date_hint")),
        "participants": participants,
        "center_lat": center_lat,
        "center_lng": center_lng,
    }


