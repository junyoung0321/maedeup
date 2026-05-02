"""폼 입력 → scenario dict 변환

입력 (폼 필드):
    date_time    : str | None   예) "2026-05-10 19:00", "내일 저녁", "오후 7시"
    location     : str | None   예) "홍대", "서울대입구역 근처"
    meeting_type : str          예) "식사", "카페", "술자리", "회의"
    extras       : str | None   예) "조용한 곳, 분위기 좋은 카페"
    headcount    : int          기본 4

출력: scenario dict (ranker.rank() + report.generate_report() 바로 전달 가능)
"""

from __future__ import annotations

import logging
import os
import re

import numpy as np
import requests

logger = logging.getLogger(__name__)

KAKAO_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
_GEOCODE_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

_TYPE_ALIAS: dict[str, str] = {
    "커피": "카페", "회식": "술자리", "미팅": "회의", "모임": "식사",
}
_TYPE_TO_CAT: dict[str, int] = {
    "식사": 0, "카페": 1, "술자리": 2, "회의": 3,
}
_TYPE_TO_BUDGET: dict[str, int] = {
    "식사": 20000, "카페": 8000, "술자리": 25000, "회의": 7000,
}

_EXTRAS_MOOD_MAP: dict[str, str] = {
    "조용": "mood_quiet",
    "전망": "mood_quiet",
    "뷰": "mood_quiet",
    "단체": "mood_group",
    "회식": "mood_group",
    "분위기": "mood_vibe",
    "감성": "mood_vibe",
    "인테리어": "mood_vibe",
    "가성비": "mood_budget",
    "저렴": "mood_budget",
    "합리": "mood_budget",
    "프라이빗": "mood_private",
    "개인실": "mood_private",
    "예약": "mood_private",
}

_KW_SLOTS: dict[str, str] = {
    "점심": "점심", "오전": "점심", "아침": "점심",
    "저녁": "저녁", "오후": "저녁", "밤": "저녁",
    "심야": "심야", "자정": "심야", "새벽": "심야",
}

_HOUR_RE = re.compile(r"(\d{1,2})\s*[시:]")

_DEFAULT_CENTER = (37.5665, 126.9780)  # 서울시청


def _geocode(location: str) -> tuple[float, float] | None:
    """Kakao 키워드 검색 → (lat, lng). API 키 없거나 실패 시 None."""
    if not KAKAO_API_KEY or not location:
        return None
    try:
        r = requests.get(
            _GEOCODE_URL,
            headers={"Authorization": f"KakaoAK {KAKAO_API_KEY}"},
            params={"query": location, "size": 1},
            timeout=3,
        )
        r.raise_for_status()
        docs = r.json().get("documents", [])
        if docs:
            return float(docs[0]["y"]), float(docs[0]["x"])
    except Exception as e:
        logger.warning(f"지오코딩 실패 ({location}): {e}")
    return None


def _infer_time_slot(date_time: str | None) -> str:
    """date_time 자유 텍스트 → '점심'/'저녁'/'심야'."""
    if not date_time:
        return "저녁"
    dt_lower = date_time.lower()
    for kw, slot in _KW_SLOTS.items():
        if kw in dt_lower:
            return slot
    m = _HOUR_RE.search(date_time)
    if m:
        hour = int(m.group(1))
        if hour < 12:
            return "점심"
        if hour < 22:
            return "저녁"
        return "심야"
    return "저녁"


def _extract_moods(extras: str | None) -> list[str]:
    """extras 자유 텍스트에서 mood 키워드 추출 (중복 제거)."""
    if not extras:
        return []
    found: set[str] = set()
    for kw, mood in _EXTRAS_MOOD_MAP.items():
        if kw in extras:
            found.add(mood)
    return list(found)


def _make_participants(center_lat: float, center_lng: float, headcount: int) -> list[dict]:
    """headcount 기반 더미 참여자 좌표 (center ± ~2km)."""
    import random as _rng
    # seed 없이 매 요청마다 다른 분산
    return [
        {
            "lat": center_lat + _rng.uniform(-0.018, 0.018),
            "lng": center_lng + _rng.uniform(-0.022, 0.022),
        }
        for _ in range(max(2, headcount))
    ]


def parse_form(
    date_time: str | None = None,
    location: str | None = None,
    meeting_type: str = "식사",
    extras: str | None = None,
    headcount: int = 4,
) -> dict:
    """폼 입력 → scenario dict.

    반환값은 ranker.rank(candidates, scenario)와 report.generate_report(ranked, scenario)에 바로 전달 가능.
    내부 전용 키(_date_time, _extras, _headcount)는 report에서 디스플레이용으로 사용.
    """
    mt = _TYPE_ALIAS.get(meeting_type, meeting_type)
    if mt not in _TYPE_TO_CAT:
        mt = "식사"

    time_slot = _infer_time_slot(date_time)

    coords = _geocode(location) if location else None
    if coords:
        center_lat, center_lng = coords
        location_specified = True
        location_name = location
    else:
        center_lat, center_lng = _DEFAULT_CENTER
        location_specified = False
        location_name = None
        if location:
            logger.warning(f"지오코딩 실패, 서울시청 기본값 사용: {location}")

    participants = _make_participants(center_lat, center_lng, headcount)

    if location_specified:
        effective_lat, effective_lng = center_lat, center_lng
    else:
        effective_lat = float(np.mean([p["lat"] for p in participants]))
        effective_lng = float(np.mean([p["lng"] for p in participants]))

    return {
        "purpose": mt,
        "purpose_cat": _TYPE_TO_CAT[mt],
        "budget": _TYPE_TO_BUDGET[mt],
        "moods": _extract_moods(extras),
        "time_slot": time_slot,
        "participants": participants,
        "center_lat": center_lat,
        "center_lng": center_lng,
        "location_specified": location_specified,
        "location_name": location_name,
        "effective_center_lat": effective_lat,
        "effective_center_lng": effective_lng,
        # report 디스플레이용
        "_date_time": date_time,
        "_extras": extras,
        "_headcount": headcount,
    }
