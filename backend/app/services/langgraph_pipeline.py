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
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

import holidays

from app.core.config import settings
from app.models.chat import ChatMessage, PaneType
from app.models.room import RoomMember
from app.models.user import User
from app.services.gemini import call_gemini
from app.services.google_calendar import GoogleCalendarAuthError, get_google_access_token
from app.services.intent_classifier import classify_intent
from app.services.kakao_maps import search_address, search_keyword
from app.services.meeting_history import get_recent_meeting_records, search_meeting_history

KST = ZoneInfo("Asia/Seoul")
GOOGLE_FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"
WORK_HOUR_START = 9
WORK_HOUR_END = 22
SLOT_MINUTES = 60
INTENT_CONFIDENCE_THRESHOLD = 0.7

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
    status: str


def _default_state(
    room_id: str,
    db: AsyncSession,
    messages: list[Any],
    slot_context: dict | None = None,
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
        "seen_message_ids": seen_ids,
        "new_assistant_messages": [],
        "intent": "general",
        "intent_confidence": 0.0,
        "confidence_score": 0.0,
        "date_hint": ctx.get("date_hint"),
        "place_hint": ctx.get("place_hint"),
        "place_coord": ctx.get("place_coord"),
        "default_place_hint": ctx.get("default_place_hint") or "서울 강남",
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
    if state.get("recent_messages"):
        parts.append("\n".join(state["recent_messages"]))
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
        resolved = "서울 강남"

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
        "아래 스키마 그대로 JSON만 반환하세요:\n"
        "{"
        '"date_hint": string | null, '
        '"date_hints": [string] | null, '
        '"place_hint": string | null, '
        '"headcount": number | null, '
        '"meeting_type": string | null'
        "}\n\n"
        "date_hint: 첫 번째 날짜 표현. 가능하면 YYYY-MM-DD 형식으로 변환, 범위면 "
        "'YYYY-MM-DD~YYYY-MM-DD'\n"
        "date_hints: 여러 날짜가 선택지로 제시된 경우 모든 날짜 표현의 배열. "
        "예: '목요일에 볼까 금요일에 볼까' → [\"목요일\", \"금요일\"]\n"
        "place_hint: 장소 힌트. 한국 지명(동, 구, 역, 로, 길 등)이나 "
        "잘 알려진 지역명(강남, 홍대, 건대, 이태원, 명동, 합정, 신촌 등)을 "
        "반드시 추출하세요. 문맥에서 장소를 나타내는 명사를 놓치지 마세요.\n"
        "  예시:\n"
        '  - "역삼동에서 만나자" → place_hint: "역삼동"\n'
        '  - "홍대 맛집 추천해줘" → place_hint: "홍대"\n'
        '  - "강남역 근처 카페" → place_hint: "강남역"\n'
        '  - "서울숲 쪽에서 보자" → place_hint: "서울숲"\n'
        '  - "을지로 맛집" → place_hint: "을지로"\n'
        "headcount: 예상 인원 수\n"
        "meeting_type: 모임 종류 (맛집, 카페, 술집 등 키워드가 있으면 반영)\n\n"
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

    message = ChatMessage(
        pane_type=PaneType.agent,
        role="assistant",
        content=content,
        sender="매듭 AI",
        room_id=room_pk,
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
) -> list[dict[str, Any]]:
    """참여자 가용성을 기준으로 시간대를 SLOT_MINUTES 단위로 탐색합니다."""
    total = len(busy_by_user)
    free_slots: list[dict[str, Any]] = []
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
                free_slots.append({
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
                })
                slot_idx += 1

        current = current + timedelta(minutes=SLOT_MINUTES)

    return free_slots


async def get_free_slots(state: GraphState) -> list[dict[str, Any]]:
    """구글 캘린더 API로 룸 멤버 전원의 빈 시간대를 조회합니다."""
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])

    if room_pk is None or not settings.GOOGLE_CLIENT_ID:
        # 설정 없으면 더미 슬롯 3개 반환
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

    # 룸 멤버 조회
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
    time_min = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    time_max = time_min + timedelta(days=14)

    busy_by_user: dict[str, list[dict[str, Any]]] = {}
    for user in consenting_users:
        busy_by_user[_user_calendar_key(user)] = await _get_user_busy_periods(user, time_min, time_max, db)

    if not busy_by_user:
        return []

    full_slots = _find_free_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
        minimum_available=len(busy_by_user),
        require_exact_absent_count=0,
    )
    if full_slots:
        state["calendar_strategy"] = "all_members_available"
        return full_slots

    n_minus_one_slots = _find_free_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
        minimum_available=max(len(busy_by_user) - 1, 1),
        require_exact_absent_count=1 if len(busy_by_user) > 1 else 0,
    )
    if n_minus_one_slots:
        state["calendar_strategy"] = "n_minus_one"
        return n_minus_one_slots

    extended_time_max = time_max + timedelta(days=7)
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
    )
    if extended_full_slots:
        state["calendar_strategy"] = "all_members_available_extended"
        return extended_full_slots

    final_slots = _find_free_slots(
        busy_by_user=refreshed_busy_by_user,
        time_min=time_min,
        time_max=extended_time_max,
        minimum_available=max(len(refreshed_busy_by_user) - 1, 1),
        require_exact_absent_count=1 if len(refreshed_busy_by_user) > 1 else 0,
    )
    if final_slots:
        state["calendar_strategy"] = "n_minus_one_extended"
    return final_slots


