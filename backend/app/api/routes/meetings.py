from datetime import datetime, timezone
import json
import logging
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
from app.services.google_calendar import (
    GoogleCalendarAuthError,
    GoogleCalendarError,
    create_calendar_event,
    get_google_access_token,
)
from app.services.langgraph_pipeline import suggest_alternative_slots
from app.services.meeting_history import save_meeting_record

router = APIRouter(tags=["meetings"])
logger = logging.getLogger(__name__)


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


class MeetingListItem(BaseModel):
    id: int
    room_id: int
    title: str
    scheduled_at: datetime
    end_at: Optional[datetime] = None
    location_name: Optional[str] = None
    location_address: Optional[str] = None
    status: str


@router.get("/", response_model=list[MeetingListItem])
async def list_my_meetings(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """현재 유저가 참여 중인 모임 목록을 반환합니다."""
    user_id = int(current_user.sub)
    # 유저가 속한 룸의 모임 전체 조회
    room_result = await session.execute(
        select(RoomMember.room_id).where(RoomMember.user_id == user_id)
    )
    room_ids = [r for (r,) in room_result.all()]
    if not room_ids:
        return []

    result = await session.execute(
        select(MeetingSchedule)
        .where(MeetingSchedule.room_id.in_(room_ids))
        .order_by(MeetingSchedule.scheduled_at.desc())
        .limit(20)
    )
    return [
        MeetingListItem(
            id=m.id,
            room_id=m.room_id,
            title=m.title,
            scheduled_at=m.scheduled_at,
            end_at=m.end_at,
            location_name=m.location_name,
            location_address=m.location_address,
            status=m.status,
        )
        for m in result.scalars().all()
    ]


@router.get("/upcoming", response_model=Optional[MeetingListItem])
async def get_upcoming_meeting(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """가장 임박한 확정 모임 1건을 반환합니다."""
    user_id = int(current_user.sub)
    room_result = await session.execute(
        select(RoomMember.room_id).where(RoomMember.user_id == user_id)
    )
    room_ids = [r for (r,) in room_result.all()]
    if not room_ids:
        return None

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await session.execute(
        select(MeetingSchedule)
        .where(
            MeetingSchedule.room_id.in_(room_ids),
            MeetingSchedule.status == MeetingStatus.confirmed,
            MeetingSchedule.scheduled_at >= now,
        )
        .order_by(MeetingSchedule.scheduled_at.asc())
        .limit(1)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        return None

    return MeetingListItem(
        id=meeting.id,
        room_id=meeting.room_id,
        title=meeting.title,
        scheduled_at=meeting.scheduled_at,
        end_at=meeting.end_at,
        location_name=meeting.location_name,
        location_address=meeting.location_address,
        status=meeting.status,
    )


@router.post("/confirm", response_model=ConfirmMeetingResponse, status_code=201)
async def confirm_meeting(
    body: ConfirmMeetingRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if body.end_at <= body.scheduled_at:
        raise HTTPException(status_code=400, detail="end_at must be after scheduled_at")
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="title must not be empty")

    member_result = await session.execute(
        select(RoomMember).where(
            RoomMember.user_id == int(current_user.sub),
            RoomMember.room_id == body.room_id,
        )
    )
    if member_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Forbidden")

    # DB는 naive datetime을 사용하므로 timezone 제거
    scheduled_at = body.scheduled_at.replace(tzinfo=None) if body.scheduled_at.tzinfo else body.scheduled_at
    end_at = body.end_at.replace(tzinfo=None) if body.end_at.tzinfo else body.end_at

    meeting = MeetingSchedule(
        room_id=body.room_id,
        title=body.title,
        scheduled_at=scheduled_at,
        end_at=end_at,
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

    member_result = await session.execute(
        select(RoomMember).where(
            RoomMember.user_id == int(current_user.sub),
            RoomMember.room_id == meeting.room_id,
        )
    )
    if member_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Forbidden")

    vote_options = meeting.vote_options or []
    if body.option_index < 0 or body.option_index >= len(vote_options):
        raise HTTPException(status_code=400, detail="Invalid option_index")

    votes = dict(meeting.votes or {})
    votes[str(current_user.sub)] = body.option_index
    meeting.votes = votes
    meeting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        try:
            await redis_client.publish(
                f"agent:{meeting.room_id}",
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception:
            logger.warning("Redis publish failed for vote update meeting_id=%s", meeting.id, exc_info=True)

        # --- 갈등 조율 (Conflict Resolution) ---
        # 전체 멤버가 투표를 완료했는지 확인
        num_voted = len(votes)
        if num_voted >= total_voters and total_voters > 0:
            # 최다 득표 옵션과 득표율 계산
            best_option = max(aggregated_votes, key=lambda k: aggregated_votes[k])
            best_count = aggregated_votes[best_option]
            unanimity_rate = best_count / total_voters

            if unanimity_rate < 1.0:
                # 만장일치가 아님 → 갈등 조율 시도
                try:
                    best_option_idx = int(best_option)
                    best_option_detail = vote_options[best_option_idx] if best_option_idx < len(vote_options) else {}

                    # 최다 득표 옵션에 투표하지 않은 유저 식별
                    dissenting_user_ids = [
                        int(uid) for uid, oidx in votes.items()
                        if oidx != best_option_idx
                    ]
                    dissenter_result = await session.execute(
                        select(User).where(User.id.in_(dissenting_user_ids))
                    )
                    dissenter_names = [u.name for u in dissenter_result.scalars().all() if u.name]

                    # 대안 시간대 검색
                    alternative = await suggest_alternative_slots(
                        room_id=meeting.room_id,
                        dissenting_user_ids=dissenting_user_ids,
                        session=session,
                    )

                    if alternative:
                        dissenter_mentions = ", ".join(f"@{n}" for n in dissenter_names)
                        alt_label = alternative.get("label", "대안 시간")
                        conflict_message = (
                            f"{alt_label}(으)로 바꾸면 전원 가능해요! "
                            f"({dissenter_mentions}님이 기존 시간에 어려워요)"
                        )

                        conflict_payload = {
                            "type": "conflict_resolution",
                            "meeting_id": meeting.id,
                            "current_best": {
                                "option_index": best_option_idx,
                                "detail": best_option_detail,
                                "vote_count": best_count,
                            },
                            "alternative": alternative,
                            "dissenting_users": dissenter_names,
                            "message": conflict_message,
                        }
                        try:
                            await redis_client.publish(
                                f"agent:{meeting.room_id}",
                                json.dumps(conflict_payload, ensure_ascii=False),
                            )
                        except Exception:
                            logger.warning(
                                "Redis publish failed for conflict resolution meeting_id=%s",
                                meeting.id,
                                exc_info=True,
                            )
                except Exception:
                    logger.warning(
                        "Conflict resolution failed for meeting_id=%s",
                        meeting.id,
                        exc_info=True,
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
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="name must not be empty")
    if not body.address.strip():
        raise HTTPException(status_code=400, detail="address must not be empty")

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
    meeting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(meeting)

    # Calendar registration BEFORE commit so we can rollback on failure
    if meeting.scheduled_at and meeting.location_name:
        try:
            participant_result = await session.execute(
                select(User)
                .join(RoomMember, RoomMember.user_id == User.id)
                .where(RoomMember.room_id == meeting.room_id)
                .where(User.calendar_consent == True)  # noqa: E712
            )
            participants = participant_result.scalars().all()
            event_end = meeting.end_at or meeting.scheduled_at
            event_location = meeting.location_address or meeting.location_name
            auth_error_users: list[str] = []
            calendar_error_users: list[str] = []

            eligible_participants = [
                participant
                for participant in participants
                if participant.google_access_token or participant.google_refresh_token
            ]

            for participant in eligible_participants:
                try:
                    await get_google_access_token(participant, session)
                except GoogleCalendarAuthError:
                    auth_error_users.append(participant.name)

            if auth_error_users:
                joined_names = ", ".join(sorted(set(auth_error_users)))
                await session.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Google Calendar authorization is invalid for: "
                        f"{joined_names}. Reconnect Google Calendar and try again."
                    ),
                )

            for participant in eligible_participants:
                try:
                    await create_calendar_event(
                        user=participant,
                        session=session,
                        title=meeting.title,
                        start_datetime=meeting.scheduled_at,
                        end_datetime=event_end,
                        location=event_location,
                    )
                except GoogleCalendarAuthError:
                    auth_error_users.append(participant.name)
                except GoogleCalendarError:
                    calendar_error_users.append(participant.name)
                except Exception:
                    logger.warning("Unexpected calendar sync failure for meeting_id=%s user_id=%s", meeting.id, participant.id, exc_info=True)
                    calendar_error_users.append(participant.name)

            if auth_error_users:
                joined_names = ", ".join(sorted(set(auth_error_users)))
                await session.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Google Calendar authorization expired for: "
                        f"{joined_names}. Reconnect Google Calendar and try again."
                    ),
                )
            if calendar_error_users:
                joined_names = ", ".join(sorted(set(calendar_error_users)))
                await session.rollback()
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to create Google Calendar events for: {joined_names}.",
                )
        except HTTPException:
            raise
        except Exception:
            logger.exception("Calendar registration failed for meeting_id=%s", meeting.id)
            await session.rollback()
            raise HTTPException(
                status_code=500,
                detail="Failed to register calendar events. Place was not saved.",
            )

    await session.commit()
    await session.refresh(meeting)

    # 모임 히스토리 저장 (non-critical, after commit)
    try:
        await save_meeting_record(meeting.id, session)
    except Exception:
        logger.warning(
            "Failed to save meeting record for meeting_id=%s",
            meeting.id,
            exc_info=True,
        )

    return ConfirmMeetingResponse(id=meeting.id)
