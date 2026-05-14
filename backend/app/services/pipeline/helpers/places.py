"""한국 지명 + cuisine 키워드 + 패턴 매칭 + Kakao 검색 헬퍼.

원본 위치: langgraph_pipeline.py 라인 436~456 (_resolve_place_hint),
  959~1066 (_WELL_KNOWN_PLACES, _KOREAN_PLACE_PATTERN, _CUISINE_TRIGGERS,
  _CUISINE_CATEGORY_KEYWORDS, _PLACE_INTENT_PATTERN, _OTHER_ENTITY_SIGNAL_PATTERN,
  _REJECT_SIGNAL_PATTERN, _detect_cuisine_type, _filter_places_by_cuisine,
  _extract_korean_place_keyword), 1239~1248 (_resolve_place_coord),
  2320~2326 (_contains_disliked_keyword), 2363~2439 (search_place).

Phase 2 + 4.2 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

조정 메모 (v2 §3.17 대비):
  - search_place는 v2 계획서에서 nodes/place.py 배정이었으나,
    function_calling 노드와 place_recommendation 노드 양쪽에서 호출되어
    helpers/places.py로 이동 (노드 간 import 회피).

의존:
  - kakao_maps.search_address, search_keyword
  - state.GraphState (TYPE_CHECKING only — runtime import 회피 위해)
"""
from __future__ import annotations

import logging
import re
from typing import Any, TYPE_CHECKING

from app.services.kakao_maps import search_address, search_keyword

if TYPE_CHECKING:
    from app.services.pipeline.state import GraphState

logger = logging.getLogger(__name__)


# 한국 지명 추출을 위한 잘 알려진 지역명
# Fix 9 (2026-05-14): 광역시 + 주요 도시 확장 (천안, 청주, 광주, 울산, 제주 등).
_WELL_KNOWN_PLACES = [
    "강남", "홍대", "건대", "이태원", "명동", "합정", "신촌", "연남", "망원",
    "성수", "잠실", "여의도", "광화문", "종로", "을지로", "혜화", "대학로",
    "압구정", "청담", "삼성", "선릉", "역삼", "서초", "방배", "사당",
    "신림", "구로", "영등포", "용산", "마포", "서울숲", "왕십리", "한양대",
    "동대문", "남대문", "북촌", "삼청", "안국", "경복궁", "이수", "노량진",
    "가산", "판교", "분당", "일산", "수원", "인천", "부산", "대구", "대전",
    # Fix 9: 광역시 + 주요 도시 보강
    "천안", "청주", "광주", "울산", "제주", "춘천", "포항", "전주", "원주",
    "안산", "안양", "성남", "용인", "고양", "파주", "김포", "의정부", "남양주",
]

# 한국 지명 패턴: XX동, XX구, XX역, XX로, XX길, XX리, XX면, XX읍
_KOREAN_PLACE_PATTERN = re.compile(
    r'([가-힣]{1,10}(?:동|구|역|로|길|리|면|읍|시|군|산|공원|숲))'
)

# 해결점 A5-1: cuisine 의도 → fast-path에서 meeting_type set + Kakao 검색 query 강제 + 응답 카테고리 후처리.
# 첫 매칭이 우선이라 longer-key first 정렬로 컴파일 시 보강.
_CUISINE_TRIGGERS: dict[str, str] = {
    "한정식": "한식", "고깃집": "한식", "삼겹살": "한식", "비빔밥": "한식",
    "떡볶이": "분식", "김밥": "분식",
    "한식": "한식", "국밥": "한식", "찌개": "한식", "불고기": "한식", "냉면": "한식", "백반": "한식",
    "중식": "중식", "중국집": "중식", "짜장": "중식", "짬뽕": "중식", "마라": "중식",
    "일식": "일식", "초밥": "일식", "스시": "일식", "라멘": "일식", "돈카츠": "일식", "우동": "일식",
    "이탈리안": "양식", "이태리": "양식", "파스타": "양식", "스테이크": "양식", "피자": "양식",
    "양식": "양식",
    "분식": "분식",
    "베이커리": "카페", "브런치": "카페", "디저트": "카페",
    "카페": "카페", "커피": "카페",
    "이자카야": "주점", "포차": "주점", "술집": "주점",
    "주점": "주점", "호프": "주점",
}

# Kakao category_name (예: "음식점 > 한식 > 국밥") 후처리 필터 키워드.
_CUISINE_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "한식": ["한식", "한정식", "국밥", "찌개", "고깃집", "쌈밥", "비빔밥", "국수",
             "냉면", "백반", "삼겹살", "불고기", "곱창", "전골", "구이", "탕"],
    "중식": ["중식", "중국집", "딤섬", "마라"],
    "일식": ["일식", "초밥", "라멘", "돈카츠", "우동", "사시미", "스시"],
    "양식": ["양식", "이탈리안", "스테이크", "파스타", "피자", "프렌치"],
    "분식": ["분식", "떡볶이", "김밥"],
    "카페": ["카페", "커피", "디저트", "베이커리", "브런치"],
    "주점": ["주점", "술집", "이자카야", "포차", "호프", "바", "와인"],
}

