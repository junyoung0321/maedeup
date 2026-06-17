"""GraphState + 메시지 정규화 헬퍼.

원본 위치: langgraph_pipeline.py 라인 88~94 (MessageRecord), 96~174 (GraphState),
  177~254 (_default_state), 256~280 (_normalize_message), 282~289
  (_split_message_context), 291~295 (_message_to_text), 297~310 (_serialize_context).

Phase 3 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

의존:
  - constants: SLOT_KEYS, RECENT_MESSAGE_LIMIT
  - sqlmodel/sqlalchemy: AsyncSession (state 필드 type)

설계 메모:
  - 이 모듈은 Layer 1 — 외부 helpers/* 모듈 import 금지 (순환 방지).
  - helpers/* 가 GraphState를 type hint로 쓸 때는 TYPE_CHECKING 또는
    forward reference 사용.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.pipeline.constants import RECENT_MESSAGE_LIMIT, SLOT_KEYS


class MessageRecord(TypedDict, total=False):
    id: int
    role: str
    content: str
    sender: str | None
    created_at: str | None


class GraphState(TypedDict, total=False):
    run_id: str  # P0 instrumentation: uuid4().hex[:8], 파이프라인 단위 추적 ID
    room_id: str
    db: AsyncSession
    message_records: list[MessageRecord]
    recent_messages: list[str]
    conversation_summary: str
    # 트리거 발화 시점의 user 메시지 원문 (해결점 G).
    # intent_detection이 latest_user_message 대신 이 값을 우선 사용 → race condition 방지.
    trigger_message_text: str | None
    # 자동 트리거 분기용 (해결점 C). LangGraph entry conditional edge가 이걸 보고 시작 노드 결정.
    # 값: "stalemate_judged" | "conclusion_detected" | "all_members_selected"
    #     | "direct_request" | "preference_toggle" | None
    # PR-Z1 (2026-05-14): "preference_toggle" — recommendations/refresh 라우트가
    #   group↔speaker 선호 기준 전환을 위해 vote_card/place 재호출할 때 박는 값.
    trigger_reason: str | None
    # 부분 카드 발행 모드. 값: "time_only" | None
    partial_mode: str | None
    # direct_request fast path 분류 결과 (해결점 E).
    # 값: "schedule" | "place" | "schedule+place" | "general" | None
    direct_request_kind: str | None
    context_meeting_id: int | None
    # A3-3 (2026-05-08): 호스트가 [조율] 모달에서 직접 선택한 시간. ai_auto_trigger 흐름의
    # slot_context를 통해 주입됨. _slot_filling_all_members가 이 값을 confirmed_date/time으로
    # 박고 partial maedeup 카드 직행. 값: {"date": "YYYY-MM-DD", "start_idx": int, "end_idx": int} | None.
    manual_chosen_time: dict[str, Any] | None
    # 해결점 N: 모든 후보 날짜가 거부되어 다음 주로 확장됐는지 표시.
    # _slot_filling_stalemate가 이 플래그 보고 alternative vote 카드 발행.
    expanded_to_next_week: bool
    # validation → function_calling redirect용 임시 flag.
    # supervisor_validation이 set → function_calling이 date_hint +7일 shift 후 즉시 pop.
    needs_next_week_expansion: bool
    # 방의 소셜(전체 공개) 채팅 최근 N개 + 그 이전 대화 요약.
    # entity_extraction / general_response 가 AI 패널 컨텍스트에 덧붙여 사용.
    social_recent: list[str]
    social_summary: str
    seen_message_ids: list[int]
    new_assistant_messages: list[dict[str, Any]]
    intent: str
    intent_confidence: float
    confidence_score: float
    date_hint: str | None
    place_hint: str | None
    place_coord: dict[str, str] | None
    default_place_hint: str | None
    confirmed_date: str | None
    confirmed_time: str | None
    confirmed_place: str | None
    parsed_time_hint: str | None
    date_hints: list[str]
    date_is_flexible: bool
    date_hint_source_text: str | None
    headcount: int | None
    meeting_type: str | None
    is_location_first: bool
    all_slots_filled: bool
    missing_slots: list[str]
    slot_filling_turns: int
    message_count_since_last_trigger: int
    awaiting_user_reply: bool
    wait_timed_out: bool
    extracted_entities: dict[str, Any]
    time_options: list[str]
    calendar_free_slots: list[dict[str, Any]]
    place_search_results: list[dict[str, Any]]
    validation_errors: list[str]
    validation_passed: bool
    vote_card_payload: dict[str, Any] | None
    place_recommendation_payload: dict[str, Any] | None
    maedeup_card_payload: dict[str, Any] | None
    calendar_registration: dict[str, Any] | None
    # PR-Y1: blocker_notification_payload는 vote_card 레벨 요약 (카드당 1회).
    # 형식 1) {"type": "social_system_message", "room_id", "sender", "content", "blocker_name"}
    #        — 기존 동작: 일부 슬롯에 충돌이 있을 때 가장 빈번한 blocker 호출.
    # 형식 2) {"type": "f1_fallback", "reason": "no_full_slot", "missing_count",
    #          "total_count", "max_available_count"}
    #        — F1 fallback (spec §4.4): 전원 가능 슬롯 0개 → 다수결 추천 카드와 함께 발행.
    blocker_notification_payload: dict[str, Any] | None
    # calendar_strategy 값:
    #   "all_members_available" | "all_members_available_extended"
    #   | "n_minus_one" | "n_minus_one_extended"
    #   | "multi_date_vote" | "preference_based"
    #   | "natural_language_time_options"
    #   | "majority_fallback"   # PR-Y1 (F1 fallback)
    calendar_strategy: str | None
    summary_message_count: int
    meeting_history_context: str | None
    # 교착 감지
    conflict_detected: bool
    conflict_type: str | None  # "date" | "place" | "time"
    conflict_options: list[str]
    conflict_users: list[str]
    rejected_dates: list[dict[str, Any]]  # chat-level explicitly rejected dates
    # PR-V1.5 / §6.15 — chat-level explicitly rejected places.
    # 형식: [{"place": "강남", "reason": "...", "user": str | None}]
    # entity_extraction이 거부 발화에서 누적 (예: "강남 말고", "홍대는 별로")
    # place_recommendation 노드가 place_search_results 필터 시 제외 처리.
    rejected_places: list[dict[str, Any]]
    # PR-V1.5 / §6.15 — Kakao 응답이 정상 0건일 때 분기용 (장애와 구분).
    place_search_empty: bool
    pre_extracted_signals: dict[str, Any] | None
    # 선호 정보
    preference_common_times: list[str]
    # PR-V1.5 / F1 외 — 0 슬롯 원인 분기 reason.
    # 값: "calendar_consent_zero" | "all_blocked" | None
    zero_slot_reason: str | None
    status: str
    # 프라이버시 경계 (docs/ai-separation.md §9.4)
    viewer_user_id: int | None  # None = auto-trigger (shared), int = private viewer

    # PR-Z1 (Q5/Q7 hybrid refresh) — recommendations/refresh 라우트가 주입.
    # P0-2·3·4 plumbing: 발화자(요청자) 본인의 personal data lookup 결과.
    #   - vote_card / place 페이로드의 preference_source/preference_toggle_enabled 계산
    #   - 후속 PR에서 group↔speaker 추천 비교 시 사용
    requester_user_id: int | None
    requester_home_base: str | None
    # 형식: {food_preferences, food_restrictions, liked_areas, disliked_areas,
    #        transport_mode, time_preference, share_food_data,
    #        share_location_data, share_schedule_data, is_guest}
    requester_preferences: dict[str, Any] | None
    # Q7 hybrid 토글 상태. "group" (기본) | "speaker".
    preference_source: str | None
    # refresh 라우트 재호출 여부 (audit/logging용).
    is_preference_refresh: bool


def _default_state(
    room_id: str,
    db: AsyncSession,
    messages: list[Any],
    slot_context: dict | None = None,
    viewer_user_id: int | None = None,
) -> GraphState:
    normalized_messages = [_normalize_message(message) for message in messages]
    recent_messages, derived_summary = _split_message_context(normalized_messages)
    seen_ids = [
        message["id"]
        for message in normalized_messages
        if isinstance(message.get("id"), int)
    ]
    ctx = slot_context or {}
    conversation_summary = str(ctx.get("conversation_summary") or derived_summary or "").strip()
    return {
        "room_id": room_id,
        "db": db,
        "message_records": normalized_messages,
        "recent_messages": recent_messages,
        "conversation_summary": conversation_summary,
        "trigger_message_text": ctx.get("trigger_message_text"),
        "trigger_reason": ctx.get("trigger_reason"),
        "partial_mode": ctx.get("partial_mode"),
        "direct_request_kind": ctx.get("direct_request_kind"),
        "context_meeting_id": ctx.get("context_meeting_id"),
        "manual_chosen_time": ctx.get("manual_chosen_time"),
        "social_recent": [],
        "social_summary": "",
        "seen_message_ids": seen_ids,
        "new_assistant_messages": [],
        "viewer_user_id": viewer_user_id,
        "intent": "general",
        "intent_confidence": 0.0,
        "confidence_score": 0.0,
        "date_hint": ctx.get("date_hint"),
        "place_hint": ctx.get("place_hint"),
        "place_coord": ctx.get("place_coord"),
        "default_place_hint": ctx.get("default_place_hint") or "",
        "confirmed_date": ctx.get("confirmed_date"),
        "confirmed_time": ctx.get("confirmed_time"),
        "confirmed_place": ctx.get("confirmed_place"),
        "parsed_time_hint": ctx.get("parsed_time_hint"),
        "date_hints": list(ctx.get("date_hints") or []),
        "date_is_flexible": bool(ctx.get("date_is_flexible", False)),
        "date_hint_source_text": ctx.get("date_hint_source_text"),
        "headcount": ctx.get("headcount"),
        "meeting_type": ctx.get("meeting_type"),
        "is_location_first": False,
        "all_slots_filled": False,
        "missing_slots": list(SLOT_KEYS),
        "slot_filling_turns": int(ctx.get("slot_filling_turns") or 0),
        "message_count_since_last_trigger": int(ctx.get("message_count_since_last_trigger") or 0),
        "awaiting_user_reply": bool(ctx.get("awaiting_user_reply", False)),
        "wait_timed_out": False,
        "extracted_entities": {},
        "time_options": list(ctx.get("time_options") or []),
        "calendar_free_slots": [],
        "place_search_results": [],
        "validation_errors": [],
        "validation_passed": False,
        "vote_card_payload": None,
        "place_recommendation_payload": None,
        "maedeup_card_payload": None,
        "calendar_registration": None,
        "blocker_notification_payload": None,
        "calendar_strategy": None,
        "summary_message_count": int(ctx.get("summary_message_count") or 0),
        "conflict_detected": False,
        "conflict_type": None,
        "conflict_options": [],
        "conflict_users": [],
        "rejected_dates": [],
        "rejected_places": [],
        "place_search_empty": False,
        "pre_extracted_signals": ctx.get("pre_extracted_signals"),
        "preference_common_times": [],
        "zero_slot_reason": None,
        "status": "initialized",
        # PR-Z1: refresh 라우트가 slot_context로 주입.
        "requester_user_id": ctx.get("requester_user_id"),
        "requester_home_base": ctx.get("requester_home_base"),
        "requester_preferences": ctx.get("requester_preferences"),
        "preference_source": ctx.get("preference_source") or "group",
        "is_preference_refresh": bool(ctx.get("is_preference_refresh", False)),
    }


def _normalize_message(message: Any) -> MessageRecord:
    if isinstance(message, dict):
        created_at = message.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        return {
            "id": message.get("id"),
            "role": str(message.get("role", "user")),
            "content": str(message.get("content", "")).strip(),
            "sender": message.get("sender"),
            "created_at": created_at,
        }

    created_at_value = getattr(message, "created_at", None)
    if isinstance(created_at_value, datetime):
        created_at_value = created_at_value.isoformat()

    return {
        "id": getattr(message, "id", None),
        "role": str(getattr(message, "role", "user")),
        "content": str(getattr(message, "content", "")).strip(),
        "sender": getattr(message, "sender", None),
        "created_at": created_at_value,
    }


def _split_message_context(messages: list[MessageRecord]) -> tuple[list[str], str]:
    raw_text_messages = [_message_to_text(message) for message in messages if message.get("content")]
    if len(raw_text_messages) <= RECENT_MESSAGE_LIMIT:
        return raw_text_messages, ""

    recent_messages = raw_text_messages[-RECENT_MESSAGE_LIMIT:]
    return recent_messages, ""


def _message_to_text(message: MessageRecord) -> str:
    role = message.get("role", "user")
    content = message.get("content", "").strip()
    return f"{role}: {content}"


def _serialize_context(state: GraphState) -> str:
    parts: list[str] = []
    if state.get("conversation_summary"):
        parts.append(f"[summary]\n{state['conversation_summary']}")
    if state.get("meeting_history_context"):
        parts.append(f"[모임 히스토리]\n{state['meeting_history_context']}")
    if state.get("social_summary"):
        parts.append(f"[방 채팅 요약]\n{state['social_summary']}")
    if state.get("social_recent"):
        parts.append("[방 채팅 최근]\n" + "\n".join(state["social_recent"]))
    if state.get("recent_messages"):
        parts.append("[AI 대화]\n" + "\n".join(state["recent_messages"]))
    return "\n\n".join(part for part in parts if part).strip()
