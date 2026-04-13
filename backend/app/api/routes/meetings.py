from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.meeting import MeetingSchedule

router = APIRouter(tags=["meetings"])


class ConfirmMeetingRequest(BaseModel):
    room_id: int
    title: str
    scheduled_at: datetime
    end_at: datetime
    location_name: Optional[str] = None


class ConfirmMeetingResponse(BaseModel):
    id: int


class ConfirmPlaceRequest(BaseModel):
    place_id: str
    name: str
    address: str
    url: Optional[str] = None


@router.post("/confirm", response_model=ConfirmMeetingResponse, status_code=201)
async def confirm_meeting(
    body: ConfirmMeetingRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if body.end_at <= body.scheduled_at:
        raise HTTPException(status_code=400, detail="end_at must be after scheduled_at")

    meeting = MeetingSchedule(
        room_id=body.room_id,
        title=body.title,
        scheduled_at=body.scheduled_at,
        location_name=body.location_name,
        created_by=int(current_user.sub),
    )
    session.add(meeting)
    await session.commit()
    await session.refresh(meeting)
    return ConfirmMeetingResponse(id=meeting.id)


@router.patch("/{meeting_id}/place", response_model=ConfirmMeetingResponse)
async def confirm_place(
    meeting_id: int,
    body: ConfirmPlaceRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from sqlmodel import select
    result = await session.execute(
        select(MeetingSchedule).where(MeetingSchedule.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.created_by != int(current_user.sub):
        raise HTTPException(status_code=403, detail="Forbidden")

    meeting.location_name = body.name
    meeting.location_address = body.address
    meeting.kakao_place_id = body.place_id
    meeting.kakao_place_url = body.url
    from datetime import datetime as _dt
    meeting.updated_at = _dt.utcnow()
    session.add(meeting)
    await session.commit()
    await session.refresh(meeting)
    return ConfirmMeetingResponse(id=meeting.id)
