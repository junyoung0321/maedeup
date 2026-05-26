"""intent_detection + general_response 노드 + _try_template_response 헬퍼.

원본 위치: langgraph_pipeline.py 라인 2453~2518 (_try_template_response),
  2521~2589 (general_response), 2592~2676 (intent_detection).

Phase 4 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

의존:
  - state.GraphState, _serialize_context
  - helpers.messaging: _has_node_error, _emit_assistant_message, _handle_node_exception
  - helpers.dates: _detect_multi_date_options
  - helpers.places: _extract_korean_place_keyword, _detect_cuisine_type,
    _PLACE_INTENT_PATTERN, _OTHER_ENTITY_SIGNAL_PATTERN
  - app.services.gemini.call_gemini
  - app.services.intent_classifier.classify_intent
  - app.services.meeting_history.get_recent_meeting_records
"""
from __future__ import annotations

import logging
import re
import time

from app.observability.snapshot import dump
from app.services.gemini import call_gemini
from app.services.intent_classifier import classify_intent
from app.services.meeting_history import get_recent_meeting_records
from app.services.pipeline.helpers.dates import _detect_multi_date_options
from app.services.pipeline.helpers.messaging import (
    _emit_assistant_message,
    _handle_node_exception,
    _has_node_error,
)
from app.services.pipeline.helpers.places import (
    _OTHER_ENTITY_SIGNAL_PATTERN,
    _PLACE_INTENT_PATTERN,
    _detect_cuisine_type,
    _extract_korean_place_keyword,
)
from app.services.pipeline.state import GraphState, _serialize_context

logger = logging.getLogger(__name__)


def _try_template_response(user_msg: str, state: GraphState) -> str | None:
    """단순 확인/인사 메시지에 대해 Gemini 호출 없이 템플릿 응답을 반환합니다.
    복잡한 대화는 None을 반환하여 Gemini로 넘깁니다."""
    if not user_msg:
        return None

    # 여러 날짜 선택지 패턴 → 템플릿 응답 건너뛰기 (entity_extraction으로 처리)
    if _detect_multi_date_options(user_msg):
        return None

    lower = user_msg.strip().lower()

    # 짧은 인사/감탄사
    _GREETING_PATTERNS = {
        "안녕", "ㅎㅇ", "하이", "hi", "hello", "헬로", "반가워", "안뇽",
    }
    _ACK_PATTERNS = {
        "ㅇㅋ", "ㅇㅇ", "ok", "오키", "오케이", "알겠어", "알겠습니다",
        "네", "넵", "넹", "응", "웅", "ㅎㅎ", "ㅋㅋ", "ㅋㅋㅋ",
        "고마워", "고맙", "감사", "땡큐", "ㄳ", "thx", "thanks",
        "좋아", "좋아요", "굿", "good", "👍",
    }
    _FAREWELL_PATTERNS = {
        "ㅂㅂ", "바이", "bye", "잘가", "수고", "고생", "나중에",
    }

    if lower in _GREETING_PATTERNS or any(lower.startswith(p) for p in _GREETING_PATTERNS):
        return "안녕! 모임 얘기 나오면 바로 정리해줄게요 😊"

    if lower in _ACK_PATTERNS:
        return "알겠어요! 👍"

    if lower in _FAREWELL_PATTERNS or any(lower.startswith(p) for p in _FAREWELL_PATTERNS):
        return "수고했어요! 다음에 또 불러줘요 👋"

    # 날짜 확인 패턴: "4월 22일" 같은 짧은 날짜만 있는 경우
    if re.fullmatch(r"\d{1,2}월\s*\d{1,2}일[에요!~.]*", lower):
        return f"{user_msg} 좋아요! 👍 정리해둘게요~"

    # 요일만 언급한 경우: "금요일", "토요일 ㄱㄱ"
    if re.fullmatch(r"[월화수목금토일]요일\s*[ㄱ-ㅎ!~.요]*", lower):
        return f"{user_msg} 좋아요! 📅 정리해둘게요~"

    # "내일", "모레", "다음주" 같은 짧은 날짜 표현
    if lower in ("내일", "모레", "이번주", "다음주", "이번주말", "다음주말"):
        return f"{user_msg} 좋아요! 📅 정리해둘게요~"

    # 장소만 짧게 언급한 경우: "강남", "홍대 ㄱㄱ" 등 (5자 이하)
    if len(lower) <= 5 and re.fullmatch(r"[가-힣]+\s*[ㄱ-ㅎ]*", lower):
        known_place = state.get("place_hint")
        if known_place:
            return f"{known_place} 좋아요! 🔍 맛집 찾아볼게요~"

    # "아무데나", "상관없어" 등 모호한 장소 → 기본 위치 사용 안내
    _VAGUE_PLACE_PATTERNS = ("아무데나", "상관없", "어디든", "아무곳", "아무거나", "알아서")
    if any(p in lower for p in _VAGUE_PLACE_PATTERNS):
        default_place = state.get("default_place_hint") or "서울 강남"
        return f"알겠어요! 기본 위치({default_place}) 기준으로 추천해드릴게요 📍"

    # 짧은 단순 메시지 (10자 이하, 한글+이모지+ㅋㅎ만)
    if len(lower) <= 10 and re.fullmatch(r"[가-힣ㄱ-ㅎㅏ-ㅣ\s!?.~😊👍🎉🔥💪]+", lower):
        # 이미 위에서 안 잡힌 짧은 감탄사/반응
        if re.fullmatch(r"[ㅋㅎㅜㅠ]+", lower):
            return "ㅋㅋ 😄"

    return None


