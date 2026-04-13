from datetime import datetime
import json
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.meeting import MeetingSchedule, MeetingStatus
from app.models.room import RoomMember
from app.models.user import User
from app.services.google_calendar import create_calendar_event

router = APIRouter(tags=["meetings"])


class ConfirmMeetingRequest(BaseModel):
    room_id: int
    title: str
    scheduled_at: datetime
    end_at: datetime
    location_name: Optional[str] = None
    vote_options: Optional[list[dict[str, str]]] = None


class ConfirmMeetingResponse(BaseModel):
    id: int


class ConfirmPlaceRequest(BaseModel):
    place_id: str
    name: str
    address: str
    url: Optional[str] = None


class VoteRequest(BaseModel):
    option_index: int


class VoteResponse(BaseModel):
    meeting_id: int
    votes: dict[str, int]
    total_voters: int
    selected_option_index: int


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
        end_at=body.end_at,
        location_name=body.location_name,
        vote_options=body.vote_options,
        votes={},
        status=MeetingStatus.confirmed,
        created_by=int(current_user.sub),
    )
    session.add(meeting)
    await session.commit()
    await session.refresh(meeting)
    return ConfirmMeetingResponse(id=meeting.id)


@router.post("/{meeting_id}/vote", response_model=VoteResponse)
async def vote_meeting(
    meeting_id: int,
    body: VoteRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(MeetingSchedule).where(MeetingSchedule.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    vote_options = meeting.vote_options or []
    if body.option_index < 0 or body.option_index >= len(vote_options):
        raise HTTPException(status_code=400, detail="Invalid option_index")

    votes = dict(meeting.votes or {})
    votes[str(current_user.sub)] = body.option_index
    meeting.votes = votes
    meeting.updated_at = datetime.utcnow()
    session.add(meeting)
    await session.commit()
    await session.refresh(meeting)

    aggregated_votes: dict[str, int] = {}
    for option_index in votes.values():
        key = str(option_index)
        aggregated_votes[key] = aggregated_votes.get(key, 0) + 1

    member_result = await session.execute(
        select(RoomMember).where(RoomMember.room_id == meeting.room_id)
    )
    total_voters = len(member_result.scalars().all())

    payload = {
        "type": "vote_update",
        "meeting_id": meeting.id,
        "votes": aggregated_votes,
        "total_voters": total_voters,
    }
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await redis_client.publish(
            f"agent:{meeting.room_id}",
            json.dumps(payload, ensure_ascii=False),
        )
    finally:
        await redis_client.aclose()

    return VoteResponse(
        meeting_id=meeting.id,
        votes=aggregated_votes,
        total_voters=total_voters,
        selected_option_index=body.option_index,
    )


@router.patch("/{meeting_id}/place", response_model=ConfirmMeetingResponse)
async def confirm_place(
    meeting_id: int,
    body: ConfirmPlaceRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
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

    if meeting.scheduled_at and meeting.location_name:
        participant_result = await session.execute(
            select(User)
            .join(RoomMember, RoomMember.user_id == User.id)
            .where(RoomMember.room_id == meeting.room_id)
            .where(User.calendar_consent == True)  # noqa: E712
        )
        participants = participant_result.scalars().all()
        event_end = meeting.end_at or meeting.scheduled_at
        event_location = meeting.location_address or meeting.location_name

        for participant in participants:
            if not participant.google_access_token:
                continue
            try:
                await create_calendar_event(
                    token=participant.google_access_token,
                    title=meeting.title,
                    start_datetime=meeting.scheduled_at,
                    end_datetime=event_end,
                    location=event_location,
                )
            except Exception:
                continue

    return ConfirmMeetingResponse(id=meeting.id)
