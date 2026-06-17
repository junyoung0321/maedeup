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
    # 기본 (해결점 O)
    r"안\s*[돼되]|못\s*가|못\s*해|힘들|어려워|어렵다|어렵겠|"
    r"불가능|패스|빠질|곤란|선약|일정.*있어|일정.*잡혀|"
    # demo-stab BE-2 보강 (시연 ACT 2 발언 직접 매칭): MT/본가/쉬고 싶다/약속 있다/건너뛰
    r"MT\b|본가|쉬고\s*싶|약속\s*있|건너뛰"
)


def _resolve_place_hint(state: GraphState) -> str:
    """F5 4-step 분기 (§6.17, PR-V1.5):

    1. state["place_hint"] (이미 명시된 값) — fast-path 호환.
    2. default_place_hint — 그룹 다수결 (recommendations/refresh 라우트가 주입).
    3. requester_home_base — 발화자 본인 home_base (group이 비었을 때 fallback).
    4. creator_home_base — 방장의 home_base (PR-Z1 이전 기본).
    5. None ("") — place_recommendation 노드가 검색 건너뜀.

    Spec §6.17 (F5)의 의도: 선호 장소 다수결 → 발화자 → 방장 → None.
    state 키 매핑:
      - "default_place_hint": 라우트가 미리 계산한 group consensus (preferred_location).
      - "requester_home_base": PR-Z1 refresh 라우트가 발화자별 lookup해서 주입.
      - "creator_home_base": (legacy) 방장 home_base. 일부 entry point가 주입.
    """
    # Step 1: 이미 추출된 place_hint가 있으면 사용 (entity_extraction이 채워둔 값).
    place_hint = state.get("place_hint")
    if isinstance(place_hint, str) and place_hint.strip():
        return place_hint.strip()

    # Step 2: 다수결 default_place_hint (그룹 선호 — refresh 라우트 또는 preferences 헬퍼가 주입).
    default_place_hint = state.get("default_place_hint")
    if isinstance(default_place_hint, str) and default_place_hint.strip():
        resolved = default_place_hint.strip()
        state["place_hint"] = resolved
        return resolved

    # Step 3: 발화자 home_base (PR-Z1, requester_home_base).
    requester_home = state.get("requester_home_base")
    if isinstance(requester_home, str) and requester_home.strip():
        resolved = requester_home.strip()
        state["place_hint"] = resolved
        return resolved

    # Step 4: 방장 home_base (legacy).
    creator_home = state.get("creator_home_base")
    if isinstance(creator_home, str) and creator_home.strip():
        resolved = creator_home.strip()
        state["place_hint"] = resolved
        return resolved

    # Step 5: 셋 다 없음 → 검색 skip.
    return ""