async def general_response(state: GraphState) -> GraphState:
    """일반 대화에 대해 Gemini로 친근한 응답을 반환합니다."""
    _t0 = time.monotonic()
    dump("node_in", state.get("run_id"), {
        "node": "general_response",
        "status": state.get("status"),
        "trigger_reason": state.get("trigger_reason"),
        "has_card": bool(state.get("maedeup_card_payload") or state.get("vote_card_payload")),
        "message_count": len(state.get("message_records", [])),
    })
    try:
        if _has_node_error(state):
            return state

        # --- 템플릿 응답: 단순 확인 메시지는 Gemini 호출 없이 바로 반환 ---
        latest_user_msg = ""
        for msg in reversed(state["message_records"]):
            if msg.get("role") == "user" and msg.get("content"):
                latest_user_msg = msg["content"].strip()
                break

        template_reply = _try_template_response(latest_user_msg, state)
        if template_reply:
            await _emit_assistant_message(state["room_id"], state["db"], template_reply, state)
            state["status"] = "general_response_sent"
            logger.info("[TIMING] general_response (template): %.2fs", time.monotonic() - _t0)
            dump("node_out", state.get("run_id"), {
                "node": "general_response",
                "status_after": state.get("status"),
                "card_type": None,
                "slot_count": len(state.get("missing_slots", [])),
            })
            return state

        # --- Gemini 호출이 필요한 실제 대화 ---

        # 모임 히스토리 컨텍스트 로드
        try:
            room_id_int = int(state["room_id"])
            db = state["db"]
            records = await get_recent_meeting_records(room_id_int, db, limit=10)
            if records:
                history_lines: list[str] = []
                for r in records:
                    date_str = r.get("scheduled_at", "날짜 미정")
                    place = r.get("location_name", "장소 미정")
                    title = r.get("title", "")
                    members = ", ".join(r.get("participants", []))
                    history_lines.append(
                        f"- {title} | {date_str} | {place} | 참여: {members}"
                    )
                state["meeting_history_context"] = "\n".join(history_lines)
        except Exception:
            logger.debug("Failed to load meeting history context", exc_info=True)

        context = _serialize_context(state)
        prompt = (
            "너는 한국인 친구들 단톡방에 같이 있는 매듭이야.\n"
            "항상 캐주얼한 한국어로 자연스럽게 답하고, 말투는 주로 요/해요체로 써.\n"
            "너무 공손한 안내문이나 비서 말투는 피하고, 따뜻하고 편한 톤으로 말해.\n"
            "가끔 이모지 하나 정도는 자연스럽게 써도 돼.\n"
            "반드시 이전 대화 맥락을 참고해서, 이미 나온 날짜·장소·모임 종류·멤버 취향이 있으면 자연스럽게 이어받아.\n"
            "모임 얘기라면 일정이나 장소 정리를 같이 도와주겠다는 느낌으로 답해.\n"
            "'모임 히스토리'가 있으면 과거 모임 기록을 참고해서 답해. "
            "예: '저번에 갔던 맛집', '지난달에 몇 번 만났어' 같은 질문에 히스토리 기반으로 정확하게 답해줘.\n\n"
            "⚠️ 중요 규칙:\n"
            "- 빠진 정보(장소, 인원, 날짜 등)를 사용자에게 되물어보지 마.\n"
            "- 있는 정보만으로 도와줘. 모르는 건 '대화에서 나오면 정리해줄게' 정도로만 말해.\n"
            "- 사용자가 장소를 언급하면 바로 추천해줘, 되물어보지 마.\n"
            "- '어디가 좋으세요?', '몇 명이에요?', '언제가 좋으세요?' 같은 질문은 절대 하지 마.\n"
            "- 너는 비서가 아니라 똑똑한 친구처럼 행동해.\n\n"
            f"대화 맥락:\n{context or '(empty)'}"
        )
        reply = (await call_gemini(prompt)).strip()
        if not reply:
            reply = "안녕! 지금까지 나온 얘기 이어서 같이 정리해볼게요 😊"
        await _emit_assistant_message(state["room_id"], state["db"], reply, state)
        state["status"] = "general_response_sent"
        logger.info("[TIMING] general_response (gemini): %.2fs", time.monotonic() - _t0)
        dump("node_out", state.get("run_id"), {
            "node": "general_response",
            "status_after": state.get("status"),
            "card_type": None,
            "slot_count": len(state.get("missing_slots", [])),
        })
        return state
    except Exception as exc:
        return await _handle_node_exception("general_response", state, exc)


async def intent_detection(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    dump("node_in", state.get("run_id"), {
        "node": "intent_detection",
        "status": state.get("status"),
        "trigger_reason": state.get("trigger_reason"),
        "has_card": bool(state.get("maedeup_card_payload") or state.get("vote_card_payload")),
        "message_count": len(state.get("message_records", [])),
    })
    try:
        if _has_node_error(state):
            return state
        # 해결점 G: 트리거 시점 메시지 원문이 있으면 우선 사용 (race 방지).
        # fallback: message_records에서 latest user message 검색.
        latest_user_message = (state.get("trigger_message_text") or "").strip()
        if not latest_user_message:
            for message in reversed(state["message_records"]):
                if message.get("role") == "user" and message.get("content"):
                    latest_user_message = message["content"]
                    break

        # ── Fast-path: 명확한 패턴이 보이면 Gemini 의도 분류 생략 (−3~5s).
        _place_hint_pattern = re.compile(r"맛집|카페|식당|근처|동\s|역\s|장소.*추천|추천.*장소")
        pref_keywords = ["선호 정보", "선호정보", "최적", "일정.*추천"]
        pref_keywords_loose = ["추천해줘", "추천해"]
        fast_path_hit = False
        if latest_user_message:
            msg_lower = latest_user_message.lower()
            if _detect_multi_date_options(latest_user_message):
                state["intent"] = "meeting_schedule"
                state["intent_confidence"] = 0.9
                state["confidence_score"] = 0.9
                fast_path_hit = True
                logger.info("[INTENT] fast-path: multi-date pattern → meeting_schedule (skip Gemini)")
            elif any(re.search(kw, msg_lower) for kw in pref_keywords):
                state["intent"] = "meeting_schedule"
                state["intent_confidence"] = 0.95
                state["confidence_score"] = 0.95
                fast_path_hit = True
                logger.info("[INTENT] fast-path: pref recommendation pattern → meeting_schedule (skip Gemini)")
            else:
                # 해결점 A5-1: cuisine/place 의도 + 한국 지명 동시 매칭 → place_suggestion 직행.
                # entity_extraction에서 추가로 fast-skip되어 Gemini 6초 추출도 생략.
                # 단 메시지에 날짜/인원/시간 신호가 있으면 Gemini에 위임 (constraint 손실 방지).
                # pref_keywords_loose보다 먼저 시도 — "강남 한식 추천해줘"가 loose에 잡혀 meeting_schedule로
                # 오분류되는 사각지대 방지 (Codex review 2026-05-07 P2).
                place_kw = _extract_korean_place_keyword(latest_user_message)
                # PR-V1.5 / S18: _detect_cuisine_type → list[str]. 첫 매칭만 fast-path에 사용.
                cuisines = _detect_cuisine_type(latest_user_message)
                cuisine = cuisines[0] if cuisines else None
                has_place_intent = bool(cuisine) or bool(_PLACE_INTENT_PATTERN.search(latest_user_message))
                has_other_entities = bool(_OTHER_ENTITY_SIGNAL_PATTERN.search(latest_user_message))
                if place_kw and has_place_intent and not has_other_entities:
                    state["intent"] = "place_suggestion"
                    state["intent_confidence"] = 0.92
                    state["confidence_score"] = 0.92
                    state["place_hint"] = place_kw
                    state["meeting_type"] = cuisine or "맛집"
                    # entity_extraction이 이번 run의 fast-path 한정으로만 fast-skip 하도록 sentinel.
                    # 이전 턴에서 잔존한 place_hint + Gemini 분류 place_suggestion 조합으론 fast-skip 안 됨.
                    state["_place_fast_path_this_run"] = True
                    fast_path_hit = True
                    logger.info(
                        "[INTENT] fast-path: place pattern → place_suggestion "
                        "(skip Gemini, place=%s, cuisine=%s)",
                        place_kw,
                        cuisine or "맛집",
                    )
                elif any(re.search(kw, msg_lower) for kw in pref_keywords_loose) and not _place_hint_pattern.search(msg_lower):
                    state["intent"] = "meeting_schedule"
                    state["intent_confidence"] = 0.9
                    state["confidence_score"] = 0.9
                    fast_path_hit = True
                    logger.info("[INTENT] fast-path: loose recommendation pattern → meeting_schedule (skip Gemini)")

        if not fast_path_hit:
            if state.get("conversation_summary"):
                intent_input = (
                    f"[이전 대화 요약]: {state['conversation_summary']}\n"
                    f"[현재 메시지]: {latest_user_message or _serialize_context(state)}"
                )
            else:
                intent_input = latest_user_message or _serialize_context(state)

            intent_result = await classify_intent(intent_input)
            state["intent"] = str(intent_result.get("intent", "general"))
            state["intent_confidence"] = float(intent_result.get("confidence", 0.0))
            state["confidence_score"] = state["intent_confidence"]

        state["status"] = "intent_detected"
        logger.info("[TIMING] intent_detection: %.2fs", time.monotonic() - _t0)
        dump("node_out", state.get("run_id"), {
            "node": "intent_detection",
            "status_after": state.get("status"),
            "card_type": None,
            "slot_count": len(state.get("missing_slots", [])),
        })
        return state
    except Exception as exc:
        return await _handle_node_exception("intent_detection", state, exc)
