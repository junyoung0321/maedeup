from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

import redis.asyncio as aioredis
import sqlalchemy as sa
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.chat import ChatMessage, ChatMessageCreate, ChatMessageRead, PaneType, Visibility
from app.models.room import RoomMember

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ShareMessageResponse(BaseModel):
    id: int
    shared_from_id: int
    created_at: str
    already_shared: bool = False


def _message_to_event_dict(msg: ChatMessage) -> dict[str, Any]:
    """Serialize ChatMessage for Redis publish (matches agent.py output shape)."""
    return {
        "id": msg.id,
        "pane_type": msg.pane_type,
        "role": msg.role,
        "content": msg.content,
        "sender": msg.sender,
        "created_at": msg.created_at.isoformat() if msg.created_at else "",
        "user_id": msg.user_id,
        "visibility": msg.visibility,
        "shared_from_id": msg.shared_from_id,
        "shared_by_user_id": msg.shared_by_user_id,
    }


@router.get("/messages", response_model=List[ChatMessageRead])
async def list_messages(
    pane_type: Optional[PaneType] = Query(default=None),
    room_id: Optional[int] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    _current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Room membership check
    user_id = int(_current_user.sub)
    if room_id is not None:
        member_result = await session.execute(
            select(RoomMember).where(
                RoomMember.room_id == room_id,
                RoomMember.user_id == user_id,
            )
        )
        if member_result.scalar_one_or_none() is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Not a member of this room")

    stmt = select(ChatMessage).order_by(ChatMessage.created_at.asc()).limit(limit)
    if pane_type:
        stmt = stmt.where(ChatMessage.pane_type == pane_type)
    if room_id is not None:
        stmt = stmt.where(ChatMessage.room_id == room_id)
    if session_id:
        stmt = stmt.where(ChatMessage.session_id == session_id)
    # 프라이버시 경계: agent pane 요청은 shared + 본인 private만 노출
    # (social pane은 원래 shared만 있음)
    if pane_type == PaneType.agent or pane_type is None:
        stmt = stmt.where(
            or_(
                ChatMessage.pane_type != PaneType.agent,
                ChatMessage.visibility == Visibility.shared.value,
                and_(
                    ChatMessage.visibility == Visibility.private.value,
                    ChatMessage.user_id == user_id,
                ),
            )
        )
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/messages", response_model=ChatMessageRead, status_code=201)
async def create_message(
    payload: ChatMessageCreate,
    _current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Room membership check
    if payload.room_id is not None:
        user_id = int(_current_user.sub)
        member_result = await session.execute(
            select(RoomMember).where(
                RoomMember.room_id == payload.room_id,
                RoomMember.user_id == user_id,
            )
        )
        if member_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Not a member of this room")

    msg = ChatMessage.model_validate(payload)
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


@router.post("/messages/{message_id}/share", response_model=ShareMessageResponse)
async def share_message(
    message_id: int,
    card_payload: Optional[dict] = Body(default=None, embed=True),
    _current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Share a private AI message to the room.

    docs/ai-separation.md §4.3 — hybrid share model:
    - Text: copies `content` into a new shared ChatMessage
    - Cards: pass `card_payload` to re-publish as a shared card event (Vote/Place/Maedeup).
      `vote_id` / `place_id` / `maedeup_id` are inherited, not copied.

    Idempotency via PG advisory lock on `message_id` (Phase 3 eng review §3.5 A1).
    Concurrent shares of the same source return the existing shared row.
    """
    user_id = int(_current_user.sub)

    original = await session.get(ChatMessage, message_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Message not found")

    if original.pane_type != PaneType.agent:
        raise HTTPException(status_code=400, detail="Only agent messages are shareable")

    if original.visibility != Visibility.private.value:
        raise HTTPException(status_code=400, detail="Message is already shared")

    if original.user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can share this message")

    if original.room_id is None:
        raise HTTPException(status_code=400, detail="Message has no room context")

    # Advisory lock — serialize concurrent share requests for the same source message
    await session.execute(
        sa.text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": message_id},
    )

    # Idempotency check — return existing shared record if any
    existing_result = await session.execute(
        select(ChatMessage).where(ChatMessage.shared_from_id == message_id).limit(1)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return ShareMessageResponse(
            id=existing.id,
            shared_from_id=message_id,
            created_at=existing.created_at.isoformat() if existing.created_at else "",
            already_shared=True,
        )

    # Create shared copy — text content copied; card refs flow through card_payload
    shared = ChatMessage(
        pane_type=original.pane_type,
        role=original.role,
        content=original.content,
        sender=original.sender,
        session_id=original.session_id,
        room_id=original.room_id,
        user_id=user_id,
        visibility=Visibility.shared.value,
        shared_from_id=original.id,
        shared_by_user_id=user_id,
    )
    session.add(shared)
    await session.commit()
    await session.refresh(shared)

    # Publish to room's shared channel so all members' WS subscribers receive it
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        shared_channel = f"agent:{original.room_id}"
        # Primary event: the shared chat message itself
        event = _message_to_event_dict(shared)
        await redis_client.publish(shared_channel, json.dumps(event, ensure_ascii=False))
        # If caller supplied a card_payload (vote_card / place_recommendation / maedeup_card),
        # re-publish it on the shared channel so cards render for everyone.
        if card_payload and isinstance(card_payload, dict):
            card_type = card_payload.get("type")
            if card_type in ("vote_card", "place_recommendation", "maedeup_card"):
                card_event = dict(card_payload)
                card_event["shared_from_id"] = original.id
                card_event["shared_by_user_id"] = user_id
                card_event["shared_message_id"] = shared.id
                await redis_client.publish(
                    shared_channel, json.dumps(card_event, ensure_ascii=False)
                )
        await redis_client.aclose()
    except Exception:
        logger.warning(
            "Share publish failed for message %d room %d", message_id, original.room_id,
            exc_info=True,
        )

    return ShareMessageResponse(
        id=shared.id,
        shared_from_id=message_id,
        created_at=shared.created_at.isoformat() if shared.created_at else "",
        already_shared=False,
    )
