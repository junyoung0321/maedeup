"""Quick Recommend 파이프라인

폼 입력 → 장소 추천 보고서 (parser → place_features 반경 필터 → ranker.rank() → report)

사용법:
    from serving.quick_recommend import quick_recommend

    result = quick_recommend(
        date_time="내일 저녁 7시",
        location="홍대",
        meeting_type="카페",
        extras="조용하고 분위기 좋은 곳",
        headcount=3,
        top_k=5,
    )
    # {
    #   "scenario": {"purpose": "카페", "time_slot": "저녁", "location_name": "홍대", ...},
    #   "recommendations": [{"rank": 1, "place_name": "...", "score": 0.91, "distance_label": "도보 3분", "reasons": [...]}, ...],
    #   "meta": {"candidates_found": 42, "ml_model": "model_v2"},
    # }
"""

from __future__ import annotations

import logging

import numpy as np

from serving.parser import parse_form
from serving.ranker import _load_place_features, rank
from serving.report import generate_report

logger = logging.getLogger(__name__)


def _filter_candidates(
    features_df,
    center_lat: float,
    center_lng: float,
    lat_r: float,
    lng_r: float,
    max_candidates: int = 60,
) -> list[dict]:
    """place_features DataFrame에서 반경 내 후보 필터링. 부족 시 반경 2배 확장."""
    mask = (
        features_df["lat"].between(center_lat - lat_r, center_lat + lat_r)
        & features_df["lng"].between(center_lng - lng_r, center_lng + lng_r)
    )
    nearby = features_df[mask]

    if len(nearby) < 10:
        mask2 = (
            features_df["lat"].between(center_lat - lat_r * 2, center_lat + lat_r * 2)
            & features_df["lng"].between(center_lng - lng_r * 2, center_lng + lng_r * 2)
        )
        nearby = features_df[mask2]
        if len(nearby) > 0:
            logger.info(f"반경 확장 적용: {len(nearby)}곳")

    if len(nearby) > max_candidates:
        nearby = nearby.sample(n=max_candidates, random_state=42)

    return nearby.reset_index().to_dict("records")


def quick_recommend(
    date_time: str | None = None,
    location: str | None = None,
    meeting_type: str = "식사",
    extras: str | None = None,
    headcount: int = 4,
    top_k: int = 5,
    radius_km: float = 3.0,
) -> dict:
    """폼 입력 → 장소 추천 보고서.

    Args:
        date_time: 날짜/시간 자유 텍스트 (예: "내일 저녁", "5월 10일 오후 7시")
        location:  장소명 또는 지역 (예: "홍대", "강남역")
        meeting_type: 모임 유형 (식사/카페/술자리/회의/모임/커피/회식/미팅)
        extras:    추가 요구사항 자유 텍스트 (예: "조용하고 분위기 좋은 곳")
        headcount: 참여 인원
        top_k:     추천 장소 수
        radius_km: 후보 탐색 반경 (km)

    Returns:
        {
            "scenario": {purpose, time_slot, location_name, headcount, moods},
            "recommendations": [{rank, naver_place_id, place_name, score, distance_label, reasons}, ...],
            "meta": {candidates_found, ml_model},
        }
    """
    # 1. 폼 파싱 → scenario dict
    scenario = parse_form(
        date_time=date_time,
        location=location,
        meeting_type=meeting_type,
        extras=extras,
        headcount=headcount,
    )
    logger.info(
        f"시나리오: purpose={scenario['purpose']}, time_slot={scenario['time_slot']}, "
        f"moods={scenario['moods']}, center=({scenario['center_lat']:.4f},{scenario['center_lng']:.4f})"
    )

    # 2. place_features 반경 필터 → 후보 list[dict]
    features_df = _load_place_features().reset_index()
    eff_lat = scenario["effective_center_lat"]
    eff_lng = scenario["effective_center_lng"]

    lat_r = radius_km / 111.0
    lng_r = radius_km / (111.0 * np.cos(np.radians(eff_lat)))

    candidates = _filter_candidates(features_df, eff_lat, eff_lng, lat_r, lng_r)
    logger.info(f"후보 장소: {len(candidates)}곳")

    if not candidates:
        return {
            "scenario": _scenario_summary(scenario, headcount),
            "recommendations": [],
            "meta": {"candidates_found": 0, "ml_model": "model_v2", "error": "no_candidates"},
        }

    # 3. LGBMRanker 스코어링
    ranked = rank(candidates, scenario, top_k=top_k)
    logger.info(f"랭킹 완료: {len(ranked)}개 추천")

    # 4. 규칙 기반 보고서 생성
    report = generate_report(ranked, scenario)

    return {
        "scenario": _scenario_summary(scenario, headcount),
        "recommendations": report,
        "meta": {"candidates_found": len(candidates), "ml_model": "model_v2"},
    }


def _scenario_summary(scenario: dict, headcount: int) -> dict:
    return {
        "purpose": scenario["purpose"],
        "time_slot": scenario["time_slot"],
        "location_name": scenario.get("location_name"),
        "headcount": headcount,
        "moods": scenario.get("moods", []),
    }
