"""홈 비서 어시스턴트 — 사용자 단위 1:1 AI 대화.

`/ws/agent`(룸 내부 모임 코디네이터)와 구분되는, 홈 화면의 personal assistant.
사용자의 personal data + 다가오는 모임 + 친구 + 최근 AI memory를 컨텍스트로 묶어
Gemini에 던지고 자연어 답변을 돌려준다.

엔드포인트:
- POST /api/v1/assistant/chat — 메시지 전송, 응답 받기 (히스토리 자동 저장)
- GET  /api/v1/assistant/history — 사용자의 비서 대화 히스토리 (최근 50개)
- DELETE /api/v1/assistant/history — 대화 히스토리 전체 삭제
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.ai_memory import AIMemory
from app.models.chat import ChatMessage, PaneType
from app.models.friendship import Friendship, FriendshipStatus
from app.models.meeting import MeetingSchedule, MeetingStatus
from app.models.room import RoomMember
from app.models.user import User
from app.services.gemini import call_gemini

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])

KST = ZoneInfo("Asia/Seoul")

HISTORY_LIMIT = 50
CONTEXT_RECENT_TURNS = 10  # 최근 10개 메시지(=5턴)를 LLM 컨텍스트로


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AssistantMessage(BaseModel):
    id: int
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime


class AssistantChatResponse(BaseModel):
    user_message: AssistantMessage
    assistant_message: AssistantMessage


class AssistantHistoryResponse(BaseModel):
    messages: list[AssistantMessage]


# ─────────────────────────────────────────────────────────────────────────────
# Context builders — 사용자 정보를 LLM이 읽기 좋은 텍스트로 직렬화
# ─────────────────────────────────────────────────────────────────────────────


def _format_dt_kst(dt: Optional[datetime]) -> str:
    if dt is None:
        return "미정"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    kst = dt.astimezone(KST)
    return kst.strftime("%Y-%m-%d %H:%M")


def _bullets(label: str, items: list[str]) -> str:
    if not items:
        return f"- {label}: (없음)\n"
    return f"- {label}: {', '.join(items)}\n"


async def _build_user_context(user: User) -> str:
    """User 객체에서 personal data + 캘린더 동의 + share consent를 직렬화."""
    parts = ["## 사용자 정보"]
    parts.append(f"- 이름: {user.name}")
    parts.append(_bullets("음식 제한(못 먹음)", user.food_restrictions or []).rstrip("\n"))
    parts.append(_bullets("음식 취향", user.food_preferences or []).rstrip("\n"))
    if user.food_preference_note:
        parts.append(f"- 음식 메모: {user.food_preference_note}")
    parts.append(_bullets("선호 지역", user.liked_areas or []).rstrip("\n"))
    parts.append(_bullets("회피 지역", user.disliked_areas or []).rstrip("\n"))
    parts.append(f"- 선호 시간대: {user.time_preference or '(미설정)'}")
    parts.append(f"- 이동수단: {user.transport_mode or '(미설정)'}")
    # PR-V1.5 / Q-X3 (2026-05-14): 토큰 체크 보강.
    # calendar_consent=True 라도 google_access_token / google_refresh_token이
    # 둘 다 없으면 실제 GCal 호출 불가능 — "아니오"로 표기해 사용자에게 정확한 상태 전달.
    has_token = bool(
        getattr(user, "google_access_token", None)
        or getattr(user, "google_refresh_token", None)
    )
    calendar_active = bool(user.calendar_consent) and has_token
    parts.append(
        f"- 캘린더 연동: {'예' if calendar_active else '아니오'}"
    )
    return "\n".join(parts)


async def _build_meetings_context(
    session: AsyncSession, user: User, *, limit: int = 5
) -> str:
    """다가오는 모임 N개 + 최근 종료된 모임 1개."""
    # 사용자가 속한 room들
    rm_rows = (
        await session.execute(select(RoomMember).where(RoomMember.user_id == user.id))
    ).scalars().all()
    room_ids = [rm.room_id for rm in rm_rows]
    if not room_ids:
        return "## 모임\n- (속한 모임 없음)"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    upcoming = (
        await session.execute(
            select(MeetingSchedule)
            .where(MeetingSchedule.room_id.in_(room_ids))
            .where(MeetingSchedule.scheduled_at >= now)
            .where(MeetingSchedule.status == MeetingStatus.confirmed)
            .order_by(MeetingSchedule.scheduled_at.asc())
            .limit(limit)
        )
    ).scalars().all()

    parts = ["## 다가오는 모임"]
    if not upcoming:
        parts.append("- (예정된 모임 없음)")
    else:
        for m in upcoming:
            line = f"- {_format_dt_kst(m.scheduled_at)} · {m.title or '(제목 없음)'}"
            if m.location_name:
                line += f" @ {m.location_name}"
            parts.append(line)
    return "\n".join(parts)


async def _build_friends_context(
    session: AsyncSession, user: User, *, limit: int = 20
) -> str:
    """수락된 친구 이름 list."""
    rows = (
        await session.execute(
            select(Friendship).where(
                or_(
                    Friendship.requester_id == user.id,
                    Friendship.addressee_id == user.id,
                ),
                Friendship.status == FriendshipStatus.accepted.value,
            )
        )
    ).scalars().all()
    if not rows:
        return "## 친구\n- (수락된 친구 없음)"

    other_ids: list[int] = []
    for fr in rows:
        other_ids.append(
            fr.addressee_id if fr.requester_id == user.id else fr.requester_id
        )
    if not other_ids:
        return "## 친구\n- (수락된 친구 없음)"

    other_users = (
        await session.execute(
            select(User).where(User.id.in_(other_ids[:limit]))
        )
    ).scalars().all()
    names = [u.name for u in other_users if u.name]
    return "## 친구\n- " + (", ".join(names) if names else "(없음)")


async def _build_memory_context(
    session: AsyncSession, user: User, *, limit: int = 5
) -> str:
    """최근 추출된 AI 메모리 (active만)."""
    rows = (
        await session.execute(
            select(AIMemory)
            .where(AIMemory.user_id == user.id)
            .order_by(AIMemory.created_at.desc())
            .limit(limit * 3)  # active만 추리려면 여유 있게
        )
    ).scalars().all()

    parts = ["## 최근 AI 학습 기록 (active만)"]
    appended = 0
    for m in rows:
        if appended >= limit:
            break
        try:
            content = json.loads(m.content) if m.content else {}
        except (json.JSONDecodeError, TypeError):
            continue
        if content.get("status", "active") != "active":
            continue
        value = content.get("value")
        quote = content.get("source_quote") or ""
        parts.append(
            f"- [{m.memory_type}] {value} ← \"{quote[:40]}\""
            f" ({_format_dt_kst(m.created_at)})"
        )
        appended += 1
    if appended == 0:
        parts.append("- (없음)")
    return "\n".join(parts)


def _personal_session_id(user_id: int) -> str:
    """비서 대화를 user별로 묶는 session id. ChatMessage.session_id에 박힘.

    pane_type만으로는 사용자별 분리가 안 됨 (sender 필드는 user 메시지엔 사용자 이름,
    assistant 메시지엔 '비서'라 join key가 안 됨). session_id로 통일.
    """
    return f"personal_assistant:{user_id}"


async def _load_recent_history(
    session: AsyncSession, user: User, *, limit: int
) -> list[ChatMessage]:
    """비서 대화 이력에서 최근 N개를 시간 순(과거→현재)으로 반환."""
    rows = (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.pane_type == PaneType.personal_assistant.value)
            .where(ChatMessage.session_id == _personal_session_id(user.id))
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(reversed(rows))


def _format_history_for_prompt(history: list[ChatMessage]) -> str:
    if not history:
        return "## 최근 대화\n- (없음)"
    lines = ["## 최근 대화"]
    for m in history:
        speaker = "사용자" if m.role == "user" else "어시스턴트"
        text = (m.content or "").replace("\n", " ").strip()
        if not text:
            continue
        lines.append(f"- {speaker}: {text}")
    return "\n".join(lines)


SYSTEM_PROMPT_TEMPLATE = """\
당신은 매듭(Maedeup) 홈의 *비서 어시스턴트*입니다.
사용자가 질문하면 아래 컨텍스트만 근거로 한국어로 자연스럽고 간결하게 답하세요.

