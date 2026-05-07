from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, TypedDict
from zoneinfo import ZoneInfo

import httpx
import redis.asyncio as aioredis
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

import holidays

import redis.asyncio as aioredis
from sqlalchemy import func as sa_func

from app.core.config import settings
from app.models.ai_memory import AIMemory
from app.services import scheduling_round as sr
from app.models.chat import ChatMessage, PaneType
from app.models.meeting import MeetingSchedule
from app.models.meeting_preference import MeetingPreference
from app.models.room import RoomMember
from app.models.user import User
from app.repositories.messages import AgentContextMessages, MessageReader
from app.services.gemini import call_gemini
from app.services.google_calendar import GoogleCalendarAuthError, get_google_access_token
from app.services.intent_classifier import classify_intent
from app.services.kakao_maps import search_address, search_keyword
from app.services.meeting_history import get_recent_meeting_records, search_meeting_history
from app.services.personal_data_extractor import (
    CATEGORY_FIELDS as PERSONAL_DATA_CATEGORIES,
    CategoryExtraction,
    extract_personal_data,
)

KST = ZoneInfo("Asia/Seoul")
GOOGLE_FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"
WORK_HOUR_START = 9
WORK_HOUR_END = 22
SLOT_MINUTES = 60
INTENT_CONFIDENCE_THRESHOLD = 0.7
PREFERRED_TIME_RANGES = {
    "평일오전": (9, 12),
    "평일오후": (13, 17),
    "평일저녁": (18, 21),
    "주말오전": (9, 12),
    "주말오후": (13, 17),
    "주말저녁": (18, 21),
}

_KR_HOLIDAYS = holidays.KR()


def _get_korean_holiday(dt: datetime) -> str | None:
    """해당 날짜가 한국 공휴일이면 공휴일 이름 반환, 아니면 None."""
    d = dt.date() if isinstance(dt, datetime) else dt
    return _KR_HOLIDAYS.get(d)


def _is_weekend(dt: datetime) -> bool:
    return dt.weekday() >= 5  # 토(5), 일(6)

RECENT_MESSAGE_LIMIT = 12
SLOT_KEYS = ("date_hint", "place_hint", "headcount", "meeting_type")
MAX_SLOT_FILLING_TURNS = 4
SUMMARY_TRIGGER_INTERVAL = 10
FRIENDLY_ERROR_MESSAGE = "잠깐, 뭔가 잘못됐어요 😅 다시 한번 말해줄래요?"

logger = logging.getLogger(__name__)


class MessageRecord(TypedDict, total=False):
    id: int
    role: str
    content: str
    sender: str | None
    created_at: str | None


class GraphState(TypedDict, total=False):
    room_id: str
    db: AsyncSession
    message_records: list[MessageRecord]
    recent_messages: list[str]
    conversation_summary: str
    # 트리거 발화 시점의 user 메시지 원문 (해결점 G).
    # intent_detection이 latest_user_message 대신 이 값을 우선 사용 → race condition 방지.
    trigger_message_text: str | None
    # 자동 트리거 분기용 (해결점 C). LangGraph entry conditional edge가 이걸 보고 시작 노드 결정.
    # 값: "stalemate_judged" | "conclusion_detected" | "all_members_selected" | "direct_request" | None
    trigger_reason: str | None
    # 부분 카드 발행 모드. 값: "time_only" | None
    partial_mode: str | None
    # direct_request fast path 분류 결과 (해결점 E).
    # 값: "schedule" | "place" | "schedule+place" | "general" | None
    direct_request_kind: str | None
    # 해결점 N: 모든 후보 날짜가 거부되어 다음 주로 확장됐는지 표시.
    # _slot_filling_stalemate가 이 플래그 보고 alternative vote 카드 발행.
    expanded_to_next_week: bool
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
    blocker_notification_payload: dict[str, Any] | None
    calendar_strategy: str | None
    summary_message_count: int
    meeting_history_context: str | None
    # 교착 감지
    conflict_detected: bool
    conflict_type: str | None  # "date" | "place" | "time"
    conflict_options: list[str]
    conflict_users: list[str]
    rejected_dates: list[dict[str, Any]]  # chat-level explicitly rejected dates
    pre_extracted_signals: dict[str, Any] | None
    # 선호 정보
    preference_common_times: list[str]
    status: str
    # 프라이버시 경계 (docs/ai-separation.md §9.4)
    viewer_user_id: int | None  # None = auto-trigger (shared), int = private viewer


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
        "pre_extracted_signals": ctx.get("pre_extracted_signals"),
        "preference_common_times": [],
        "status": "initialized",
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


async def _compress_message_history(state: GraphState) -> None:
    raw_text_messages = [_message_to_text(message) for message in state["message_records"] if message.get("content")]
    state["recent_messages"] = raw_text_messages[-RECENT_MESSAGE_LIMIT:]
    total_message_count = len(raw_text_messages)
    last_summary_count = int(state.get("summary_message_count") or 0)

    if total_message_count == 0:
        return
    if total_message_count - last_summary_count < SUMMARY_TRIGGER_INTERVAL:
        return

    messages_for_summary = raw_text_messages[last_summary_count:total_message_count]
    if not messages_for_summary:
        return

    prompt = (
        "당신은 모임 대화 메모를 구조화해서 정리하는 요약기입니다.\n"
        "아래 형식을 그대로 유지한 구조화된 문자열만 반환하세요.\n"
        "각 항목은 비어 있으면 '없음'으로 적으세요.\n\n"
        "[확정된 결정]\n"
        "- 날짜: ...\n"
        "- 장소: ...\n"
        "- 모임 종류: ...\n"
        "[남은 질문]\n"
        "- ...\n"
        "[멤버 선호]\n"
        "- ...\n"
        "[핵심 맥락]\n"
        "- ...\n\n"
        "기존 요약:\n"
        f"{state.get('conversation_summary') or '없음'}\n\n"
        "새로 반영할 대화:\n"
        f"{chr(10).join(messages_for_summary)}"
    )

    try:
        summary = (await call_gemini(prompt)).strip()
    except Exception as exc:
        logger.exception("Failed to summarize conversation memory: %s", exc)
        summary = ""

    if summary:
        state["conversation_summary"] = summary
        state["summary_message_count"] = total_message_count


def _coerce_headcount(value: Any) -> int | None:
    if value in (None, "", []):
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count > 0 else None


def _update_slot_state(state: GraphState, extracted: dict[str, Any]) -> None:
    previous_date_hint = state.get("date_hint")
    date_hint = extracted.get("date_hint")
    date_hints = extracted.get("date_hints")
    place_hint = extracted.get("place_hint")
    meeting_type = extracted.get("meeting_type")
    headcount = _coerce_headcount(extracted.get("headcount"))
    parsed_time_hint = extracted.get("parsed_time_hint")
    date_is_flexible = extracted.get("date_is_flexible")
    date_hint_source_text = extracted.get("date_hint_source_text")

    if date_hint not in (None, ""):
        state["date_hint"] = str(date_hint)
    if isinstance(date_hints, list) and len(date_hints) >= 2:
        state["date_hints"] = [str(d) for d in date_hints]
    if place_hint not in (None, ""):
        state["place_hint"] = str(place_hint)
    if meeting_type not in (None, ""):
        state["meeting_type"] = str(meeting_type)
    if headcount is not None:
        state["headcount"] = headcount
    if "parsed_time_hint" in extracted:
        state["parsed_time_hint"] = str(parsed_time_hint) if parsed_time_hint not in (None, "") else None
    if "date_is_flexible" in extracted:
        state["date_is_flexible"] = _coerce_bool(date_is_flexible)
    if "date_hint_source_text" in extracted:
        state["date_hint_source_text"] = (
            str(date_hint_source_text) if date_hint_source_text not in (None, "") else None
        )
    if previous_date_hint != state.get("date_hint"):
        state["time_options"] = []

    missing_slots: list[str] = []
    for key in SLOT_KEYS:
        if state.get(key) in (None, "", []):
            missing_slots.append(key)

    state["missing_slots"] = missing_slots
    state["all_slots_filled"] = not missing_slots


def _has_meaningful_slot_progress(previous_missing_slots: list[str], state: GraphState) -> bool:
    for key in previous_missing_slots:
        if state.get(key) not in (None, "", []):
            return True
    return False


def _has_node_error(state: GraphState) -> bool:
    return str(state.get("status", "")).endswith("_error")


async def _handle_node_exception(
    node_name: str,
    state: GraphState,
    exc: Exception,
) -> GraphState:
    logger.exception("LangGraph node failed: %s", node_name, exc_info=exc)
    state["status"] = f"{node_name}_error"
    state["validation_passed"] = False
    state["awaiting_user_reply"] = False
    try:
        await _emit_assistant_message(state["room_id"], state["db"], FRIENDLY_ERROR_MESSAGE, state)
    except Exception:
        logger.exception("Failed to emit recovery message for node: %s", node_name)
    return state


def _resolve_place_hint(state: GraphState) -> str:
    place_hint = state.get("place_hint")
    if isinstance(place_hint, str) and place_hint.strip():
        return place_hint.strip()

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


def _format_slot_label(start_at: datetime, unavailable_names: list[str]) -> str:
    weekday = ["월", "화", "수", "목", "금", "토", "일"][start_at.weekday()]
    ampm = "오전" if start_at.hour < 12 else "오후"
    hour = start_at.hour if start_at.hour <= 12 else start_at.hour - 12
    holiday = _get_korean_holiday(start_at)
    day_tag = f" {holiday}" if holiday else ""
    if _is_weekend(start_at) and not holiday:
        day_tag = " 주말"
    suffix = " (전원 가능)"
    if unavailable_names:
        absent_users = ", ".join(f"@{name}" for name in unavailable_names)
        suffix = f" (N-1명 가능, {absent_users} 불참)"
    return f"{start_at.month}월 {start_at.day}일 ({weekday}){day_tag} {ampm} {hour}:{start_at.minute:02d}{suffix}"


def _format_confirmed_time(start_at: datetime | None) -> str | None:
    if start_at is None:
        return None
    start_kst = start_at.astimezone(KST)
    ampm = "오전" if start_kst.hour < 12 else "오후"
    hour = start_kst.hour % 12 or 12
    return f"{ampm} {hour}:{start_kst.minute:02d}"


def _extract_json_object(text: str | None) -> dict[str, Any]:
    if not isinstance(text, str):
        return {}
    stripped = text.strip()
    if stripped.startswith("```"):
        chunks = [chunk.strip() for chunk in stripped.split("```") if chunk.strip()]
        if chunks:
            stripped = chunks[0].removeprefix("json").strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        stripped = stripped[start : end + 1]

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_json_array(text: str | None) -> list[dict[str, Any]]:
    if not isinstance(text, str):
        return []
    stripped = text.strip()
    if stripped.startswith("```"):
        chunks = [chunk.strip() for chunk in stripped.split("```") if chunk.strip()]
        if chunks:
            stripped = chunks[0].removeprefix("json").strip()

    start = stripped.find("[")
    end = stripped.rfind("]")
    if start != -1 and end != -1 and end > start:
        stripped = stripped[start : end + 1]

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _extract_loose_json_object(text: str | None) -> dict[str, Any]:
    parsed = _extract_json_object(text)
    if parsed:
        return parsed
    if not isinstance(text, str):
        return {}

    stripped = text.strip()
    if stripped.startswith("```"):
        chunks = [chunk.strip() for chunk in stripped.split("```") if chunk.strip()]
        if chunks:
            stripped = chunks[0].removeprefix("json").strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        stripped = stripped[start : end + 1]

    normalized = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", r'\1"\2"\3', stripped)
    normalized = normalized.replace("'", '"')

    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _is_iso_date_hint(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}(~\d{4}-\d{2}-\d{2})?", normalized))


def _is_specific_iso_date(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()))


