from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional, TypedDict
from zoneinfo import ZoneInfo

import httpx
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.models.chat import ChatMessage, PaneType
from app.models.room import RoomMember
from app.models.user import User
from app.services.gemini import call_gemini
from app.services.intent_classifier import classify_intent

KST = ZoneInfo("Asia/Seoul")
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
GOOGLE_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
WORK_HOUR_START = 9
WORK_HOUR_END = 22
SLOT_MINUTES = 60

RECENT_MESSAGE_LIMIT = 12
SLOT_KEYS = ("date_hint", "place_hint", "headcount", "meeting_type")
MAX_SLOT_FILLING_TURNS = 4


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
    intent: str
    intent_confidence: float
    date_hint: str | None
    place_hint: str | None
    headcount: int | None
    meeting_type: str | None
    all_slots_filled: bool
    missing_slots: list[str]
    slot_filling_turns: int
    awaiting_user_reply: bool
    wait_timed_out: bool
    extracted_entities: dict[str, Any]
    calendar_free_slots: list[dict[str, Any]]
    place_search_results: list[dict[str, Any]]
    validation_errors: list[str]
    validation_passed: bool
    vote_card_payload: dict[str, Any] | None
    place_recommendation_payload: dict[str, Any] | None
    maedeup_card_payload: dict[str, Any] | None
    calendar_registration: dict[str, Any] | None
    status: str