async def _get_room_member_food_preferences(state: GraphState) -> list[str]:
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    if room_pk is None:
        return []

    member_result = await db.execute(select(RoomMember).where(RoomMember.room_id == room_pk))
    members = member_result.scalars().all()
    user_ids = [member.user_id for member in members]
    if not user_ids:
        return []

    user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = user_result.scalars().all()

    disliked_foods: list[str] = []
    seen: set[str] = set()
    for user in users:
        for item in user.food_preferences or []:
            normalized = str(item).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                disliked_foods.append(normalized)
    return disliked_foods


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
        latest_user_message = ""
        for message in reversed(state["message_records"]):
            if message.get("role") == "user" and message.get("content"):
                latest_user_message = message["content"]
                break

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

        # 패턴 기반 intent 오버라이드: 여러 날짜 선택지 제시 → meeting_schedule
        if latest_user_message and _detect_multi_date_options(latest_user_message):
            state["intent"] = "meeting_schedule"
            state["confidence_score"] = max(state["confidence_score"], 0.9)
            logger.info("[INTENT] Multi-date option pattern detected, overriding to meeting_schedule")

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
        state["is_location_first"] = bool(state.get("place_hint")) and not bool(state.get("date_hint"))
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
        state["is_location_first"] = bool(state.get("place_hint")) and not bool(state.get("date_hint"))
        state["time_options"] = _build_flexible_time_options(state)

        # 여러 날짜 선택지 → 투표 카드 생성으로 바로 진행
        multi_date_hints = state.get("date_hints") or []
        if len(multi_date_hints) >= 2:
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
            logger.info("[TIMING] slot_filling (multi-date vote): %.2fs", time.monotonic() - _t0)
            return state

        has_date = bool(state.get("date_hint"))
        has_place = bool(state.get("place_hint"))
        has_headcount = state.get("headcount") is not None

        # 장소만 있고 날짜 없음 → 장소 추천 먼저
        if state.get("is_location_first"):
            state["awaiting_user_reply"] = False
            state["wait_timed_out"] = False
            state["message_count_since_last_trigger"] = 0
            state["status"] = "location_first_ready"
            return state

        # 모든 슬롯이 채워짐 → 투표 카드 생성으로 진행
        if state["all_slots_filled"]:
            state["awaiting_user_reply"] = False
            state["wait_timed_out"] = False
            state["message_count_since_last_trigger"] = 0
            state["status"] = "slots_filled"
            return state

        # date + place + headcount → 기본 meeting_type 채우고 진행
        if has_date and has_place and has_headcount:
            if not state.get("meeting_type"):
                state["meeting_type"] = "모임"
            state["all_slots_filled"] = True
            state["missing_slots"] = []
            state["awaiting_user_reply"] = False
            state["wait_timed_out"] = False
            state["message_count_since_last_trigger"] = 0
            state["status"] = "slots_filled"
            return state

        # date + place (headcount 없음) → 기본 headcount 채우고 진행
        if has_date and has_place:
            if not has_headcount:
                state["headcount"] = 4  # 기본값
            if not state.get("meeting_type"):
                state["meeting_type"] = "모임"
            state["all_slots_filled"] = True
            state["missing_slots"] = []
            state["awaiting_user_reply"] = False
            state["wait_timed_out"] = False
            state["message_count_since_last_trigger"] = 0
            state["status"] = "slots_filled_with_defaults"
            return state

        # date만 있음 → 날짜 확인 메시지만 보내고, 나머지는 대화에서 자연스럽게 기다림
        if has_date and not has_place:
            state["slot_filling_turns"] += 1
            # 첫 트리거에서만 확인 메시지 발행, 이후에는 조용히 대기
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

        # place만 있음 → 장소 확인 + 추천 시작
        if has_place and not has_date:
            state["slot_filling_turns"] += 1
            if state["slot_filling_turns"] <= 1:
                place_display = state.get("place_hint", "")
                confirm_msg = (
                    f"{place_display} 근처로요! 🔍 "
                    "맛집 몇 개 찾아볼게요~ 날짜는 대화에서 나오면 정리할게요!"
                )
                await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)
            # location_first 모드로 전환 → place_recommendation 실행
            state["is_location_first"] = True
            state["awaiting_user_reply"] = False
            state["wait_timed_out"] = False
            state["message_count_since_last_trigger"] = 0
            state["status"] = "partial_info_acknowledged"
            state["all_slots_filled"] = True  # function_calling으로 진행
            return state

        # 아무 정보도 없음 → 최소한 확인 메시지는 보냄
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
        logger.info("[TIMING] slot_filling: %.2fs", time.monotonic() - _t0)
        return state
    except Exception as exc:
        return await _handle_node_exception("slot_filling", state, exc)