def _resolve_rejected_date(raw: str | None, now_kst: datetime | None = None) -> str | None:
    """LLM이 자연어로 반환한 거부 날짜를 ISO(YYYY-MM-DD) 문자열로 변환.

    예: "2026-05-09" → "2026-05-09" (이미 ISO)
        "금요일"      → 다음 금요일 ISO
        "다음 금요일" → 다음주 금요일 ISO
        "5월 9일"     → "{year}-05-09" (이미 지난 날이면 다음 해)
        "5/9"         → "{year}-05-09"
        변환 실패 시 None
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if _is_specific_iso_date(text):
        return text

    base = now_kst or datetime.now(KST)

    # "5/9" 같은 슬래시 형식 → "5월 9일"로 정규화 후 재시도
    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})", text)
    if slash_match:
        text = f"{int(slash_match.group(1))}월 {int(slash_match.group(2))}일"

    parsed = _fallback_parse_natural_date(text, base)
    if not parsed:
        return None
    date_value = parsed.get("date")
    if isinstance(date_value, str) and _is_specific_iso_date(date_value):
        return date_value
    return None


def _detect_multi_date_options(text: str) -> bool:
    """여러 날짜 선택지를 제시하는 패턴을 감지합니다.

    예: "목요일에 볼까 금요일에 볼까", "토요일 어때 일요일 어때",
        "내일 아니면 모레", "15일이나 16일"
    """
    if not text:
        return False

    # 요일 2개 이상 언급
    weekday_mentions = re.findall(r'[월화수목금토일]요일', text)
    if len(set(weekday_mentions)) >= 2:
        return True

    # M월D일 패턴 2개 이상
    md_mentions = re.findall(r'\d{1,2}월\s*\d{1,2}일', text)
    if len(md_mentions) >= 2:
        return True

    # D일 패턴 2개 이상 (같은 문장에서)
    day_mentions = re.findall(r'(?<!\d)(\d{1,2})일', text)
    if len(set(day_mentions)) >= 2:
        return True

    # 선택 패턴: "A 아니면 B", "A이나 B", "A or B" + 날짜 키워드
    choice_patterns = [
        r'(?:볼까|어때|할까|갈까|만날까).*(?:볼까|어때|할까|갈까|만날까)',
        r'(?:내일|모레|[월화수목금토일]요일|\d{1,2}일)\s*(?:아니면|이나|or|말고)\s*(?:내일|모레|[월화수목금토일]요일|\d{1,2}일)',
    ]
    for pattern in choice_patterns:
        if re.search(pattern, text):
            return True

    return False


def _weekday_from_korean(text: str) -> int | None:
    mapping = {
        "월": 0,
        "화": 1,
        "수": 2,
        "목": 3,
        "금": 4,
        "토": 5,
        "일": 6,
    }
    match = re.search(r"([월화수목금토일])요일?", text)
    if not match:
        return None
    return mapping.get(match.group(1))


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _next_weekday(base: datetime, weekday: int, include_current_week: bool = False) -> datetime:
    days_ahead = (weekday - base.weekday()) % 7
    if days_ahead == 0 and not include_current_week:
        days_ahead = 7
    return base + timedelta(days=days_ahead)


def _fallback_parse_natural_date(text: str, now_kst: datetime) -> dict[str, Any] | None:
    normalized = text.strip()
    if not normalized:
        return None

    compact = normalized.replace(" ", "")
    result: dict[str, Any] = {}
    target_date: datetime | None = None

    if "모레" in compact:
        target_date = now_kst + timedelta(days=2)
    elif "내일" in compact:
        target_date = now_kst + timedelta(days=1)
    elif "오늘" in compact:
        target_date = now_kst
    elif "이번주말" in compact:
        target_date = _next_weekday(now_kst, 5, include_current_week=True)
        result["is_flexible"] = True
    elif "다음주" in compact:
        weekday = _weekday_from_korean(normalized)
        if weekday is not None:
            this_week_monday = now_kst - timedelta(days=now_kst.weekday())
            next_week_base = this_week_monday + timedelta(days=7)
            target_date = next_week_base + timedelta(days=weekday)
    elif "이번주" in compact:
        weekday = _weekday_from_korean(normalized)
        if weekday is not None:
            this_week_monday = now_kst - timedelta(days=now_kst.weekday())
            target_date = this_week_monday + timedelta(days=weekday)
            if target_date.date() < now_kst.date():
                target_date += timedelta(days=7)
    else:
        # 요일만 있으면 (예: "목요일", "금요일") → 다음 해당 요일로
        weekday = _weekday_from_korean(normalized)
        if weekday is not None:
            days_ahead = weekday - now_kst.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            target_date = now_kst + timedelta(days=days_ahead)

        day_match = re.search(r"(?<!\d)(\d{1,2})일(?!\d)", normalized) if target_date is None else None
        if day_match:
            day = int(day_match.group(1))
            year = now_kst.year
            month = now_kst.month
            if day < now_kst.day:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            try:
                target_date = now_kst.replace(
                    year=year,
                    month=month,
                    day=day,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            except ValueError:
                target_date = None

    if target_date is None:
        return None

    normalized_no_space = normalized.replace(" ", "")
    if any(keyword in normalized_no_space for keyword in ("저녁", "밤")):
        result["time"] = "18:00"
        result["is_flexible"] = True
    elif "오후" in normalized_no_space:
        result["time"] = "13:00"
        result["is_flexible"] = True
    elif any(keyword in normalized_no_space for keyword in ("오전", "아침")):
        result["time"] = "09:00"
        result["is_flexible"] = True
    elif "점심" in normalized_no_space:
        result["time"] = "12:00"
        result["is_flexible"] = True

    result["date"] = target_date.strftime("%Y-%m-%d")
    result.setdefault("is_flexible", "time" not in result)
    result.setdefault("time", None)
    return result


def _normalize_parsed_natural_date(
    parsed: dict[str, Any],
    source_text: str,
    now_kst: datetime,
) -> dict[str, Any] | None:
    if not parsed:
        return None

    date_value = str(parsed.get("date") or "").strip()
    time_value = str(parsed.get("time") or "").strip()
    is_flexible = _coerce_bool(parsed.get("is_flexible", False))

    if date_value:
        try:
            datetime.strptime(date_value, "%Y-%m-%d")
        except ValueError:
            date_value = ""
    if time_value:
        try:
            datetime.strptime(time_value, "%H:%M")
        except ValueError:
            time_value = ""

    fallback = _fallback_parse_natural_date(source_text, now_kst) or {}
    if not date_value:
        date_value = str(fallback.get("date") or "").strip()
    if not time_value:
        time_value = str(fallback.get("time") or "").strip()
    if not is_flexible and "is_flexible" in fallback:
        is_flexible = _coerce_bool(fallback.get("is_flexible"))

    if not date_value:
        return None

    return {
        "date": date_value,
        "time": time_value or None,
        "is_flexible": is_flexible,
    }


async def _parse_natural_date(text: str) -> dict[str, Any] | None:
    normalized = str(text or "").strip()
    if not normalized:
        return None

    now_kst = datetime.now(KST)

    # --- OPTIMIZATION: Try pattern-based parsing first, skip Gemini if successful ---
    fallback_result = _fallback_parse_natural_date(normalized, now_kst)
    if fallback_result and fallback_result.get("date"):
        logger.info("[OPT] _parse_natural_date resolved by pattern fallback, skipping Gemini")
        return fallback_result

    today = now_kst.strftime("%Y-%m-%d")
    prompt = (
        "다음 텍스트에서 날짜/시간 정보를 추출해서 ISO 8601 형식으로 변환해줘. "
        f"오늘은 {today}입니다. 결과만 JSON으로: "
        "{date: 'YYYY-MM-DD', time: 'HH:MM', is_flexible: true/false}\n"
        f"텍스트: {normalized}"
    )

    try:
        raw = await call_gemini(prompt)
    except Exception as exc:
        logger.warning("Failed to parse natural date with Gemini: %s", exc)
        return fallback_result

    parsed = _extract_loose_json_object(raw)
    normalized_result = _normalize_parsed_natural_date(parsed, normalized, now_kst)
    if normalized_result:
        return normalized_result
    return fallback_result


def _infer_time_bucket(source_text: str | None, parsed_time_hint: str | None) -> str:
    normalized = str(source_text or "").replace(" ", "")
    if any(keyword in normalized for keyword in ("저녁", "밤")):
        return "evening"
    if any(keyword in normalized for keyword in ("오후", "점심")):
        return "afternoon"
    if any(keyword in normalized for keyword in ("오전", "아침", "새벽")):
        return "morning"

    if parsed_time_hint:
        try:
            hour = datetime.strptime(parsed_time_hint, "%H:%M").hour
        except ValueError:
            hour = -1
        if hour >= 17:
            return "evening"
        if hour >= 12:
            return "afternoon"
        if hour >= 0:
            return "morning"

    return "afternoon"


def _build_flexible_time_options(state: GraphState) -> list[str]:
    if not state.get("date_is_flexible"):
        return []
    if not _is_specific_iso_date(state.get("date_hint")):
        return []

    bucket = _infer_time_bucket(
        state.get("date_hint_source_text"),
        state.get("parsed_time_hint"),
    )
    if bucket == "evening":
        return ["18:00", "19:00", "20:00"]
    if bucket == "morning":
        return ["09:00", "10:00", "11:00"]
    return ["13:00", "14:00", "15:00"]


def _normalize_preferred_time(value: Any) -> str:
    return str(value or "").strip().replace(" ", "")


def _normalize_preferred_times(values: list[Any] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = _normalize_preferred_time(value)
        if item in PREFERRED_TIME_RANGES and item not in seen:
            seen.add(item)
            normalized.append(item)
    return normalized


def _preference_score_for_start(start_at: datetime, pref_times: list[str]) -> int:
    if not pref_times:
        return 0
    start_kst = start_at.astimezone(KST)
    is_weekend = _is_weekend(start_kst)
    score = 0
    for pref_time in pref_times:
        normalized = _normalize_preferred_time(pref_time)
        hours = PREFERRED_TIME_RANGES.get(normalized)
        if not hours:
            continue
        if normalized.startswith("평일") and is_weekend:
            continue
        if normalized.startswith("주말") and not is_weekend:
            continue
        start_hour, end_hour = hours
        if start_hour <= start_kst.hour < end_hour:
            score += 1
    return score


def _build_time_option_slots(state: GraphState) -> list[dict[str, Any]]:
    date_hint = state.get("date_hint")
    time_options = list(state.get("time_options") or [])
    if not _is_specific_iso_date(date_hint) or not time_options:
        return []

    try:
        base_date = datetime.strptime(str(date_hint), "%Y-%m-%d").replace(tzinfo=KST)
    except ValueError:
        return []

    holiday = _get_korean_holiday(base_date)
    slots: list[dict[str, Any]] = []
    for index, time_value in enumerate(time_options, start=1):
        try:
            hour, minute = map(int, str(time_value).split(":"))
        except ValueError:
            continue
        start_at = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        end_at = start_at + timedelta(minutes=SLOT_MINUTES)
        slots.append({
            "slot_id": f"time-option-{index}",
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "label": _format_slot_label(start_at, []),
            "available_count": state.get("headcount"),
            "total_count": state.get("headcount"),
            "has_conflict": False,
            "unavailable_users": [],
            "is_holiday": bool(holiday),
            "holiday_name": holiday,
            "is_weekend": _is_weekend(start_at),
        })
    return slots


def _room_id_as_int(room_id: str) -> int | None:
    try:
        return int(room_id)
    except (TypeError, ValueError):
        return None


def _user_calendar_key(user: User) -> str:
    return f"{user.id}:{user.name}"


def _user_display_name(user_key: str) -> str:
    _, _, name = user_key.partition(":")
    return name or user_key


# 한국 지명 추출을 위한 잘 알려진 지역명
_WELL_KNOWN_PLACES = [
    "강남", "홍대", "건대", "이태원", "명동", "합정", "신촌", "연남", "망원",
    "성수", "잠실", "여의도", "광화문", "종로", "을지로", "혜화", "대학로",
    "압구정", "청담", "삼성", "선릉", "역삼", "서초", "방배", "사당",
    "신림", "구로", "영등포", "용산", "마포", "서울숲", "왕십리", "한양대",
    "동대문", "남대문", "북촌", "삼청", "안국", "경복궁", "이수", "노량진",
    "가산", "판교", "분당", "일산", "수원", "인천", "부산", "대구", "대전",
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

    return None


def _pattern_extract_entities(context: str) -> dict[str, Any]:
    """패턴 기반으로 엔티티를 추출합니다. Gemini 호출 없이 빠르게 처리."""
    result: dict[str, Any] = {"date_hint": None, "date_hints": [], "place_hint": None, "headcount": None, "meeting_type": None}
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
        '"rejected_dates": [{"date": string, "user": string | null, "reason": string | null}] | null'
        "}\n\n"
        "date_hint: 첫 번째 날짜 표현. 가능하면 YYYY-MM-DD 형식으로 변환, 범위면 "
        "'YYYY-MM-DD~YYYY-MM-DD'\n"
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
        "  예시:\n"
        '  - "금요일은 알바 있어서 안 돼" → [{"date": "2026-05-08", "user": "민수", "reason": "알바"}]\n'
        '  - "토요일 가족 모임이라 힘들어" → [{"date": "2026-05-09", "user": "수현", "reason": "가족 모임"}]\n'
        '  - "그날은 좀..." → [] (모호하면 빈 배열)\n\n'
        f"대화 맥락:\n{context or '(empty)'}\n\n"
        "모르면 null로 반환하세요."
    )
    try:
        result = _extract_json_object(await call_gemini(prompt))
        if result:
            # Merge date_hints from pattern_result if Gemini didn't return them
            if not result.get("date_hints") and pattern_result.get("date_hints"):
                result["date_hints"] = pattern_result["date_hints"]
            return result
    except Exception:
        pass

    # Gemini 실패 시 패턴 기반 fallback 반환
    return pattern_result


async def _resolve_place_coord(keyword: str | None) -> dict[str, str] | None:
    if not keyword:
        return None
    place_coord = await search_address(keyword)
    if not place_coord:
        return None
    if not place_coord.get("x") or not place_coord.get("y"):
        return None
    return place_coord


async def _emit_assistant_message(
    room_id: str,
    db: AsyncSession,
    content: str,
    state: GraphState,
    *,
    shared: bool = False,
) -> None:
    room_pk = _room_id_as_int(room_id)
    timestamp = datetime.now(timezone.utc).isoformat()
    state["message_records"].append(
        {
            "role": "assistant",
            "content": content,
            "sender": "매듭 AI",
            "created_at": timestamp,
        }
    )
    await _compress_message_history(state)

    if room_pk is None:
        return

    viewer_user_id = state.get("viewer_user_id")
    if shared:
        vis = "shared"
        uid = None
    else:
        vis = "private" if viewer_user_id is not None else "shared"
        uid = viewer_user_id
    message = ChatMessage(
        pane_type=PaneType.agent,
        role="assistant",
        content=content,
        sender="매듭 AI",
        room_id=room_pk,
        user_id=uid,
        visibility=vis,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    if message.id is not None:
        state["seen_message_ids"].append(message.id)
        # 새 어시스턴트 메시지 추적 (agent.py가 Redis로 발행할 수 있도록)
        if "new_assistant_messages" not in state:
            state["new_assistant_messages"] = []  # type: ignore[typeddict-unknown-key]
        state["new_assistant_messages"].append(  # type: ignore[typeddict-unknown-key]
            {
                "id": message.id,
                "pane_type": message.pane_type,
                "role": message.role,
                "content": message.content,
                "sender": message.sender,
                "created_at": message.created_at.isoformat(),
                "visibility": message.visibility,
                "user_id": message.user_id,
            }
        )



def _slot_snapshot(state: GraphState) -> dict[str, Any]:
    return {
        "date_hint": state.get("date_hint"),
        "place_hint": state.get("place_hint"),
        "headcount": state.get("headcount"),
        "meeting_type": state.get("meeting_type"),
        "all_slots_filled": state.get("all_slots_filled", False),
    }


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


async def _get_user_busy_periods(
    user: User,
    time_min: datetime,
    time_max: datetime,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Google Calendar freeBusy API로 특정 유저의 바쁜 시간대(시작/종료)만 조회합니다."""
    try:
        access_token = await get_google_access_token(user, db)
    except GoogleCalendarAuthError:
        return []
    except Exception:
        return []

    try:

        payload = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "timeZone": "Asia/Seoul",
            "items": [{"id": "primary"}],
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(GOOGLE_FREEBUSY_URL, json=payload, headers=headers)

            if resp.status_code == 401:
                refreshed_token = await get_google_access_token(user, db, force_refresh=True)
                headers = {"Authorization": f"Bearer {refreshed_token}"}
                resp = await client.post(
                    GOOGLE_FREEBUSY_URL,
                    json=payload,
                    headers=headers,
                )

            if resp.status_code != 200:
                return []

        try:
            busy_periods = resp.json().get("calendars", {}).get("primary", {}).get("busy", [])
        except ValueError:
            return []

        result = []
        for item in busy_periods:
            start_raw = item.get("start")
            end_raw = item.get("end")
            if not start_raw or not end_raw:
                continue
            start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            result.append({"start": start, "end": end})
        return result
    except Exception:
        return []


def _find_free_slots(
    busy_by_user: dict[str, list[dict[str, Any]]],
    time_min: datetime,
    time_max: datetime,
    minimum_available: int,
    require_exact_absent_count: int | None,
    preferred_times: list[str] | None = None,
) -> list[dict[str, Any]]:
    """참여자 가용성을 기준으로 시간대를 SLOT_MINUTES 단위로 탐색합니다."""
    total = len(busy_by_user)
    free_slots: list[dict[str, Any]] = []
    fallback_slots: list[dict[str, Any]] = []
    normalized_preferred_times = _normalize_preferred_times(preferred_times)
    current = time_min
    slot_idx = 1

    while current < time_max and len(free_slots) < 5:
        slot_end = current + timedelta(minutes=SLOT_MINUTES)
        current_kst = current.astimezone(KST)

        if WORK_HOUR_START <= current_kst.hour < WORK_HOUR_END:
            unavailable_names = [
                name
                for name, periods in busy_by_user.items()
                if any(bp["start"] < slot_end and bp["end"] > current for bp in periods)
            ]
            available_count = total - len(unavailable_names)

            absent_count_matches = (
                require_exact_absent_count is None
                or len(unavailable_names) == require_exact_absent_count
            )
            if available_count >= minimum_available and absent_count_matches:
                s = current.astimezone(KST)
                holiday = _get_korean_holiday(s)
                slot = {
                    "slot_id": f"slot-{slot_idx}",
                    "start_at": current.isoformat(),
                    "end_at": slot_end.isoformat(),
                    "label": _format_slot_label(
                        s,
                        [_user_display_name(name) for name in unavailable_names],
                    ),
                    "available_count": available_count,
                    "total_count": total,
                    "has_conflict": bool(unavailable_names),
                    "unavailable_users": [_user_display_name(name) for name in unavailable_names],
                    "is_holiday": bool(holiday),
                    "holiday_name": holiday,
                    "is_weekend": _is_weekend(s),
                }
                if normalized_preferred_times:
                    if _preference_score_for_start(s, normalized_preferred_times) > 0:
                        free_slots.append(slot)
                    elif len(fallback_slots) < 5:
                        fallback_slots.append(slot)
                else:
                    free_slots.append(slot)
                slot_idx += 1

        current = current + timedelta(minutes=SLOT_MINUTES)

    if normalized_preferred_times and free_slots:
        return free_slots
    return free_slots if free_slots else fallback_slots


_SOCIAL_RECENT_LIMIT = 10
_SOCIAL_SUMMARY_THRESHOLD = 15  # 이 이상 누적되면 이전 부분을 요약


async def _load_social_context(
    db: AsyncSession, room_pk: Optional[int]
) -> tuple[list[str], str]:
    """방의 소셜 채팅 최근 N개 + 더 오래된 메시지가 충분하면 Redis-캐시된 요약을 반환.
    실패해도 pipeline은 계속 — 빈 값 반환."""
    if room_pk is None:
        return [], ""
    try:
        result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.room_id == room_pk,
                ChatMessage.pane_type == PaneType.social,
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(_SOCIAL_RECENT_LIMIT)
        )
        recent_rows = list(reversed(result.scalars().all()))
    except Exception:
        logger.debug("social recent load failed room=%s", room_pk, exc_info=True)
        return [], ""

    recent_lines = [
        f"{m.sender or '익명'}: {m.content}"
        for m in recent_rows if m.content and m.content.strip()
    ]

    summary = ""
    try:
        total_result = await db.execute(
            select(sa_func.count())
            .select_from(ChatMessage)
            .where(
                ChatMessage.room_id == room_pk,
                ChatMessage.pane_type == PaneType.social,
            )
        )
        total = int(total_result.scalar() or 0)
    except Exception:
        total = 0

    if total >= _SOCIAL_SUMMARY_THRESHOLD and recent_rows:
        # Redis 캐시: last_id 기준으로 10개 이상 밀렸을 때만 재생성
        try:
            r = aioredis.from_url(
                settings.REDIS_URL, decode_responses=True,
                socket_connect_timeout=1, socket_timeout=1,
            )
        except Exception:
            r = None

        cache_key = f"social_summary:{room_pk}"
        oldest_recent_id = recent_rows[0].id or 0
        cached = None
        if r is not None:
            try:
                raw = await r.get(cache_key)
                if raw:
                    cached = json.loads(raw)
            except Exception:
                cached = None

        if (
            cached
            and isinstance(cached, dict)
            and cached.get("summary")
            and int(cached.get("boundary_id") or 0) >= oldest_recent_id
        ):
            summary = str(cached["summary"]).strip()
        else:
            # 최근 N개보다 오래된 메시지를 모아 요약.
            try:
                older_res = await db.execute(
                    select(ChatMessage)
                    .where(
                        ChatMessage.room_id == room_pk,
                        ChatMessage.pane_type == PaneType.social,
                        ChatMessage.id < oldest_recent_id,
                    )
                    .order_by(ChatMessage.created_at)
                )
                older = older_res.scalars().all()
            except Exception:
                older = []

            joined = "\n".join(
                f"{m.sender or '익명'}: {m.content}"
                for m in older
                if m.content and m.content.strip()
            )
            if joined.strip():
                prompt = (
                    "다음은 모임 채팅방의 과거 대화입니다. 합의/진행 중인 결정/"
                    "멤버 선호·불만을 3줄 이내로 간결히 요약하세요. 가십 제외.\n\n"
                    f"{joined}"
                )
                try:
                    summary = (await call_gemini(prompt) or "").strip()
                except Exception:
                    summary = ""

            if r is not None and summary:
                try:
                    await r.setex(
                        cache_key,
                        6 * 3600,
                        json.dumps({"summary": summary, "boundary_id": oldest_recent_id}),
                    )
                except Exception:
                    pass

        if r is not None:
            try:
                await r.aclose()
            except Exception:
                pass

    return recent_lines, summary


async def _load_blocked_dates(room_pk: Optional[int]) -> set[str]:
    """방의 '불가능 날짜' 집합을 Redis에서 조회. 한 명이라도 불가능이면 해당 날짜 제외.
    Redis 실패 시 빈 set 반환 (pipeline은 graceful degradation)."""
    if room_pk is None:
        return set()
    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        try:
            unavail = await sr.load_room_unavailability(r, room_id=room_pk)
        finally:
            await r.aclose()
    except Exception:
        return set()
    blocked: set[str] = set()
    for dates in unavail.values():
        for d in dates:
            if isinstance(d, str):
                blocked.add(d)
    return blocked


def _filter_out_blocked(
    slots: list[dict[str, Any]], blocked_dates: set[str]
) -> list[dict[str, Any]]:
    if not blocked_dates:
        return slots
    return [
        s for s in slots
        if isinstance(s.get("start_at"), str) and s["start_at"][:10] not in blocked_dates
    ]