def _default_state(
    room_id: str,
    db: AsyncSession,
    messages: list[Any],
    slot_context: dict | None = None,
) -> GraphState:
    normalized_messages = [_normalize_message(message) for message in messages]
    recent_messages, conversation_summary = _split_message_context(normalized_messages)
    seen_ids = [
        message["id"]
        for message in normalized_messages
        if isinstance(message.get("id"), int)
    ]
    ctx = slot_context or {}
    return {
        "room_id": room_id,
        "db": db,
        "message_records": normalized_messages,
        "recent_messages": recent_messages,
        "conversation_summary": conversation_summary,
        "seen_message_ids": seen_ids,
        "intent": "general",
        "intent_confidence": 0.0,
        "date_hint": ctx.get("date_hint"),
        "place_hint": ctx.get("place_hint"),
        "headcount": ctx.get("headcount"),
        "meeting_type": ctx.get("meeting_type"),
        "all_slots_filled": False,
        "missing_slots": list(SLOT_KEYS),
        "slot_filling_turns": int(ctx.get("slot_filling_turns") or 0),
        "awaiting_user_reply": False,
        "wait_timed_out": False,
        "extracted_entities": {},
        "calendar_free_slots": [],
        "place_search_results": [],
        "validation_errors": [],
        "validation_passed": False,
        "vote_card_payload": None,
        "place_recommendation_payload": None,
        "maedeup_card_payload": None,
        "calendar_registration": None,
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
    older_messages = raw_text_messages[:-RECENT_MESSAGE_LIMIT]
    return recent_messages, "\n".join(older_messages)


def _message_to_text(message: MessageRecord) -> str:
    role = message.get("role", "user")
    content = message.get("content", "").strip()
    return f"{role}: {content}"


def _serialize_context(state: GraphState) -> str:
    parts: list[str] = []
    if state.get("conversation_summary"):
        parts.append(f"[summary]\n{state['conversation_summary']}")
    if state.get("recent_messages"):
        parts.append("\n".join(state["recent_messages"]))
    return "\n\n".join(part for part in parts if part).strip()


async def _compress_message_history(state: GraphState) -> None:
    raw_text_messages = [_message_to_text(message) for message in state["message_records"] if message.get("content")]
    if len(raw_text_messages) <= RECENT_MESSAGE_LIMIT:
        state["recent_messages"] = raw_text_messages
        return

    older_messages = raw_text_messages[:-RECENT_MESSAGE_LIMIT]
    recent_messages = raw_text_messages[-RECENT_MESSAGE_LIMIT:]
    older_block = "\n".join(older_messages)

    if state.get("conversation_summary"):
        prompt = (
            "Update the running summary of this meeting-planning conversation.\n"
            "Preserve resolved facts and unresolved constraints.\n"
            "Return plain text only.\n\n"
            f"Current summary:\n{state['conversation_summary']}\n\n"
            f"New older messages:\n{older_block}"
        )
    else:
        prompt = (
            "Summarize this meeting-planning conversation.\n"
            "Preserve date hints, place hints, headcount, meeting type, and unresolved questions.\n"
            "Return plain text only.\n\n"
            f"Conversation:\n{older_block}"
        )

    summary = (await call_gemini(prompt)).strip()
    state["conversation_summary"] = summary or state.get("conversation_summary", "")
    state["recent_messages"] = recent_messages


def _coerce_headcount(value: Any) -> int | None:
    if value in (None, "", []):
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count > 0 else None


def _update_slot_state(state: GraphState, extracted: dict[str, Any]) -> None:
    date_hint = extracted.get("date_hint")
    place_hint = extracted.get("place_hint")
    meeting_type = extracted.get("meeting_type")
    headcount = _coerce_headcount(extracted.get("headcount"))

    if date_hint not in (None, ""):
        state["date_hint"] = str(date_hint)
    if place_hint not in (None, ""):
        state["place_hint"] = str(place_hint)
    if meeting_type not in (None, ""):
        state["meeting_type"] = str(meeting_type)
    if headcount is not None:
        state["headcount"] = headcount

    missing_slots: list[str] = []
    for key in SLOT_KEYS:
        if state.get(key) in (None, "", []):
            missing_slots.append(key)

    state["missing_slots"] = missing_slots
    state["all_slots_filled"] = not missing_slots


def _extract_json_object(text: str) -> dict[str, Any]:
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


def _room_id_as_int(room_id: str) -> int | None:
    try:
        return int(room_id)
    except (TypeError, ValueError):
        return None


async def _extract_entities_from_context(state: GraphState) -> dict[str, Any]:
    prompt = (
        "Extract meeting planning entities from the conversation.\n"
        "Return JSON only with this exact schema:\n"
        "{"
        '"date_hint": string | null, '
        '"place_hint": string | null, '
        '"headcount": number | null, '
        '"meeting_type": string | null'
        "}\n\n"
        f"Conversation context:\n{_serialize_context(state) or '(empty)'}\n\n"
        "Use null for unknown values."
    )
    return _extract_json_object(await call_gemini(prompt))


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
            "sender": "LangGraph",
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
        sender="LangGraph",
        room_id=room_pk,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    if message.id is not None:
        state["seen_message_ids"].append(message.id)



async def _build_slot_question(state: GraphState) -> str:
    prompt = (
        "You are helping schedule a meeting.\n"
        "Write one concise follow-up question in Korean asking only for the missing information.\n"
        f"Missing slots: {', '.join(state.get('missing_slots', [])) or '(none)'}\n"
        f"Known slots: {json.dumps(_slot_snapshot(state), ensure_ascii=False)}"
    )
    question = (await call_gemini(prompt)).strip()
    return question or "모임 일정을 이어가려면 날짜, 장소, 인원, 모임 종류 중 빠진 정보를 알려주세요."


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
    """Google Calendar API로 특정 유저의 바쁜 시간대(시작/종료)만 조회합니다."""
    if not user.google_access_token:
        return []

    params = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "fields": "items(start,end)",
    }
    headers = {"Authorization": f"Bearer {user.google_access_token}"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(GOOGLE_EVENTS_URL, params=params, headers=headers)

        # 토큰 만료 시 refresh
        if resp.status_code == 401 and user.google_refresh_token:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": user.google_refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if token_resp.status_code == 200:
                new_token = token_resp.json().get("access_token")
                if new_token:
                    user.google_access_token = new_token
                    db.add(user)
                    await db.commit()
                    headers = {"Authorization": f"Bearer {new_token}"}
                    resp = await client.get(GOOGLE_EVENTS_URL, params=params, headers=headers)

        if resp.status_code != 200:
            return []

    result = []
    for item in resp.json().get("items", []):
        start_raw = item.get("start", {})
        end_raw = item.get("end", {})
        if "dateTime" in start_raw:
            start = datetime.fromisoformat(start_raw["dateTime"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_raw["dateTime"].replace("Z", "+00:00"))
        else:
            start = datetime.fromisoformat(start_raw["date"]).replace(tzinfo=KST)
            end = datetime.fromisoformat(end_raw["date"]).replace(tzinfo=KST)
        result.append({"start": start, "end": end})
    return result


def _find_free_slots(
    busy_by_user: dict[str, list[dict[str, Any]]],
    time_min: datetime,
    time_max: datetime,
    headcount: Optional[int],
) -> list[dict[str, Any]]:
    """참여자 전원이 비어있는 시간대를 SLOT_MINUTES 단위로 탐색합니다."""
    total = len(busy_by_user)
    free_slots: list[dict[str, Any]] = []
    current = time_min
    slot_idx = 1

    while current < time_max and len(free_slots) < 5:
        slot_end = current + timedelta(minutes=SLOT_MINUTES)
        current_kst = current.astimezone(KST)

        if WORK_HOUR_START <= current_kst.hour < WORK_HOUR_END:
            available_count = sum(
                1 for periods in busy_by_user.values()
                if not any(bp["start"] < slot_end and bp["end"] > current for bp in periods)
            )
            min_needed = total if total > 0 else 1
            if available_count >= min_needed:
                s = current.astimezone(KST)
                e = slot_end.astimezone(KST)
                weekday = ["월", "화", "수", "목", "금", "토", "일"][s.weekday()]
                ampm = "오전" if s.hour < 12 else "오후"
                h = s.hour if s.hour <= 12 else s.hour - 12
                label = f"{s.month}월 {s.day}일 ({weekday}) {ampm} {h}:{s.minute:02d}"
                free_slots.append({
                    "slot_id": f"slot-{slot_idx}",
                    "start_at": current.isoformat(),
                    "end_at": slot_end.isoformat(),
                    "label": label,
                    "available_count": available_count,
                    "total_count": total,
                    "has_conflict": False,
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
                "label": (base + timedelta(days=i)).astimezone(KST).strftime("%m월 %d일 오후 %I:%M"),
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
    consenting_users = user_result.scalars().all()

    now = datetime.now(timezone.utc)
    time_min = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    time_max = time_min + timedelta(days=14)

    busy_by_user: dict[str, list[dict[str, Any]]] = {}
    for user in consenting_users:
        busy_by_user[user.name] = await _get_user_busy_periods(user, time_min, time_max, db)

    return _find_free_slots(busy_by_user, time_min, time_max, state.get("headcount"))


async def search_place(state: GraphState) -> list[dict[str, Any]]:
    """카카오맵 API로 장소 후보를 검색합니다."""
    place_hint = state.get("place_hint") or "강남"
    meeting_type = state.get("meeting_type") or ""
    query = f"{place_hint} {meeting_type}".strip()

    if not settings.KAKAO_REST_API_KEY:
        return []

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            KAKAO_KEYWORD_URL,
            params={"query": query, "size": 10},
            headers={"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"},
        )

    if resp.status_code != 200:
        return []

    results = []
    for doc in resp.json().get("documents", []):
        results.append({
            "place_id": doc.get("id", ""),
            "name": doc.get("place_name", ""),
            "address": doc.get("road_address_name") or doc.get("address_name", ""),
            "phone": doc.get("phone", ""),
            "url": doc.get("place_url", ""),
            "x": doc.get("x", ""),
            "y": doc.get("y", ""),
            "category": doc.get("category_name", ""),
            "max_headcount": 20,  # 카카오 API는 수용인원 미제공 → 기본값
            "score": 1.0,
        })
    return results


async def _register_google_calendar(state: GraphState) -> dict[str, Any]:
    """구글 캘린더에 모임 이벤트를 등록합니다."""
    selected_slot = state["calendar_free_slots"][0] if state.get("calendar_free_slots") else {}
    selected_place = state["place_search_results"][0] if state.get("place_search_results") else {}

    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])

    # 룸 owner 조회
    owner: Optional[User] = None
    if room_pk is not None:
        member_result = await db.execute(
            select(RoomMember).where(RoomMember.room_id == room_pk)
        )
        members = member_result.scalars().all()
        if members:
            user_result = await db.execute(
                select(User).where(User.id == members[0].user_id)
            )
            owner = user_result.scalars().first()

    if not owner or not owner.google_access_token:
        return {
            "provider": "google_calendar",
            "status": "skipped",
            "reason": "no_token",
            "scheduled_at": selected_slot.get("start_at"),
        }

    event_body = {
        "summary": f"{state.get('meeting_type') or '모임'} — 매듭",
        "location": selected_place.get("address", ""),
        "start": {"dateTime": selected_slot.get("start_at"), "timeZone": "Asia/Seoul"},
        "end": {"dateTime": selected_slot.get("end_at"), "timeZone": "Asia/Seoul"},
    }

    headers = {"Authorization": f"Bearer {owner.google_access_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(GOOGLE_EVENTS_URL, json=event_body, headers=headers)

        if resp.status_code == 401 and owner.google_refresh_token:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": owner.google_refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if token_resp.status_code == 200:
                new_token = token_resp.json().get("access_token")
                if new_token:
                    owner.google_access_token = new_token
                    db.add(owner)
                    await db.commit()
                    headers = {"Authorization": f"Bearer {new_token}"}
                    resp = await client.post(GOOGLE_EVENTS_URL, json=event_body, headers=headers)

    if resp.status_code in (200, 201):
        event = resp.json()
        return {
            "provider": "google_calendar",
            "status": "created",
            "event_id": event.get("id"),
            "html_link": event.get("htmlLink"),
            "scheduled_at": selected_slot.get("start_at"),
        }

    return {
        "provider": "google_calendar",
        "status": "failed",
        "http_status": resp.status_code,
        "scheduled_at": selected_slot.get("start_at"),
    }


async def intent_detection(state: GraphState) -> GraphState:
    latest_user_message = ""
    for message in reversed(state["message_records"]):
        if message.get("role") == "user" and message.get("content"):
            latest_user_message = message["content"]
            break

    intent_result = await classify_intent(latest_user_message or _serialize_context(state))
    state["intent"] = str(intent_result.get("intent", "general"))
    state["intent_confidence"] = float(intent_result.get("confidence", 0.0))
    state["status"] = "intent_detected"
    return state


async def entity_extraction(state: GraphState) -> GraphState:
    extracted = await _extract_entities_from_context(state)
    state["extracted_entities"] = extracted
    _update_slot_state(state, extracted)
    state["status"] = "entities_extracted"
    return state


async def slot_filling(state: GraphState) -> GraphState:
    _update_slot_state(state, state.get("extracted_entities", {}))
    if state["all_slots_filled"]:
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["status"] = "slots_filled"
        return state

    state["slot_filling_turns"] += 1
    if state["slot_filling_turns"] > MAX_SLOT_FILLING_TURNS:
        # 최대 턴 초과 → 남은 슬롯을 기본값으로 채워 진행
        if not state.get("date_hint"):
            state["date_hint"] = "이번 주 내"
        if not state.get("place_hint"):
            state["place_hint"] = "강남"
        if not state.get("headcount"):
            state["headcount"] = 4
        if not state.get("meeting_type"):
            state["meeting_type"] = "모임"
        state["all_slots_filled"] = True
        state["missing_slots"] = []
        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["status"] = "slots_filled_with_defaults"
        return state

    question = await _build_slot_question(state)
    # 마지막 메시지가 이미 같은 질문이면 중복 발송 방지
    latest_content = state["message_records"][-1]["content"] if state["message_records"] else None
    if latest_content != question:
        await _emit_assistant_message(state["room_id"], state["db"], question, state)

    # 내부 블로킹 대기 제거: WS receive loop가 다음 사용자 메시지를 받아
    # 새 run_pipeline 호출로 이어지도록 즉시 반환
    state["awaiting_user_reply"] = True
    state["status"] = "awaiting_user_reply"
    return state


async def function_calling(state: GraphState) -> GraphState:
    free_slots, place_results = await asyncio.gather(
        get_free_slots(state),
        search_place(state),
    )
    state["calendar_free_slots"] = free_slots
    state["place_search_results"] = place_results
    state["status"] = "functions_called"
    return state


async def supervisor_validation(state: GraphState) -> GraphState:
    errors: list[str] = []
    now = datetime.now(timezone.utc)
    valid_slots: list[dict[str, Any]] = []

    headcount = state.get("headcount")
    if headcount is None:
        errors.append("headcount is required")
    elif headcount > 20:
        errors.append("headcount exceeds current recommendation constraints")

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
        if bool(slot.get("has_conflict")):
            errors.append("calendar slot conflicts with an existing event")
            continue
        valid_slots.append(slot)

    valid_places: list[dict[str, Any]] = []
    for place in state.get("place_search_results", []):
        max_headcount = _coerce_headcount(place.get("max_headcount"))
        if headcount is not None and max_headcount is not None and max_headcount < headcount:
            continue
        valid_places.append(place)

    if not valid_slots:
        errors.append("no valid free time slots available")
    if not valid_places:
        errors.append("no place recommendations satisfy the headcount")

    state["calendar_free_slots"] = valid_slots
    state["place_search_results"] = valid_places
    state["validation_errors"] = errors
    state["validation_passed"] = not errors
    state["status"] = "validated" if not errors else "validation_failed"
    return state


async def vote_card_creation(state: GraphState) -> GraphState:
    state["vote_card_payload"] = {
        "type": "vote_card",
        "title": f"{state.get('meeting_type') or '모임'} 시간 투표",
        "room_id": state["room_id"],
        "time_options": [
            {
                "slot_id": slot.get("slot_id"),
                "label": slot.get("label"),
                "start_at": slot.get("start_at"),
                "end_at": slot.get("end_at"),
            }
            for slot in state.get("calendar_free_slots", [])
        ],
        "headcount": state.get("headcount"),
    }
    state["status"] = "vote_card_created"
    return state


async def place_recommendation(state: GraphState) -> GraphState:
    ranked_places = sorted(
        state.get("place_search_results", []),
        key=lambda item: float(item.get("score", 0.0)),
        reverse=True,
    )
    state["place_search_results"] = ranked_places
    state["place_recommendation_payload"] = {
        "type": "place_recommendation",
        "room_id": state["room_id"],
        "place_hint": state.get("place_hint"),
        "recommendations": ranked_places[:5],
    }
    state["status"] = "place_recommended"
    return state


async def maedeup_card_creation(state: GraphState) -> GraphState:
    selected_slot = state["calendar_free_slots"][0] if state.get("calendar_free_slots") else {}
    selected_place = state["place_search_results"][0] if state.get("place_search_results") else {}
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
    return state


def _route_after_slot_filling(state: GraphState) -> Literal["slot_filling", "function_calling", "__end__"]:
    if state.get("all_slots_filled"):
        return "function_calling"
    if state.get("wait_timed_out"):
        return END
    return "slot_filling"


def _route_after_validation(state: GraphState) -> Literal["vote_card_creation", "__end__"]:
    return "vote_card_creation" if state.get("validation_passed") else END


def _build_graph() -> Any:
    graph = StateGraph(GraphState)
    graph.add_node("intent_detection", intent_detection)
    graph.add_node("entity_extraction", entity_extraction)
    graph.add_node("slot_filling", slot_filling)
    graph.add_node("function_calling", function_calling)
    graph.add_node("supervisor_validation", supervisor_validation)
    graph.add_node("vote_card_creation", vote_card_creation)
    graph.add_node("place_recommendation", place_recommendation)
    graph.add_node("maedeup_card_creation", maedeup_card_creation)

    graph.add_edge(START, "intent_detection")
    graph.add_edge("intent_detection", "entity_extraction")
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
            END: END,
        },
    )
    graph.add_edge("vote_card_creation", "place_recommendation")
    graph.add_edge("place_recommendation", "maedeup_card_creation")
    graph.add_edge("maedeup_card_creation", END)
    return graph.compile()


GRAPH = _build_graph()


async def run_pipeline(
    room_id: str,
    messages: list[Any],
    db: AsyncSession,
    slot_context: dict | None = None,
) -> dict[str, Any]:
    initial_state = _default_state(room_id=room_id, db=db, messages=messages, slot_context=slot_context)
    final_state = await GRAPH.ainvoke(initial_state)
    return {
        "status": final_state.get("status"),
        "intent": final_state.get("intent"),
        "intent_confidence": final_state.get("intent_confidence"),
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
        "date_hint": final_state.get("date_hint"),
        "place_hint": final_state.get("place_hint"),
        "headcount": final_state.get("headcount"),
        "meeting_type": final_state.get("meeting_type"),
    }