# Place 의도 키워드 (cuisine 없어도 fast-path 진입 허용).
# 해결점 A5-1 보강 (2026-05-07): "갈만한", "어딘가", "알려" 등 자연어 표현 추가.
_PLACE_INTENT_PATTERN = re.compile(
    r"맛집|추천|식당|음식점|예약|있는데|어디|놀러|가볼|"
    r"갈\s*만|갈만|먹을|먹기|어디서|어딘가|알려"
)

# Place fast-path gate: 날짜/인원/시간 등 다른 entity 신호가 있으면 Gemini 추출에 위임.
# 시연 단순 케이스("강남 한식 맛집 추천")만 fast-path, 복합 케이스는 정상 흐름.
_OTHER_ENTITY_SIGNAL_PATTERN = re.compile(
    r"\d+\s*명|\d+\s*시|\d+\s*분|\d+\s*월|\d+\s*일|"
    r"월요일|화요일|수요일|목요일|금요일|토요일|일요일|"
    r"주말|평일|내일|모레|오늘|이번\s*주|다음\s*주|이번\s*주말|다음\s*주말|"
    r"아침|점심|저녁|밤|새벽|오전|오후"
)

# 해결점 O: shortcut gate. context에 거부/불가능 키워드가 있으면 정규식 단축 경로를
# 통과시키지 않고 Gemini 추출을 강제 — _pattern_extract_entities는 rejected_dates와
# conflict_detected를 만들지 않으므로 단축이 hit하면 후속 vote_card 후보 필터에서
# 거부 날짜가 누락되는 사각지대가 생김 (audit-findings.md 해결점 O).
# 패턴은 entity_extraction Gemini prompt의 "거부 키워드 예시"와 동일 (line 1183).
_REJECT_SIGNAL_PATTERN = re.compile(
    r"안\s*[돼되]|못\s*가|못\s*해|힘들|어려워|어렵다|어렵겠|"
    r"불가능|패스|빠질|곤란|선약|일정.*있어|일정.*잡혀"
)


def _resolve_place_hint(state: GraphState) -> str:
    place_hint = state.get("place_hint")
    if isinstance(place_hint, str) and place_hint.strip():
        return place_hint.strip()

    # Fix 10 (2026-05-14): direct_request로 place 요청한 경우 "서울 강남" default 강제 적용 금지.
    # 사용자가 명시했는데 못 추출한 거면 default보다 차라리 발화자 home_base 또는 skip.
    # auto-trigger (stalemate/conclusion 등)는 영향 없음 — direct_request 한정.
    trigger_reason = state.get("trigger_reason")
    direct_kind = state.get("direct_request_kind")
    if trigger_reason == "direct_request" and direct_kind in ("place", "schedule+place"):
        requester_hb = state.get("requester_home_base")
        if isinstance(requester_hb, str) and requester_hb.strip():
            resolved = requester_hb.strip()
            state["place_hint"] = resolved
            return resolved
        return ""  # 빈 string → place_recommendation에서 skip (default 강제 안 함)

    default_place_hint = state.get("default_place_hint")
    if isinstance(default_place_hint, str) and default_place_hint.strip():
        resolved = default_place_hint.strip()
    else:
        # 방장의 home_base가 있으면 사용, 없으면 빈 문자열 반환
        # (빈 문자열이면 place_recommendation 노드에서 검색을 건너뜀)
        home_base = state.get("creator_home_base")
        if isinstance(home_base, str) and home_base.strip():
            resolved = home_base.strip()
        else:
            resolved = ""

    if resolved:
        state["place_hint"] = resolved
    return resolved


def _detect_cuisine_type(text: str) -> str | None:
    """사용자 메시지에서 cuisine 의도 추출. 매칭되면 cuisine ID, 없으면 None."""
    if not text:
        return None
    for trigger, cuisine in _CUISINE_TRIGGERS.items():
        if trigger in text:
            return cuisine
    return None


def _filter_places_by_cuisine(
    places: list[dict[str, Any]],
    cuisine: str,
) -> list[dict[str, Any]]:
    """Kakao 응답 category로 cuisine 필터. 호출자는 결과 0개 시 원본 fallback 결정."""
    keywords = _CUISINE_CATEGORY_KEYWORDS.get(cuisine)
    if not keywords:
        return list(places)
    return [p for p in places if any(kw in str(p.get("category", "")) for kw in keywords)]


