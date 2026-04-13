from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.session import get_session
from app.models.chat import ChatMessage, ChatMessageCreate, ChatMessageRead, PaneType

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/messages", response_model=List[ChatMessageRead])
async def list_messages(
    pane_type: Optional[PaneType] = Query(default=None),
    room_id: Optional[int] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
):
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
    session: AsyncSession = Depends(get_session),
):
    msg = ChatMessage.model_validate(payload)
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg
