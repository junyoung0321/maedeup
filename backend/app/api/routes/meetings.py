from datetime import datetime, timezone
import json
import logging
from typing import Any, Literal, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
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
from app.models.meeting_preference import MeetingPreference
from app.models.room import Room, RoomMember
from app.models.user import User
from app.repositories.messages import MessageReader
from app.schemas.meetings import PlacePatchRequest, PlacePatchResponse
from app.services import scheduling_round as sr
from app.services.google_calendar import (
    delete_events_for_meeting_members,
    sync_events_for_meeting_members,
)
from app.services.kakao_maps import search_address, search_keyword
from app.services.langgraph_pipeline import (
    memory_extraction,
    run_pipeline,
    suggest_alternative_slots,
)
from app.services.meeting_history import save_meeting_record
from app.services.pipeline.helpers.preference_toggle import (
    compute_preference_toggle_enabled,
)
from app.services.pipeline.helpers.preferences import load_requester_context
from app.db.session import AsyncSessionLocal
import asyncio as _asyncio


async def _spawn_personal_data_extraction(room_id: int) -> None:
    """장소 확정(PATCH /meetings/{id}/place) 직후 transcript에서 personal_data 학습.

    LangGraph maedeup_card_creation 노드가 안 도는 경로(/place patch)에서도
    ACT 6 '비린 거 → ✨' 학습 임팩트가 살도록 fire-and-forget으로 별도 호출.
    state dict는 memory_extraction 함수가 요구하는 최소값만 채움.
    실패는 silent log only — 모임 자체를 깨뜨리지 않음.
    """
    try:
        async with AsyncSessionLocal() as new_session:
            await memory_extraction({
                "room_id": room_id,
                "maedeup_card_payload": {"_": "place_patch_trigger"},
                "db": new_session,
            })
    except Exception:
        logger.exception("Personal data extraction (place patch) failed room=%s", room_id)

router = APIRouter(tags=["meetings"])
logger = logging.getLogger(__name__)


async def _load_group_preference_context(
    session: AsyncSession, room_id: int
) -> dict[str, Any]:
    """Codex P2 (2026-05-15): refresh route Q7-c C3 probe용 group 컨텍스트.

    `_lightweight_speaker_matches_group`는 state["default_place_hint"]와
    state["preference_common_foods"] 둘 다 있어야 비교가 가능. refresh route
    probe_state는 requester-only 필드만 채웠기 때문에 C3 분기가 절대 발동되지
    않는 버그를 수정.

    Returns:
        {
          "default_place_hint": str | None,   # MeetingPreference 다수결 위치
          "preference_common_foods": list[str],  # 멤버 선호 음식 union
        }

    실패/데이터 없음 시 빈 dict 반환 → C3는 자연스럽게 skip되어 토글 활성 유지.
    """
    try:
        pref_result = await session.execute(
            select(MeetingPreference).where(MeetingPreference.room_id == room_id)
        )
        prefs = pref_result.scalars().all()
    except Exception:
        logger.warning(
            "MeetingPreference load failed room_id=%s — C3 probe will skip",
            room_id,
            exc_info=True,
        )
        return {}

    # 장소 다수결 (best_location)
    default_place_hint: str | None = None
    if prefs:
        location_counts: dict[str, int] = {}
        for p in prefs:
            loc = (p.preferred_location or "").strip()
            if loc:
                location_counts[loc] = location_counts.get(loc, 0) + 1
        if location_counts:
            default_place_hint = max(location_counts, key=location_counts.get)

    # 선호 음식 union (preference_common_foods로 사용 — Q7-c C3 비교에서
    # 70% 교집합 검사이므로 union이 보수적·충분).
    common_foods: list[str] = []
    seen: set[str] = set()
    for p in prefs or []:
        for item in (p.preferred_foods or []):
            normalized = str(item).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                common_foods.append(normalized)

    return {
        "default_place_hint": default_place_hint,
        "preference_common_foods": common_foods,
    }


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
    # True if the caller's own user_id appears in meeting.google_event_ids after
    # the operation — i.e. their personal Google Calendar has the event.
    # False when the user revoked consent, never linked Google, or the operation
    # cancelled/removed events. Frontends use this to render "내 캘린더에 추가됨".
    calendar_event_for_self: bool = False
    # Total members whose calendars currently hold this meeting's event.
    calendar_member_count: int = 0