def _extract_korean_place_keyword(text: str) -> str | None:
    """사용자 메시지에서 한국 지명 키워드를 추출합니다."""
    if not text:
        return None

    # 1. 잘 알려진 지역명 매칭 (우선순위 높음)
    for place in _WELL_KNOWN_PLACES:
        if place in text:
            return place

    # 2. 한국 지명 패턴 매칭 (XX동, XX역, XX구 등)
    matches = _KOREAN_PLACE_PATTERN.findall(text)
    if matches:
        # 가장 긴 매칭을 반환 (더 구체적인 지명일 가능성)
        return max(matches, key=len)

    # 3. Fix 9 (2026-05-14): 자유 텍스트 fallback.
    #    "천안 터미널", "을지로 입구" 같은 미등록 지명을 Kakao Local에 그대로 전달.
    #    의도/조사 단어 제거 후 남는 명사 덩어리가 2~20자면 fallback.
    cleaned = re.sub(
        r"(근처|주변|쪽|에서|에|는|이|가|을|를|"
        r"추천해줘|추천해|추천|찾아줘|알려줘|보여줘|"
        r"맛집|식당|음식점|카페|술집|먹을곳|먹을\s*곳|"
        r"\s+)",
        "", text
    ).strip()
    if 2 <= len(cleaned) <= 20:
        return cleaned

    return None


async def _resolve_place_coord(keyword: str | None) -> dict[str, str] | None:
    if not keyword:
        return None
    place_coord = await search_address(keyword)
    if not place_coord:
        return None
    if not place_coord.get("x") or not place_coord.get("y"):
        return None
    return place_coord


def _contains_disliked_keyword(category: str, disliked_foods: list[str]) -> str | None:
    normalized_category = str(category or "").strip().lower()
    for keyword in disliked_foods:
        normalized_keyword = str(keyword).strip().lower()
        if normalized_keyword and normalized_keyword in normalized_category:
            return str(keyword).strip()
    return None


async def search_place(state: GraphState) -> list[dict[str, Any]]:
    """카카오맵 API로 장소 후보를 검색합니다."""
    place_hint = _resolve_place_hint(state)
    meeting_type = state.get("meeting_type") or ""
    # place_suggestion intent에서 meeting_type이 없으면 기본 "맛집" 추가
    if not meeting_type and state.get("intent") == "place_suggestion":
        meeting_type = "맛집"

    # 해결점 A5-3: cuisine 의도 식별. meeting_type 우선, 없으면 trigger/latest user msg에서.
    cuisine = meeting_type if meeting_type in _CUISINE_CATEGORY_KEYWORDS else None
    if not cuisine:
        latest_user_msg = (state.get("trigger_message_text") or "").strip()
        if not latest_user_msg:
            for msg in reversed(state.get("message_records") or []):
                if msg.get("role") == "user" and msg.get("content"):
                    latest_user_msg = str(msg["content"])
                    break
        cuisine = _detect_cuisine_type(latest_user_msg)

    # query 강제: cuisine이 있으면 cuisine 단어를 query에 명시.
    if cuisine:
        query = f"{place_hint} {cuisine}".strip()
    else:
        query = f"{place_hint} {meeting_type}".strip()

    place_coord = state.get("place_coord") or {}
    documents = await search_keyword(
        query,
        x=place_coord.get("x"),
        y=place_coord.get("y"),
        radius=2000 if place_coord.get("x") and place_coord.get("y") else None,
    )

    results = []
    for doc in documents:
        distance_m = int(doc.get("distance") or 0)
        # 거리 기반 기본 점수: 500m 이내 1.0, 2km이면 0.5, 5km+ 이면 0.2
        if distance_m <= 0:
            distance_score = 0.7  # 거리 정보 없음
        elif distance_m <= 500:
            distance_score = 1.0
        elif distance_m <= 2000:
            distance_score = max(0.5, 1.0 - (distance_m - 500) / 3000)
        else:
            distance_score = max(0.2, 0.5 - (distance_m - 2000) / 10000)

        results.append({
            "place_id": doc.get("id", ""),
            "name": doc.get("place_name", ""),
            "address": doc.get("road_address_name") or doc.get("address_name", ""),
            "phone": doc.get("phone", ""),
            "url": doc.get("place_url", ""),
            "x": doc.get("x", ""),
            "y": doc.get("y", ""),
            "category": doc.get("category_name", ""),
            "distance_m": distance_m,
            "max_headcount": 20,  # 카카오 API는 수용인원 미제공 → 기본값
            "score": round(distance_score, 2),
        })
    # 거리 가까운 순으로 정렬 (Gemini 스코어링에서 재정렬됨)
    results.sort(key=lambda p: p["distance_m"] if p["distance_m"] > 0 else 99999)

    # 해결점 A5-3 후처리: cuisine 카테고리로 필터. 0개면 원본 fallback (UX 빈 카드 방지).
    if cuisine and results:
        filtered = _filter_places_by_cuisine(results, cuisine)
        if filtered:
            logger.info(
                "[KAKAO] cuisine filter %s: %d → %d",
                cuisine, len(results), len(filtered),
            )
            return filtered
        logger.info(
            "[KAKAO] cuisine filter %s yielded 0, using unfiltered (%d)",
            cuisine, len(results),
        )

    return results