def _build_multi_date_slots(state: GraphState) -> list[dict[str, Any]]:
    """여러 날짜 힌트로부터 투표용 슬롯을 생성합니다."""
    date_hints = state.get("date_hints") or []
    now_kst = datetime.now(KST)
    slots: list[dict[str, Any]] = []

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

        # Default to afternoon time
        start_at = target_date.replace(hour=14, minute=0, second=0, microsecond=0)
        end_at = start_at + timedelta(hours=2)
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


async def function_calling(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state
        state["blocker_notification_payload"] = None

        # 여러 날짜 선택지 → 각 날짜별 슬롯 생성
        multi_date_hints = state.get("date_hints") or []
        if len(multi_date_hints) >= 2:
            multi_slots = _build_multi_date_slots(state)
            if multi_slots:
                state["calendar_free_slots"] = multi_slots
                state["calendar_strategy"] = "multi_date_vote"
                place_results = await search_place(state)
                state["place_search_results"] = place_results
                state["status"] = "functions_called"
                logger.info("[TIMING] function_calling (multi-date): %.2fs", time.monotonic() - _t0)
                return state

        if state.get("is_location_first") and not state.get("date_hint"):
            state["calendar_free_slots"] = []
            place_results = await search_place(state)
        elif state.get("time_options"):
            state["calendar_free_slots"] = _build_time_option_slots(state)
            state["calendar_strategy"] = "natural_language_time_options"
            place_results = await search_place(state)
        else:
            free_slots, place_results = await asyncio.gather(
                get_free_slots(state),
                search_place(state),
            )
            state["calendar_free_slots"] = free_slots
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
        errors: list[str] = []
        now = datetime.now(timezone.utc)
        valid_slots: list[dict[str, Any]] = []
        is_location_first = bool(state.get("is_location_first") and not state.get("date_hint"))
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

        if not valid_slots and not is_location_first:
            errors.append("no valid free time slots available")
        if not valid_places and not is_location_first and not is_multi_date_vote:
            errors.append("no place recommendations satisfy the headcount")

        state["calendar_free_slots"] = valid_slots
        state["place_search_results"] = valid_places
        state["validation_errors"] = errors

        # location_first 모드에서는 장소 결과만 중요 — 시간 슬롯 없어도 통과
        # multi_date_vote 모드에서는 시간 슬롯만 중요 — 장소 없어도 통과
        if is_location_first or is_multi_date_vote:
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


async def vote_card_creation(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state
        selected_slot = state["calendar_free_slots"][0] if state.get("calendar_free_slots") else {}
        start_at = _parse_iso_datetime(selected_slot.get("start_at")) if selected_slot else None
        meeting_id = selected_slot.get("meeting_id") or selected_slot.get("id")
        if state.get("date_hint"):
            state["confirmed_date"] = state.get("date_hint")
        if start_at is not None:
            state["confirmed_time"] = _format_confirmed_time(start_at)
        is_multi_date = state.get("calendar_strategy") == "multi_date_vote"
        vote_title = (
            f"{state.get('meeting_type') or '모임'} 날짜 투표 📅"
            if is_multi_date
            else f"{state.get('meeting_type') or '모임'} 시간 투표"
        )
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
                for slot in state.get("calendar_free_slots", [])
            ],
            "headcount": state.get("headcount"),
            "blocker_notification": state.get("blocker_notification_payload"),
        }
        state["status"] = "vote_card_created"
        logger.info("[TIMING] vote_card_creation: %.2fs", time.monotonic() - _t0)
        return state
    except Exception as exc:
        return await _handle_node_exception("vote_card_creation", state, exc)


