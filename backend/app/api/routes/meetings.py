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
