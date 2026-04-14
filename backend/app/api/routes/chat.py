from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.chat import ChatMessage, ChatMessageCreate, ChatMessageRead, PaneType
from app.models.room import RoomMember

router = APIRouter(prefix="/chat", tags=["chat"])


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
    if room_id is not None:
        user_id = int(_current_user.sub)
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
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Not a member of this room")

    msg = ChatMessage.model_validate(payload)
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg
