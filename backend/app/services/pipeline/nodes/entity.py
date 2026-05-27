"""entity_extraction 노드 + pattern/context 추출 헬퍼.

원본 위치: langgraph_pipeline.py 라인 1069~1137 (_pattern_extract_entities),
  1140~1236 (_extract_entities_from_context), 2679~3026 (entity_extraction).

Phase 4 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.
가장 큰 노드 함수 (entity_extraction 349줄).

의존:
  - state.GraphState, _serialize_context
  - helpers.messaging: _has_node_error, _handle_node_exception
  - helpers.dates: _is_iso_date_hint, _resolve_rejected_date,
    _expand_date_hint, _parse_natural_date
  - helpers.places: _extract_korean_place_keyword, _detect_cuisine_type,
    _resolve_place_coord, _PLACE_INTENT_PATTERN, _OTHER_ENTITY_SIGNAL_PATTERN,
    _REJECT_SIGNAL_PATTERN
  - helpers.slot_state: _update_slot_state
  - helpers.json_extract: _extract_json_object
  - constants.KST
  - app.services.gemini.call_gemini
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.observability.snapshot import dump
from app.services.llm import call_llm
from app.services.pipeline.constants import KST
from app.services.pipeline.helpers.dates import (
    _expand_date_hint,
    _is_iso_date_hint,
    _parse_natural_date,
    _resolve_rejected_date,
)
from app.services.pipeline.helpers.json_extract import _extract_json_object
from app.services.pipeline.helpers.messaging import (
    _handle_node_exception,
    _has_node_error,
)
from app.services.pipeline.helpers.places import (
    _OTHER_ENTITY_SIGNAL_PATTERN,
    _PLACE_INTENT_PATTERN,
    _REJECT_SIGNAL_PATTERN,
    _detect_cuisine_type,
    _extract_korean_place_keyword,
    _resolve_place_coord,
)
from app.services.pipeline.helpers.slot_state import _update_slot_state
from app.services.pipeline.state import GraphState, _serialize_context

logger = logging.getLogger(__name__)


def _pattern_extract_entities(context: str) -> dict[str, Any]:
    """패턴 기반으로 엔티티를 추출합니다. Gemini 호출 없이 빠르게 처리.

    PR-V1.5 / S16 (§6.15): rejected_places 누적용 패턴.
    """
    result: dict[str, Any] = {
        "date_hint": None,
        "date_hints": [],
        "place_hint": None,
        "headcount": None,
        "meeting_type": None,
        # PR-V1.5 / S16: 거부 발화에서 추출한 장소 list. 형식: [{"place": "강남", "reason": None, "user": None}]
        "rejected_places": [],
    }
    if not context:
        return result

    # 장소 추출
    place = _extract_korean_place_keyword(context)
    if place:
        result["place_hint"] = place

    # 날짜 키워드 추출 (모든 날짜 수집)
    now_kst = datetime.now(KST)
    all_date_hints: list[str] = []

    # 요일 패턴 (여러 개 추출): 월요일, 화요일, ...
    weekday_matches = re.findall(r'[월화수목금토일]요일', context)
    if weekday_matches:
        all_date_hints.extend(weekday_matches)

    # M월 D일 패턴 (여러 개 추출)
    md_matches = re.finditer(r'(\d{1,2})월\s*(\d{1,2})일', context)
    for m in md_matches:
        all_date_hints.append(f"{now_kst.year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}")

    # D일 패턴 (월 없이, M월D일 매칭이 없을 때만)
    if not all_date_hints:
        day_matches = re.findall(r'(\d{1,2})일', context)
        for d in day_matches:
            all_date_hints.append(f"{d}일")

    # 상대적 날짜 키워드
    relative_patterns = [
        (r'다음\s*주', "다음주"),
        (r'이번\s*주', "이번주"),
        (r'내일', "내일"),
        (r'모레', "모레"),
    ]
    for pattern, label in relative_patterns:
        if re.search(pattern, context):
            if label not in all_date_hints:
                all_date_hints.append(label)

    # 중복 제거하면서 순서 유지
    seen: set[str] = set()
    unique_hints: list[str] = []
    for h in all_date_hints:
        if h not in seen:
            seen.add(h)
            unique_hints.append(h)
    all_date_hints = unique_hints

    if all_date_hints:
        result["date_hint"] = all_date_hints[0]
        result["date_hints"] = all_date_hints

    # 인원 추출
    headcount_match = re.search(r'(\d+)\s*명', context)
    if headcount_match:
        result["headcount"] = int(headcount_match.group(1))

    # 모임 종류 추출
    _MEETING_TYPE_KEYWORDS = ["맛집", "카페", "술집", "고기", "회식", "저녁", "점심", "브런치", "치킨", "피자", "스터디"]
    for keyword in _MEETING_TYPE_KEYWORDS:
        if keyword in context:
            result["meeting_type"] = keyword
            break

    # PR-V1.5 / S16 (§6.15): 거부 장소 패턴 추출.
    # 예: "강남 말고", "홍대는 별로", "역삼 빼고", "이태원 싫어".
    # _WELL_KNOWN_PLACES와 _KOREAN_PLACE_PATTERN 양쪽 모두 검사.
    from app.services.pipeline.helpers.places import (
        _WELL_KNOWN_PLACES, _KOREAN_PLACE_PATTERN,
    )
    rejected_place_keywords: list[str] = []
    # _WELL_KNOWN_PLACES 매칭
    for place in _WELL_KNOWN_PLACES:
        # 거부 패턴: "{place} 말고", "{place}는 별로", "{place} 빼고", "{place} 싫"
        pattern = rf"{re.escape(place)}\s*(?:말고|은\s*별로|는\s*별로|빼고|싫)"
        if re.search(pattern, context):
            rejected_place_keywords.append(place)
    # _KOREAN_PLACE_PATTERN 매칭 (XX동, XX역 등)
    for m in _KOREAN_PLACE_PATTERN.finditer(context):
        place = m.group(1)
        if place in rejected_place_keywords:
            continue
        tail_start = m.end()
        tail = context[tail_start:tail_start + 10]
        if re.match(r"\s*(?:말고|은\s*별로|는\s*별로|빼고|싫)", tail):
            rejected_place_keywords.append(place)

    seen_rp: set[str] = set()
    rejected_places: list[dict[str, Any]] = []
    for p in rejected_place_keywords:
        if p in seen_rp:
            continue
        seen_rp.add(p)
        rejected_places.append({"place": p, "reason": None, "user": None})
    if rejected_places:
        result["rejected_places"] = rejected_places

    return result


async def _extract_entities_from_context(state: GraphState) -> dict[str, Any]:
    context = _serialize_context(state) or ""

    # --- OPTIMIZATION: Try pattern-based extraction first ---
    pattern_result = _pattern_extract_entities(context)
    # 해결점 O: 거부/불가능 키워드가 context에 있으면 정규식 shortcut 차단.
    # _pattern_extract_entities는 rejected_dates/conflict 정보를 못 만들기 때문.
    has_reject_signal = bool(_REJECT_SIGNAL_PATTERN.search(context))
    if has_reject_signal:
        logger.info("[OPT] reject signal in context — forcing Gemini extraction (skip pattern shortcut)")
    else:
        # If we got multiple date hints from patterns, skip Gemini (vote scenario)
        if len(pattern_result.get("date_hints") or []) >= 2:
            logger.info("[OPT] Multiple date hints found by pattern matching, skipping Gemini")
            return pattern_result
        # If we got at least date+place from patterns, skip Gemini
        if pattern_result.get("date_hint") and pattern_result.get("place_hint"):
            logger.info("[OPT] Entity extraction resolved by pattern matching, skipping Gemini")
            return pattern_result

    today_kst = datetime.now(KST).strftime("%Y-%m-%d")
    prompt = (
        "당신은 매듭 AI입니다. 한국인들의 모임 일정을 돕는 어시스턴트입니다.\n"
        f"오늘 날짜는 {today_kst}입니다.\n"
        "대화에서 모임 조율에 필요한 정보를 추출하세요.\n"
        "또한, 멤버들 간의 의견 충돌(교착)도 감지하세요.\n"
        "아래 스키마 그대로 JSON만 반환하세요:\n"
        "{"
        '"date_hint": string | null, '
        '"date_hints": [string] | null, '
        '"place_hint": string | null, '
        '"headcount": number | null, '
        '"meeting_type": string | null, '
        '"conflict_detected": boolean, '
        '"conflict_type": "date" | "place" | "time" | null, '
        '"conflict_options": [string] | null, '
        '"conflict_users": [string] | null, '
        '"rejected_dates": [{"date": string, "user": string | null, "reason": string | null}] | null, '
        '"rejected_places": [{"place": string, "user": string | null, "reason": string | null}] | null'
        "}\n\n"
        "date_hint: 첫 번째 날짜 표현. 가능하면 YYYY-MM-DD 형식으로 변환, 범위면 "
        "'YYYY-MM-DD~YYYY-MM-DD'\n"
        "  날짜 표현 예시:\n"
        '  - "다음주 월요일" → next_monday (date_hint)\n'
        '  - "차주 월요일" → next_monday (date_hint, "차주" = "다음주" 동의어)\n'
        '  - "그 다음주 화요일" → next_next_tuesday (date_hint, 오늘 기준 2주 후)\n'
        '  - "다다음주 수요일" → next_next_wednesday (date_hint, 오늘 기준 2주 후)\n'
        "date_hints: 여러 날짜가 선택지로 제시된 경우 모든 날짜 표현의 배열. "
        "예: '목요일에 볼까 금요일에 볼까' → [\"목요일\", \"금요일\"]\n"
        "place_hint: 구체적 한국 지명(동/구/역/로/길 등)이나 잘 알려진 지역명"
        "(강남, 홍대, 건대, 이태원, 명동, 합정, 신촌 등)이 **실제로 명시된 경우에만** "
        "추출하세요. 명확한 장소 단어가 없거나 재시도 지시어/모호한 표현이면 "
        "반드시 null을 반환하세요. 억지로 뽑지 말 것.\n"
        "  긍정 예시 (추출):\n"
        '  - "역삼동에서 만나자" → place_hint: "역삼동"\n'
        '  - "홍대 맛집 추천해줘" → place_hint: "홍대"\n'
        '  - "강남역 근처 카페" → place_hint: "강남역"\n'
        '  - "서울숲 쪽에서 보자" → place_hint: "서울숲"\n'
        '  - "을지로 맛집" → place_hint: "을지로"\n'
        "  부정 예시 (반드시 null — 장소 아님):\n"
        '  - "다시 추천해줘" → null (재시도 지시어, 장소 아님)\n'
        '  - "안되는 날짜 고려해서 다시 해봐" → null\n'
        '  - "아무데나 괜찮아" → null (모호, 지역 미지정)\n'
        '  - "어디든 상관없어" → null\n'
        '  - "또 해봐" / "한번 더" → null (재시도)\n'
        '  - "그냥 추천해" → null\n'
        "headcount: 예상 인원 수\n"
        "meeting_type: 모임 종류 (맛집, 카페, 술집 등 키워드가 있으면 반영)\n\n"
        "conflict_detected: 대화에서 멤버 간 의견 충돌이 감지되면 true\n"
        "  충돌 예시:\n"
        '  - "나는 목요일이 좋아" + "금요일이 낫지 않아?" → 날짜 충돌\n'
        '  - "강남이 좋겠다" + "홍대가 낫지 않아?" → 장소 충돌\n'
        '  - "점심에 보자" + "저녁이 좋은데" → 시간 충돌\n'
        "  주의: 단순 질문('금요일은 어때?')은 충돌이 아닙니다. "
        "2명 이상이 서로 다른 의견을 명시적으로 표현했을 때만 충돌입니다.\n"
        "conflict_type: 충돌 유형 (date/place/time)\n"
        "conflict_options: 충돌하는 선택지 배열 (예: ['목요일', '금요일'])\n"
        "conflict_users: 충돌하는 사용자 이름 배열 (메시지 발신자 기반, 알 수 없으면 null)\n\n"
        "rejected_dates: 특정 사용자가 명시적으로 거부/불가능을 표현한 날짜 배열.\n"
        f"  - date는 반드시 YYYY-MM-DD 형식. 요일만 언급되면 오늘({today_kst}) 이후 가장 가까운 미래 날짜로 변환.\n"
        "  - user는 메시지 발신자 이름 (모르면 null).\n"
        '  - reason은 거부 이유 (예: "알바", "가족 모임"). 모르면 null.\n'
        '  - 단순 선호 ("금요일이 좋아", "토요일 가능")는 제외. 명시적 거부만 포함.\n'
        "  - 거부 키워드 예: 안 돼, 못 가, 힘들어, 불가능, 어려워, 패스, 어렵다.\n"
        "rejected_places: 특정 사용자가 명시적으로 거부/제외한 장소 배열.\n"
        "  - 형식: [{\"place\": \"강남\", \"user\": str | null, \"reason\": str | null}]\n"
        "  - 거부 패턴: '강남 말고', '홍대는 별로', '역삼 빼고', '이태원 싫어' 등.\n"
        "  - 단순 선호 ('홍대가 좋아')는 제외. 명시적 거부만 포함.\n"
        "  - 추출 못 하면 null 또는 빈 배열.\n"
        "  예시:\n"
        '  - "금요일은 알바 있어서 안 돼" → [{"date": "2026-05-08", "user": "민수", "reason": "알바"}]\n'
        '  - "토요일 가족 모임이라 힘들어" → [{"date": "2026-05-09", "user": "수현", "reason": "가족 모임"}]\n'
        '  - "그날은 좀..." → [] (모호하면 빈 배열)\n\n'
        f"대화 맥락:\n{context or '(empty)'}\n\n"
        "모르면 null로 반환하세요."
    )
    try:
        result = _extract_json_object(await call_llm(prompt, provider=settings.LLM_PROVIDER_FOR_ENTITY))
        if result:
            # Merge date_hints from pattern_result if Gemini didn't return them
            if not result.get("date_hints") and pattern_result.get("date_hints"):
                result["date_hints"] = pattern_result["date_hints"]
            # PR-V1.5 / S16: rejected_places — pattern + Gemini union (Gemini가 못 잡은 well-known 보강).
            gemini_rp = result.get("rejected_places") or []
            pattern_rp = pattern_result.get("rejected_places") or []
            if pattern_rp or gemini_rp:
                merged: list[dict[str, Any]] = []
                seen: set[str] = set()
                for rp in list(gemini_rp) + list(pattern_rp):
                    if not isinstance(rp, dict):
                        continue
                    p = rp.get("place")
                    if not isinstance(p, str) or not p.strip() or p in seen:
                        continue
                    seen.add(p)
                    merged.append({
                        "place": p.strip(),
                        "user": rp.get("user"),
                        "reason": rp.get("reason"),
                    })
                result["rejected_places"] = merged
            return result
    except Exception:
        # BUG-26-4 패턴 재발 방지: pass 로 swallow 하면 NameError 같은 코드 버그가 무음.
        # fallback 동작은 유지하되 traceback 항상 stderr 노출.
        logger.exception("entity extraction Gemini path failed — falling back to pattern result")

    # Gemini 실패 시 패턴 기반 fallback 반환
    return pattern_result


async def entity_extraction(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    dump("node_in", state.get("run_id"), {
        "node": "entity_extraction",
        "status": state.get("status"),
        "trigger_reason": state.get("trigger_reason"),
        "has_card": bool(state.get("maedeup_card_payload") or state.get("vote_card_payload")),
        "message_count": len(state.get("message_records", [])),
    })
    try:
        if _has_node_error(state):
            return state

        pre_extracted = state.get("pre_extracted_signals")
        if isinstance(pre_extracted, dict):
            raw_date_hints = pre_extracted.get("date_hints") or []
            expanded_date_hints: list[str] = []
            seen_iso: set[str] = set()
            for raw in raw_date_hints:
                for iso in _expand_date_hint(raw):
                    if iso not in seen_iso:
                        seen_iso.add(iso)
                        expanded_date_hints.append(iso)
            if not expanded_date_hints:
                for pref in (pre_extracted.get("preferred_dates") or []):
                    if isinstance(pref, dict):
                        for iso in _expand_date_hint(pref.get("date")):
                            if iso not in seen_iso:
                                seen_iso.add(iso)
                                expanded_date_hints.append(iso)
            # Fix#2 (2026-05-20): 과거 날짜 사전 컷 — validation 단계에서 past 필터로
            # valid_remaining이 깎이기 전에 제거해 "no valid free time slots available" 방지.
            today_kst = datetime.now(KST).date()
            before_filter_count = len(expanded_date_hints)
            expanded_date_hints = [d for d in expanded_date_hints if d >= today_kst.isoformat()]
            dropped_count = before_filter_count - len(expanded_date_hints)
            if dropped_count:
                logger.info(
                    "[OPT] _expand_date_hint dropped %d past dates (today=%s)",
                    dropped_count, today_kst.isoformat(),
                )

            if expanded_date_hints:
                logger.info("[DATE_HINTS] Expanded: %s -> %s", raw_date_hints, expanded_date_hints)

            extracted: dict[str, Any] = {
                "date_hint": expanded_date_hints[0] if expanded_date_hints else None,
                "date_hints": expanded_date_hints,
                "place_hint": pre_extracted.get("place_hint"),
                "headcount": pre_extracted.get("headcount"),
                "meeting_type": pre_extracted.get("meeting_type"),
                "parsed_time_hint": pre_extracted.get("parsed_time_hint"),
                "date_is_flexible": bool(pre_extracted.get("date_is_flexible", False)),
                "date_hint_source_text": pre_extracted.get("date_hint_source_text"),
                "preferred_dates": pre_extracted.get("preferred_dates") or [],
                "conflict_detected": bool(pre_extracted.get("conflict_detected", False)),
                "conflict_type": pre_extracted.get("conflict_type"),
                "conflict_options": pre_extracted.get("conflict_options") or [],
                "conflict_users": pre_extracted.get("conflict_users") or [],
                "rejected_dates": pre_extracted.get("rejected_dates") or [],
            }
            state["extracted_entities"] = extracted
            _update_slot_state(state, extracted)

            state["conflict_detected"] = bool(extracted.get("conflict_detected"))
            state["conflict_type"] = extracted.get("conflict_type") if state["conflict_detected"] else None
            state["conflict_options"] = extracted.get("conflict_options") or []
            state["conflict_users"] = extracted.get("conflict_users") or []
            if state["conflict_detected"]:
                logger.info(
                    "[CONFLICT] Pre-extracted: type=%s options=%s users=%s",
                    state["conflict_type"],
                    state["conflict_options"],
                    state["conflict_users"],
                )

            cleaned_rejected = []
            raw_rejected = extracted.get("rejected_dates")
            if isinstance(raw_rejected, list):
                for item in raw_rejected:
                    if not isinstance(item, dict) or not isinstance(item.get("date"), str):
                        continue
                    resolved = _resolve_rejected_date(item.get("date"))
                    if not resolved:
                        continue
                    cleaned_rejected.append({
                        "date": resolved,
                        "user": item.get("user"),
                        "reason": item.get("reason"),
                    })
            state["rejected_dates"] = cleaned_rejected
            if cleaned_rejected and state.get("extracted_entities", {}).get("date_hints"):
                rejected_set = {r["date"] for r in cleaned_rejected if isinstance(r.get("date"), str)}
                current = state["extracted_entities"]["date_hints"]
                filtered = [d for d in current if d not in rejected_set]
                if len(filtered) != len(current):
                    logger.info("[DATE_HINTS] Filtered to exclude rejected: %s -> %s", current, filtered)
                    state["extracted_entities"]["date_hints"] = filtered
                    state["extracted_entities"]["date_hint"] = filtered[0] if filtered else None
                    state["date_hints"] = filtered
                    state["date_hint"] = filtered[0] if filtered else None

                # 해결점 N: 모든 후보가 거부됐으면 flag만 세움.
                # 실제 alternatives는 _slot_filling_stalemate에서 사용자 선호를 보고 생성
                # (다음주 평일/주말 카테고리 매칭 + 거부 set 제외).
                if not filtered:
                    state["expanded_to_next_week"] = True
                    logger.info(
                        "[DATE_HINTS] All candidates rejected, flagging for next-week expansion in slot_filling"
                    )
            # 방어 검증: rejected에 있는 날짜는 conflict_options에서 자동 제거.
            # Gemini가 룰을 어겨 같은 날짜를 양쪽에 넣어도 시스템이 일관성 유지.
            if cleaned_rejected and state.get("conflict_options"):
                rejected_set = {r["date"] for r in cleaned_rejected if isinstance(r.get("date"), str)}
                original_options = state.get("conflict_options") or []
                filtered_options = [o for o in original_options if o not in rejected_set]
                if len(filtered_options) != len(original_options):
                    logger.info(
                        "[CONFLICT] Filtered conflict_options to exclude rejected dates: %s -> %s",
                        original_options, filtered_options,
                    )
                state["conflict_options"] = filtered_options
                # 옵션이 1개 이하로 줄면 conflict_detected를 false로 (mediation 진입 차단)
                if len(filtered_options) < 2:
                    state["conflict_detected"] = False
                    state["conflict_type"] = None
                    state["conflict_options"] = []
                    state["conflict_users"] = []
                    logger.info("[CONFLICT] Suppressed: too few non-rejected options remaining")
            if cleaned_rejected:
                logger.info("[REJECTED_DATES] Pre-extracted: %s", cleaned_rejected)

            # PR-V1.5 / S16: pre-extracted rejected_places 머지.
            raw_rp_pre = pre_extracted.get("rejected_places")
            if isinstance(raw_rp_pre, list) and raw_rp_pre:
                existing_rp = state.get("rejected_places") or []
                seen_rp = {it["place"] for it in existing_rp if isinstance(it, dict) and isinstance(it.get("place"), str)}
                for it in raw_rp_pre:
                    if not isinstance(it, dict):
                        continue
                    p = it.get("place")
                    if not isinstance(p, str) or not p.strip() or p in seen_rp:
                        continue
                    seen_rp.add(p)
                    existing_rp.append({"place": p.strip(), "user": it.get("user"), "reason": it.get("reason")})
                state["rejected_places"] = existing_rp

            place_coord = await _resolve_place_coord(state.get("place_hint"))
            if place_coord:
                state["place_coord"] = place_coord
            state["is_location_first"] = (
                bool(state.get("place_hint"))
                and not bool(state.get("date_hint"))
                and state.get("intent") != "meeting_schedule"
            )
            state["status"] = "entities_extracted"
            logger.info("[TIMING] entity_extraction (pre-extracted): %.2fs", time.monotonic() - _t0)
            return state

        # ── Fast-skip: 해결점 F-3 (2026-05-07). AI 패널 direct_request 경로 전용.
        # _route_from_start가 direct_request에 대해 intent_detection을 스킵하므로 sentinel
        # (intent_detection 내부에서 set)이 안 박힘. 여기서 동일 조건 직접 체크해서
        # Gemini 추출 ~15s 생략. quick_classify가 이미 "place" 분류한 경우만.
        if (
            state.get("trigger_reason") == "direct_request"
            and state.get("direct_request_kind") == "place"
        ):
            latest_msg = (state.get("trigger_message_text") or "").strip()
            if not latest_msg:
                for m in reversed(state.get("message_records") or []):
                    if m.get("role") == "user" and m.get("content"):
                        latest_msg = str(m["content"]).strip()
                        break
            place_kw = _extract_korean_place_keyword(latest_msg)
            # PR-V1.5 / S18: _detect_cuisine_type → list[str]. 첫 매칭만 fast-path에 사용.
            cuisines = _detect_cuisine_type(latest_msg)
            cuisine = cuisines[0] if cuisines else None
            has_place_intent = bool(cuisine) or bool(_PLACE_INTENT_PATTERN.search(latest_msg))
            has_other_entities = bool(_OTHER_ENTITY_SIGNAL_PATTERN.search(latest_msg))
            if place_kw and has_place_intent and not has_other_entities:
                state["intent"] = "place_suggestion"
                state["intent_confidence"] = 0.92
                state["confidence_score"] = 0.92
                state["place_hint"] = place_kw
                if not state.get("meeting_type"):
                    state["meeting_type"] = cuisine or "맛집"
                extracted: dict[str, Any] = {
                    "date_hint": None,
                    "date_hints": [],
                    "place_hint": place_kw,
                    "headcount": None,
                    "meeting_type": state.get("meeting_type"),
                    "parsed_time_hint": None,
                    "date_is_flexible": False,
                    "date_hint_source_text": None,
                }
                state["extracted_entities"] = extracted
                _update_slot_state(state, extracted)
                place_coord = await _resolve_place_coord(place_kw)
                if place_coord:
                    state["place_coord"] = place_coord
                state["is_location_first"] = True
                state["status"] = "entities_extracted"
                logger.info(
                    "[ENTITY] direct_request place fast-skip: place=%s cuisine=%s",
                    place_kw,
                    cuisine or "맛집",
                )
                logger.info(
                    "[TIMING] entity_extraction (direct_request fast-skip): %.2fs",
                    time.monotonic() - _t0,
                )
                return state

        # ── Fast-skip: 해결점 A5-1. intent_detection fast-path가 이번 run에서 직접 채운 경우만.
        # sentinel 키로 검증 — 이전 턴 잔존 place_hint + Gemini 재분류 조합에서 헤드카운트 손실 방지.
        if (
            state.pop("_place_fast_path_this_run", False)
            and state.get("intent") == "place_suggestion"
            and state.get("place_hint")
            and not state.get("date_hint")
        ):
            extracted: dict[str, Any] = {
                "date_hint": None,
                "date_hints": [],
                "place_hint": state["place_hint"],
                "headcount": None,
                "meeting_type": state.get("meeting_type"),
                "parsed_time_hint": None,
                "date_is_flexible": False,
                "date_hint_source_text": None,
            }
            state["extracted_entities"] = extracted
            _update_slot_state(state, extracted)
            place_coord = await _resolve_place_coord(state["place_hint"])
            if place_coord:
                state["place_coord"] = place_coord
            state["is_location_first"] = True
            state["status"] = "entities_extracted"
            logger.info(
                "[ENTITY] place fast-skip: place=%s cuisine=%s",
                state.get("place_hint"),
                state.get("meeting_type"),
            )
            logger.info("[TIMING] entity_extraction (place fast-skip): %.2fs", time.monotonic() - _t0)
            return state

        # ── Fast-skip: 명령형 추천 요청("일정 추천해줘" 등)은 뽑을 엔티티가 없음 → Gemini 호출 생략 (−3~4s).
        # 숫자·월/일·지명 흔적이 없고 짧으면 빈 결과로 처리. 이후 slot_filling에서 선호 데이터가 채움.
        latest_msg = ""
        for m in reversed(state["message_records"]):
            if m.get("role") == "user" and m.get("content"):
                latest_msg = m["content"].strip()
                break
        is_short_cmd = (
            latest_msg
            and len(latest_msg) <= 20
            and not re.search(r"\d", latest_msg)
            and not re.search(r"(월|일|시|분|주말|평일|내일|모레|오늘|다음주|이번주)", latest_msg)
            and not re.search(r"(맛집|카페|식당|근처|역|동\s)", latest_msg)
            and re.search(r"(추천|정리|제안|뽑아|추려)", latest_msg)
        )
        if is_short_cmd:
            logger.info("[ENTITY] fast-skip: short recommendation command, skipping Gemini extraction")
            extracted: dict[str, Any] = {
                "date_hint": None,
                "date_hints": [],
                "place_hint": None,
                "headcount": None,
                "meeting_type": None,
                "parsed_time_hint": None,
                "date_is_flexible": False,
                "date_hint_source_text": None,
            }
            state["extracted_entities"] = extracted
            _update_slot_state(state, extracted)
            state["is_location_first"] = False
            state["status"] = "entities_extracted"
            logger.info("[TIMING] entity_extraction (fast-skip): %.2fs", time.monotonic() - _t0)
            return state

        extracted = await _extract_entities_from_context(state)
        raw_date_hint = extracted.get("date_hint")
        raw_date_hints = extracted.get("date_hints") or []
        extracted["parsed_time_hint"] = None
        extracted["date_is_flexible"] = False
        extracted["date_hint_source_text"] = None

        # Multi-date: resolve each date hint to ISO dates (병렬)
        # Fix 2 (2026-05-14): N개 hint × 1.5s 직렬 → max(1.5s) 병렬.
        # Fix 1 캐시와 결합 시 같은 hint 반복은 0초.
        if len(raw_date_hints) >= 2:
            async def _resolve_one(hint: str) -> str:
                if _is_iso_date_hint(hint):
                    return hint
                parsed = await _parse_natural_date(hint)
                if parsed and parsed.get("date"):
                    return parsed["date"]
                return hint  # keep raw if can't resolve

            resolved_hints = list(
                await asyncio.gather(*[_resolve_one(h) for h in raw_date_hints])
            )
            # Fix#2 (2026-05-20): past 날짜 사전 필터 (Gemini 경로)
            _today_kst = datetime.now(KST).date()
            _before = len(resolved_hints)
            resolved_hints = [d for d in resolved_hints if d >= _today_kst.isoformat()]
            _dropped = _before - len(resolved_hints)
            if _dropped:
                logger.info(
                    "[OPT] _expand_date_hint dropped %d past dates (today=%s)",
                    _dropped, _today_kst.isoformat(),
                )
            extracted["date_hints"] = resolved_hints
            # Set date_hint to first resolved date for compatibility
            if resolved_hints:
                extracted["date_hint"] = resolved_hints[0]
                extracted["date_is_flexible"] = True
        elif isinstance(raw_date_hint, str) and raw_date_hint.strip() and not _is_iso_date_hint(raw_date_hint):
            parsed_natural_date = await _parse_natural_date(raw_date_hint)
            if parsed_natural_date:
                extracted["date_hint"] = parsed_natural_date.get("date")
                extracted["parsed_time_hint"] = parsed_natural_date.get("time")
                extracted["date_is_flexible"] = parsed_natural_date.get("is_flexible", False)
                extracted["date_hint_source_text"] = raw_date_hint
        state["extracted_entities"] = extracted
        _update_slot_state(state, extracted)

        # 교착 감지 결과를 state에 반영
        if extracted.get("conflict_detected"):
            state["conflict_detected"] = True
            state["conflict_type"] = extracted.get("conflict_type")
            state["conflict_options"] = extracted.get("conflict_options") or []
            state["conflict_users"] = extracted.get("conflict_users") or []
            logger.info(
                "[CONFLICT] Detected: type=%s options=%s users=%s",
                state["conflict_type"],
                state["conflict_options"],
                state["conflict_users"],
            )

        raw_rejected = extracted.get("rejected_dates")
        if isinstance(raw_rejected, list):
            cleaned_rejected = []
            for item in raw_rejected:
                if isinstance(item, dict) and isinstance(item.get("date"), str):
                    resolved = _resolve_rejected_date(item.get("date"))
                    if resolved:
                        cleaned_rejected.append({
                            "date": resolved,
                            "user": item.get("user"),
                            "reason": item.get("reason"),
                        })
            state["rejected_dates"] = cleaned_rejected
            if cleaned_rejected:
                logger.info("[REJECTED_DATES] Extracted: %s", cleaned_rejected)

        # PR-V1.5 / S16 (§6.15): rejected_places 누적.
        raw_rp = extracted.get("rejected_places")
        if isinstance(raw_rp, list) and raw_rp:
            existing = state.get("rejected_places") or []
            existing_set = {
                item["place"] for item in existing
                if isinstance(item, dict) and isinstance(item.get("place"), str)
            }
            for item in raw_rp:
                if not isinstance(item, dict):
                    continue
                place = item.get("place")
                if not isinstance(place, str) or not place.strip():
                    continue
                if place in existing_set:
                    continue
                existing_set.add(place)
                existing.append({
                    "place": place.strip(),
                    "user": item.get("user"),
                    "reason": item.get("reason"),
                })
            state["rejected_places"] = existing
            logger.info("[REJECTED_PLACES] Extracted: %s", existing)

        # place_suggestion intent인데 place_hint가 없으면 메시지에서 직접 추출
        if state.get("intent") == "place_suggestion" and not state.get("place_hint"):
            for msg in reversed(state["message_records"]):
                if msg.get("role") == "user" and msg.get("content"):
                    user_text = msg["content"].strip()
                    extracted_place = _extract_korean_place_keyword(user_text)
                    if extracted_place:
                        state["place_hint"] = extracted_place
                        state["extracted_entities"]["place_hint"] = extracted_place
                    else:
                        # 패턴 매칭 실패 시 메시지 전체를 힌트로 사용
                        state["place_hint"] = user_text
                        state["extracted_entities"]["place_hint"] = user_text
                    break

        # meeting_schedule intent에서도 place_hint가 없으면 한국 지명 추출 시도
        if not state.get("place_hint"):
            for msg in reversed(state["message_records"]):
                if msg.get("role") == "user" and msg.get("content"):
                    extracted_place = _extract_korean_place_keyword(msg["content"].strip())
                    if extracted_place:
                        state["place_hint"] = extracted_place
                        state["extracted_entities"]["place_hint"] = extracted_place
                    break

        place_coord = await _resolve_place_coord(state.get("place_hint"))
        if place_coord:
            state["place_coord"] = place_coord
        # intent가 명시적 meeting_schedule이면 장소가 있어도 location-first로 강등 금지.
        # — 사용자가 '일정 추천'을 요구한 경우 투표 카드(시간)가 메인이어야 함.
        state["is_location_first"] = (
            bool(state.get("place_hint"))
            and not bool(state.get("date_hint"))
            and state.get("intent") != "meeting_schedule"
        )
        state["status"] = "entities_extracted"
        logger.info("[TIMING] entity_extraction: %.2fs", time.monotonic() - _t0)
        dump("node_out", state.get("run_id"), {
            "node": "entity_extraction",
            "status_after": state.get("status"),
            "card_type": None,
            "slot_count": len(state.get("missing_slots", [])),
        })
        return state
    except Exception as exc:
        return await _handle_node_exception("entity_extraction", state, exc)