_DATE_RANGE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})~(\d{4}-\d{2}-\d{2})$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _expand_date_hint(hint: Any) -> list[str]:
    if not isinstance(hint, str):
        return []

    if _ISO_DATE_RE.match(hint):
        try:
            return [datetime.fromisoformat(hint).date().isoformat()]
        except ValueError:
            return []

    range_match = _DATE_RANGE_RE.match(hint)
    if not range_match:
        return []

    try:
        start = datetime.fromisoformat(range_match.group(1)).date()
        end = datetime.fromisoformat(range_match.group(2)).date()
    except ValueError:
        return []

    if end < start:
        return []

    day_count = (end - start).days
    if day_count > 14:
        return []

    return [(start + timedelta(days=offset)).isoformat() for offset in range(day_count + 1)]


def _filter_out_rejected(
    slots: list[dict[str, Any]], rejected_dates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not rejected_dates:
        return slots
    rejected_set = {r["date"] for r in rejected_dates if isinstance(r.get("date"), str)}
    if not rejected_set:
        return slots
    return [
        s for s in slots
        if isinstance(s.get("start_at"), str) and s["start_at"][:10] not in rejected_set
    ]


async def get_free_slots(state: GraphState) -> list[dict[str, Any]]:
    """구글 캘린더 API로 룸 멤버 전원의 빈 시간대를 조회합니다.
    불가능 날짜(방 내 누군가 명시한 날)는 결과에서 제외."""
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    blocked_dates = await _load_blocked_dates(room_pk)
    preferred_times = state.get("preference_common_times") or []
    normalized_preferred_times = _normalize_preferred_times(preferred_times)
    minimum_preferred_slots = 3

    def _matching_preference_slots(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not normalized_preferred_times:
            return slots
        matching: list[dict[str, Any]] = []
        for slot in slots:
            start_at = slot.get("start_at")
            if not isinstance(start_at, str):
                continue
            try:
                slot_start = datetime.fromisoformat(start_at)
            except ValueError:
                continue
            if _preference_score_for_start(slot_start, normalized_preferred_times) > 0:
                matching.append(slot)
        return matching

    if room_pk is None or not settings.GOOGLE_CLIENT_ID:
        if preferred_times:
            return _build_preference_time_slots(state, preferred_times, blocked_dates)
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        base = now + timedelta(days=2, hours=10)
        return [
            {
                "slot_id": f"slot-{i+1}",
                "start_at": (base + timedelta(days=i)).isoformat(),
                "end_at": (base + timedelta(days=i, hours=2)).isoformat(),
                "label": _format_slot_label((base + timedelta(days=i)).astimezone(KST), []),
                "has_conflict": False,
            }
            for i in range(3)
        ]

    member_result = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room_pk)
    )
    members = member_result.scalars().all()
    user_ids = [m.user_id for m in members]

    if not user_ids:
        return []

    user_result = await db.execute(
        select(User).where(User.id.in_(user_ids)).where(User.calendar_consent == True)  # noqa: E712
    )
    consenting_users = [
        user
        for user in user_result.scalars().all()
        if user.google_access_token or user.google_refresh_token
    ]

    now = datetime.now(timezone.utc)
    date_hint = state.get("date_hint")

    # 멤버 날짜 선택을 Redis에서 읽어 활용 (캘린더 클릭 + 시간바 선택 모두)
    user_dates: dict[str, str] = {}
    if not date_hint and room_pk is not None:
        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
            try:
                date_sels = await sr.load_room_date_selections(r, room_id=room_pk)
                for uid, d in date_sels.items():
                    if d:
                        user_dates[str(uid)] = d
                avail = await sr.load_room_availability(r, room_id=room_pk)
                for uid, entries in avail.items():
                    for entry in entries:
                        d = entry.get("date")
                        if d:
                            user_dates[str(uid)] = d
            finally:
                await r.aclose()
        except Exception:
            logger.debug("Failed to read member selections from Redis", exc_info=True)

    if not date_hint and not user_dates:
        state["no_date_selection"] = True
        return []

    if not date_hint and user_dates:
        from collections import Counter
        date_counts = Counter(user_dates.values())
        most_common_date, count = date_counts.most_common(1)[0]

        date_hint = most_common_date
        state["date_hint"] = date_hint
        if len(date_counts) > 1:
            state["date_conflict"] = True
            state["date_selection_summary"] = dict(date_counts)
            logger.info("Date conflict: %s (picked %s with %d/%d)", dict(date_counts), date_hint, count, len(user_dates))
        else:
            logger.info("All %d members selected %s", len(user_dates), date_hint)

    if date_hint and re.match(r"\d{4}-\d{2}-\d{2}", str(date_hint)):
        hint_date = datetime.fromisoformat(str(date_hint)).replace(tzinfo=timezone.utc)
        time_min = hint_date.replace(hour=0, minute=0, second=0, microsecond=0)
        time_max = time_min + timedelta(days=1)
    else:
        time_min = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        time_max = time_min + timedelta(days=14)

    busy_by_user: dict[str, list[dict[str, Any]]] = {}
    for user in consenting_users:
        busy_by_user[_user_calendar_key(user)] = await _get_user_busy_periods(user, time_min, time_max, db)

    if not busy_by_user:
        if preferred_times:
            return _build_preference_time_slots(state, preferred_times, blocked_dates)
        return []

    full_slots = _find_free_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
        minimum_available=len(busy_by_user),
        require_exact_absent_count=0,
        preferred_times=preferred_times,
    )
    full_slots = _filter_out_blocked(full_slots, blocked_dates)
    full_slots = _matching_preference_slots(full_slots)
    if full_slots and (
        not normalized_preferred_times or len(full_slots) >= minimum_preferred_slots
    ):
        state["calendar_strategy"] = "all_members_available"
        return full_slots

    n_minus_one_slots = _find_free_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
        minimum_available=max(len(busy_by_user) - 1, 1),
        require_exact_absent_count=1 if len(busy_by_user) > 1 else 0,
        preferred_times=preferred_times,
    )
    n_minus_one_slots = _filter_out_blocked(n_minus_one_slots, blocked_dates)
    n_minus_one_slots = _matching_preference_slots(n_minus_one_slots)
    if n_minus_one_slots and (
        not normalized_preferred_times or len(n_minus_one_slots) >= minimum_preferred_slots
    ):
        state["calendar_strategy"] = "n_minus_one"
        return n_minus_one_slots

    extended_time_max = time_max + timedelta(days=14 if normalized_preferred_times else 7)
    refreshed_busy_by_user: dict[str, list[dict[str, Any]]] = {}
    for user in consenting_users:
        refreshed_busy_by_user[_user_calendar_key(user)] = await _get_user_busy_periods(
            user,
            time_min,
            extended_time_max,
            db,
        )

    extended_full_slots = _find_free_slots(
        busy_by_user=refreshed_busy_by_user,
        time_min=time_min,
        time_max=extended_time_max,
        minimum_available=len(refreshed_busy_by_user),
        require_exact_absent_count=0,
        preferred_times=preferred_times,
    )
    extended_full_slots = _filter_out_blocked(extended_full_slots, blocked_dates)
    extended_full_slots = _matching_preference_slots(extended_full_slots)
    if extended_full_slots and (
        not normalized_preferred_times or len(extended_full_slots) >= minimum_preferred_slots
    ):
        state["calendar_strategy"] = "all_members_available_extended"
        return extended_full_slots

    final_slots = _find_free_slots(
        busy_by_user=refreshed_busy_by_user,
        time_min=time_min,
        time_max=extended_time_max,
        minimum_available=max(len(refreshed_busy_by_user) - 1, 1),
        require_exact_absent_count=1 if len(refreshed_busy_by_user) > 1 else 0,
        preferred_times=preferred_times,
    )
    final_slots = _filter_out_blocked(final_slots, blocked_dates)
    final_slots = _matching_preference_slots(final_slots)
    if normalized_preferred_times and len(final_slots) < minimum_preferred_slots:
        matching_slots: list[dict[str, Any]] = []
        seen_matching_start_ats: set[str] = set()
        for slot in extended_full_slots + final_slots:
            start_at = slot.get("start_at")
            if isinstance(start_at, str) and start_at not in seen_matching_start_ats:
                seen_matching_start_ats.add(start_at)
                matching_slots.append(slot)

        fallback_slots = _find_free_slots(
            busy_by_user=refreshed_busy_by_user,
            time_min=time_min,
            time_max=extended_time_max,
            minimum_available=max(len(refreshed_busy_by_user) - 1, 1),
            require_exact_absent_count=1 if len(refreshed_busy_by_user) > 1 else 0,
            preferred_times=preferred_times,
        )
        fallback_slots = _filter_out_blocked(fallback_slots, blocked_dates)
        fallback_slots = _matching_preference_slots(fallback_slots)
        final_slots = matching_slots + [
            slot for slot in fallback_slots
            if slot.get("start_at") not in seen_matching_start_ats
        ]
        final_slots.sort(
            key=lambda slot: (
                -_preference_score_for_start(
                    datetime.fromisoformat(str(slot.get("start_at"))).astimezone(KST),
                    normalized_preferred_times,
                ),
                str(slot.get("start_at")),
            )
        )

    if final_slots:
        state["calendar_strategy"] = "n_minus_one_extended"
    return final_slots


async def _get_room_member_food_preferences(state: GraphState) -> list[str]:
    """비선호 음식 목록을 반환합니다. meeting_preferences 우선, 없으면 User 프로필 사용."""
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    if room_pk is None:
        return []

    # 1. meeting_preferences에서 비선호 음식 로드 (팝업 데이터)
    pref_result = await db.execute(
        select(MeetingPreference).where(MeetingPreference.room_id == room_pk)
    )
    prefs = pref_result.scalars().all()

    disliked_foods: list[str] = []
    seen: set[str] = set()

    if prefs:
        for pref in prefs:
            for item in pref.disliked_foods or []:
                normalized = str(item).strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    disliked_foods.append(normalized)
        if disliked_foods:
            return disliked_foods

    # 2. fallback: User 프로필의 food_preferences
    member_result = await db.execute(select(RoomMember).where(RoomMember.room_id == room_pk))
    members = member_result.scalars().all()
    user_ids = [member.user_id for member in members]
    if not user_ids:
        return []

    user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = user_result.scalars().all()

    for user in users:
        for item in user.food_preferences or []:
            normalized = str(item).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                disliked_foods.append(normalized)
    return disliked_foods


async def _get_room_member_constraints(state: GraphState) -> dict[str, list[str]]:
    """모임 멤버 전체의 6 카테고리 personal data를 합성.

    프라이버시 모델 (디자인 P1, P2): 누가 어떤 값을 가지는지 식별 가능한 형태로
    반환하지 않음. 모든 멤버의 값을 union해서 익명 합산만 노출. 호출자는 이걸
    Gemini prompt에 컨텍스트로 넘기거나 reasoning summary 합성에 쓴다.

    반환 dict의 키는 6 카테고리 이름. 값은 누적 string list (deduplicated).
    time_preference / transport_mode는 단일 string 칼럼이지만 멤버별로 다를 수
    있으므로 list로 모음.
    """
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    empty: dict[str, list[str]] = {
        "food_restrictions": [],
        "food_preferences": [],
        "liked_areas": [],
        "disliked_areas": [],
        "time_preference": [],
        "transport_mode": [],
    }
    if room_pk is None:
        return empty

    member_result = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room_pk)
    )
    members = member_result.scalars().all()
    user_ids = [member.user_id for member in members]
    if not user_ids:
        return empty

    user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = user_result.scalars().all()

    constraints: dict[str, list[str]] = {k: [] for k in empty}
    seen: dict[str, set[str]] = {k: set() for k in empty}

    def _push(category: str, value: str) -> None:
        v = str(value or "").strip()
        if not v or v in seen[category]:
            return
        seen[category].add(v)
        constraints[category].append(v)

    for user in users:
        # QuickPreferences 토글 respect — OFF면 해당 카테고리 skip.
        # opt-out 모델이므로 None이면 True로 간주 (기존 row backfill 안 됐어도 안전).
        share_food = bool(getattr(user, "share_food_data", True) if getattr(user, "share_food_data", True) is not None else True)
        share_location = bool(getattr(user, "share_location_data", True) if getattr(user, "share_location_data", True) is not None else True)
        share_schedule = bool(getattr(user, "share_schedule_data", True) if getattr(user, "share_schedule_data", True) is not None else True)

        if share_food:
            for item in user.food_restrictions or []:
                _push("food_restrictions", str(item))
            for item in user.food_preferences or []:
                _push("food_preferences", str(item))
        if share_location:
            for item in user.liked_areas or []:
                _push("liked_areas", str(item))
            for item in user.disliked_areas or []:
                _push("disliked_areas", str(item))
        if share_schedule:
            if user.time_preference:
                _push("time_preference", user.time_preference)
            if user.transport_mode:
                _push("transport_mode", user.transport_mode)

    return constraints


def _build_group_constraints_summary(constraints: dict[str, list[str]]) -> str:
    """추천 reasoning에 붙는 익명 group constraint 요약 (디자인 P2 가운데 톤).

    Count 없음, 누구인지도 없음. 멤버 수가 0이면 빈 문자열.
    예: "모임 멤버 중 갑각류 회피 / 강남 회피 / 대중교통 선호 고려"
    """
    parts: list[str] = []
    if constraints.get("food_restrictions"):
        joined = ", ".join(constraints["food_restrictions"])
        parts.append(f"{joined} 회피")
    if constraints.get("disliked_areas"):
        joined = ", ".join(constraints["disliked_areas"])
        parts.append(f"{joined} 지역 회피")
    if constraints.get("liked_areas"):
        joined = ", ".join(constraints["liked_areas"])
        parts.append(f"{joined} 지역 선호")
    if constraints.get("time_preference"):
        joined = " · ".join(constraints["time_preference"])
        parts.append(f"선호 시간대: {joined}")
    if constraints.get("transport_mode"):
        joined = ", ".join(constraints["transport_mode"])
        parts.append(f"이동수단: {joined}")
    if not parts:
        return ""
    return "모임 멤버 중 " + " / ".join(parts) + " 고려"


async def _get_room_member_constraints_named(state: GraphState) -> list[dict[str, Any]]:
    """해결점 A5-2: per-user constraints with name. 강도순 차등 처리용.

    공유 토글(share_food/location/schedule_data) 존중. 토글 OFF면 해당 카테고리 빈 값.
    이름이 없는 user는 제외. 빈 entry(어떤 값도 없는)도 제외.
    """
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    if room_pk is None:
        return []

    member_result = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room_pk)
    )
    members = member_result.scalars().all()
    user_ids = [member.user_id for member in members]
    if not user_ids:
        return []

    user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = user_result.scalars().all()

    per_user: list[dict[str, Any]] = []
    for user in users:
        name = (getattr(user, "name", None) or "").strip()
        if not name:
            continue

        share_food = bool(
            getattr(user, "share_food_data", True)
            if getattr(user, "share_food_data", True) is not None
            else True
        )
        share_location = bool(
            getattr(user, "share_location_data", True)
            if getattr(user, "share_location_data", True) is not None
            else True
        )
        share_schedule = bool(
            getattr(user, "share_schedule_data", True)
            if getattr(user, "share_schedule_data", True) is not None
            else True
        )

        food_restrictions = list(user.food_restrictions or []) if share_food else []
        food_preferences = list(user.food_preferences or []) if share_food else []
        liked_areas = list(user.liked_areas or []) if share_location else []
        disliked_areas = list(user.disliked_areas or []) if share_location else []
        time_preference = user.time_preference if share_schedule else None
        transport_mode = user.transport_mode if share_schedule else None

        if not any([
            food_restrictions, food_preferences, liked_areas, disliked_areas,
            time_preference, transport_mode,
        ]):
            continue

        per_user.append({
            "name": name,
            "food_restrictions": food_restrictions,
            "food_preferences": food_preferences,
            "liked_areas": liked_areas,
            "disliked_areas": disliked_areas,
            "time_preference": time_preference,
            "transport_mode": transport_mode,
        })
    return per_user


def _build_named_constraints_summary(per_user: list[dict[str, Any]]) -> str:
    """해결점 A5-2: 이름 인용 + 강도순 차등 reasoning summary.

    - 강 (food_restrictions, disliked_areas) → 이름 명시 + ✨
    - 중 (food_preferences) → 이름 명시 (강한 제약 없는 멤버 한정)
    - 약 (liked_areas, time_preference, transport_mode) → 익명 합산
    - 같은 강도에 3명 이상이면 "외 N명" 표기

    예: "수현님 채식·홍대 비선호 ✨ + 다른 멤버 매운맛 선호 반영"
    """
    if not per_user:
        return ""

    # 강한 제약: food_restrictions / disliked_areas.
    # food_restrictions와 disliked_areas는 의미가 다르므로(식단 제약 vs 지역 회피)
    # 분리해서 표기 — "수현님 채식 비선호"처럼 의미 반전 방지.
    strong_phrases: list[str] = []
    strong_names: set[str] = set()
    for u in per_user:
        bits: list[str] = []
        if u.get("food_restrictions"):
            bits.append(f"{', '.join(u['food_restrictions'])} 식단")
        if u.get("disliked_areas"):
            bits.append(f"{', '.join(u['disliked_areas'])} 비선호")
        if bits:
            strong_phrases.append(f"{u['name']}님 " + " · ".join(bits))
            strong_names.add(u["name"])

    # 중간: food_preferences (강한 제약 가진 멤버는 제외)
    mid_phrases: list[str] = []
    for u in per_user:
        if u["name"] in strong_names:
            continue
        if u.get("food_preferences"):
            mid_phrases.append(f"{u['name']}님 {'·'.join(u['food_preferences'])} 선호")

    # 약한 선호: liked_areas, time_preference, transport_mode (익명 합산)
    liked = sorted({a for u in per_user for a in (u.get("liked_areas") or [])})
    times = sorted({
        u["time_preference"] for u in per_user if u.get("time_preference")
    })
    trans = sorted({
        u["transport_mode"] for u in per_user if u.get("transport_mode")
    })
    weak_pieces: list[str] = []
    if liked:
        weak_pieces.append(f"{', '.join(liked)} 선호 지역")
    if times:
        weak_pieces.append(f"선호 시간 {', '.join(times)}")
    if trans:
        weak_pieces.append(f"이동수단 {', '.join(trans)}")

    def _join_named(phrases: list[str], marker: str = "") -> str:
        if len(phrases) <= 2:
            return " + ".join(phrases) + marker
        return " + ".join(phrases[:2]) + f" 외 {len(phrases) - 2}명" + marker

    parts: list[str] = []
    if strong_phrases:
        parts.append(_join_named(strong_phrases, " ✨"))
    if mid_phrases:
        parts.append(_join_named(mid_phrases))
    if weak_pieces:
        parts.append("다른 멤버 " + " / ".join(weak_pieces))

    if not parts:
        return ""
    return " · ".join(parts) + " 반영"