def _calendar_response_fields(meeting: MeetingSchedule, user_id: int) -> dict:
    event_ids = meeting.google_event_ids or {}
    return {
        "calendar_event_for_self": str(user_id) in event_ids,
        "calendar_member_count": len(event_ids),
    }


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

    votes = meeting.votes or {}
    current_user_vote = votes.get(str(user_id))  # int | None

    return {
        "type": "vote_card",
        "title": meeting.title,
        "room_id": str(meeting.room_id),
        "meeting_id": meeting.id,
        "time_options": meeting.vote_options,
        "headcount": None,
        "votes": votes,
        "current_user_vote": current_user_vote,
    }


class MeetingMemberInfo(BaseModel):
    id: int
    name: str
    picture: Optional[str] = None
    is_guest: bool = False


class MeetingDetailResponse(BaseModel):
    id: int
    room_id: int
    room_name: str
    title: str
    scheduled_at: datetime
    end_at: Optional[datetime] = None
    location_name: Optional[str] = None
    location_address: Optional[str] = None
    kakao_place_url: Optional[str] = None
    status: str
    members: list[MeetingMemberInfo]


@router.get("/{meeting_id}", response_model=MeetingDetailResponse)
async def get_meeting_detail(
    meeting_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """모임 + 방 이름 + 멤버 목록을 한 번에 반환. 완료 페이지에서 사용."""
    meeting_result = await session.execute(
        select(MeetingSchedule).where(MeetingSchedule.id == meeting_id)
    )
    meeting = meeting_result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    user_id = int(current_user.sub)
    membership_result = await session.execute(
        select(RoomMember).where(
            RoomMember.room_id == meeting.room_id,
            RoomMember.user_id == user_id,
        )
    )
    if membership_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Forbidden")

    room_result = await session.execute(
        select(Room).where(Room.id == meeting.room_id)
    )
    room = room_result.scalar_one_or_none()

    members_result = await session.execute(
        select(User)
        .join(RoomMember, RoomMember.user_id == User.id)
        .where(RoomMember.room_id == meeting.room_id)
    )
    members = members_result.scalars().all()

    return MeetingDetailResponse(
        id=meeting.id,
        room_id=meeting.room_id,
        room_name=room.name if room else "",
        title=meeting.title,
        scheduled_at=meeting.scheduled_at,
        end_at=meeting.end_at,
        location_name=meeting.location_name,
        location_address=meeting.location_address,
        kakao_place_url=meeting.kakao_place_url,
        status=meeting.status,
        members=[
            MeetingMemberInfo(
                id=u.id,
                name=u.name,
                picture=u.picture,
                is_guest=u.is_guest,
            )
            for u in members
        ],
    )


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

    # A4-1: AI 패널에 확정 안내 박스 emit (시연 멘트 "원클릭으로 일정 확정"
    # 직후 화면 변화 0인 어색함 해결). DB 커밋 후, GCal 등록 전.
    try:
        from app.services.agent_messaging import emit_agent_message, format_korean_meeting_time
        time_label = format_korean_meeting_time(scheduled_at)
        await emit_agent_message(
            redis,
            body.room_id,
            f"✅ 일정이 확정되었어요 — {time_label}",
        )
        await emit_agent_message(
            redis,
            body.room_id,
            "이제 어디서 만날지 정해볼까요? 장소를 추천해드릴게요.",
        )
    except Exception:
        logger.warning(
            "A4-1 confirm announcement failed (meeting_id=%s)",
            meeting.id, exc_info=True,
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
            meeting, members, session, event_title=room.name,
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

    return ConfirmMeetingResponse(
        id=meeting.id,
        **_calendar_response_fields(meeting, int(current_user.sub)),
    )


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
        "user_votes": votes,
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


def _meeting_card_time(meeting: MeetingSchedule) -> dict[str, str]:
    if meeting.end_at:
        label = f"{meeting.scheduled_at:%Y-%m-%d %H:%M} - {meeting.end_at:%H:%M}"
    else:
        label = f"{meeting.scheduled_at:%Y-%m-%d %H:%M}"
    payload = {
        "label": label,
        "start_at": meeting.scheduled_at.isoformat(),
    }
    if meeting.end_at:
        payload["end_at"] = meeting.end_at.isoformat()
    return payload


async def _publish_maedeup_place_update(
    meeting: MeetingSchedule,
    *,
    calendar_registered: bool,
    headcount: int | None,
) -> None:
    payload = {
        "type": "maedeup_card",
        "room_id": str(meeting.room_id),
        "meeting_id": meeting.id,
        "title": meeting.title or "모임 매듭 카드",
        "meeting_type": "모임",
        "date_hint": meeting.scheduled_at.date().isoformat(),
        "date": meeting.scheduled_at.date().isoformat(),
        "time": _meeting_card_time(meeting),
        "place": meeting.location_name,
        "place_pending": False,
        "headcount": headcount,
        "calendar_registered": calendar_registered,
        "selected_time": _meeting_card_time(meeting),
        "selected_place": {
            "name": meeting.location_name or "",
            "address": meeting.location_address or "",
            "url": meeting.kakao_place_url or "",
            "place_id": meeting.kakao_place_id or "",
        },
    }
    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        await redis_client.publish(
            f"agent:{meeting.room_id}",
            json.dumps(payload, ensure_ascii=False),
        )
    finally:
        await redis_client.aclose()


@router.patch("/{meeting_id}/place", response_model=PlacePatchResponse)
async def patch_meeting_place(
    meeting_id: int,
    body: PlacePatchRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    place = body.place.strip()
    if not place:
        raise HTTPException(status_code=400, detail="place must not be empty")

    result = await session.execute(
        select(MeetingSchedule).where(MeetingSchedule.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    membership_result = await session.execute(
        select(RoomMember).where(
            RoomMember.room_id == meeting.room_id,
            RoomMember.user_id == int(current_user.sub),
        )
    )
    if membership_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Forbidden")

    meeting.location_name = body.name.strip() if body.name and body.name.strip() else place
    meeting.location_address = body.address.strip() if body.address and body.address.strip() else None
    meeting.kakao_place_id = body.place_id.strip() if body.place_id and body.place_id.strip() else None
    meeting.kakao_place_url = body.url.strip() if body.url and body.url.strip() else None
    meeting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(meeting)
    await session.commit()
    await session.refresh(meeting)

    calendar_registered = False
    headcount: int | None = None
    try:
        members_result = await session.execute(
            select(User)
            .join(RoomMember, RoomMember.user_id == User.id)
            .where(RoomMember.room_id == meeting.room_id)
        )
        members = members_result.scalars().all()
        headcount = len(members)

        if not meeting.location_address or not meeting.kakao_place_id or not meeting.kakao_place_url:
            documents = await search_keyword(place, size=1)
            if documents:
                first = documents[0]
                meeting.location_name = str(first.get("place_name") or meeting.location_name or place)
                meeting.location_address = str(
                    first.get("road_address_name") or first.get("address_name") or meeting.location_address or ""
                )
                meeting.kakao_place_id = str(first.get("id") or meeting.kakao_place_id or "")
                meeting.kakao_place_url = str(first.get("place_url") or meeting.kakao_place_url or "")
            else:
                address = await search_address(place)
                if not address:
                    raise RuntimeError("Kakao place lookup returned no results")
                meeting.location_address = address.get("address_name") or meeting.location_address

            meeting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            session.add(meeting)
            await session.commit()
            await session.refresh(meeting)

        if meeting.scheduled_at and meeting.location_name:
            room_row = await session.execute(
                select(Room).where(Room.id == meeting.room_id)
            )
            room = room_row.scalar_one_or_none()
            updated_event_ids = await sync_events_for_meeting_members(
                meeting, members, session,
                event_title=room.name if room else None,
            )
            if updated_event_ids != (meeting.google_event_ids or {}):
                meeting.google_event_ids = updated_event_ids
                session.add(meeting)
                await session.commit()
                await session.refresh(meeting)
            calendar_registered = bool(updated_event_ids)
    except Exception:
        logger.warning(
            "Place patch external sync failed after DB commit (meeting_id=%s)",
            meeting.id, exc_info=True,
        )

    try:
        if headcount is None:
            member_result = await session.execute(
                select(RoomMember).where(RoomMember.room_id == meeting.room_id)
            )
            headcount = len(member_result.scalars().all())
        await _publish_maedeup_place_update(
            meeting,
            calendar_registered=calendar_registered,
            headcount=headcount,
        )
    except Exception:
        logger.warning(
            "Redis publish failed for place patch meeting_id=%s",
            meeting.id,
            exc_info=True,
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

    # ACT 6 학습 — fire-and-forget personal_data extraction.
    # LangGraph maedeup_card_creation 노드가 안 도는 /place patch 경로에서도
    # 학습 ✨ 임팩트가 살도록 별도 호출. detach 모드 — 응답 latency 영향 X.
    _asyncio.create_task(_spawn_personal_data_extraction(meeting.room_id))

    return PlacePatchResponse(
        meeting_id=meeting.id,
        place=meeting.location_name or place,
        calendar_registered=calendar_registered,
    )


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
        return ConfirmMeetingResponse(
            id=meeting.id,
            **_calendar_response_fields(meeting, int(current_user.sub)),
        )

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

    return ConfirmMeetingResponse(
        id=meeting.id,
        **_calendar_response_fields(meeting, int(current_user.sub)),
    )


# ---------------------------------------------------------------------------
# PR-Z1: POST /{meeting_id}/recommendations/refresh
# Q5/Q7 hybrid 토글 — 그룹 다수결 ↔ 발화자 선호 재추천.
# Decisions: Q7=B (preference_source + preference_toggle_enabled),
#            Q13=B (발화자 or 방장만 권한),
#            Q14=C (Redis idempotency 5분 + 일일 100회),
#            Q15=A (narrator 실명 안내).
# ---------------------------------------------------------------------------


REFRESH_DAILY_LIMIT = 100
REFRESH_IDEMPOTENCY_TTL_SECONDS = 300  # 5분


class RefreshRequest(BaseModel):
    scope: Literal["vote_card", "place_recommendation", "both"]
    preference_source: Literal["group", "speaker"]
    requester_user_id: int = Field(
        ...,
        description="발화자(speaker) user id — viewer가 본인이거나 viewer가 방장일 때만 허용 (Q13=B).",
    )


class RefreshResponse(BaseModel):
    vote_card: Optional[dict[str, Any]] = None
    place_recommendation: Optional[dict[str, Any]] = None
    narrator: str
    cached: bool = False


def _today_kst_date_str() -> str:
    """Q14=C 일일 카운트 키에 박는 날짜. KST 기준 — 한국 사용자 시연 시점 일치."""
    from datetime import timedelta
    now_utc = datetime.now(timezone.utc)
    kst = (now_utc + timedelta(hours=9)).date()
    return kst.isoformat()


def _refresh_count_key(viewer_user_id: int) -> str:
    return f"refresh_count:{viewer_user_id}:{_today_kst_date_str()}"


def _refresh_idem_key(
    viewer_user_id: int, meeting_id: int, scope: str, preference_source: str
) -> str:
    return (
        f"refresh:{viewer_user_id}:{meeting_id}:{scope}:{preference_source}"
    )


@router.post("/{meeting_id}/recommendations/refresh", response_model=RefreshResponse)
async def refresh_recommendations(
    meeting_id: int,
    body: RefreshRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_finalization_redis),
) -> RefreshResponse:
    """Q5 hybrid refresh — 추천 페이로드를 group ↔ speaker 기준으로 재발행.

    1) 멤버십 검증, 2) 권한 검증 (Q13=B: 발화자 OR 방장),
    3) Q7-c 차단 검증, 4) Q14=C rate limit / idempotency,
    5) run_pipeline 재호출 with trigger_reason="preference_toggle",
    6) WS broadcast, 7) narrator(Q15=A), 8) Redis 캐시.
    """
    viewer_user_id = int(current_user.sub)

    # ── 1) Meeting + room 조회
    meeting_row = await session.execute(
        select(MeetingSchedule).where(MeetingSchedule.id == meeting_id)
    )
    meeting = meeting_row.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting_not_found")

    room_id = meeting.room_id

    # ── 2) 멤버십 검증 (viewer가 방 멤버)
    member_row = await session.execute(
        select(RoomMember).where(
            RoomMember.room_id == room_id,
            RoomMember.user_id == viewer_user_id,
        )
    )
    viewer_membership = member_row.scalar_one_or_none()
    if viewer_membership is None:
        raise HTTPException(status_code=403, detail="not_a_room_member")

    # ── 3) 권한 검증 (Q13=B): viewer == requester OR viewer가 방장
    is_requester = viewer_user_id == body.requester_user_id
    is_owner = (viewer_membership.role or "").lower() == "owner"
    if not (is_requester or is_owner):
        raise HTTPException(
            status_code=403,
            detail="permission_denied: requester or room owner only",
        )

    # ── 4) 발화자 본인 정보 lookup → state plumbing
    requester_ctx = await load_requester_context(session, body.requester_user_id)

    # ── 4b) Codex P2 (2026-05-15): group 선호 컨텍스트 lookup.
    # C3 lightweight 비교는 default_place_hint + preference_common_foods 둘 다
    # state에 있어야 발동. 이전 버전은 requester-only 필드만 채워 C3가 사실상
    # 죽어 있었음 → group=speaker 케이스에서 의미 없는 토글 허용 회귀.
    group_pref_ctx = await _load_group_preference_context(session, room_id)

    # ── 5) Q7-c 차단 검증 — toggle_enabled=False면 422
    probe_state: dict[str, Any] = {
        "requester_home_base": requester_ctx.get("requester_home_base"),
        "requester_preferences": requester_ctx.get("requester_preferences"),
        "preference_source": body.preference_source,
        "default_place_hint": group_pref_ctx.get("default_place_hint"),
        "preference_common_foods": group_pref_ctx.get("preference_common_foods"),
    }
    if not compute_preference_toggle_enabled(probe_state):  # type: ignore[arg-type]
        raise HTTPException(
            status_code=422,
            detail="toggle_disabled: 발화자 선호 정보 부족 또는 공유 동의 미설정",
        )

    # ── 6) Q14=C rate limit + idempotency
    daily_key = _refresh_count_key(viewer_user_id)
    idem_key = _refresh_idem_key(
        viewer_user_id, meeting_id, body.scope, body.preference_source
    )

    # Idempotency hit?
    try:
        cached_raw = await redis.get(idem_key)
    except Exception:
        cached_raw = None
        logger.warning(
            "Redis GET failed for refresh idempotency key=%s", idem_key, exc_info=True
        )
    if cached_raw:
        try:
            cached_payload = json.loads(cached_raw)
            return RefreshResponse(**cached_payload, cached=True)
        except Exception:
            logger.warning(
                "Cached refresh payload parse failed key=%s — recomputing",
                idem_key,
                exc_info=True,
            )

    # Daily limit (INCR + EXPIRE on first hit)
    try:
        count = await redis.incr(daily_key)
        if count == 1:
            # 26h TTL so a refresh just before midnight KST still expires next day.
            await redis.expire(daily_key, 26 * 3600)
        if count > REFRESH_DAILY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"daily_limit_exceeded: {REFRESH_DAILY_LIMIT}/day",
            )
    except HTTPException:
        raise
    except Exception:
        logger.warning(
            "Redis INCR failed for refresh daily key=%s — proceeding without limit",
            daily_key,
            exc_info=True,
        )

    # ── 7) run_pipeline 재호출
    slot_context: dict[str, Any] = {
        "trigger_reason": "preference_toggle",
        "preference_source": body.preference_source,
        "is_preference_refresh": True,
        "requester_user_id": requester_ctx["requester_user_id"],
        "requester_home_base": requester_ctx.get("requester_home_base"),
        "requester_preferences": requester_ctx.get("requester_preferences"),
        # graph._route_from_start 가 scope 매핑에 사용.
        # vote_card / both → slot_filling 진입, place_recommendation → entity_extraction.
        "partial_mode": "place_only" if body.scope == "place_recommendation" else None,
    }
    # 확정된 meeting의 시간을 reuse — entity 재추출 비용 절감.
    if meeting.scheduled_at:
        slot_context["confirmed_date"] = meeting.scheduled_at.date().isoformat()
        slot_context["confirmed_time"] = meeting.scheduled_at.strftime("%H:%M")

    context = await MessageReader.load_agent_context(
        session=session,
        room_id=room_id,
        viewer_user_id=viewer_user_id,
        limit=30,
    )

    result = await run_pipeline(
        room_id=str(room_id),
        context=context,
        db=session,
        slot_context=slot_context,
    )

    # ── 8) narrator (Q15=A: 발화자 실명)
    requester_user_row = await session.execute(
        select(User).where(User.id == body.requester_user_id)
    )
    requester_user = requester_user_row.scalar_one_or_none()
    requester_name = (requester_user.name if requester_user else None) or "발화자"
    if body.preference_source == "speaker":
        narrator = f"{requester_name}님 선호 기준으로 다시 추천했어요"
    else:
        narrator = "그룹 다수결 기준으로 다시 추천했어요"

    vote_payload = (
        result.get("vote_card_payload")
        if body.scope != "place_recommendation"
        else None
    )
    place_payload = (
        result.get("place_recommendation_payload")
        if body.scope != "vote_card"
        else None
    )

    # ── 9) WS broadcast (Q7-b: 방 전체 broadcast)
    channel = f"agent:{room_id}"
    try:
        if vote_payload:
            await redis.publish(channel, json.dumps(vote_payload, ensure_ascii=False))
        if place_payload:
            await redis.publish(channel, json.dumps(place_payload, ensure_ascii=False))
        await redis.publish(
            channel,
            json.dumps(
                {
                    "type": "preference_refresh_narrator",
                    "room_id": str(room_id),
                    "meeting_id": meeting_id,
                    "preference_source": body.preference_source,
                    "requester_user_id": body.requester_user_id,
                    "content": narrator,
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        logger.warning(
            "Redis publish failed for refresh meeting_id=%s", meeting_id, exc_info=True
        )

    response_payload = {
        "vote_card": vote_payload,
        "place_recommendation": place_payload,
        "narrator": narrator,
    }

    # ── 10) Redis idempotency 캐시 (TTL 5분)
    try:
        await redis.set(
            idem_key,
            json.dumps(response_payload, ensure_ascii=False),
            ex=REFRESH_IDEMPOTENCY_TTL_SECONDS,
        )
    except Exception:
        logger.warning(
            "Redis SET failed for refresh idempotency key=%s",
            idem_key,
            exc_info=True,
        )

    return RefreshResponse(cached=False, **response_payload)
