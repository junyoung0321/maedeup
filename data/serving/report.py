"""추천 결과 → 구조화된 JSON + 규칙 기반 추천 이유 생성

사용법:
    from serving.report import generate_report

    report = generate_report(ranked, scenario)
    # [{"rank": 1, "place_name": "...", "score": 0.87, "distance_label": "도보 5분", "reasons": [...]}, ...]
"""

from __future__ import annotations

import math


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _rating_label(rating_norm: float) -> str | None:
    if rating_norm >= 0.9:
        return "평점 상위 10%"
    if rating_norm >= 0.7:
        return "평점 상위 30%"
    if rating_norm >= 0.5:
        return "평점 상위 50%"
    return None


def _review_label(review_count_log: float) -> str | None:
    if review_count_log >= 0.8:
        return "리뷰 매우 많음"
    if review_count_log >= 0.5:
        return "리뷰 많음"
    return None


def _sentiment_label(food: float, mood: float, svc: float) -> str | None:
    """ABSA 감성 점수(percentile rank) 기반 label. 0.0 = 데이터 없음."""
    active = [(v, name) for v, name in [(food, "음식"), (mood, "분위기"), (svc, "서비스")] if v > 0]
    if not active:
        return None
    best_score, best_name = max(active)
    if best_score >= 0.8:
        return f"{best_name} 만족도 상위 20%"
    if best_score >= 0.6:
        return f"{best_name} 만족도 높음"
    return None


def _distance_label(dist_km: float) -> str:
    m = dist_km * 1000
    if m < 100:
        return "도보 1분 이내"
    if m < 1500:
        minutes = max(1, round(m / 80))  # 도보 80m/min
        return f"도보 약 {minutes}분"
    drive_min = math.ceil(dist_km / 0.5)
    return f"차로 약 {drive_min}분"


def _resolve_distance(place: dict, scenario: dict) -> float:
    """place의 lat/lng와 scenario 유효 중심 간 거리 (km)."""
    lat = place.get("lat")
    lng = place.get("lng")
    if lat is None or lng is None:
        return place.get("avg_distance_km", 0.0)
    return _haversine_km(
        scenario.get("effective_center_lat", scenario.get("center_lat", 0)),
        scenario.get("effective_center_lng", scenario.get("center_lng", 0)),
        float(lat), float(lng),
    )


def _mood_labels(place: dict, scenario_moods: list[str]) -> list[str]:
    _MOOD_TEXT = {
        "mood_quiet": "조용한 분위기",
        "mood_group": "단체 모임 적합",
        "mood_vibe": "인테리어/감성 우수",
        "mood_budget": "가성비 좋음",
        "mood_private": "프라이빗 공간",
    }
    return [_MOOD_TEXT[m] for m in scenario_moods if place.get(m) == 1 and m in _MOOD_TEXT]


_PURPOSE_LABEL = {
    "식사": "식사 장소로 적합",
    "카페": "카페/디저트 전문",
    "술자리": "술자리/바 전문",
    "회의": "스터디/미팅 공간",
}


def generate_report(ranked: list[dict], scenario: dict) -> list[dict]:
    """랭킹 결과 → 추천 이유 포함 report list.

    Args:
        ranked: ranker.rank() 반환값
        scenario: parse_form() 반환값

    Returns:
        [{
            rank, naver_place_id, place_name, score,
            distance_label: str,
            reasons: list[str],   # 최대 4개, 우선순위 순
        }, ...]
    """
    results = []
    for place in ranked:
        reasons: list[str] = []

        dist_km = _resolve_distance(place, scenario)
        dist_label = _distance_label(dist_km)

        # 1순위: 평점
        r = _rating_label(place.get("rating_norm", 0))
        if r:
            reasons.append(r)

        # 2순위: 요청 무드 매치
        reasons.extend(_mood_labels(place, scenario.get("moods", [])))

        # 3순위: 감성 점수
        s = _sentiment_label(
            place.get("food_sentiment", 0),
            place.get("mood_sentiment", 0),
            place.get("svc_sentiment", 0),
        )
        if s:
            reasons.append(s)

        # 4순위: 목적 카테고리 매치
        if place.get("category_match") == 1:
            lbl = _PURPOSE_LABEL.get(scenario.get("purpose", ""))
            if lbl:
                reasons.append(lbl)

        # 보충: 리뷰 수 (앞 이유가 부족할 때)
        if len(reasons) < 2:
            rv = _review_label(place.get("review_count_log", 0))
            if rv:
                reasons.append(rv)

        results.append({
            "rank": place["rank"],
            "naver_place_id": place.get("naver_place_id"),
            "place_name": place.get("place_name", ""),
            "score": place.get("score", 0),
            "distance_label": dist_label,
            "reasons": reasons[:4],
        })

    return results