async def _load_meeting_preferences(state: GraphState) -> dict[str, Any]:
    """meeting_preferences 테이블에서 모임별 선호 정보를 로드하고 집계합니다.

    Returns:
        {
            "has_preferences": bool,
            "all_submitted": bool,
            "total_members": int,
            "submitted_count": int,
            "best_location": str | None,       # 다수결 장소
            "common_times": list[str],          # 교차 시간대
            "all_disliked_foods": list[str],    # 모든 비선호 음식
            "all_preferred_foods": list[str],   # 모든 선호 음식
            "notes": list[str],                 # 메모들
        }
    """
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    if room_pk is None:
        return {"has_preferences": False, "all_submitted": False}

    # 멤버 수
    member_result = await db.execute(select(RoomMember).where(RoomMember.room_id == room_pk))
    members = member_result.scalars().all()
    total_members = len(members)

    # 선호 정보 로드
    pref_result = await db.execute(
        select(MeetingPreference).where(MeetingPreference.room_id == room_pk)
    )
    prefs = pref_result.scalars().all()

    if not prefs:
        return {
            "has_preferences": False,
            "all_submitted": False,
            "total_members": total_members,
            "submitted_count": 0,
        }

    # 장소 다수결
    location_counts: dict[str, int] = {}
    for p in prefs:
        loc = (p.preferred_location or "").strip()
        if loc:
            location_counts[loc] = location_counts.get(loc, 0) + 1
    best_location = max(location_counts, key=location_counts.get) if location_counts else None

    # 시간대 교차 (모든 멤버가 공통으로 선택한 시간대)
    time_sets = [
        set(_normalize_preferred_times(p.preferred_times))
        for p in prefs
        if _normalize_preferred_times(p.preferred_times)
    ]
    if time_sets:
        common_times = list(time_sets[0].intersection(*time_sets[1:]))
        if not common_times:
            # 교차 없으면 가장 많이 선택된 시간대 상위 3개
            time_counts: dict[str, int] = {}
            for p in prefs:
                for t in _normalize_preferred_times(p.preferred_times):
                    time_counts[t] = time_counts.get(t, 0) + 1
            common_times = sorted(time_counts, key=time_counts.get, reverse=True)[:3]
    else:
        common_times = []

    # 비선호 음식 합집합
    all_disliked: list[str] = []
    seen_disliked: set[str] = set()
    for p in prefs:
        for food in p.disliked_foods or []:
            if food not in seen_disliked:
                seen_disliked.add(food)
                all_disliked.append(food)

    # 선호 음식 합집합
    all_preferred: list[str] = []
    seen_preferred: set[str] = set()
    for p in prefs:
        for food in p.preferred_foods or []:
            if food not in seen_preferred:
                seen_preferred.add(food)
                all_preferred.append(food)

    # 메모 수집
    notes = [p.note for p in prefs if p.note and p.note.strip()]

    return {
        "has_preferences": True,
        "all_submitted": len(prefs) >= total_members,
        "total_members": total_members,
        "submitted_count": len(prefs),
        "best_location": best_location,
        "common_times": common_times,
        "all_disliked_foods": all_disliked,
        "all_preferred_foods": all_preferred,
        "notes": notes,
    }


def _contains_disliked_keyword(category: str, disliked_foods: list[str]) -> str | None:
    normalized_category = str(category or "").strip().lower()
    for keyword in disliked_foods:
        normalized_keyword = str(keyword).strip().lower()
        if normalized_keyword and normalized_keyword in normalized_category:
            return str(keyword).strip()
    return None


async def _run_place_self_correction(
    place_list: list[dict[str, Any]],
    disliked_foods: list[str],
) -> list[dict[str, Any]]:
    if not place_list or not disliked_foods:
        return place_list

    prompt = (
        "다음 장소 추천 목록에서 "
        f"{json.dumps(disliked_foods, ensure_ascii=False)}"
        "에 해당하는 항목이 있으면 제거하고, 제거된 경우 그 이유를 reason 필드에 추가해줘: "
        f"{json.dumps(place_list, ensure_ascii=False)}\n"
        "반드시 JSON 배열만 반환하세요."
    )
    try:
        corrected_places = _extract_json_array(await call_gemini(prompt))
    except Exception:
        return place_list
    if not corrected_places:
        return place_list

    original_by_id = {
        str(place.get("place_id")): dict(place)
        for place in place_list
        if place.get("place_id") not in (None, "")
    }
    merged_places: list[dict[str, Any]] = []
    for corrected_place in corrected_places:
        place_id = str(corrected_place.get("place_id", ""))
        base_place = original_by_id.get(place_id, {})
        merged_places.append({**base_place, **corrected_place})
    return merged_places


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


async def _register_google_calendar(state: GraphState) -> dict[str, Any]:
    """최종 확정 전에는 캘린더 자동 등록을 보류합니다."""
    selected_slot = state["calendar_free_slots"][0] if state.get("calendar_free_slots") else {}
    return {
        "provider": "google_calendar",
        "status": "skipped",
        "reason": "pending_confirmation",
        "scheduled_at": selected_slot.get("start_at"),
    }


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
        return state
    except Exception as exc:
        return await _handle_node_exception("general_response", state, exc)


async def intent_detection(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
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
                cuisine = _detect_cuisine_type(latest_user_message)
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
        return state
    except Exception as exc:
        return await _handle_node_exception("intent_detection", state, exc)


async def entity_extraction(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
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
            cuisine = _detect_cuisine_type(latest_msg)
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

        # Multi-date: resolve each date hint to ISO dates
        if len(raw_date_hints) >= 2:
            resolved_hints: list[str] = []
            for hint in raw_date_hints:
                if _is_iso_date_hint(hint):
                    resolved_hints.append(hint)
                else:
                    parsed = await _parse_natural_date(hint)
                    if parsed and parsed.get("date"):
                        resolved_hints.append(parsed["date"])
                    else:
                        resolved_hints.append(hint)  # keep raw if can't resolve
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
        return state
    except Exception as exc:
        return await _handle_node_exception("entity_extraction", state, exc)


async def slot_filling(state: GraphState) -> GraphState:
    """빠진 정보를 질문하지 않고, 현재 가진 정보만으로 최선의 행동을 수행합니다.

    - date만 있으면: 날짜 확인 + 나머지는 대화에서 자연스럽게 나오면 정리하겠다고 안내
    - date+place 있으면: 장소 추천 바로 실행 (location_first_ready)
    - date+place+headcount 있으면: 투표 카드 자동 생성 (slots_filled)
    - 아무것도 없으면: 조용히 대기 (질문하지 않음)
    """
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state

        _update_slot_state(state, state.get("extracted_entities", {}))
        pref_data = await _load_meeting_preferences(state)
        _enrich_with_preferences(state, pref_data)

        trigger = state.get("trigger_reason")
        if trigger == "stalemate_judged":
            return await _slot_filling_stalemate(state, pref_data)
        if trigger == "conclusion_detected":
            return await _slot_filling_conclusion(state, pref_data)
        if trigger == "all_members_selected":
            return await _slot_filling_all_members(state, pref_data)
        return await _slot_filling_default(state, pref_data)
    except Exception as exc:
        return await _handle_node_exception("slot_filling", state, exc)


def _enrich_with_preferences(state: GraphState, pref_data: dict[str, Any]) -> None:
    if pref_data.get("has_preferences") and state.get("intent") != "place_suggestion":
        if not state.get("place_hint") and pref_data.get("best_location"):
            state["place_hint"] = pref_data["best_location"]
            logger.info("[PREF] place_hint set from preferences: %s", pref_data["best_location"])
        if not state.get("headcount") and pref_data.get("total_members"):
            state["headcount"] = pref_data["total_members"]
        if not state.get("meeting_type"):
            state["meeting_type"] = "모임"
        if pref_data.get("all_submitted") and state.get("intent") in (
            "meeting_schedule", "place_suggestion", None,
        ):
            common_times = pref_data.get("common_times", [])
            if common_times:
                state["preference_common_times"] = common_times
            if not state.get("all_slots_filled"):
                state["all_slots_filled"] = True
                state["missing_slots"] = []
                if state.get("place_hint"):
                    logger.info("[PREF] All preferences submitted. Auto-suggesting with place=%s", state["place_hint"])
                else:
                    logger.info("[PREF] All preferences submitted. Auto-suggesting (no place hint, time-only)")
        elif not pref_data.get("all_submitted"):
            common_times = pref_data.get("common_times", [])
            if common_times:
                state["preference_common_times"] = common_times

    state["is_location_first"] = (
        bool(state.get("place_hint"))
        and not bool(state.get("date_hint"))
        and state.get("intent") != "meeting_schedule"
    )
    state["time_options"] = _build_flexible_time_options(state)


async def _slot_filling_stalemate(state: GraphState, pref_data: dict[str, Any]) -> GraphState:
    # 해결점 N: 거부 후 다음 주로 확장된 케이스 — 사용자 선호에 맞는 다음주 전체 후보 생성
    if state.get("expanded_to_next_week"):
        common_times = pref_data.get("common_times") or []
        prefers_weekday = any(str(t).startswith("평일") for t in common_times)
        prefers_weekend = any(str(t).startswith("주말") for t in common_times)
        # 선호 미입력 시 기본값: 둘 다 가능 (보수적)
        if not prefers_weekday and not prefers_weekend:
            prefers_weekday = True
            prefers_weekend = True

        rejected_set = {
            r.get("date") for r in (state.get("rejected_dates") or [])
            if isinstance(r, dict) and isinstance(r.get("date"), str)
        }

        # 오늘부터 시작 — 가까운 평일/주말부터 후보 제시. 거부 set 제외.
        today = datetime.now(KST).date()

        # 오늘부터 21일 스캔 — 거부 후 가까운 후보 우선, 다 차면 종료
        candidates: list[str] = []
        for offset in range(21):
            d = today + timedelta(days=offset)
            is_weekend = d.weekday() >= 5
            if is_weekend and not prefers_weekend:
                continue
            if not is_weekend and not prefers_weekday:
                continue
            iso = d.strftime("%Y-%m-%d")
            if iso in rejected_set:
                continue
            candidates.append(iso)
            if len(candidates) >= 5:  # vote UX: 최대 5개
                break

        if not candidates:
            logger.info("[STALEMATE] No alternatives match user preference, fallback to default")
            state.pop("expanded_to_next_week", None)
            return await _slot_filling_default(state, pref_data)

        state["date_hints"] = candidates
        state["date_hint"] = candidates[0]

        rejected_summary = ", ".join(sorted(rejected_set))
        narrator = (
            "안 되는 날짜들 빼고 가까운 일정으로 추천드릴게요! 📅"
        )
        await _emit_assistant_message(state["room_id"], state["db"], narrator, state)
        if not state.get("headcount"):
            state["headcount"] = pref_data.get("total_members", 4)
        if not state.get("meeting_type"):
            state["meeting_type"] = "모임"
        state["all_slots_filled"] = True
        state["missing_slots"] = []
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "multi_date_vote"
        logger.info(
            "[STALEMATE] Generated alternatives from today (rejected=%s, candidates=%s, weekday_pref=%s, weekend_pref=%s)",
            rejected_summary, candidates, prefers_weekday, prefers_weekend,
        )
        return state

    if not (state.get("conflict_detected") and state.get("conflict_options")):
        return await _slot_filling_default(state, pref_data)

    conflict_type = state.get("conflict_type", "date")
    options = state.get("conflict_options", [])
    options_text = "과 ".join(f"**{o}**" for o in options)
    mediation_msg = f"{options_text} 의견이 나뉘네요! 😊\n"
    if pref_data.get("has_preferences"):
        total = pref_data.get("total_members", 0)
        common = pref_data.get("common_times", [])
        if common and conflict_type in ("date", "time"):
            mediation_msg += f"선호 정보를 보면 공통 가능 시간대는 {', '.join(common)}이에요.\n"
        mediation_msg += f"총 {total}명의 선호를 고려해서 "
    mediation_msg += "투표로 결정할까요?"
    await _emit_assistant_message(state["room_id"], state["db"], mediation_msg, state)

    if conflict_type == "date" and len(options) >= 2:
        state["date_hints"] = options
    elif conflict_type == "place" and len(options) >= 2:
        state["place_hint"] = options[0]
    if not state.get("headcount"):
        state["headcount"] = pref_data.get("total_members", 4)
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "multi_date_vote"
    logger.info("[CONFLICT] Mediation triggered: type=%s options=%s", conflict_type, options)
    return state


async def _slot_filling_conclusion(state: GraphState, pref_data: dict[str, Any]) -> GraphState:
    has_date = bool(state.get("date_hint"))
    has_place = bool(state.get("place_hint"))
    if not has_date and not has_place:
        state["new_assistant_messages"] = []
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "conclusion_false_positive"
        logger.info("[TRIGGER] conclusion_detected false positive, silent abort")
        return state

    if not state.get("headcount"):
        state["headcount"] = pref_data.get("total_members", 4)
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "slots_filled" if has_date and has_place else "slots_filled_with_defaults"
    return state


async def _slot_filling_all_members(state: GraphState, pref_data: dict[str, Any]) -> GraphState:
    best_location = pref_data.get("best_location")
    if state.get("place_hint"):
        state["status"] = "location_first_ready"
        logger.info("[TRIGGER] all_members_selected with place_hint=%s", state.get("place_hint"))
    elif best_location:
        state["place_hint"] = best_location
        state["status"] = "location_first_ready"
        logger.info("[TRIGGER] all_members_selected using preference location=%s", best_location)
    else:
        state["partial_mode"] = "time_only"
        state["status"] = "time_only_ready"
        logger.info("[TRIGGER] all_members_selected time-only partial card")

    if not state.get("headcount"):
        state["headcount"] = pref_data.get("total_members", 4)
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    return state


async def _slot_filling_default(state: GraphState, pref_data: dict[str, Any]) -> GraphState:
    if state.get("conflict_detected") and state.get("conflict_options"):
        return await _slot_filling_stalemate(state, pref_data)

    multi_date_hints = state.get("date_hints") or []
    if len(multi_date_hints) >= 2:
        return _slot_filling_default_multi_date(state)

    has_date = bool(state.get("date_hint"))
    has_place = bool(state.get("place_hint"))
    has_headcount = state.get("headcount") is not None
    if state.get("is_location_first"):
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "location_first_ready"
        return state

    if state["all_slots_filled"]:
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "slots_filled"
        return state

    if has_date and has_place and has_headcount:
        return await _slot_filling_default_confirmed(state)
    if has_date and has_place:
        return await _slot_filling_default_with_defaults(state, has_headcount)
    return await _slot_filling_default_partial(state, has_date, has_place)


def _slot_filling_default_multi_date(state: GraphState) -> GraphState:
    if not state.get("headcount"):
        state["headcount"] = 4  # 기본값
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "multi_date_vote"
    return state


async def _slot_filling_default_confirmed(state: GraphState) -> GraphState:
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    date_display = state.get("date_hint", "")
    place_display = state.get("place_hint", "")
    confirm_msg = (
        f"{date_display}에 {place_display}에서 {state.get('headcount', '')}명이요! 👍 "
        "일정과 장소를 정리해드릴게요~"
    )
    await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "slots_filled"
    return state


async def _slot_filling_default_with_defaults(state: GraphState, has_headcount: bool) -> GraphState:
    if not has_headcount:
        state["headcount"] = 4  # 기본값
    if not state.get("meeting_type"):
        state["meeting_type"] = "모임"
    date_display = state.get("date_hint", "")
    place_display = state.get("place_hint", "")
    confirm_msg = (
        f"{date_display}에 {place_display}에서요! 👍 "
        "일정과 장소를 정리해드릴게요~"
    )
    await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)
    state["all_slots_filled"] = True
    state["missing_slots"] = []
    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "slots_filled_with_defaults"
    return state


async def _slot_filling_default_partial(state: GraphState, has_date: bool, has_place: bool) -> GraphState:
    if has_date and not has_place:
        state["slot_filling_turns"] += 1
        if state["slot_filling_turns"] <= 1:
            date_display = state.get("date_hint", "")
            confirm_msg = (
                f"{date_display} 좋아요! 👍 "
                "장소나 인원이 대화에서 나오면 제가 바로 정리해드릴게요~"
            )
            await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)

        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "partial_info_acknowledged"
        return state

    if has_place and not has_date and state.get("intent") != "meeting_schedule":
        state["slot_filling_turns"] += 1
        if state["slot_filling_turns"] <= 1:
            place_display = state.get("place_hint", "")
            confirm_msg = (
                f"{place_display} 근처로요! 🔍 "
                "맛집 몇 개 찾아볼게요~ 날짜는 대화에서 나오면 정리할게요!"
            )
            await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)
        state["is_location_first"] = True
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "partial_info_acknowledged"
        state["all_slots_filled"] = True  # function_calling으로 진행
        return state

    if state.get("intent") in ("meeting_schedule", "place_suggestion"):
        latest_content = ""
        for msg in reversed(state["message_records"]):
            if msg.get("role") == "user" and msg.get("content"):
                latest_content = msg["content"].strip()
                break
        confirm_msg = (
            f"네! \"{latest_content}\" 알겠어요 👍 "
            "좀 더 구체적인 날짜나 장소가 나오면 바로 정리해드릴게요~"
        )
        await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)

    state["awaiting_user_reply"] = False
    state["wait_timed_out"] = False
    state["message_count_since_last_trigger"] = 0
    state["status"] = "no_slots_yet"
    return state