async def place_recommendation(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state
        if state.get("confirmed_place"):
            state["place_recommendation_payload"] = {
                "type": "place_recommendation",
                "room_id": state["room_id"],
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
            state["place_hint"] = _resolve_place_hint(state)

        place_results = list(state.get("place_search_results", []))
        ranked_places = place_results
        disliked_foods = await _get_room_member_food_preferences(state)

        if place_results:
            top_candidates = place_results[:10]
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
                ranked_places = reranked + place_results[10:]
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
                scoring_prompt = (
                    "당신은 매듭 AI입니다. 한국인들의 모임 일정과 장소 조율을 돕는 "
                    "어시스턴트입니다.\n"
                    f"아래 장소 후보들을 {headcount}명 {meeting_type} 모임에 얼마나 적합한지 "
                    "0부터 1 사이 점수로 평가하세요.\n"
                    f"{time_context}"
                    f"{dislike_context}"
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
                    ranked_places = reranked + place_results[10:]
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
        state["place_recommendation_payload"] = {
            "type": "place_recommendation",
            "room_id": state["room_id"],
            "place_hint": state.get("place_hint"),
            "recommendations": ranked_places[:5],
        }
        state["status"] = "place_recommended"
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
        return state
    except Exception as exc:
        return await _handle_node_exception("maedeup_card_creation", state, exc)


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
    if state.get("is_location_first"):
        return "function_calling"
    if state.get("all_slots_filled"):
        return "function_calling"
    # 부분 정보만 있거나 정보가 없는 경우 → 질문 없이 종료
    status = state.get("status", "")
    if status in ("no_slots_yet", "partial_info_acknowledged"):
        return END
    if state.get("wait_timed_out") or state.get("awaiting_user_reply"):
        return END
    return "slot_filling"


def _route_after_validation(state: GraphState) -> Literal["vote_card_creation", "place_recommendation", "__end__"]:
    if _has_node_error(state):
        return END
    if not state.get("validation_passed"):
        return END
    if state.get("is_location_first") and not state.get("date_hint"):
        return "place_recommendation"
    return "vote_card_creation"


def _route_after_vote_card_creation(state: GraphState) -> Literal["place_recommendation", "maedeup_card_creation"]:
    if _has_node_error(state):
        return "place_recommendation"
    if state.get("confirmed_place"):
        return "maedeup_card_creation"
    return "place_recommendation"


def _route_after_place_recommendation(state: GraphState) -> Literal["maedeup_card_creation", "__end__"]:
    if _has_node_error(state):
        return END
    if state.get("is_location_first") and not state.get("date_hint"):
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

    graph.add_edge(START, "intent_detection")
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
            END: END,
        },
    )
    graph.add_conditional_edges(
        "vote_card_creation",
        _route_after_vote_card_creation,
        {
            "place_recommendation": "place_recommendation",
            "maedeup_card_creation": "maedeup_card_creation",
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
    graph.add_edge("maedeup_card_creation", END)
    return graph.compile()


GRAPH = _build_graph()


async def run_pipeline(
    room_id: str,
    messages: list[Any],
    db: AsyncSession,
    slot_context: dict | None = None,
) -> dict[str, Any]:
    _pipeline_t0 = time.monotonic()
    initial_state = _default_state(room_id=room_id, db=db, messages=messages, slot_context=slot_context)
    await _compress_message_history(initial_state)
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


async def extract_meeting_summary(room_id: str, db: AsyncSession) -> dict:
    """최근 소셜 채팅에서 모임 관련 정보를 추출합니다."""
    try:
        room_pk = int(room_id)
    except (TypeError, ValueError):
        return {}

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.room_id == room_pk)
        .where(ChatMessage.pane_type == PaneType.social)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(20)
    )
    recent_messages = list(reversed(result.scalars().all()))

    if not recent_messages:
        return {}

    conversation = "\n".join(
        f"{msg.sender or msg.role}: {msg.content.strip()}"
        for msg in recent_messages
        if msg.content and msg.content.strip()
    )

    if not conversation:
        return {}

    prompt = (
        "아래 대화에서 모임 관련 정보를 추출해서 JSON으로 정리해줘.\n"
        "반드시 아래 JSON 형식만 출력하고, 다른 텍스트는 포함하지 마.\n"
        "정보가 없는 필드는 null로 채워줘.\n\n"
        "출력 형식:\n"
        '{"date": "날짜/시간 정보", "place": "장소", "headcount": "인원", '
        '"type": "모임 유형(식사/카페/술 등)", "notes": ["기타 메모"]}\n\n'
        f"대화:\n{conversation}"
    )

    raw = await call_gemini(prompt)
    if not raw:
        return {}

    # JSON 블록 추출 (```json ... ``` 또는 순수 JSON)
    cleaned = raw.strip()
    if "```" in cleaned:
        # 코드 블록에서 JSON 추출
        import re
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()

    try:
        summary = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse meeting summary JSON: %s", cleaned[:200])
        return {}

    return {
        "date": summary.get("date"),
        "place": summary.get("place"),
        "headcount": summary.get("headcount"),
        "type": summary.get("type"),
        "notes": summary.get("notes") or [],
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


