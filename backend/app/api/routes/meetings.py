from datetime import datetime, timezone
import json
import logging
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.finalization import (
    _publish_finalization_event,
    get_redis as get_finalization_redis,
)
from app.core.config import settings
from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.meeting import MeetingSchedule, MeetingStatus
from app.models.room import Room, RoomMember
from app.models.user import User
from app.services import scheduling_round as sr
from app.services.google_calendar import (
    delete_events_for_meeting_members,
    sync_events_for_meeting_members,
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
    meeting_id: int | None = None
    # If the confirm is driven by a finalization proposal, the front-end
    # supplies this so the server can enforce host-auth + proposal-state
    # guards (superseded → 409, below-majority → 409, non-host → 403).
    proposal_id: Optional[str] = None


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


@router.get("/rooms/{room_id}/pending-place")
async def get_pending_place_recommendation(
    room_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """방의 가장 최근 장소 추천 payload를 Redis에서 반환. 새로고침 복구용."""
    user_id = int(current_user.sub)
    member_check = await session.execute(
        select(RoomMember).where(
            RoomMember.room_id == room_id,
            RoomMember.user_id == user_id,
        )
    )
    if member_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not a room member")

    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            raw = await r.get(f"room_place_rec:{room_id}")
        finally:
            await r.aclose()
    except Exception:
        raw = None

    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


@router.get("/rooms/{room_id}/pending-vote")
async def get_pending_vote_card(
    room_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """방의 가장 최근 pending MeetingSchedule을 vote_card payload 형태로 반환합니다.
    새로고침 후 투표 카드 복구용 — WebSocket은 휘발성이므로 pending 상태를 DB에서 읽음."""
    user_id = int(current_user.sub)
    member_check = await session.execute(
        select(RoomMember).where(
            RoomMember.room_id == room_id,
            RoomMember.user_id == user_id,
        )
    )
    if member_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not a room member")

    result = await session.execute(
        select(MeetingSchedule)
        .where(
            MeetingSchedule.room_id == room_id,
            MeetingSchedule.status == MeetingStatus.pending,
        )
        .order_by(MeetingSchedule.created_at.desc())
        .limit(1)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None or not meeting.vote_options:
        return None

    return {
        "type": "vote_card",
        "title": meeting.title,
        "room_id": str(meeting.room_id),
        "meeting_id": meeting.id,
        "time_options": meeting.vote_options,
        "headcount": None,
        "votes": meeting.votes or {},
    }


@router.post("/confirm", response_model=ConfirmMeetingResponse, status_code=201)
async def confirm_meeting(
    body: ConfirmMeetingRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_finalization_redis),
):
    if body.end_at <= body.scheduled_at:
        raise HTTPException(status_code=400, detail="end_at must be after scheduled_at")
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="title must not be empty")

    room_row = await session.execute(
        select(Room).where(Room.id == body.room_id)
    )
    room = room_row.scalar_one_or_none()
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    # 멤버라면 누구나 확정 가능.
    member_result = await session.execute(
        select(RoomMember).where(
            RoomMember.user_id == int(current_user.sub),
            RoomMember.room_id == body.room_id,
        )
    )
    if member_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Host is not a room member")

    # Finalization-proposal path: validate proposal state before DB write.
    if body.proposal_id is not None:
        try:
            await sr.host_confirm(
                redis,
                room_id=body.room_id,
                proposal_id=body.proposal_id,
                user_id=int(current_user.sub),
                room_host_id=room.created_by,
            )
        except sr.NotFoundError:
            raise HTTPException(status_code=404, detail="proposal_not_found")
        except sr.SupersededError as exc:
            raise HTTPException(status_code=409, detail=f"superseded: {exc}")
        except sr.BelowMajorityError as exc:
            raise HTTPException(status_code=409, detail=f"below_majority: {exc}")
        except sr.NotHostError as exc:
            # Should be caught by the earlier room.created_by check, but be
            # defensive — scheduling_round is the source of truth for state.
            raise HTTPException(status_code=403, detail=str(exc))

    # DB는 naive datetime을 사용하므로 timezone 제거
    scheduled_at = body.scheduled_at.replace(tzinfo=None) if body.scheduled_at.tzinfo else body.scheduled_at
    end_at = body.end_at.replace(tzinfo=None) if body.end_at.tzinfo else body.end_at

    if body.meeting_id is not None:
        # 기존 pending 미팅을 confirmed로 승격
        result = await session.execute(
            select(MeetingSchedule).where(MeetingSchedule.id == body.meeting_id)
        )
        meeting = result.scalar_one_or_none()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        if meeting.room_id != body.room_id:
            raise HTTPException(status_code=400, detail="Meeting does not belong to this room")

        meeting.status = MeetingStatus.confirmed
        meeting.scheduled_at = scheduled_at
        meeting.end_at = end_at
        meeting.title = body.title
        meeting.vote_options = body.vote_options
        meeting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(meeting)
    else:
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

    # If a proposal drove this confirm, mark it as confirmed in Redis and
    # broadcast `meeting_confirmed` on the social channel so every client
    # transitions into the success state together.
    if body.proposal_id is not None:
        try:
            await sr.mark_confirmed(
                redis, room_id=body.room_id, proposal_id=body.proposal_id
            )
            # 확정 후 availability / unavailability / date_selection 캐시 비우기 —
            # 다음 선택이 새 제안을 만들지 않도록.
            await sr.clear_availability(redis, room_id=body.room_id)
            await sr.clear_unavailability(redis, room_id=body.room_id)
            await sr.clear_date_selections(redis, room_id=body.room_id)
            await _publish_finalization_event(
                redis,
                body.room_id,
                {
                    "type": "meeting_confirmed",
                    "room_id": body.room_id,
                    "meeting_id": meeting.id,
                    "proposal_id": body.proposal_id,
                    "scheduled_at": scheduled_at.isoformat(),
                    "end_at": end_at.isoformat(),
                    "title": body.title,
                },
            )
        except Exception:
            # Redis post-commit cleanup should never unwind the DB commit.
            logger.warning(
                "Finalization post-confirm bookkeeping failed (proposal_id=%s, meeting_id=%s)",
                body.proposal_id, meeting.id, exc_info=True,
            )

    # Best-effort: push the confirmed meeting onto each consenting member's
    # Google Calendar. Failures here MUST NOT unwind the DB commit.
    try:
        members_result = await session.execute(
            select(User)
            .join(RoomMember, RoomMember.user_id == User.id)
            .where(RoomMember.room_id == body.room_id)
        )
        members = members_result.scalars().all()
        updated_event_ids = await sync_events_for_meeting_members(
            meeting, members, session
        )
        if updated_event_ids != (meeting.google_event_ids or {}):
            meeting.google_event_ids = updated_event_ids
            session.add(meeting)
            await session.commit()
            await session.refresh(meeting)
    except Exception:
        logger.warning(
            "Google Calendar fan-out failed (meeting_id=%s, room_id=%s)",
            meeting.id, body.room_id, exc_info=True,
        )

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
    await session.commit()
    await session.refresh(meeting)

    # Best-effort: propagate the new place to each member's existing Google
    # Calendar event (or create it if they consented since confirm_meeting).
    # Failures are logged and tolerated — the place change must not be undone.
    if meeting.scheduled_at and meeting.location_name:
        try:
            members_result = await session.execute(
                select(User)
                .join(RoomMember, RoomMember.user_id == User.id)
                .where(RoomMember.room_id == meeting.room_id)
            )
            members = members_result.scalars().all()
            updated_event_ids = await sync_events_for_meeting_members(
                meeting, members, session
            )
            if updated_event_ids != (meeting.google_event_ids or {}):
                meeting.google_event_ids = updated_event_ids
                session.add(meeting)
                await session.commit()
                await session.refresh(meeting)
        except Exception:
            logger.warning(
                "Google Calendar place-update fan-out failed (meeting_id=%s)",
                meeting.id, exc_info=True,
            )

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


@router.post("/{meeting_id}/cancel", response_model=ConfirmMeetingResponse)
async def cancel_meeting(
    meeting_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_finalization_redis),
):
    """Soft-cancel a confirmed (or pending) meeting.

    - Host-only.
    - Marks the meeting cancelled, broadcasts `meeting_cancelled` to the room,
      and removes the corresponding events from each member's Google Calendar
      best-effort.
    - Idempotent: cancelling an already-cancelled meeting is a no-op.
    """
    result = await session.execute(
        select(MeetingSchedule).where(MeetingSchedule.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.created_by != int(current_user.sub):
        raise HTTPException(status_code=403, detail="Forbidden")
    if meeting.status == MeetingStatus.cancelled:
        return ConfirmMeetingResponse(id=meeting.id)

    # Capture members BEFORE status flip — used by the calendar fan-out below.
    members_result = await session.execute(
        select(User)
        .join(RoomMember, RoomMember.user_id == User.id)
        .where(RoomMember.room_id == meeting.room_id)
    )
    members = members_result.scalars().all()

    meeting.status = MeetingStatus.cancelled
    meeting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(meeting)
    await session.commit()
    await session.refresh(meeting)

    # Broadcast cancellation so every client transitions UI together.
    try:
        await _publish_finalization_event(
            redis,
            meeting.room_id,
            {
                "type": "meeting_cancelled",
                "room_id": meeting.room_id,
                "meeting_id": meeting.id,
            },
        )
    except Exception:
        logger.warning(
            "Failed to broadcast meeting_cancelled (meeting_id=%s)",
            meeting.id, exc_info=True,
        )

    # Best-effort: delete the matching event from each member's calendar.
    # Failures here MUST NOT undo the cancellation.
    try:
        remaining = await delete_events_for_meeting_members(
            meeting, members, session
        )
        if remaining != (meeting.google_event_ids or {}):
            meeting.google_event_ids = remaining
            session.add(meeting)
            await session.commit()
            await session.refresh(meeting)
    except Exception:
        logger.warning(
            "Google Calendar delete fan-out failed (meeting_id=%s)",
            meeting.id, exc_info=True,
        )

    return ConfirmMeetingResponse(id=meeting.id)