def _build_multi_date_slots(state: GraphState) -> list[dict[str, Any]]:
    """여러 날짜 힌트로부터 투표용 슬롯을 생성합니다."""
    date_hints = state.get("date_hints") or []
    now_kst = datetime.now(KST)
    slots: list[dict[str, Any]] = []
    preferred_times = _normalize_preferred_times(state.get("preference_common_times"))

    for index, hint in enumerate(date_hints, start=1):
        target_date: datetime | None = None

        # ISO date (YYYY-MM-DD)
        if _is_specific_iso_date(hint):
            try:
                target_date = datetime.strptime(hint, "%Y-%m-%d").replace(tzinfo=KST)
            except ValueError:
                pass
        else:
            # Try fallback natural date parsing (synchronous)
            parsed = _fallback_parse_natural_date(hint, now_kst)
            if parsed and parsed.get("date"):
                try:
                    target_date = datetime.strptime(parsed["date"], "%Y-%m-%d").replace(tzinfo=KST)
                except ValueError:
                    pass

        if target_date is None:
            continue

        start_hour = 14
        end_hour = 17
        is_weekend = target_date.weekday() >= 5
        for pref_time in preferred_times:
            if pref_time.startswith("평일") and is_weekend:
                continue
            if pref_time.startswith("주말") and not is_weekend:
                continue
            pref_range = PREFERRED_TIME_RANGES[pref_time]
            start_hour, end_hour = pref_range
            break

        end_of_pref = target_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        # 오늘 + 현재 시각이 선호 시간대 시작 이후면 now+1h로 시작 (즉시 약속 UX).
        # 1시간짜리 슬롯이 선호 시간대 안에 못 들어가면 오늘 후보 스킵.
        if target_date.date() == now_kst.date() and now_kst.hour >= start_hour:
            bumped = (now_kst + timedelta(hours=1)).replace(second=0, microsecond=0)
            if bumped + timedelta(minutes=SLOT_MINUTES) > end_of_pref:
                continue
            start_at = bumped
        else:
            start_at = target_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end_at = min(start_at + timedelta(minutes=SLOT_MINUTES), end_of_pref)
        holiday = _get_korean_holiday(target_date)

        slots.append({
            "slot_id": f"date-option-{index}",
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "label": _format_slot_label(start_at, []),
            "available_count": state.get("headcount"),
            "total_count": state.get("headcount"),
            "has_conflict": False,
            "unavailable_users": [],
            "is_holiday": bool(holiday),
            "holiday_name": holiday,
            "is_weekend": _is_weekend(target_date),
        })

    return slots


def _build_preference_time_slots(
    state: GraphState, pref_times: list[str],
    blocked_dates: Optional[set[str]] = None,
) -> list[dict[str, Any]]:
    """선호 시간대 기반으로 이번 주/다음 주 투표용 슬롯을 생성합니다.
    blocked_dates에 있는 날짜는 애초에 생성하지 않음 (뒤에서 잘라내면 5개 미만 위험)."""
    now_kst = datetime.now(KST)
    slots: list[dict[str, Any]] = []
    slot_index = 0
    _blocked = blocked_dates or set()
    normalized_pref_times = _normalize_preferred_times(pref_times)

    # 오늘 포함 향후 4주 — 오늘은 현재 시각 + 1h 룰로 즉시 약속 가능.
    for day_offset in range(0, 29):
        target = now_kst + timedelta(days=day_offset)
        weekday = target.weekday()  # 0=월 6=일
        is_weekend = weekday >= 5
        if target.strftime("%Y-%m-%d") in _blocked:
            continue

        for pref_time in normalized_pref_times:
            # 평일/주말 필터
            if pref_time.startswith("평일") and is_weekend:
                continue
            if pref_time.startswith("주말") and not is_weekend:
                continue

            hours = PREFERRED_TIME_RANGES.get(pref_time)
            if not hours:
                continue

            start_h, end_h = hours
            end_of_pref = target.replace(hour=end_h, minute=0, second=0, microsecond=0)
            # 오늘 + 현재 시각이 선호 시간대 시작 이후면 now+1h로 시작.
            if target.date() == now_kst.date() and now_kst.hour >= start_h:
                bumped = (now_kst + timedelta(hours=1)).replace(second=0, microsecond=0)
                if bumped + timedelta(minutes=SLOT_MINUTES) > end_of_pref:
                    continue
                start_at = bumped
            else:
                start_at = target.replace(hour=start_h, minute=0, second=0, microsecond=0)
            end_at = min(start_at + timedelta(minutes=SLOT_MINUTES), end_of_pref)

            # 과거 시간 건너뛰기 (안전망 — 위 로직이 보통 차단)
            if start_at <= now_kst:
                continue

            holiday = _get_korean_holiday(target)

            slot_index += 1
            slots.append({
                "slot_id": f"pref-slot-{slot_index}",
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "label": _format_slot_label(start_at, []),
                "available_count": state.get("headcount"),
                "total_count": state.get("headcount"),
                "has_conflict": False,
                "unavailable_users": [],
                "is_holiday": bool(holiday),
                "holiday_name": holiday,
                "is_weekend": is_weekend,
            })

            if len(slots) >= 5:
                break
        if len(slots) >= 5:
            break

    # 최소 3개 슬롯 보장: 선호 시간대가 좁아서 슬롯이 부족하면 같은 시간 창에서 보강
    if len(slots) < 3 and normalized_pref_times:
        fallback_pref = normalized_pref_times[0]
        fallback_hours = PREFERRED_TIME_RANGES[fallback_pref]
        for day_offset in range(1, 29):
            if len(slots) >= 3:
                break
            target = now_kst + timedelta(days=day_offset)
            date_str = target.strftime("%Y-%m-%d")
            if date_str in _blocked:
                continue
            is_weekend = target.weekday() >= 5
            if fallback_pref.startswith("평일") and is_weekend:
                continue
            if fallback_pref.startswith("주말") and not is_weekend:
                continue
            start_at = target.replace(hour=fallback_hours[0], minute=0, second=0, microsecond=0)
            if start_at <= now_kst:
                continue
            end_at = min(
                start_at + timedelta(minutes=SLOT_MINUTES),
                target.replace(hour=fallback_hours[1], minute=0, second=0, microsecond=0),
            )
            # 중복 날짜 체크
            existing_dates = {s["start_at"][:10] for s in slots}
            if date_str in existing_dates:
                continue
            holiday = _get_korean_holiday(target)
            slot_index += 1
            slots.append({
                "slot_id": f"pref-slot-{slot_index}",
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "label": _format_slot_label(start_at, []),
                "available_count": state.get("headcount"),
                "total_count": state.get("headcount"),
                "has_conflict": False,
                "unavailable_users": [],
                "is_holiday": bool(holiday),
                "holiday_name": holiday,
                "is_weekend": target.weekday() >= 5,
            })

    return slots[:5]