답변 규칙:
1. 모든 시간은 KST(서울)로 표시.
2. 컨텍스트에 없는 사실을 만들어내지 마세요. 모르면 "기록이 없네요"라고 답.
3. 사용자가 묻지 않은 정보는 굳이 언급하지 않기.
4. 답은 1~3문장. 길어지면 줄여서 핵심만.
5. 사용자가 자신의 personal data를 물으면 위 컨텍스트의 사용자 정보를 그대로 쓰면 됩니다.
6. 모임 추천이나 새 모임 만들기 요청은 "모임방을 만들어 친구에게 보내드릴게요" 같은 안내만 하고 실제 생성은 안 합니다 (이번 단계 한정).

오늘은 {today_kst} (KST).

{user_block}

{meetings_block}

{friends_block}

{memories_block}

{history_block}

이제 사용자의 새 메시지에 답하세요:
"""


async def _build_full_prompt(
    session: AsyncSession, user: User, history: list[ChatMessage], message: str
) -> str:
    today_kst = datetime.now(timezone.utc).astimezone(KST).strftime("%Y-%m-%d (%a)")
    user_block = await _build_user_context(user)
    meetings_block = await _build_meetings_context(session, user)
    friends_block = await _build_friends_context(session, user)
    memories_block = await _build_memory_context(session, user)
    history_block = _format_history_for_prompt(history)
    body = SYSTEM_PROMPT_TEMPLATE.format(
        today_kst=today_kst,
        user_block=user_block,
        meetings_block=meetings_block,
        friends_block=friends_block,
        memories_block=memories_block,
        history_block=history_block,
    )
    return f"{body}\n사용자: {message}\n어시스턴트:"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


def _serialize(msg: ChatMessage) -> AssistantMessage:
    return AssistantMessage(
        id=msg.id or 0,
        role=msg.role,
        content=msg.content,
        created_at=msg.created_at,
    )


@router.post("/chat", response_model=AssistantChatResponse)
async def post_chat(
    body: AssistantChatRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """비서에 메시지 전송 + 응답 수신. 사용자 메시지와 응답 모두 chat_messages에 저장."""
    user = await session.get(User, int(current_user.sub))
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    sid = _personal_session_id(user.id)
    user_msg = ChatMessage(
        pane_type=PaneType.personal_assistant.value,
        role="user",
        content=body.message.strip(),
        sender=user.name,
        session_id=sid,
        room_id=None,
    )
    session.add(user_msg)
    await session.flush()  # id 필요

    history = await _load_recent_history(session, user, limit=CONTEXT_RECENT_TURNS)
    # _load_recent_history는 방금 insert한 user_msg는 아직 commit 전이지만 같은 session이라 보임 — 마지막 항목으로 들어와있음.
    # prompt 조립에서 history는 "최근 대화"이고 현재 message는 마지막에 별도로 붙으므로 history에서 빼낸다.
    history_for_prompt = [m for m in history if m.id != user_msg.id]

    prompt = await _build_full_prompt(
        session, user, history_for_prompt, body.message
    )

    try:
        reply_text = await call_gemini(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("assistant: gemini call failed: %s", exc)
        reply_text = ""

    if not reply_text or not reply_text.strip():
        reply_text = "지금은 답변을 만들 수 없어요. 잠시 후 다시 시도해주세요."

    assistant_msg = ChatMessage(
        pane_type=PaneType.personal_assistant.value,
        role="assistant",
        content=reply_text.strip(),
        sender="비서",
        session_id=sid,
        room_id=None,
    )
    session.add(assistant_msg)
    await session.commit()
    await session.refresh(user_msg)
    await session.refresh(assistant_msg)

    return AssistantChatResponse(
        user_message=_serialize(user_msg),
        assistant_message=_serialize(assistant_msg),
    )


@router.get("/history", response_model=AssistantHistoryResponse)
async def get_history(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """사용자의 비서 대화 히스토리 (최근 HISTORY_LIMIT개, 시간 순)."""
    user = await session.get(User, int(current_user.sub))
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    rows = await _load_recent_history(session, user, limit=HISTORY_LIMIT)
    return AssistantHistoryResponse(messages=[_serialize(m) for m in rows])


@router.delete("/history", status_code=204)
async def clear_history(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """사용자의 비서 대화 전부 삭제 (room이 없는 personal_assistant pane만)."""
    user = await session.get(User, int(current_user.sub))
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    rows = (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.pane_type == PaneType.personal_assistant.value)
            .where(ChatMessage.session_id == _personal_session_id(user.id))
        )
    ).scalars().all()
    for m in rows:
        await session.delete(m)
    await session.commit()
    return None