def _detect_cuisine_type(text: str) -> list[str]:
    """사용자 메시지에서 cuisine 의도 추출. 매칭된 모든 cuisine을 list로 반환.

    PR-V1.5 / S18 / §6.16 — 다중 cuisine 충돌 ambiguity 처리.
    이전 시그니처: `str | None` (첫 매칭만). 변경: `list[str]` (전부, 중복 제거).
    호출자는 첫 원소를 default cuisine로 쓰고, len() > 1이면 ambiguity 분기.
    """
    if not text:
        return []
    matched: list[str] = []
    seen: set[str] = set()
    for trigger, cuisine in _CUISINE_TRIGGERS.items():
        if trigger in text and cuisine not in seen:
            seen.add(cuisine)
            matched.append(cuisine)
    return matched


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

    known_hits = [
        (place, text.find(place))
        for place in _WELL_KNOWN_PLACES
        if place in text
    ]
    known_hits = [(place, pos) for place, pos in known_hits if pos >= 0]
    suffix_hits = [
        (match.group(1), match.start(1))
        for match in _KOREAN_PLACE_PATTERN.finditer(text)
    ]

    for suffix, _suffix_pos in sorted(suffix_hits, key=lambda item: (item[1], -len(item[0]))):
        if any(known in suffix for known, _known_pos in known_hits):
            return suffix

    for known, known_pos in sorted(known_hits, key=lambda item: item[1]):
        for suffix, suffix_pos in sorted(suffix_hits, key=lambda item: (item[1], -len(item[0]))):
            gap = suffix_pos - (known_pos + len(known))
            if 0 <= gap <= 4 and suffix != known:
                return f"{known} {suffix}"

    if suffix_hits:
        return sorted(suffix_hits, key=lambda item: (item[1], -len(item[0])))[0][0]

    if known_hits:
        return sorted(known_hits, key=lambda item: item[1])[0][0]

    # 3. Fix 9 (2026-05-14): 자유 텍스트 fallback.
    #    "천안 터미널", "을지로 입구" 같은 미등록 지명을 Kakao Local에 그대로 전달.
    # Fix 13 (2026-05-14): 사람 명사/조사/날짜/식사 키워드도 제거해서 진짜 장소만 남기기.
    #    "내일 친구들이랑 저녁 식사 추천해줘" → "" (cleaned 비면 None) → place_hint 안 박힘.
    cleaned = re.sub(
        # 조사 (Fix 13에서 확장)
        r"(이랑|랑|와|과|에서|에|은|는|이|가|을|를|로|으로|도|만|"
        # 사람 명사 (Fix 13 신규 + 2026-05-16 review 보강)
        r"친구들|친구네|친구|사람들|사람|멤버|동료|동기들|동기|선배|후배|"
        r"우리네|우리|저희|모두|다같이|같이|함께|"
        # 사람 + 장소 합성 (review P1: "친구네집", "우리네집" 같은 noise 차단)
        r"네집|네\s*집|"
        # 시간/날짜 표현 (Fix 13 신규)
        r"내일|모레|오늘|이번|다음|주말|평일|"
        r"오전|오후|저녁|아침|밤|새벽|점심|"
        r"\d+시(?:\s*\d+분)?|\d+월\s*\d+일|"
        # 식사/모임 명사 (Fix 13 신규)
        r"식사|회식|모임|약속|"
        # 의도 동사
        r"근처|주변|쪽|"
        r"추천해줘|추천해|추천|찾아줘|찾아|알려줘|알려|보여줘|보여|"
        # 장소 카테고리 (이미 _PLACE_RE 등에서 처리)
        r"맛집|식당|음식점|카페|술집|먹을곳|먹을\s*곳|"
        r"\s+)",
        "", text
    ).strip()
    # 길이 ≥ 3 (이전 2)로 강화 — 1~2자 noise 차단 (review P1).
    if 3 <= len(cleaned) <= 20:
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
    # PR-V1.5 / S18: cuisine을 list로 추출. 다중 매칭 시 OR query + ambiguity narrator 분기.
    cuisines: list[str] = []
    if meeting_type and meeting_type in _CUISINE_CATEGORY_KEYWORDS:
        cuisines = [meeting_type]
    if not cuisines:
        latest_user_msg = (state.get("trigger_message_text") or "").strip()
        if not latest_user_msg:
            for msg in reversed(state.get("message_records") or []):
                if msg.get("role") == "user" and msg.get("content"):
                    latest_user_msg = str(msg["content"])
                    break
        cuisines = _detect_cuisine_type(latest_user_msg)

    cuisine = cuisines[0] if cuisines else None
    # S18: 다중 cuisine 발화 → OR query로 Kakao 검색 (두 종류 모두 후보로).
    if len(cuisines) >= 2:
        query = f"{place_hint} {' '.join(cuisines)}".strip()
    elif cuisine:
        query = f"{place_hint} {cuisine}".strip()
    else:
        query = f"{place_hint} {meeting_type}".strip()

    # PR-V1.5 / S18: cuisine list를 state에 캐시 → place_recommendation 노드가
    # narrator 분기에 사용 (한식·일식 모두 추천 중이에요 ...).
    state["detected_cuisines"] = cuisines

    place_coord = state.get("place_coord") or {}
    documents = await search_keyword(
        query,
        x=place_coord.get("x"),
        y=place_coord.get("y"),
        radius=2000 if place_coord.get("x") and place_coord.get("y") else None,
    )
    # PR-V1.5 / §6.15: Kakao 응답 정상 0건이면 flag (장애와 구분, F7).
    state["place_search_empty"] = not documents

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
            # PR-V1.5 / S20 (Q4=A): 점수 통합 공식 0.4·ML + 0.3·Gemini + 0.3·거리.
            # distance_score는 항상 채우고, ML/Gemini는 호출자(place_recommendation)가 박음.
            "distance_score": round(distance_score, 2),
        })
    # 거리 가까운 순으로 정렬 (Gemini 스코어링에서 재정렬됨)
    results.sort(key=lambda p: p["distance_m"] if p["distance_m"] > 0 else 99999)

    # 해결점 A5-3 후처리: cuisine 카테고리로 필터. 0개면 원본 fallback (UX 빈 카드 방지).
    # PR-V1.5 / S18: 다중 cuisine이면 union 필터.
    if cuisines and results:
        union: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for c in cuisines:
            for p in _filter_places_by_cuisine(results, c):
                pid = str(p.get("place_id", ""))
                if pid and pid in seen_ids:
                    continue
                seen_ids.add(pid)
                union.append(p)
        if union:
            logger.info(
                "[KAKAO] cuisine filter %s: %d → %d",
                "+".join(cuisines), len(results), len(union),
            )
            # PR-V1.5 / §6.15: rejected_places 필터 (검색 단계).
            return _filter_out_rejected_places(union, state.get("rejected_places") or [])
        logger.info(
            "[KAKAO] cuisine filter %s yielded 0, using unfiltered (%d)",
            "+".join(cuisines), len(results),
        )

    # PR-V1.5 / §6.15: rejected_places 필터.
    return _filter_out_rejected_places(results, state.get("rejected_places") or [])


def _filter_out_rejected_places(
    places: list[dict[str, Any]],
    rejected_places: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """PR-V1.5 / §6.15 — 거부 누적된 장소를 결과에서 제거.

    매칭 기준: place 카드의 name/address/category 중 하나라도 거부 키워드를
    포함하면 제외. 사용자가 "강남 말고"라고 했으면 name/address에 "강남"이
    들어간 모든 후보 제거.
    """
    if not rejected_places:
        return places
    rejected_keywords: list[str] = []
    for item in rejected_places:
        place = item.get("place") if isinstance(item, dict) else None
        if isinstance(place, str) and place.strip():
            rejected_keywords.append(place.strip())
    if not rejected_keywords:
        return places

    out: list[dict[str, Any]] = []
    for p in places:
        haystack = " ".join([
            str(p.get("name", "")),
            str(p.get("address", "")),
            str(p.get("category", "")),
        ])
        if any(kw in haystack for kw in rejected_keywords):
            continue
        out.append(p)
    return out