async def function_calling(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state
        if state["status"] == "conclusion_false_positive":
            logger.info("[TIMING] function_calling (false_positive): %.2fs", time.monotonic() - _t0)
            return state
        if state["status"] == "time_only_ready":
            state["calendar_free_slots"] = []
            state["place_search_results"] = []
            logger.info("[TIMING] function_calling (time_only_ready): %.2fs", time.monotonic() - _t0)
            return state
        state["blocker_notification_payload"] = None

        # entity_extraction이 "다시 추천해줘" 같은 재시도 지시어에서 "다시"를
        # place_hint로 잘못 뽑는 경우 있음 — 카카오맵 검색이 무의미해지니 스킵.
        _NOISE_PLACE_HINTS = {
            "다시", "재시도", "또", "한번더", "한 번 더", "다시해봐", "다시 해줘",
            "다시 해", "재추천", "추천", "다시추천",
        }
        pl = state.get("place_hint")
        if isinstance(pl, str) and pl.strip() in _NOISE_PLACE_HINTS:
            state["place_hint"] = None

        if state.get("intent") == "place_suggestion":
            place_results = await search_place(state)
            state["place_search_results"] = place_results
            state["status"] = "functions_called"
            logger.info("[TIMING] function_calling (place-suggestion): %.2fs", time.monotonic() - _t0)
            return state

        # 방의 '불가능 날짜' — 모든 경로의 최종 후보에서 제외.
        room_pk = _room_id_as_int(state["room_id"])
        blocked_dates = await _load_blocked_dates(room_pk)
        rejected_dates = state.get("rejected_dates") or []

        # 여러 날짜 선택지 → 각 날짜별 슬롯 생성
        multi_date_hints = state.get("date_hints") or []
        if state.get("intent") != "place_suggestion" and len(multi_date_hints) >= 2:
            multi_slots = _filter_out_rejected(
                _filter_out_blocked(_build_multi_date_slots(state), blocked_dates),
                rejected_dates,
            )
            if multi_slots:
                state["calendar_free_slots"] = multi_slots
                state["calendar_strategy"] = "multi_date_vote"
                place_results = await search_place(state)
                state["place_search_results"] = place_results
                state["status"] = "functions_called"
                logger.info("[TIMING] function_calling (multi-date): %.2fs", time.monotonic() - _t0)
                return state

        # 선호 데이터 기반 자동 제안: preference_common_times로 슬롯 생성
        pref_times = state.get("preference_common_times") or []
        if (
            pref_times
            and not state.get("date_hint")
            and state.get("intent") != "place_suggestion"
        ):
            # 생성 단계부터 blocked_dates를 제외하면서 만들어야 5개 채우기 가능.
            pref_slots = _build_preference_time_slots(state, pref_times, blocked_dates)
            pref_slots = _filter_out_rejected(pref_slots, rejected_dates)
            state["calendar_free_slots"] = pref_slots
            state["calendar_strategy"] = "preference_based"
            place_results = await search_place(state)
            state["place_search_results"] = place_results
            state["status"] = "functions_called"
            logger.info("[TIMING] function_calling (preference-based): %.2fs", time.monotonic() - _t0)
            return state

        if (
            state.get("intent") != "place_suggestion"
            and state.get("is_location_first")
            and not state.get("date_hint")
        ):
            state["calendar_free_slots"] = []
            place_results = await search_place(state)
        elif (
            state.get("intent") != "place_suggestion"
            and state.get("time_options")
            and not state.get("preference_common_times")
        ):
            state["calendar_free_slots"] = _filter_out_rejected(
                _filter_out_blocked(_build_time_option_slots(state), blocked_dates),
                rejected_dates,
            )
            state["calendar_strategy"] = "natural_language_time_options"
            place_results = await search_place(state)
        else:
            free_slots, place_results = await asyncio.gather(
                get_free_slots(state),
                search_place(state),
            )
            # get_free_slots에서 이미 필터링되지만, 이중 방어.
            state["calendar_free_slots"] = _filter_out_rejected(
                _filter_out_blocked(free_slots, blocked_dates),
                rejected_dates,
            )
            blocker_counts: dict[str, int] = {}
            if free_slots and any(slot.get("has_conflict") for slot in free_slots):
                for slot in free_slots:
                    for unavailable_user in slot.get("unavailable_users", []):
                        blocker_counts[unavailable_user] = blocker_counts.get(unavailable_user, 0) + 1
                if blocker_counts:
                    blocker_name = max(
                        blocker_counts.items(),
                        key=lambda item: (item[1], item[0]),
                    )[0]
                    state["blocker_notification_payload"] = {
                        "type": "social_system_message",
                        "room_id": state["room_id"],
                        "sender": "매듭이",
                        "content": f"@{blocker_name}님, 혹시 일정 조정이 가능하신가요? 😊",
                        "blocker_name": blocker_name,
                    }
        state["place_search_results"] = place_results
        state["status"] = "functions_called"
        logger.info("[TIMING] function_calling: %.2fs", time.monotonic() - _t0)
        return state
    except Exception as exc:
        return await _handle_node_exception("function_calling", state, exc)


async def supervisor_validation(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state
        if state.get("status") in ("conclusion_false_positive", "time_only_ready"):
            return state
        errors: list[str] = []
        now = datetime.now(timezone.utc)
        valid_slots: list[dict[str, Any]] = []
        has_preference_time_slots = bool(
            state.get("calendar_strategy") == "preference_based"
            and state.get("preference_common_times")
        )
        is_location_first = bool(
            state.get("is_location_first")
            and not state.get("date_hint")
            and not has_preference_time_slots
        )
        is_multi_date_vote = state.get("calendar_strategy") == "multi_date_vote"

        headcount = state.get("headcount")
        if headcount is None and not is_location_first and not is_multi_date_vote:
            errors.append("headcount is required")
        elif headcount is not None and headcount > 20:
            errors.append("headcount exceeds current recommendation constraints")

        if not is_location_first:
            for slot in state.get("calendar_free_slots", []):
                start_at = _parse_iso_datetime(slot.get("start_at"))
                end_at = _parse_iso_datetime(slot.get("end_at"))
                if start_at is None or end_at is None:
                    errors.append("calendar slot has invalid timestamps")
                    continue
                if start_at < now:
                    errors.append("calendar slot is in the past")
                    continue
                if end_at <= start_at:
                    errors.append("calendar slot duration is invalid")
                    continue
                valid_slots.append(slot)

        valid_places: list[dict[str, Any]] = []
        for place in state.get("place_search_results", []):
            max_headcount = _coerce_headcount(place.get("max_headcount"))
            if headcount is not None and max_headcount is not None and max_headcount < headcount:
                continue
            valid_places.append(place)

        is_preference_based = state.get("calendar_strategy") == "preference_based"

        is_place_only = state.get("intent") == "place_suggestion"
        if not valid_slots and not is_location_first and not is_place_only:
            errors.append("no valid free time slots available")
        # preference_based 추천은 시간 후보가 주된 결과물 — 장소 검색이 실패해도
        # 일정 투표 카드라도 내보내기 위해 통과.
        if (
            not valid_places
            and not is_location_first
            and not is_multi_date_vote
            and not is_preference_based
        ):
            errors.append("no place recommendations satisfy the headcount")

        state["calendar_free_slots"] = valid_slots
        state["place_search_results"] = valid_places
        state["validation_errors"] = errors

        # location_first 모드에서는 장소 결과만 중요 — 시간 슬롯 없어도 통과
        # multi_date_vote 모드에서는 시간 슬롯만 중요 — 장소 없어도 통과
        if is_location_first or is_multi_date_vote or is_place_only:
            state["validation_passed"] = bool(valid_slots) if is_multi_date_vote else True
            state["status"] = "validated"
        else:
            state["validation_passed"] = not errors
            state["status"] = "validated" if not errors else "validation_failed"

        if not state["validation_passed"] and errors:
            error_summary = "; ".join(errors)
            await _emit_assistant_message(
                state["room_id"],
                state["db"],
                f"죄송해요, 조건에 맞는 시간이나 장소를 찾지 못했어요. ({error_summary}) "
                "날짜나 장소 조건을 조금 바꿔서 다시 시도해볼까요?",
                state,
            )

        logger.info("[TIMING] supervisor_validation: %.2fs", time.monotonic() - _t0)
        return state
    except Exception as exc:
        return await _handle_node_exception("supervisor_validation", state, exc)


def _card_payload_meeting_id(payload: dict[str, Any] | None) -> int | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("meeting_id")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


async def _ensure_pending_meeting_id(state: GraphState, title: str) -> int:
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    if room_pk is None:
        raise ValueError(f"room_id is invalid for pending meeting creation: {state['room_id']!r}")

    # F-1 fix (2026-05-07) + Codex P2 강화 (2026-05-07):
    # 같은 흐름 (vote_card → place → maedeup)에서 발행된 pending meeting을 재사용해
    # frontend cardsByMeetingId가 단일 meeting_id로 라이프사이클 유지하도록 함. 단,
    # "룸의 최신 pending"을 무조건 재사용하면 무관한 stale pending(예: 어제 vote에서 남은 것)에
    # 새 카드가 잘못 붙는 사각지대가 있어, 가드 2단계:
    #   1) date_hint와 scheduled_at이 일치하는 pending 우선 (강한 증거 — 시간 제한 X,
    #      장시간 합의 흐름도 정상 처리)
    #   2) date_hint 없음/매칭 실패 → 최근 30분 내 생성된 pending만 (약한 증거,
    #      stale flow 차단용 단일 세션 보장)
    # 둘 다 매칭 실패 시 새로 생성.
    existing_pending: MeetingSchedule | None = None

    date_hint = state.get("date_hint")
    date_iso = date_hint[:10] if isinstance(date_hint, str) and re.match(r"^\d{4}-\d{2}-\d{2}", date_hint) else None

    if date_iso:
        # Codex P2 review v2 (2026-05-07): vote_options에 multi-date 슬롯이 있을 때
        # MeetingSchedule.scheduled_at은 첫 옵션만 반영하므로 SQL where절만으론 부분 매칭.
        # 따라서 룸 최근 pending 10건을 가져와 Python에서 scheduled_at OR vote_options 매칭.
        try:
            target_date = datetime.fromisoformat(f"{date_iso}T00:00:00")
            next_day = target_date + timedelta(days=1)
            candidates = (
                await db.execute(
                    select(MeetingSchedule)
                    .where(MeetingSchedule.room_id == room_pk)
                    .where(MeetingSchedule.status == "pending")
                    .order_by(MeetingSchedule.created_at.desc())
                    .limit(10)
                )
            ).scalars().all()
            for cand in candidates:
                # 1) scheduled_at primary date 매칭
                sched_at = cand.scheduled_at
                if sched_at is not None and target_date <= sched_at < next_day:
                    existing_pending = cand
                    break
                # 2) vote_options 슬롯 중 어느 하나라도 같은 날짜면 매칭 (multi-date vote 케이스)
                for opt in (cand.vote_options or []):
                    if not isinstance(opt, dict):
                        continue
                    opt_start = opt.get("start_at")
                    if isinstance(opt_start, str) and opt_start.startswith(date_iso):
                        existing_pending = cand
                        break
                if existing_pending is not None:
                    break
        except (ValueError, TypeError):
            existing_pending = None

    if existing_pending is None:
        # date_hint 매칭 실패 또는 없음 → 최근 30분 내 pending만 fallback (stale flow 차단).
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        recent_threshold = now_naive - timedelta(minutes=30)
        existing_pending = (
            await db.execute(
                select(MeetingSchedule)
                .where(MeetingSchedule.room_id == room_pk)
                .where(MeetingSchedule.status == "pending")
                .where(MeetingSchedule.created_at > recent_threshold)
                .order_by(MeetingSchedule.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if existing_pending is not None and existing_pending.id is not None:
        logger.info(
            "Reusing existing pending meeting id=%s for room=%s (F-1: same-flow continuation)",
            existing_pending.id, room_pk,
        )
        return existing_pending.id

    member_result = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room_pk).limit(1)
    )
    first_member = member_result.scalar_one_or_none()
    if first_member is None:
        raise ValueError(f"No members found in room {room_pk}; cannot determine created_by")

    selected_slot = state["calendar_free_slots"][0] if state.get("calendar_free_slots") else {}
    slot_start = _parse_iso_datetime(selected_slot.get("start_at")) if selected_slot.get("start_at") else None
    slot_end = _parse_iso_datetime(selected_slot.get("end_at")) if selected_slot.get("end_at") else None
    if slot_start is None:
        slot_start = datetime.now(timezone.utc).replace(tzinfo=None)
    if slot_end is None:
        slot_end = slot_start + timedelta(hours=2)
    if slot_start.tzinfo is not None:
        slot_start = slot_start.replace(tzinfo=None)
    if slot_end.tzinfo is not None:
        slot_end = slot_end.replace(tzinfo=None)

    new_meeting = MeetingSchedule(
        room_id=room_pk,
        title=title,
        scheduled_at=slot_start,
        end_at=slot_end,
        vote_options=None,
        votes={},
        status="pending",
        created_by=first_member.user_id,
    )
    db.add(new_meeting)
    await db.commit()
    await db.refresh(new_meeting)
    if new_meeting.id is None:
        raise ValueError("Pending meeting creation did not return an id")
    logger.info("Created pending meeting id=%s for card payload", new_meeting.id)
    return new_meeting.id


async def vote_card_creation(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state

        if state.get("no_date_selection"):
            narrator = "먼저 오른쪽 캘린더에서 가능한 날짜를 선택해주세요. 멤버들이 날짜를 선택하면 최적 시간대를 추천해드릴게요. 📅"
            async with AsyncSessionLocal() as db:
                await _emit_assistant_message(state["room_id"], db, narrator, state, shared=True)
            state["status"] = "vote_card_skipped"
            logger.info("[TIMING] vote_card_creation: skipped (no date selection) %.2fs", time.monotonic() - _t0)
            return state

        selected_slot = state["calendar_free_slots"][0] if state.get("calendar_free_slots") else {}
        start_at = _parse_iso_datetime(selected_slot.get("start_at")) if selected_slot else None
        meeting_id = selected_slot.get("meeting_id") or selected_slot.get("id")
        if state.get("date_hint"):
            state["confirmed_date"] = state.get("date_hint")
        if start_at is not None:
            state["confirmed_time"] = _format_confirmed_time(start_at)
        is_multi_date = state.get("calendar_strategy") == "multi_date_vote"
        calendar_slots = state.get("calendar_free_slots") or []

        # 단일 날짜 + 슬롯 1개 = 투표 불필요 (선호 기반은 항상 투표 카드 생성)
        is_preference_based = state.get("calendar_strategy") == "preference_based"
        if not is_multi_date and not is_preference_based and len(calendar_slots) <= 1:
            state["status"] = "vote_card_skipped"
            logger.info("[TIMING] vote_card_creation: skipped (single slot) %.2fs", time.monotonic() - _t0)
            return state

        vote_title = (
            f"{state.get('meeting_type') or '모임'} 날짜 투표 📅"
            if is_multi_date
            else f"{state.get('meeting_type') or '모임'} 시간 투표"
        )

        pref_times = _normalize_preferred_times(state.get("preference_common_times"))
        has_weekday_pref = any(t.startswith("평일") for t in pref_times)
        vote_slots = state.get("calendar_free_slots", [])
        # 안전망: 상위 노드가 예외로 중단됐을 때도 거부 날짜는 카드에 안 들어가게.
        rejected_safety = state.get("rejected_dates") or []
        if rejected_safety:
            vote_slots = _filter_out_rejected(vote_slots, rejected_safety)
        if has_weekday_pref:
            weekday_only = [s for s in vote_slots if not s.get("is_weekend", False)]
            if weekday_only:
                vote_slots = weekday_only

        # meeting_id가 없으면 DB에 pending meeting 생성 (필터된 vote_slots 사용)
        if not meeting_id:
            db = state["db"]
            room_pk = _room_id_as_int(state["room_id"])
            if room_pk is None:
                raise ValueError(f"room_id is invalid for pending meeting creation: {state['room_id']!r}")
            member_result = await db.execute(
                select(RoomMember).where(RoomMember.room_id == room_pk).limit(1)
            )
            first_member = member_result.scalar_one_or_none()
            if first_member is None:
                raise ValueError(f"No members found in room {room_pk}; cannot determine created_by")
            created_by = first_member.user_id
            first_slot = vote_slots[0] if vote_slots else {}
            slot_start = _parse_iso_datetime(first_slot.get("start_at")) if first_slot.get("start_at") else datetime.now(timezone.utc).replace(tzinfo=None)
            slot_end = _parse_iso_datetime(first_slot.get("end_at")) if first_slot.get("end_at") else slot_start + timedelta(hours=2)
            new_meeting = MeetingSchedule(
                room_id=room_pk,
                title=vote_title,
                scheduled_at=slot_start if not hasattr(slot_start, 'tzinfo') or slot_start.tzinfo is None else slot_start.replace(tzinfo=None),
                end_at=slot_end if not hasattr(slot_end, 'tzinfo') or slot_end.tzinfo is None else slot_end.replace(tzinfo=None),
                vote_options=[
                    {"slot_id": s.get("slot_id"), "label": s.get("label"), "start_at": s.get("start_at"), "end_at": s.get("end_at")}
                    for s in vote_slots
                ],
                votes={},
                status="pending",
                created_by=created_by,
            )
            db.add(new_meeting)
            await db.commit()
            await db.refresh(new_meeting)
            meeting_id = new_meeting.id
            logger.info("Created pending meeting id=%s for vote card", meeting_id)

        state["vote_card_payload"] = {
            "type": "vote_card",
            "title": vote_title,
            "room_id": state["room_id"],
            "meeting_id": meeting_id,
            "time_options": [
                {
                    "slot_id": slot.get("slot_id"),
                    "label": slot.get("label"),
                    "start_at": slot.get("start_at"),
                    "end_at": slot.get("end_at"),
                    "is_holiday": slot.get("is_holiday", False),
                    "holiday_name": slot.get("holiday_name"),
                    "is_weekend": slot.get("is_weekend", False),
                }
                for slot in vote_slots
            ],
            "headcount": state.get("headcount"),
            "blocker_notification": state.get("blocker_notification_payload"),
            "calendar_strategy": state.get("calendar_strategy"),
        }
        state["status"] = "vote_card_created"

        # ── Narrator 메시지 큐에 넣기 (해결점 L: EARLY-EMIT 제거, 정상 emit 경로 단일화)
        try:
            best_label = state.get("calendar_free_slots", [{}])[0].get("label", "")
            if state.get("date_conflict"):
                summary = state.get("date_selection_summary", {})
                parts = [f"{d}: {c}명" for d, c in sorted(summary.items(), key=lambda x: -x[1])]
                narrator = f"날짜가 엇갈리네요 ({', '.join(parts)}). 가장 많이 선택된 날짜 기준으로 {best_label}을(를) 추천드려요. 📅"
            else:
                narrator = f"캘린더 확인 결과, {best_label}을(를) 추천드려요. 📅 아래에서 확인해주세요."
            async with AsyncSessionLocal() as db:
                await _emit_assistant_message(state["room_id"], db, narrator, state, shared=True)
        except Exception:
            logger.debug("vote_card narrator emit failed", exc_info=True)

        logger.info("[TIMING] vote_card_creation: %.2fs", time.monotonic() - _t0)
        return state
    except Exception as exc:
        return await _handle_node_exception("vote_card_creation", state, exc)


async def place_recommendation(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state
        # Fix J: place cards join the same lifecycle as vote/maedeup cards.
        # If no upstream vote exists, create a pending meeting row so the card
        # still has a non-null meeting_id for frontend upsert.
        meeting_id = _card_payload_meeting_id(state.get("vote_card_payload"))
        if state.get("confirmed_place"):
            if meeting_id is None:
                meeting_id = await _ensure_pending_meeting_id(
                    state,
                    f"{state.get('meeting_type') or '모임'} 장소 추천",
                )
            state["place_recommendation_payload"] = {
                "type": "place_recommendation",
                "room_id": state["room_id"],
                "meeting_id": meeting_id,
                "place_hint": state.get("place_hint"),
                "recommendations": [
                    {
                        "name": state.get("confirmed_place"),
                        "score": 1.0,
                        "is_confirmed": True,
                    }
                ],
            }
            state["status"] = "place_recommended"
            logger.info("[TIMING] place_recommendation (confirmed): %.2fs", time.monotonic() - _t0)
            return state

        if not state.get("place_hint"):
            resolved = _resolve_place_hint(state)
            if not resolved:
                # 장소 힌트가 없으면 추천 건너뜀
                state["status"] = "place_skipped"
                logger.info("[TIMING] place_recommendation (skipped, no hint): %.2fs", time.monotonic() - _t0)
                return state
            state["place_hint"] = resolved

        place_results = list(state.get("place_search_results", []))
        ranked_places = place_results
        disliked_foods = await _get_room_member_food_preferences(state)
        # 6 카테고리 personal data 합산 (Gemini prompt용 — 익명).
        member_constraints = await _get_room_member_constraints(state)
        # 해결점 A5-2: 카드 reasoning은 강도순 차등 (강한 제약은 이름 명시 + ✨, 약한 선호는 익명).
        # ⚠ Privacy trade-off (Codex review 2026-05-07 P1, 시연용 의도적 수용):
        # group_constraints_summary는 place_recommendation_payload에 포함되어 shared agent
        # 채널로 broadcast + Redis 24h 캐시. 즉 다른 멤버들이 누가 어떤 식단/지역 제약을
        # 갖는지 보게 됨 — 이전 _build_group_constraints_summary 익명 톤의 의도와 충돌.
        # 사용자 결정 (2026-05-07): 시연 magical moment를 위해 노출 허용. 시연 후 정교화 항목:
        #   - User에 share_name_in_recommendations 플래그 추가 + opt-in 멤버만 이름 노출
        #   - 또는 trigger 사용자에게만 named version, 다른 멤버는 anonymous 표기
        per_user_constraints = await _get_room_member_constraints_named(state)
        group_constraints_summary = (
            _build_named_constraints_summary(per_user_constraints)
            or _build_group_constraints_summary(member_constraints)
        )

        if place_results:
            # 시연 latency 최적화 (2026-05-08): top 10 → top 5.
            # 측정상 place_recommendation 노드가 ~40s 단일 병목, prompt + output 토큰 절반 줄임.
            # frontend는 어차피 top 5만 노출 (line 아래 ranked_places[:5]).
            # Kakao API 응답이 이미 relevance/distance 정렬이라 top 5도 양질.
            top_candidates = place_results[:5]
            headcount = state.get("headcount") or 0
            meeting_type = state.get("meeting_type") or "모임"

            # --- OPTIMIZATION: Skip Gemini scoring for small result sets (<=3) ---
            if len(top_candidates) <= 3:
                logger.info("[OPT] Skipping Gemini place scoring: only %d candidates, using distance-based scores", len(top_candidates))
                reranked: list[dict[str, Any]] = []
                for place in top_candidates:
                    place_copy = dict(place)
                    # Apply disliked food penalty using rule-based check
                    disliked_keyword = _contains_disliked_keyword(
                        str(place_copy.get("category", "")),
                        disliked_foods,
                    )
                    if disliked_keyword:
                        place_copy["score"] = 0.1
                        place_copy["reason"] = (
                            f"멤버 비선호 음식인 {disliked_keyword} 카테고리와 겹쳐 점수를 낮췄어요."
                        )
                    reranked.append(place_copy)
                reranked.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
                ranked_places = reranked + place_results[5:]
            else:
                # Gemini scoring for larger result sets (>3)
                scoring_payload = [
                    {
                        "place_id": place.get("place_id", ""),
                        "name": place.get("name", ""),
                        "address": place.get("address", ""),
                        "category": place.get("category", ""),
                    }
                    for place in top_candidates
                ]
                time_context = ""
                if state.get("confirmed_date") and state.get("confirmed_time"):
                    time_context = (
                        f"이 모임은 {state['confirmed_date']} {state['confirmed_time']}에 예정되어 있습니다. "
                        "해당 시간대에 영업하는 장소를 우선 추천해주세요.\n"
                    )
                elif state.get("confirmed_date"):
                    time_context = (
                        f"이 모임은 {state['confirmed_date']}에 예정되어 있습니다. "
                        "해당 일정에 어울리는 장소를 우선 추천해주세요.\n"
                    )
                dislike_context = ""
                if disliked_foods:
                    dislike_context = (
                        f"멤버 중 {', '.join(disliked_foods)}을(를) 못 먹는 사람이 있으니 "
                        "해당 카테고리 장소 점수를 낮춰줘.\n"
                    )
                # 6 카테고리 personal data를 prompt에 추가 — 익명 합산 형태.
                constraints_context = ""
                if member_constraints.get("food_restrictions"):
                    constraints_context += (
                        f"멤버 중 {', '.join(member_constraints['food_restrictions'])} "
                        "회피가 있으니 해당 음식 식당 점수를 강하게 낮춰줘.\n"
                    )
                if member_constraints.get("disliked_areas"):
                    constraints_context += (
                        f"멤버 중 {', '.join(member_constraints['disliked_areas'])} "
                        "지역을 회피하는 사람이 있으니 해당 지역 점수를 낮춰줘.\n"
                    )
                if member_constraints.get("liked_areas"):
                    constraints_context += (
                        f"멤버 중 {', '.join(member_constraints['liked_areas'])} "
                        "지역을 선호하는 사람이 있으니 해당 지역 점수를 살짝 올려줘.\n"
                    )
                if member_constraints.get("transport_mode"):
                    transports = ", ".join(member_constraints["transport_mode"])
                    constraints_context += (
                        f"멤버 이동수단: {transports}. 대중교통이 있으면 역세권을, "
                        "도보가 있으면 가까운 곳을 우선.\n"
                    )
                scoring_prompt = (
                    "당신은 매듭 AI입니다. 한국인들의 모임 일정과 장소 조율을 돕는 "
                    "어시스턴트입니다.\n"
                    f"아래 장소 후보들을 {headcount}명 {meeting_type} 모임에 얼마나 적합한지 "
                    "0부터 1 사이 점수로 평가하세요.\n"
                    f"{time_context}"
                    f"{dislike_context}"
                    f"{constraints_context}"
                    "반드시 JSON 배열만 반환하세요.\n"
                    '형식: [{\"place_id\": \"...\", \"score\": 0.9}]\n'
                    "place_id는 입력과 동일해야 하며, 모든 후보를 빠짐없이 포함하세요.\n\n"
                    f"장소 후보:\n{json.dumps(scoring_payload, ensure_ascii=False)}"
                )
                try:
                    score_items = _extract_json_array(await call_gemini(scoring_prompt))
                    score_map = {
                        str(item.get("place_id")): float(item.get("score"))
                        for item in score_items
                        if item.get("place_id") not in (None, "")
                    }
                    reranked = []
                    for place in top_candidates:
                        place_copy = dict(place)
                        place_copy["score"] = score_map.get(str(place.get("place_id")), 0.5)
                        disliked_keyword = _contains_disliked_keyword(
                            str(place_copy.get("category", "")),
                            disliked_foods,
                        )
                        if disliked_keyword and float(place_copy.get("score", 0.0)) > 0.6:
                            place_copy["score"] = 0.1
                            place_copy["reason"] = (
                                f"멤버 비선호 음식인 {disliked_keyword} 카테고리와 겹쳐 점수를 낮췄어요."
                            )
                        reranked.append(place_copy)
                    reranked.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
                    ranked_places = reranked + place_results[5:]
                except Exception:
                    ranked_places = []
                    for place in place_results:
                        place_copy = dict(place)
                        place_copy["score"] = 0.5
                        ranked_places.append(place_copy)
        else:
            ranked_places = []

        # --- OPTIMIZATION: Skip self-correction Gemini call when no disliked foods ---
        if ranked_places and disliked_foods:
            top_ranked_places = [dict(place) for place in ranked_places[:5]]
            corrected_places = await _run_place_self_correction(top_ranked_places, disliked_foods)
            remaining_places = ranked_places[5:]
            ranked_places = corrected_places + remaining_places
        elif ranked_places:
            logger.info("[OPT] Skipping place self-correction: no disliked foods")

        state["place_search_results"] = ranked_places
        if meeting_id is None:
            meeting_id = await _ensure_pending_meeting_id(
                state,
                f"{state.get('meeting_type') or '모임'} 장소 추천",
            )
        state["place_recommendation_payload"] = {
            "type": "place_recommendation",
            "room_id": state["room_id"],
            "meeting_id": meeting_id,
            "place_hint": state.get("place_hint"),
            "recommendations": ranked_places[:5],
            # 익명 group constraint 요약 (디자인 P2). 누가 어떤 값을 가졌는지는
            # 식별되지 않음. 프론트는 추천 카드 옆에 이 문장을 reasoning으로 노출.
            "group_constraints_summary": group_constraints_summary,
        }
        state["status"] = "place_recommended"

        # 새로고침 복구용 — 장소 추천 페이로드를 Redis에 캐시 (24h TTL).
        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            try:
                await r.set(
                    f"room_place_rec:{state['room_id']}",
                    json.dumps(state["place_recommendation_payload"], ensure_ascii=False),
                    ex=86400,
                )
            finally:
                await r.aclose()
        except Exception:
            logger.debug("place_rec cache failed", exc_info=True)

        # Narrator: 카드만 띄우고 끝내면 사용자가 "AI가 대답 안 했나?" 헷갈림.
        try:
            count = len(ranked_places[:5])
            hint = state.get("place_hint") or "요청하신 지역"
            narrator = (
                f"{hint} 근처 추천 장소 {count}개를 정리했어요. 📍 아래 카드에서 확인해 주세요."
                if count > 0
                else "추천 장소를 정리해봤어요. 📍 아래 카드를 확인해 주세요."
            )
            async with AsyncSessionLocal() as db:
                await _emit_assistant_message(state["room_id"], db, narrator, state, shared=True)
        except Exception:
            logger.debug("place_recommendation narrator emit failed", exc_info=True)

        logger.info("[TIMING] place_recommendation: %.2fs", time.monotonic() - _t0)
        return state
    except Exception as exc:
        return await _handle_node_exception("place_recommendation", state, exc)


async def maedeup_card_creation(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state
        selected_slot = state["calendar_free_slots"][0] if state.get("calendar_free_slots") else {}
        selected_slot_meeting_id = selected_slot.get("meeting_id") or selected_slot.get("id")
        # Fix J: conclusion/all_members fast paths can enter without a vote card.
        # Reuse any upstream card meeting_id; otherwise create a pending meeting row.
        meeting_id = (
            _card_payload_meeting_id(state.get("vote_card_payload"))
            or _card_payload_meeting_id(state.get("place_recommendation_payload"))
            or _card_payload_meeting_id(selected_slot)
            or (selected_slot_meeting_id if isinstance(selected_slot_meeting_id, int) else None)
        )
        if meeting_id is None:
            meeting_id = await _ensure_pending_meeting_id(
                state,
                f"{state.get('meeting_type') or '모임'} 매듭 카드",
            )
        if state.get("partial_mode") == "time_only":
            parsed_time = state.get("parsed_time_hint")
            date_value = state.get("date_hint")
            selected_time = {}
            if date_value and parsed_time:
                import datetime as _dt
                try:
                    start_dt = _dt.datetime.fromisoformat(f"{date_value}T{parsed_time}:00")
                    end_dt = start_dt + _dt.timedelta(hours=1)
                    selected_time = {
                        "label": f"{date_value} {parsed_time}",
                        "start_at": start_dt.isoformat(),
                        "end_at": end_dt.isoformat(),
                    }
                except Exception:
                    selected_time = {"label": f"{date_value} {parsed_time}"}
            elif date_value:
                selected_time = {"label": date_value}
            elif parsed_time:
                selected_time = {"label": parsed_time}
            payload = {
                "type": "maedeup_card",
                "meeting_id": meeting_id,
                "date": date_value,
                "time": parsed_time,
                "place": None,
                "place_pending": True,
                "place_pending_message": "멤버들이 장소를 정하면 자동으로 정리해드릴게요!",
                "headcount": state.get("headcount"),
                "calendar_registered": False,
                "title": f"{state.get('meeting_type') or '모임'} 매듭 카드",
                "meeting_type": state.get("meeting_type") or "모임",
                "date_hint": date_value or state.get("date") or "",
                "selected_time": selected_time,
                "selected_place": {},
            }
            state["maedeup_card_payload"] = payload
            state["status"] = "completed"
            # P0-2: memory_extraction 분리 — graph latency에서 빼서 사용자 인식 latency ↓.
            asyncio.create_task(_spawn_memory_extraction_async(state))
            return state
        if state.get("confirmed_place"):
            selected_place = {
                "name": state.get("confirmed_place"),
                "score": 1.0,
                "is_confirmed": True,
            }
        else:
            selected_place = state["place_search_results"][0] if state.get("place_search_results") else {}
            if selected_place.get("name"):
                state["confirmed_place"] = str(selected_place.get("name"))
        state["calendar_registration"] = await _register_google_calendar(state)
        state["maedeup_card_payload"] = {
            "type": "maedeup_card",
            "room_id": state["room_id"],
            "meeting_id": meeting_id,
            "title": f"{state.get('meeting_type') or '모임'} 매듭 카드",
            "intent": state.get("intent"),
            "date_hint": state.get("date_hint"),
            "place_hint": state.get("place_hint"),
            "headcount": state.get("headcount"),
            "meeting_type": state.get("meeting_type"),
            "selected_time": selected_slot,
            "selected_place": selected_place,
            "vote_card": state.get("vote_card_payload"),
            "place_recommendation": state.get("place_recommendation_payload"),
            "calendar_registration": state.get("calendar_registration"),
        }
        state["status"] = "completed"
        logger.info("[TIMING] maedeup_card_creation: %.2fs", time.monotonic() - _t0)
        # P0-2: memory_extraction 분리 — graph latency에서 빼서 사용자 인식 latency ↓.
        asyncio.create_task(_spawn_memory_extraction_async(state))
        return state
    except Exception as exc:
        return await _handle_node_exception("maedeup_card_creation", state, exc)


def _is_empty_personal_data(value: Any) -> bool:
    """Personal data 필드가 '비어있다'고 볼 수 있는 값인지."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


async def _publish_personal_data_updates(user_ids: list[int]) -> None:
    """홈 PersonalData 패널 fade-in을 위한 user-scoped Redis publish.

    실패는 logging만. extraction 자체를 깨지 않음.
    """
    if not user_ids:
        return
    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        try:
            for uid in user_ids:
                envelope = {
                    "type": "personal_data:updated",
                    "user_id": uid,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                await r.publish(
                    f"personal_data:user:{uid}:updated",
                    json.dumps(envelope, ensure_ascii=False),
                )
        finally:
            await r.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.warning("personal_data Redis publish failed: %s", exc)


async def _spawn_memory_extraction_async(state_snapshot: GraphState) -> None:
    """P0-2 (2026-05-08): maedeup_card_creation 후 memory_extraction을 fire-and-forget으로 실행.

    Graph가 이걸 sequential로 돌면 ACT 4 latency가 4.5s → ~0.05s 차이로 사용자 인식 침묵 발생.
    분리해서 카드는 즉시 emit, ✨ 학습 카드는 ~4s 후 별도 emit (자연스러운 flow).

    state['db'] 세션은 graph 종결 후 close 가능성 → 새 session 필수.
    state 자체는 shallow copy로 detached task와 분리 (graph 이후 변경되어도 task 영향 X).
    실패는 silent log only — 모임 카드는 이미 발행된 상태라 회복 불가능 + 모임 자체를 깨뜨리면 안 됨.
    """
    try:
        async with AsyncSessionLocal() as new_session:
            detached_state: GraphState = dict(state_snapshot)  # type: ignore[assignment]
            detached_state["db"] = new_session
            await memory_extraction(detached_state)
    except Exception:
        logger.exception("Detached memory_extraction failed")


async def memory_extraction(state: GraphState) -> GraphState:
    """모임 종료(maedeup_card_creation) 직후 transcript에서 멤버별 personal data 추출.

    Write 정책 (디자인 P5):
    - User 필드가 비어있으면 → setattr + is_ai_filled[cat]=True (Case A)
    - User 필드가 AI로 채워진 적 있으면 → 새 값으로 update + is_ai_filled[cat]=True (Case B)
    - User 필드를 사용자가 직접 입력했으면 → User 건드리지 않음, AIMemory만 status='superseded_by_manual' (Case C)

    매 추출에 대해 AIMemory row INSERT (값 동일해도 — 시점 기록 가치).
    실패는 log only — 모임 자체를 깨뜨리지 않음.
    """
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state
        if not state.get("maedeup_card_payload"):
            # 매듭 카드가 안 만들어졌으면 모임이 종결된 게 아니므로 skip
            return state

        room_id_raw = state.get("room_id")
        try:
            room_id = int(room_id_raw)
        except (TypeError, ValueError):
            logger.warning("memory_extraction: invalid room_id=%r", room_id_raw)
            return state

        db: AsyncSession = state["db"]

        # 1. room members
        member_rows = (
            await db.execute(
                select(RoomMember).where(RoomMember.room_id == room_id)
            )
        ).scalars().all()
        member_ids: list[int] = [m.user_id for m in member_rows]
        if not member_ids:
            logger.info("memory_extraction: room=%s has no members, skip", room_id)
            return state

        # 2. transcript — 사용자 발화만 (assistant/system 제외, social pane만)
        transcript_rows = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.room_id == room_id)
                .where(ChatMessage.pane_type == PaneType.social.value)
                .where(ChatMessage.role == "user")
                .order_by(ChatMessage.created_at.asc())
            )
        ).scalars().all()
        if not transcript_rows:
            logger.info("memory_extraction: room=%s has no user messages, skip", room_id)
            return state

        # 3. extract (Gemini 또는 canned fallback)
        try:
            extractions = await extract_personal_data(
                transcript=transcript_rows,
                member_ids=member_ids,
                db=db,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory_extraction: extract failed: %s", exc)
            return state

        # 4. write — 단일 트랜잭션. 부분 실패 시 롤백, 부분 상태 금지.
        affected_user_ids: list[int] = []
        try:
            users_by_id = {
                u.id: u
                for u in (
                    await db.execute(select(User).where(User.id.in_(member_ids)))
                ).scalars().all()
            }

            for member_id, cat_results in extractions.items():
                if not cat_results:
                    continue
                user = users_by_id.get(member_id)
                if user is None:
                    continue

                user_changed = False
                is_ai_filled = dict(user.is_ai_filled or {})

                for category, ext in cat_results.items():
                    current_value = getattr(user, category, None)
                    already_ai = bool(is_ai_filled.get(category, False))

                    if _is_empty_personal_data(current_value):
                        # Case A
                        setattr(user, category, ext.value)
                        is_ai_filled[category] = True
                        status = "active"
                        user_changed = True
                    elif already_ai:
                        # Case B
                        setattr(user, category, ext.value)
                        is_ai_filled[category] = True
                        status = "active"
                        user_changed = True
                    else:
                        # Case C — manual entry, do not overwrite
                        status = "superseded_by_manual"

                    content_payload = {
                        "value": ext.value,
                        "confidence": ext.confidence,
                        "source_quote": ext.source_quote,
                        "status": status,
                    }
                    db.add(
                        AIMemory(
                            user_id=member_id,
                            memory_type=category,
                            content=json.dumps(content_payload, ensure_ascii=False),
                            source_room_id=room_id,
                            source_message_id=ext.source_message_id,
                        )
                    )

                if user_changed:
                    user.is_ai_filled = is_ai_filled
                    db.add(user)
                    affected_user_ids.append(member_id)

            await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("memory_extraction: write failed, rolling back: %s", exc)
            await db.rollback()
            return state

        # 5. Redis publish (트랜잭션 성공 후)
        await _publish_personal_data_updates(affected_user_ids)

        logger.info(
            "[TIMING] memory_extraction: %.2fs (room=%s, %d users affected)",
            time.monotonic() - _t0,
            room_id,
            len(affected_user_ids),
        )
        return state
    except Exception as exc:
        logger.exception("memory_extraction unexpected failure: %s", exc)
        return state


def _route_from_start(state: GraphState) -> Literal["entity_extraction", "slot_filling", "intent_detection"]:
    """해결점 C: trigger_reason 기반 LangGraph 진입 분기.

    - stalemate_judged / conclusion_detected: 의도 자명 → 노드3 entity_extraction부터 (~1s 절약)
    - all_members_selected: TimeBar 데이터 주입됨 → 노드4 slot_filling부터 (~3s 절약)
    - direct_request: quick_classify가 이미 general을 걸렀으므로 노드3 entity_extraction부터
    - 미지정: 기존 노드1 intent_detection 경로
    """
    trigger = state.get("trigger_reason")
    if trigger in {"stalemate_judged", "conclusion_detected", "direct_request"}:
        return "entity_extraction"
    if trigger == "all_members_selected":
        return "slot_filling"
    return "intent_detection"


def _route_after_intent(state: GraphState) -> Literal["entity_extraction", "general_response"]:
    """general 의도이고 슬롯 필링 진행 중이 아니면 일반 응답으로 분기."""
    if _has_node_error(state):
        return "general_response"
    if float(state.get("confidence_score", 0.0)) < INTENT_CONFIDENCE_THRESHOLD:
        return "general_response"
    if state.get("intent") == "general" and state.get("slot_filling_turns", 0) == 0:
        return "general_response"
    return "entity_extraction"


def _route_after_slot_filling(state: GraphState) -> Literal["slot_filling", "function_calling", "__end__"]:
    if _has_node_error(state):
        return END
    status = state.get("status", "")
    if status in ("conclusion_false_positive", "time_only_ready"):
        return "function_calling"
    if state.get("is_location_first"):
        return "function_calling"
    if state.get("all_slots_filled"):
        return "function_calling"
    # 부분 정보만 있거나 정보가 없는 경우 → 질문 없이 종료
    if status in ("no_slots_yet", "partial_info_acknowledged"):
        return END
    if state.get("wait_timed_out") or state.get("awaiting_user_reply"):
        return END
    return "slot_filling"


def _route_after_validation(
    state: GraphState,
) -> Literal["vote_card_creation", "place_recommendation", "maedeup_card_creation", "__end__"]:
    if _has_node_error(state):
        return END
    status = state.get("status")
    if status == "conclusion_false_positive":
        return END
    if status == "time_only_ready":
        state["partial_mode"] = "time_only"
        return "maedeup_card_creation"
    if not state.get("validation_passed"):
        return END

    # 해결점 C: trigger_reason 기반 라우팅 차별화
    trigger = state.get("trigger_reason")
    if trigger == "conclusion_detected":
        # 결론 합의됐으니 vote/place 스킵, 매듭 카드 직행
        return "maedeup_card_creation"
    if trigger == "all_members_selected":
        # TimeBar로 시간 확정됨, 장소 추천만
        return "place_recommendation"

    # 해결점 E A1: direct_request로 place 분류된 경우 vote 건너뛰고 place_recommendation
    direct_kind = state.get("direct_request_kind")
    if direct_kind == "place":
        return "place_recommendation"

    # 해결점 E A2: 이미 일정 확정된 상태면 vote_card 다시 만들 필요 없음 → place_recommendation
    if state.get("confirmed_date") and state.get("place_search_results"):
        return "place_recommendation"

    if state.get("intent") == "place_suggestion" and state.get("place_search_results"):
        return "place_recommendation"
    # 선호 데이터 기반 자동 제안: 투표 카드를 먼저 생성 (시간대 투표)
    if state.get("preference_common_times") and state.get("intent") != "place_suggestion":
        return "vote_card_creation"
    if state.get("is_location_first") and not state.get("date_hint"):
        return "place_recommendation"
    return "vote_card_creation"


def _route_after_vote_card_creation(state: GraphState) -> Literal["place_recommendation", "maedeup_card_creation", "__end__"]:
    if _has_node_error(state):
        return END
    # 사용자가 이미 시간/장소를 확정한 상태에서 진입한 경우 (vote 후 별도 트리거)
    if state.get("confirmed_place"):
        return "maedeup_card_creation"
    # 일반 흐름: vote_card만 발행하고 사용자 vote 대기.
    # 사용자가 vote → confirm endpoint가 새 run_pipeline 실행 시
    # confirmed_date/place 박아 보내면 그때 maedeup으로 진입.
    return END


def _route_after_place_recommendation(state: GraphState) -> Literal["maedeup_card_creation", "__end__"]:
    if _has_node_error(state):
        return END
    if state.get("is_location_first") and not state.get("date_hint"):
        return END
    # 사용자가 이미 장소를 확정한 상태에서 진입한 경우만 매듭 카드로 직진
    if state.get("confirmed_place"):
        return "maedeup_card_creation"
    # direct_request로 진입한 경우 — vote_card 패턴과 일관되게 사용자 confirm 대기.
    # 사용자가 place 카드에서 "이 장소로 확정" 클릭 → confirm endpoint가 별도 trigger로
    # maedeup_card_creation 발화시킴. 자동 진행하면 confirmed_date와 데이터 불일치 가능.
    if state.get("trigger_reason") == "direct_request":
        return END
    return "maedeup_card_creation"


def _build_graph() -> Any:
    graph = StateGraph(GraphState)
    graph.add_node("intent_detection", intent_detection)
    graph.add_node("general_response", general_response)
    graph.add_node("entity_extraction", entity_extraction)
    graph.add_node("slot_filling", slot_filling)
    graph.add_node("function_calling", function_calling)
    graph.add_node("supervisor_validation", supervisor_validation)
    graph.add_node("vote_card_creation", vote_card_creation)
    graph.add_node("place_recommendation", place_recommendation)
    graph.add_node("maedeup_card_creation", maedeup_card_creation)
    # P0-2 (2026-05-08): memory_extraction 노드를 graph에서 분리.
    # maedeup_card_creation 안에서 fire-and-forget으로 spawn 됨 (~4s 사용자 인식 latency 제거).

    # 해결점 C: trigger_reason 기반 진입 분기 (노드1 스킵 가능)
    graph.add_conditional_edges(
        START,
        _route_from_start,
        {
            "entity_extraction": "entity_extraction",
            "slot_filling": "slot_filling",
            "intent_detection": "intent_detection",
        },
    )
    graph.add_conditional_edges(
        "intent_detection",
        _route_after_intent,
        {
            "entity_extraction": "entity_extraction",
            "general_response": "general_response",
        },
    )
    graph.add_edge("general_response", END)
    graph.add_edge("entity_extraction", "slot_filling")
    graph.add_conditional_edges(
        "slot_filling",
        _route_after_slot_filling,
        {
            "slot_filling": "slot_filling",
            "function_calling": "function_calling",
            END: END,
        },
    )
    graph.add_edge("function_calling", "supervisor_validation")
    graph.add_conditional_edges(
        "supervisor_validation",
        _route_after_validation,
        {
            "vote_card_creation": "vote_card_creation",
            "place_recommendation": "place_recommendation",
            "maedeup_card_creation": "maedeup_card_creation",  # 해결점 C: conclusion 직행
            END: END,
        },
    )
    graph.add_conditional_edges(
        "vote_card_creation",
        _route_after_vote_card_creation,
        {
            "place_recommendation": "place_recommendation",
            "maedeup_card_creation": "maedeup_card_creation",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "place_recommendation",
        _route_after_place_recommendation,
        {
            "maedeup_card_creation": "maedeup_card_creation",
            END: END,
        },
    )
    # P0-2 (2026-05-08): 매듭 카드 즉시 종결. memory_extraction은 카드 노드 내부에서
    # asyncio.create_task로 fire-and-forget — graph latency에서 ~4s 빠짐.
    graph.add_edge("maedeup_card_creation", END)
    return graph.compile()


GRAPH = _build_graph()


async def run_pipeline(
    room_id: str,
    context: AgentContextMessages,
    db: AsyncSession,
    slot_context: dict | None = None,
) -> dict[str, Any]:
    """Run the AI pipeline.

    `context` MUST be built via `MessageReader.load_agent_context` so the privacy
    boundary (visibility + user_id filter) is enforced at the query layer. Raw
    `list[ChatMessage]` is rejected — see docs/ai-separation.md §9.4.
    """
    MessageReader.ensure_branded(context)
    _pipeline_t0 = time.monotonic()
    initial_state = _default_state(
        room_id=room_id,
        db=db,
        messages=context.messages,
        slot_context=slot_context,
        viewer_user_id=context.viewer_user_id,
    )
    await _compress_message_history(initial_state)
    # 소셜(방 전체) 채팅 컨텍스트 preload — entity/general 노드가 _serialize_context로 읽음.
    try:
        room_pk = _room_id_as_int(room_id)
        social_recent, social_summary = await _load_social_context(db, room_pk)
        initial_state["social_recent"] = social_recent
        initial_state["social_summary"] = social_summary
    except Exception:
        logger.debug("social context preload failed room=%s", room_id, exc_info=True)
    final_state = await GRAPH.ainvoke(initial_state)
    logger.info(
        "[TIMING] run_pipeline TOTAL: %.2fs | intent=%s status=%s",
        time.monotonic() - _pipeline_t0,
        final_state.get("intent"),
        final_state.get("status"),
    )
    return {
        "status": final_state.get("status"),
        "intent": final_state.get("intent"),
        "intent_confidence": final_state.get("intent_confidence"),
        "confidence_score": final_state.get("confidence_score"),
        "slots": _slot_snapshot(final_state),
        "missing_slots": final_state.get("missing_slots", []),
        "awaiting_user_reply": final_state.get("awaiting_user_reply", False),
        "validation_errors": final_state.get("validation_errors", []),
        "vote_card_payload": final_state.get("vote_card_payload"),
        "place_recommendation_payload": final_state.get("place_recommendation_payload"),
        "maedeup_card_payload": final_state.get("maedeup_card_payload"),
        "calendar_registration": final_state.get("calendar_registration"),
        "conversation_summary": final_state.get("conversation_summary", ""),
        "recent_messages": final_state.get("recent_messages", []),
        # 슬롯 컨텍스트 – agent.py가 다음 호출에 이어받을 값들
        "slot_filling_turns": final_state.get("slot_filling_turns", 0),
        "message_count_since_last_trigger": final_state.get("message_count_since_last_trigger", 0),
        "summary_message_count": final_state.get("summary_message_count", 0),
        "date_hint": final_state.get("date_hint"),
        "place_hint": final_state.get("place_hint"),
        "place_coord": final_state.get("place_coord"),
        "default_place_hint": final_state.get("default_place_hint"),
        "confirmed_date": final_state.get("confirmed_date"),
        "confirmed_time": final_state.get("confirmed_time"),
        "confirmed_place": final_state.get("confirmed_place"),
        "parsed_time_hint": final_state.get("parsed_time_hint"),
        "date_is_flexible": final_state.get("date_is_flexible", False),
        "date_hint_source_text": final_state.get("date_hint_source_text"),
        "headcount": final_state.get("headcount"),
        "meeting_type": final_state.get("meeting_type"),
        "is_location_first": final_state.get("is_location_first", False),
        "blocker_notification_payload": final_state.get("blocker_notification_payload"),
        "time_options": final_state.get("time_options", []),
        "new_assistant_messages": final_state.get("new_assistant_messages", []),  # type: ignore[typeddict-item]
    }


async def _analyze_conversation(
    room_id: str,
    db: AsyncSession,
    today_kst: str,
) -> dict[str, Any] | None:
    """최근 소셜 채팅에서 카드 표시 정보와 파이프라인 신호를 한 번에 추출합니다."""
    try:
        room_pk = int(room_id)
    except (TypeError, ValueError):
        return None

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.room_id == room_pk)
        .where(ChatMessage.pane_type == PaneType.social)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(50)
    )
    recent_messages = list(reversed(result.scalars().all()))

    if not recent_messages:
        return None

    conversation = "\n".join(
        f"{msg.sender or msg.role}: {msg.content.strip()}"
        for msg in recent_messages
        if msg.content and msg.content.strip()
    )

    if not conversation:
        return None

    prompt = (
        "당신은 매듭 AI입니다. 한국인들의 모임 조율 대화를 분석합니다.\n"
        f"오늘 날짜는 {today_kst}입니다.\n"
        "아래 대화에서 카드 표시용 요약(card)과 파이프라인 신호(signals)를 한 번에 추출하세요.\n"
        "반드시 JSON 객체만 출력하고, 다른 텍스트는 포함하지 마세요.\n"
        "정보가 없는 필드는 null 또는 빈 배열로 채우세요.\n\n"
        "출력 형식:\n"
        "{\n"
        '  "card": {\n'
        '    "date": "자연어 날짜/시간 요약 또는 null (예: \"이번 주 금/토/일 모두 막힘, 다음 주 평일 후보\")",\n'
        '    "place": "표시용 장소 또는 null",\n'
        '    "headcount": "표시용 인원 또는 null",\n'
        '    "type": "모임 유형(식사/카페/술 등) 또는 null",\n'
        '    "notes": ["멤버별 거부 사유와 합의 흐름을 구체적으로 3-5개 bullet"]\n'
        "  },\n"
        '  "signals": {\n'
        '    "date_hint": "YYYY-MM-DD 또는 YYYY-MM-DD~YYYY-MM-DD 또는 null",\n'
        '    "date_hints": ["YYYY-MM-DD"],\n'
        '    "preferred_dates": [{"date": "YYYY-MM-DD"}],\n'
        '    "rejected_dates": ['
        '{"date": "YYYY-MM-DD", "user": "발신자 또는 null", "reason": "거부 이유 또는 null"}'
        "],\n"
        '    "place_hint": "구체적 장소 힌트 또는 null",\n'
        '    "headcount": 0,\n'
        '    "meeting_type": "모임 유형 또는 null",\n'
        '    "conflict_detected": false,\n'
        '    "conflict_type": "date 또는 place 또는 time 또는 null",\n'
        '    "conflict_options": ["충돌 선택지"],\n'
        '    "conflict_users": ["충돌 사용자"],\n'
        '    "parsed_time_hint": "시간 표현 또는 null",\n'
        '    "date_is_flexible": false,\n'
        '    "date_hint_source_text": "원문 날짜 표현 또는 null"\n'
        "  }\n"
        "}\n\n"
        "signals 작성 규칙:\n"
        "- 날짜는 가능하면 ISO 형식(YYYY-MM-DD)으로 변환하세요. 요일만 언급되면 오늘 이후 가장 가까운 미래 날짜로 변환하세요.\n"
        "- date_hints는 여러 날짜 선택지가 있을 때 모두 담고, preferred_dates는 가능/선호로 표현된 날짜를 담으세요.\n"
        "- **card에 자연어로 적은 모든 날짜 표현은 signals에 ISO로 반드시 변환해 담을 것.** card.date/notes만 채우고\n"
        "  signals.preferred_dates 또는 signals.date_hints를 비워두면 후속 슬롯 빌드가 실패함.\n"
        "  preferred_dates 각 항목은 반드시 `{\"date\": \"YYYY-MM-DD\"}` dict 형태. plain string array 금지.\n"
        "  예: card.date='다음 주 평일이 후보' → signals.preferred_dates=[{\"date\":\"2026-05-11\"}, {\"date\":\"2026-05-12\"}, ...] (다음 주 월~금 ISO 5개).\n"
        "  예: card.date='5/12 화요일 저녁으로 좁혀짐' → signals.date_hint='2026-05-12'.\n"
        "- 거부된 날짜는 rejected_dates에만, 가능/선호 날짜는 preferred_dates에. 서로 배타.\n"
        "[필드 의미 구분 - 반드시 따를 것]\n\n"
        "rejected_dates: 어떤 사람이라도 다음 거부 표현을 명시적으로 사용한 날짜.\n"
        "  거부 키워드: \"안 돼\", \"못 가\", \"힘들어\", \"불가능\", \"어려워\", \"패스\", \"어렵다\"\n"
        "  - 한 명이라도 거부하면 무조건 여기. 다른 사람의 선호와 충돌하더라도 거부 우선.\n"
        "  - 단순한 미언급/무관심은 거부 아님.\n\n"
        "conflict_options: 서로 다른 사람이 서로 다른 날짜를 선호하지만, 누구도 거부하지 않은 옵션들만.\n"
        "  - \"A는 X를 원함\" + \"B는 Y를 원함\" + 둘 다 명시적 거부 없음 → conflict_options=[X, Y]\n"
        "  - 단 한 명이라도 어떤 옵션에 거부를 표시하면 그 날짜는 conflict_options에서 빠지고 rejected_dates로.\n\n"
        "상호 배타성:\n"
        "  - 같은 날짜가 rejected_dates와 conflict_options에 동시에 들어가면 안 됨.\n"
        "  - 충돌 시 우선순위: rejected_dates가 conflict_options를 이김.\n\n"
        "분류 예시:\n"
        "  대화1: \"금요일 좋아\" / \"금요일 안 돼\"\n"
        "    → rejected_dates=[금요일 ISO], conflict_options=[]\n\n"
        "  대화2: \"목요일이 좋아\" / \"금요일이 좋아\" (둘 다 명시적 거부 없음)\n"
        "    → rejected_dates=[], conflict_options=[\"목요일\", \"금요일\"]\n\n"
        "  대화3: \"금요일 안 돼\" / \"토요일 안 돼\"\n"
        "    → rejected_dates=[금요일 ISO, 토요일 ISO], conflict_options=[]\n\n"
        "  대화4: \"금요일 좋아\" / \"금요일도 OK인데 토요일이 더 좋아\"\n"
        "    → rejected_dates=[], conflict_options=[\"금요일\", \"토요일\"]\n"
        "- place_hint는 구체적 지명/역/동/구/장소명만 담으세요. 아무데나, 근처, 다시 추천, 장소 정하자 같은 모호한 표현은 null입니다.\n\n"
        "card 작성 가이드 (시연 임팩트 — 빈약한 card는 카드 의미 약화):\n"
        "- card.date는 \"시험 끝나고 모임\" 같은 한 줄 요약 X. **거부/합의 흐름을 묘사**.\n"
        "  좋은 예: \"이번 주 금/토/일 모두 불가, 다음 주 평일 후보\"\n"
        "  좋은 예: \"5/12 화요일 저녁으로 좁혀짐\"\n"
        "- card.notes는 **멤버별 사정과 합의 흐름**을 별도 bullet으로 분리:\n"
        "  - 거부 1건당 \"{멤버이름}: {날짜} {사유}\" 형태로 1 bullet\n"
        "  - 마지막에 합의 흐름 요약 1 bullet (예: \"다음 주 평일이 가장 가능성 높음\")\n"
        "  - 3~5개 bullet 권장. 너무 많으면 카드 길어짐.\n\n"
        "전체 예시 input → output (오늘=2026-05-07 가정):\n"
        "  대화:\n"
        "    지민: 다들 시험 끝나고 한번 보자!\n"
        "    수현: 5월 8일 금요일은 동아리 MT라 안 돼\n"
        "    민수: 9일은 본가 내려가야 해서 패스\n"
        "    예린: 10일 토요일은 좀 쉬고 싶다… 다음주 어때?\n"
        "  card 출력:\n"
        "    date: \"이번 주 금/토/일 모두 막힘, 다음 주 평일이 후보\"\n"
        "    place: null\n"
        "    headcount: null\n"
        "    type: \"회식\"\n"
        "    notes: [\n"
        "      \"수현: 5/8 동아리 MT로 불가\",\n"
        "      \"민수: 5/9 본가 일정\",\n"
        "      \"예린: 5/10 휴식 원함, 다음 주 제안\",\n"
        "      \"이번 주 금/토/일 막힘 → 다음 주가 후보\"\n"
        "    ]\n"
        "  signals 출력 (card에 자연어로 적은 날짜를 ISO로 변환해 짝지어 채울 것):\n"
        "    date_hint: null\n"
        "    date_hints: []\n"
        "    preferred_dates: [\n"
        "      {\"date\": \"2026-05-11\"}, {\"date\": \"2026-05-12\"}, {\"date\": \"2026-05-13\"},\n"
        "      {\"date\": \"2026-05-14\"}, {\"date\": \"2026-05-15\"}\n"
        "    ]  // 다음 주 월~금 ISO, 각 항목은 {\"date\": \"YYYY-MM-DD\"} dict 형태로\n"
        "    rejected_dates: [\n"
        "      {\"date\": \"2026-05-08\", \"user\": \"수현\", \"reason\": \"동아리 MT\"},\n"
        "      {\"date\": \"2026-05-09\", \"user\": \"민수\", \"reason\": \"본가\"},\n"
        "      {\"date\": \"2026-05-10\", \"user\": \"예린\", \"reason\": \"휴식 원함\"}\n"
        "    ]\n"
        "    place_hint: null\n"
        "    headcount: 0\n"
        "    meeting_type: \"회식\"\n"
        "    conflict_detected: false\n\n"
        "    ⚠️ card.notes의 \"다음 주 제안\"이 signals.preferred_dates에 ISO 5개로 변환되어 들어가야 함.\n"
        "    signals만 비우면 슬롯 빌드 실패 + 다음주 자동 확장 발동 못 함.\n\n"
        f"대화:\n{conversation}"
    )

    raw = await call_gemini(prompt)
    if not raw:
        return None

    parsed = _extract_json_object(raw)
    if not parsed:
        logger.warning("Failed to parse unified conversation analysis JSON: %s", raw[:200])
        return None

    card = parsed.get("card")
    signals = parsed.get("signals")
    if not isinstance(card, dict) or not isinstance(signals, dict):
        return None

    return {
        "card": {
            "date": card.get("date"),
            "place": card.get("place"),
            "headcount": card.get("headcount"),
            "type": card.get("type"),
            "notes": card.get("notes") or [],
        },
        "signals": signals,
    }


async def suggest_alternative_slots(
    room_id: int,
    dissenting_user_ids: list[int],
    session: AsyncSession,
) -> dict[str, Any] | None:
    """투표 결과 만장일치가 아닐 때, 불참자 캘린더를 포함해 전원 가능한 대안 시간대를 검색합니다.

    Returns:
        전원 가능한 대안 슬롯 dict (label, start_at, end_at 등) 또는 None.
    """
    if not settings.GOOGLE_CLIENT_ID:
        return None

    # 룸 멤버 전원 조회
    member_result = await session.execute(
        select(RoomMember).where(RoomMember.room_id == room_id)
    )
    members = member_result.scalars().all()
    user_ids = [m.user_id for m in members]

    if not user_ids:
        return None

    user_result = await session.execute(
        select(User).where(
            User.id.in_(user_ids),
            User.calendar_consent == True,  # noqa: E712
        )
    )
    consenting_users = [
        user
        for user in user_result.scalars().all()
        if user.google_access_token or user.google_refresh_token
    ]

    if not consenting_users:
        return None

    now = datetime.now(timezone.utc)
    time_min = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    time_max = time_min + timedelta(days=14)

    # 전원(불참자 포함)의 busy 기간 조회
    busy_by_user: dict[str, list[dict[str, Any]]] = {}
    for user in consenting_users:
        busy_by_user[_user_calendar_key(user)] = await _get_user_busy_periods(
            user, time_min, time_max, session
        )

    if not busy_by_user:
        return None

    # 전원 가능한 슬롯만 검색 (require_exact_absent_count=0)
    full_slots = _find_free_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
        minimum_available=len(busy_by_user),
        require_exact_absent_count=0,
    )

    if not full_slots:
        # 14일 내 없으면 21일까지 확장
        extended_time_max = time_max + timedelta(days=7)
        for user in consenting_users:
            busy_by_user[_user_calendar_key(user)] = await _get_user_busy_periods(
                user, time_min, extended_time_max, session
            )
        full_slots = _find_free_slots(
            busy_by_user=busy_by_user,
            time_min=time_min,
            time_max=extended_time_max,
            minimum_available=len(busy_by_user),
            require_exact_absent_count=0,
        )

    if not full_slots:
        return None

    # 가장 빠른 전원 가능 슬롯 반환
    best = full_slots[0]
    return {
        "slot_id": best.get("slot_id"),
        "label": best.get("label"),
        "start_at": best.get("start_at"),
        "end_at": best.get("end_at"),
        "available_count": best.get("available_count"),
        "total_count": best.get("total_count"),
        "is_holiday": best.get("is_holiday", False),
        "is_weekend": best.get("is_weekend", False),
    }

