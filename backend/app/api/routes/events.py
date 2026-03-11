from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.session import get_session
from app.models.event import Event, EventCreate, EventRead

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=List[EventRead])
async def list_events(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Event).order_by(Event.starts_at))
    return result.scalars().all()


@router.get("/{event_id}", response_model=EventRead)
async def get_event(event_id: int, session: AsyncSession = Depends(get_session)):
    event = await session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/", response_model=EventRead, status_code=201)
async def create_event(
    payload: EventCreate, session: AsyncSession = Depends(get_session)
):
    event = Event.model_validate(payload)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: int, session: AsyncSession = Depends(get_session)):
    event = await session.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await session.delete(event)
    await session.commit()
