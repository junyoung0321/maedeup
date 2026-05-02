from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

import asyncio
import json
import logging

from sqlalchemy import func as sa_func

import uuid

from fastapi import HTTPException

from app.core.security import AuthUser, get_current_user, issue_jwt
from app.db.session import get_session
from app.models.chat import ChatMessage, PaneType, Visibility
from app.models.meeting_preference import MeetingPreference
from app.models.room import MemberRole, Room, RoomMember
from app.models.user import User
from app.repositories.messages import MessageReader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rooms", tags=["rooms"])


# ── 요청/응답 모델 ──────────────────────────────────────────


class CreateRoomRequest(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    member_emails: list[str] = []


class GuestJoinRequest(BaseModel):
    display_name: str


class GuestJoinResponse(BaseModel):
    token: str
    user_id: int
    name: str


class RoomResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    category: Optional[str]
    created_by: int
    created_at: datetime


class PreferenceRequest(BaseModel):
    preferred_times: list[str] = []
    preferred_location: Optional[str] = None
    preferred_foods: list[str] = []
    disliked_foods: list[str] = []
    note: Optional[str] = None


class PreferenceResponse(BaseModel):
    user_id: int
    user_name: str
    preferred_times: list[str]
    preferred_location: Optional[str]
    preferred_foods: list[str]
    disliked_foods: list[str]
    note: Optional[str]


class PreferenceStatusResponse(BaseModel):
    total_members: int
    submitted_count: int
    all_submitted: bool
    preferences: list[PreferenceResponse]


# ── 엔드포인트 ─────────────────────────────────────────────


@router.post("/", response_model=RoomResponse, status_code=201)
async def create_room(
    body: CreateRoomRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """모임을 생성하고 초대 멤버를 room_members에 추가합니다."""
    if current_user.is_guest:
        raise HTTPException(status_code=403, detail="게스트는 방을 생성할 수 없습니다.")
    creator_id = int(current_user.sub)

    room = Room(
        name=body.name,
        description=body.description,
        category=body.category,
        created_by=creator_id,
    )
    session.add(room)
    await session.flush()  # room.id 확보

    # 생성자를 owner로 등록
    session.add(RoomMember(room_id=room.id, user_id=creator_id, role=MemberRole.owner))

    # 초대 멤버를 이메일로 조회 후 member로 등록
    if body.member_emails:
        result = await session.execute(
            select(User).where(User.email.in_(body.member_emails))
        )
        for user in result.scalars().all():
            if user.id != creator_id:
                session.add(RoomMember(room_id=room.id, user_id=user.id, role=MemberRole.member))

    await session.commit()
    await session.refresh(room)
    return RoomResponse(
        id=room.id,
        name=room.name,
        description=room.description,
        category=room.category,
        created_by=room.created_by,
        created_at=room.created_at,
    )


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """방 단건 조회. 멤버만 접근 가능 (created_by 포함 — 방장 판정에 사용)."""
    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    membership = await session.execute(
        select(RoomMember).where(
            RoomMember.room_id == room_id,
            RoomMember.user_id == int(current_user.sub),
        )
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Forbidden")
    return RoomResponse(
        id=room.id,
        name=room.name,
        description=room.description,
        category=room.category,
        created_by=room.created_by,
        created_at=room.created_at,
    )


@router.post("/{room_id}/guest-join", response_model=GuestJoinResponse)
async def guest_join_room(
    room_id: int,
    body: GuestJoinRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    로그인 없이 방에 게스트로 참여. 링크 기반 초대(카카오톡 공유 등)용.
    - 방 존재 확인
    - User 테이블에 is_guest=True로 신규 row 생성 (synthetic email)
    - RoomMember 연결
    - JWT 발급 (is_guest claim 포함)

    주의: 매 호출마다 새 게스트가 생김. 재접속 시에도 동일 세션 유지는 클라이언트가
    발급받은 토큰을 localStorage에 보관해 재사용함으로써 구현.
    """
    name = (body.display_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="이름을 입력해주세요.")
    if len(name) > 32:
        raise HTTPException(status_code=400, detail="이름은 32자 이하로 입력해주세요.")

    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 방입니다.")

    synthetic_email = f"guest-{uuid.uuid4().hex[:12]}@maedeup.local"
    guest = User(
        email=synthetic_email,
        name=name,
        is_guest=True,
        calendar_consent=False,
    )
    session.add(guest)
    await session.flush()  # guest.id 확보

    session.add(RoomMember(room_id=room.id, user_id=guest.id, role=MemberRole.member))
    await session.commit()
    await session.refresh(guest)

    token = issue_jwt(
        user_id=guest.id,
        email=guest.email,
        name=guest.name,
        picture=None,
        calendar_consent=False,
        is_guest=True,
    )
    return GuestJoinResponse(token=token, user_id=guest.id, name=guest.name)


@router.get("/", response_model=list[RoomResponse])
async def list_rooms(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """현재 로그인한 유저가 속한 모임 목록을 반환합니다."""
    result = await session.execute(
        select(Room)
        .join(RoomMember, RoomMember.room_id == Room.id)
        .where(RoomMember.user_id == int(current_user.sub))
        .order_by(Room.created_at.desc())
    )
    return [
        RoomResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            category=r.category,
            created_by=r.created_by,
            created_at=r.created_at,
        )
        for r in result.scalars().all()
    ]


# ── 선호 정보 엔드포인트 ──────────────────────────────────────


@router.post("/{room_id}/preferences", response_model=PreferenceResponse)
async def upsert_preference(
    room_id: int,
    body: PreferenceRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """모임 선호 정보를 저장(또는 업데이트)합니다."""
    user_id = int(current_user.sub)

    # 기존 preference 조회
    result = await session.execute(
        select(MeetingPreference).where(
            MeetingPreference.room_id == room_id,
            MeetingPreference.user_id == user_id,
        )
    )
    pref = result.scalar_one_or_none()

    if pref:
        pref.preferred_times = body.preferred_times
        pref.preferred_location = body.preferred_location
        pref.preferred_foods = body.preferred_foods
        pref.disliked_foods = body.disliked_foods
        pref.note = body.note
    else:
        pref = MeetingPreference(
            room_id=room_id,
            user_id=user_id,
            preferred_times=body.preferred_times,
            preferred_location=body.preferred_location,
            preferred_foods=body.preferred_foods,
            disliked_foods=body.disliked_foods,
            note=body.note,
        )
        session.add(pref)

    await session.commit()

    # 사용자 이름 조회
    user_result = await session.execute(select(User.name).where(User.id == user_id))
    user_name = user_result.scalar_one_or_none() or "Unknown"

    # 전원 입력 완료 체크 → 파이프라인 자동 트리거
    member_count_result = await session.execute(
        select(sa_func.count()).select_from(RoomMember).where(RoomMember.room_id == room_id)
    )
    total_members = member_count_result.scalar_one()
    pref_count_result = await session.execute(
        select(sa_func.count()).select_from(MeetingPreference).where(MeetingPreference.room_id == room_id)
    )
    pref_count = pref_count_result.scalar_one()

    if pref_count >= total_members:
        # 전원 완료 → 백그라운드에서 파이프라인 트리거
        asyncio.create_task(
            _trigger_auto_recommendation(room_id, session, user_name)
        )

    return PreferenceResponse(
        user_id=user_id,
        user_name=user_name,
        preferred_times=pref.preferred_times or [],
        preferred_location=pref.preferred_location,
        preferred_foods=pref.preferred_foods or [],
        disliked_foods=pref.disliked_foods or [],
        note=pref.note,
    )


@router.get("/{room_id}/preferences", response_model=PreferenceStatusResponse)
async def get_preferences(
    room_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """모임의 전체 선호 정보 현황을 반환합니다."""
    # 멤버 수
    member_count_result = await session.execute(
        select(sa_func.count()).select_from(RoomMember).where(RoomMember.room_id == room_id)
    )
    total_members = member_count_result.scalar_one()

    # 선호 정보 + 사용자 이름 조인
    pref_result = await session.execute(
        select(MeetingPreference, User.name)
        .join(User, User.id == MeetingPreference.user_id)
        .where(MeetingPreference.room_id == room_id)
    )
    rows = pref_result.all()

    preferences = [
        PreferenceResponse(
            user_id=pref.user_id,
            user_name=name,
            preferred_times=pref.preferred_times or [],
            preferred_location=pref.preferred_location,
            preferred_foods=pref.preferred_foods or [],
            disliked_foods=pref.disliked_foods or [],
            note=pref.note,
        )
        for pref, name in rows
    ]

    return PreferenceStatusResponse(
        total_members=total_members,
        submitted_count=len(preferences),
        all_submitted=len(preferences) >= total_members,
        preferences=preferences,
    )


async def _trigger_auto_recommendation(room_id: int, db_session: AsyncSession, user_name: str) -> None:
    """전원 선호 입력 완료 시 파이프라인을 자동 실행하고 결과를 Redis로 발행합니다."""
    try:
        from app.db.session import AsyncSessionLocal as async_session_factory
        from app.services.langgraph_pipeline import run_pipeline

        async with async_session_factory() as db:
            # 자동 트리거 메시지를 채팅 히스토리에 추가 (공용)
            auto_msg = ChatMessage(
                pane_type=PaneType.agent,
                role="user",
                content="모든 멤버의 선호 정보가 입력됐어! 최적의 모임 일정과 장소를 추천해줘",
                sender=user_name,
                room_id=room_id,
                user_id=None,
                visibility=Visibility.shared.value,
            )
            db.add(auto_msg)
            await db.commit()
            await db.refresh(auto_msg)

            # 최근 메시지 로드 (auto-trigger → shared-only 시야)
            context = await MessageReader.load_agent_context(
                session=db,
                room_id=room_id,
                viewer_user_id=None,
                limit=30,
            )

            # 파이프라인 실행
            result = await run_pipeline(
                room_id=str(room_id),
                context=context,
                db=db,
            )

            # 결과를 Redis로 발행 (WS로 프론트엔드에 전달)
            from app.core.config import settings
            import redis.asyncio as aioredis

            r = aioredis.from_url(settings.REDIS_URL)
            channel = f"agent:{room_id}"

            # 새 어시스턴트 메시지 발행
            new_msgs = result.get("new_assistant_messages") or []
            if not new_msgs:
                # 파이프라인이 new_assistant_messages를 반환하지 않으면 DB에서 최신 shared 메시지만 조회
                # (auto-recommendation은 shared 채널로 발행되므로 private 메시지 유출 방지)
                from sqlmodel import select as sm_select
                latest_result = await db.execute(
                    sm_select(ChatMessage)
                    .where(
                        ChatMessage.room_id == room_id,
                        ChatMessage.role == "assistant",
                        ChatMessage.visibility == Visibility.shared.value,
                    )
                    .order_by(ChatMessage.created_at.desc())
                    .limit(3)
                )
                for m in latest_result.scalars().all():
                    await r.publish(channel, json.dumps({
                        "id": m.id,
                        "pane_type": m.pane_type if isinstance(m.pane_type, str) else m.pane_type.value if m.pane_type else "agent",
                        "role": "assistant",
                        "content": m.content,
                        "sender": m.sender,
                        "created_at": m.created_at.isoformat() if m.created_at else "",
                    }))

            # 투표 카드 발행
            vote_payload = result.get("vote_card_payload")
            if vote_payload:
                logger.info("[AUTO-RECOMMEND] vote_card_payload: %s", json.dumps(vote_payload, ensure_ascii=False)[:500])
                await r.publish(channel, json.dumps(vote_payload))
            else:
                logger.info("[AUTO-RECOMMEND] No vote_card_payload in result")

            # 장소 추천 발행
            if result.get("place_recommendation_payload"):
                await r.publish(channel, json.dumps(result["place_recommendation_payload"]))

            await r.aclose()
            logger.info("[AUTO-RECOMMEND] Pipeline triggered for room %s, status=%s", room_id, result.get("status"))

    except Exception:
        logger.exception("[AUTO-RECOMMEND] Failed to trigger pipeline for room %s", room_id)
