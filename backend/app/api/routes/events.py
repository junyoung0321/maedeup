from datetime import timezone
from typing import List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.event import Event, EventCreate, EventRead
from app.models.room import RoomMember

router = APIRouter(prefix="/events", tags=["events"])


def _normalize_dt(dt):
    """datetime을 naive UTC로 변환합니다. naive datetime은 KST로 간주합니다."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    # naive datetime은 KST로 간주하여 UTC로 변환
    kst = ZoneInfo("Asia/Seoul")
    return dt.replace(tzinfo=kst).astimezone(timezone.utc).replace(tzinfo=None)


async def _user_room_ids(user_id: int, session: AsyncSession) -> list[int]:
    result = await session.execute(
        select(RoomMember.room_id).where(RoomMember.user_id == user_id)
    )
    return [r for (r,) in result.all()]


@router.get("/", response_model=List[EventRead])
async def list_events(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    room_ids = await _user_room_ids(int(current_user.sub), session)
    if not room_ids:
        return []
    result = await session.execute(
        select(Event)
        .where(Event.room_id.in_(room_ids))
        .order_by(Event.starts_at)
    )
    return result.scalars().all()


@router.get("/{event_id}", response_model=EventRead)
async def get_event(
    event_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    event = await session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    room_ids = await _user_room_ids(int(current_user.sub), session)
    if event.room_id not in room_ids:
        raise HTTPException(status_code=403, detail="Forbidden")
    return event


@router.post("/", response_model=EventRead, status_code=201)
async def create_event(
    payload: EventCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # 멤버십 확인
    room_ids = await _user_room_ids(int(current_user.sub), session)
    if payload.room_id not in room_ids:
        raise HTTPException(status_code=403, detail="Forbidden")

    event = Event.model_validate(payload)
    event.starts_at = _normalize_dt(event.starts_at)
    event.ends_at = _normalize_dt(event.ends_at)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    event = await session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    room_ids = await _user_room_ids(int(current_user.sub), session)
    if event.room_id not in room_ids:
        raise HTTPException(status_code=403, detail="Forbidden")
    await session.delete(event)
    await session.commit()
