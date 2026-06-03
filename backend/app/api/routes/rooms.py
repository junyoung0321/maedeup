from datetime import datetime, timezone
from typing import Literal, Optional

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
from sqlalchemy import delete as sa_delete

from app.api.routes.finalization import (
    _publish_finalization_event,
    get_redis as get_finalization_redis,
)
from app.api.ws.social import publish_schedule_auto_trigger
from app.services import scheduling_round as sr
from app.models.chat import ChatMessage, PaneType, Visibility
from app.models.meeting import MeetingParticipant, MeetingSchedule, MeetingStatus
from app.models.meeting_preference import MeetingPreference
from app.models.room import MemberRole, Room, RoomMember
from app.models.user import User
from app.repositories.messages import MessageReader
from app.services.google_calendar import (
    GoogleCalendarAuthError,
    GoogleCalendarError,
    delete_calendar_event,
    delete_events_for_meeting_members,
)

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

    # 중복 join 방지: 같은 방에 같은 display_name 게스트가 이미 있으면
    # 새 user 만들지 않고 기존 user에 대한 새 JWT만 발급해 반환.
    # 이렇게 해야 시연 중 토큰 분실/재가입 사고로 RoomMember가 부풀어
    # _maybe_emit_proposal의 `len(availability) >= member_count` 영구 실패
    # → ACT 3 합의 차단되는 사고를 막을 수 있다.
    existing_q = await session.execute(
        select(User)
        .join(RoomMember, RoomMember.user_id == User.id)
        .where(RoomMember.room_id == room.id)
        .where(User.is_guest.is_(True))
        .where(User.name == name)
    )
    existing = existing_q.scalars().first()
    if existing is not None:
        token = issue_jwt(
            user_id=existing.id,
            email=existing.email,
            name=existing.name,
            picture=None,
            calendar_consent=False,
            is_guest=True,
        )
        logger.info(
            "guest_join_room: reusing existing guest user_id=%s name=%r in room=%s",
            existing.id, existing.name, room.id,
        )
        return GuestJoinResponse(
            user_id=existing.id,
            name=existing.name,
            token=token,
        )

    # free-use audit round3 #10/#57: 방당 게스트 수 상한.
    # 인증 없는 guest-join으로 (a) 무한 게스트 생성, (b) 다른 이름 반복 join에 의한
    # member_count 부풀림(→ _maybe_emit_proposal explicit_count<member_count 영구 참
    # → 합의 영구 차단)을 차단한다. 같은 이름 재가입은 위 분기에서 기존 user를 재사용하므로
    # 상한과 무관. 데모 게스트 3명 << 20 → happy path 불변(약 6.6x 헤드룸).
    _GUEST_CAP = 20
    guest_count_q = await session.execute(
        select(sa_func.count())
        .select_from(RoomMember)
        .join(User, RoomMember.user_id == User.id)
        .where(RoomMember.room_id == room.id)
        .where(User.is_guest.is_(True))
    )
    if (guest_count_q.scalar_one() or 0) >= _GUEST_CAP:
        logger.warning(
            "guest_join_room: room=%s guest cap reached (>=%s) — rejecting new guest %r",
            room.id, _GUEST_CAP, name,
        )
        raise HTTPException(
            status_code=429,
            detail="이 방의 게스트 수가 한도에 도달했어요. 잠시 후 다시 시도해주세요.",
        )

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

    # 멤버 변동 → free-slots 캐시(TTL 30s) 무효화. 안 하면 캘린더 X/N 분모가
    # 캐시된 옛 멤버수로 최대 30초 남아 2/2 → (나중에) 4/4로 늦게 갱신됨.
    try:
        from app.api.routes.calendar import invalidate_free_slots_cache
        await invalidate_free_slots_cache(room.id)
    except Exception:
        logger.warning("free-slots cache invalidate failed (guest-join) room=%s", room.id, exc_info=True)

    # G-1: 다른 멤버에게 새 join 알림 → frontend가 받아서 캘린더 X/N 자동 갱신.
    # _publish_social_message wrapper 사용 — Redis 실패 시 manager.broadcast fallback.
    # 발행 실패는 join 자체를 실패시키지 않음 (silent).
    try:
        member_count_result = await session.execute(
            select(sa_func.count()).select_from(RoomMember).where(RoomMember.room_id == room.id)
        )
        member_count = int(member_count_result.scalar() or 0)
        from app.core.config import settings as _settings
        from app.api.ws.social import _publish_social_message
        import redis.asyncio as _aioredis
        social_channel = f"social:{room.id}"
        payload = json.dumps(
            {
                "type": "member_joined",
                "room_id": room.id,
                "user_id": guest.id,
                "user_name": guest.name,
                "member_count": member_count,
            },
            ensure_ascii=False,
        )
        try:
            r = _aioredis.from_url(
                _settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
        except Exception:
            r = None
        try:
            await _publish_social_message(r, social_channel, payload)
        finally:
            if r is not None:
                try:
                    await r.aclose()
                except Exception:
                    pass
    except Exception:
        logger.warning("member_joined publish failed for room=%s", room.id, exc_info=True)

    # T6 cache invalidate: 신규 멤버 join 시 free_slots 캐시 삭제 (stale 방지)
    try:
        import redis.asyncio as _aioredis_inv
        from app.core.config import settings as _settings_inv
        _r_inv = _aioredis_inv.from_url(
            _settings_inv.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        try:
            _pattern = f"maedeup:free_slots:{room.id}:*"
            _cursor = 0
            while True:
                _cursor, _keys = await _r_inv.scan(_cursor, match=_pattern, count=100)
                if _keys:
                    await _r_inv.delete(*_keys)
                if _cursor == 0:
                    break
            logger.info("[T6_INVALIDATE] guest-join room=%s pattern=%s", room.id, _pattern)
        finally:
            await _r_inv.aclose()
    except Exception:
        logger.warning("T6 cache invalidate failed for room=%s (non-fatal)", room.id, exc_info=True)

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
    _ = (total_members, pref_count)  # 향후 분석용 보존, 현재는 사용 안 함

    # 자동 추천 로직 제거 (시연/UX 흐름 부자연스러움 — 사용자가 채팅 시작도 전에 카드 발행).
    # AI 개입은 (1) 채팅방 stalemate/conclusion 자동 트리거, (2) AI 패널 직접 입력으로만 발화.

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


class LeaveRoomResponse(BaseModel):
    room_id: int
    cancelled_meeting_ids: list[int] = []
    triggered_meeting_cancellation: bool = False


class ChosenTime(BaseModel):
    """A3-3: 호스트가 [조율] 모달에서 선택한 정밀 시간 범위."""
    date: str  # "YYYY-MM-DD"
    start_idx: int  # TimeBar slot index (30분 단위, 0~47)
    end_idx: int    # inclusive


class TimebarOpenRequest(BaseModel):
    meeting_id: int
    date: str  # YYYY-MM-DD — 호스트가 TimeBar를 열 날짜


@router.post("/{room_id}/timebar-open")
async def timebar_open(
    room_id: int,
    body: TimebarOpenRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """호스트 '시간대 변경' 클릭 → 전원에게 TimeBar 진입 신호 브로드캐스트.

    (free-use audit 2026-06-03) 기존엔 프론트 requestTimeChange가 호스트 로컬
    state만 바꿔 호스트 화면에만 TimeBar가 떴고, 다른 멤버는 알림도 TimeBar도
    못 받아 새 시간 투표에 참여 못 했음. social 채널로 timebar_open 이벤트를
    발행해 전 멤버 InfoPane이 해당 meeting에 대해 dateConfirmed 단계로 전환 →
    모두 TimeBar로 원하는 시간을 투표 가능.
    """
    room_row = await session.execute(select(Room).where(Room.id == room_id))
    room = room_row.scalar_one_or_none()
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.created_by != int(current_user.sub):
        raise HTTPException(status_code=403, detail="방장만 시간대 변경을 시작할 수 있습니다.")

    from app.core.config import settings as _settings
    from app.api.ws.social import _publish_social_message
    import redis.asyncio as _aioredis

    social_channel = f"social:{room_id}"
    payload = json.dumps(
        {
            "type": "timebar_open",
            "room_id": room_id,
            "meeting_id": body.meeting_id,
            "date": body.date,
        },
        ensure_ascii=False,
    )
    try:
        r = _aioredis.from_url(
            _settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception:
        r = None
    try:
        await _publish_social_message(r, social_channel, payload)
    finally:
        if r is not None:
            try:
                await r.aclose()
            except Exception:
                pass
    return {"published": True}


class ScheduleConfirmRequest(BaseModel):
    snapshot_hash: str
    # A3-3: "auto" = AI 추천 그대로, "manual" = 호스트 정밀 선택. 기본값으로 backward-compat.
    mode: Literal["auto", "manual"] = "auto"
    chosen_time: Optional[ChosenTime] = None  # mode="manual"일 때 필수


class ScheduleConfirmResponse(BaseModel):
    triggered: bool
    snapshot_hash: str


@router.post("/{room_id}/schedule-confirm", response_model=ScheduleConfirmResponse)
async def schedule_confirm(
    room_id: int,
    body: ScheduleConfirmRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_finalization_redis),
):
    """A3-2: 호스트가 TimeBar 합의 후 "확정하기" 클릭 시 호출.

    schedule_consensus_ready 노티 받은 호스트가 명시적으로 확정 의사를 표하면
    그제서야 ai_auto_trigger publish → 파이프라인 발동.

    - 호스트 권한 필수 (room.created_by)
    - snapshot_hash 검증 (현재 availability와 일치해야)
    - idempotent (같은 snapshot 두 번 호출 시 첫 한 번만 발동)
    - A3-3: mode="manual"이면 chosen_time 필수. 0명 슬롯은 거부 (적어도 1명 가능해야).
    """
    room_row = await session.execute(select(Room).where(Room.id == room_id))
    room = room_row.scalar_one_or_none()
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.created_by != int(current_user.sub):
        raise HTTPException(status_code=403, detail="방장만 확정할 수 있습니다.")

    # 현재 availability snapshot이 요청 hash와 일치하는지 검증 (stale 요청 방어)
    availability = await sr.load_room_availability(redis, room_id=room_id)
    if not availability:
        raise HTTPException(status_code=409, detail="schedule_not_ready")
    current_hash = sr.compute_snapshot_hash(availability)
    if current_hash != body.snapshot_hash:
        raise HTTPException(status_code=409, detail="snapshot_outdated")

    # A3-3: manual mode 검증 — chosen_time 범위에 적어도 1명 가능 슬롯 있어야.
    manual_chosen_time: Optional[dict] = None
    if body.mode == "manual":
        if body.chosen_time is None:
            raise HTTPException(status_code=400, detail="chosen_time_required_for_manual")
        ct = body.chosen_time
        if (
            ct.start_idx < 0
            or ct.end_idx >= sr.TIME_SLOT_MAX
            or ct.start_idx > ct.end_idx
        ):
            raise HTTPException(status_code=400, detail="chosen_time_out_of_range")
        # availability {user_id: [{date, start, end}]}에서 ct.date 기준 슬롯별 가능 인원
        # 합산 후, chosen_time 범위 안 모든 슬롯이 ≥ 1명인지 검증.
        # discontinuous segments [14-16] + [19-22] 사이 0명 영역 [16-19]를 통째로
        # 선택하는 케이스 차단 (frontend strict mode 우회 시도 방어).
        slot_count: dict[int, int] = {}
        for entries in availability.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("date") != ct.date:
                    continue
                try:
                    e_start = int(entry.get("start"))
                    e_end = int(entry.get("end"))
                except (TypeError, ValueError):
                    continue
                # entry는 INCLUSIVE end_idx (scheduling_round.py:562)
                for idx in range(e_start, e_end + 1):
                    slot_count[idx] = slot_count.get(idx, 0) + 1
        zero_slots = [
            idx for idx in range(ct.start_idx, ct.end_idx + 1)
            if slot_count.get(idx, 0) == 0
        ]
        if zero_slots:
            raise HTTPException(
                status_code=400,
                detail=f"zero_member_slots:{','.join(map(str, zero_slots))}",
            )
        manual_chosen_time = {
            "date": ct.date,
            "start_idx": ct.start_idx,
            "end_idx": ct.end_idx,
        }

    triggered = await publish_schedule_auto_trigger(
        redis,
        room_pk=room_id,
        snapshot_hash=body.snapshot_hash,
        manual_chosen_time=manual_chosen_time,
    )
    return ScheduleConfirmResponse(triggered=triggered, snapshot_hash=body.snapshot_hash)


@router.post("/{room_id}/leave", response_model=LeaveRoomResponse)
async def leave_room(
    room_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_finalization_redis),
):
    """현재 사용자가 모임 방에서 나갑니다.

    - 모든 사용자: 본인 RoomMember + MeetingPreference + MeetingParticipant 삭제,
      이 방의 confirmed 모임에서 본인 캘린더 이벤트 best-effort 삭제.
    - 호스트(room.created_by) + 다른 멤버 존재 시: 활성 모임을 cancel하지 않고, 남은
      멤버 중 가장 먼저 가입한 멤버에게 소유권 이양(created_by 갱신 + role=owner 승격)
      → host_transferred WS 브로드캐스트 (free-use audit round4 #11+#20).
    - Idempotent: 이미 방에 없으면 빈 응답으로 200.
    """
    user_id = int(current_user.sub)

    room_result = await session.execute(select(Room).where(Room.id == room_id))
    room = room_result.scalar_one_or_none()
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    membership_result = await session.execute(
        select(RoomMember).where(
            RoomMember.room_id == room_id,
            RoomMember.user_id == user_id,
        )
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        return LeaveRoomResponse(room_id=room_id)

    is_host = room.created_by == user_id

    other_members_count_result = await session.execute(
        select(sa_func.count(RoomMember.id)).where(
            RoomMember.room_id == room_id,
            RoomMember.user_id != user_id,
        )
    )
    other_members_count = other_members_count_result.scalar() or 0

    cancelled_meeting_ids: list[int] = []
    triggered_cancellation = False

    if is_host and other_members_count > 0:
        # free-use audit round4 #11+#20: 호스트가 다른 멤버를 두고 나감.
        # 기존엔 활성 모임을 전부 cancel했으나 → 남은 멤버 입장에서 모임이 고아화되고
        # created_by가 떠난 user에 고정돼 schedule-confirm/place/cancel 권한이 영구 공백(#20).
        # 대신 남은 멤버 중 가장 먼저 가입한 멤버에게 소유권을 자동 이양한다:
        #   - Room.created_by = 새 호스트 user_id
        #   - 새 호스트 RoomMember.role = owner 승격
        # 활성 모임은 유지(유효 호스트가 생겼으므로 cancel 불필요).
        # 데모: 호스트는 leave하지 않으므로 이 분기 자체가 happy path에서 미실행.
        new_host_result = await session.execute(
            select(RoomMember)
            .where(
                RoomMember.room_id == room_id,
                RoomMember.user_id != user_id,
            )
            .order_by(RoomMember.joined_at.asc(), RoomMember.id.asc())
            .limit(1)
        )
        new_host_member = new_host_result.scalar_one_or_none()
        if new_host_member is not None:
            room.created_by = new_host_member.user_id
            new_host_member.role = MemberRole.owner
            session.add(room)
            session.add(new_host_member)
            await session.commit()
            triggered_cancellation = True  # 이양 발생 신호 (모임 cancel은 안 함)
            logger.info(
                "leave_room: host=%s left room=%s → ownership transferred to user=%s (oldest member)",
                user_id, room_id, new_host_member.user_id,
            )
            try:
                await _publish_finalization_event(
                    redis,
                    room_id,
                    {
                        "type": "host_transferred",
                        "room_id": room_id,
                        "new_host_user_id": new_host_member.user_id,
                        "previous_host_user_id": user_id,
                    },
                )
            except Exception:
                logger.warning(
                    "Failed to broadcast host_transferred (room_id=%s, new_host=%s)",
                    room_id, new_host_member.user_id, exc_info=True,
                )
    else:
        # 일반 멤버 OR 호스트 단독: 본인 캘린더 이벤트만 정리.
        confirmed_result = await session.execute(
            select(MeetingSchedule).where(
                MeetingSchedule.room_id == room_id,
                MeetingSchedule.status == MeetingStatus.confirmed,
            )
        )
        confirmed_meetings = confirmed_result.scalars().all()

        user_obj_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user_obj = user_obj_result.scalar_one_or_none()

        for meeting in confirmed_meetings:
            event_ids = dict(meeting.google_event_ids or {})
            event_id = event_ids.get(str(user_id))
            if not event_id:
                continue
            if user_obj is not None and not user_obj.is_guest:
                try:
                    await delete_calendar_event(user_obj, session, event_id)
                except (GoogleCalendarAuthError, GoogleCalendarError, Exception):
                    logger.info(
                        "Calendar self-delete skipped for user_id=%s meeting_id=%s on leave",
                        user_id, meeting.id, exc_info=True,
                    )
            del event_ids[str(user_id)]
            meeting.google_event_ids = event_ids
            session.add(meeting)
        await session.commit()

    # 본인 종속 데이터 정리 (preference, participant, room_member)
    await session.execute(
        sa_delete(MeetingParticipant).where(
            MeetingParticipant.user_id == user_id,
            MeetingParticipant.meeting_id.in_(
                select(MeetingSchedule.id).where(MeetingSchedule.room_id == room_id)
            ),
        )
    )
    await session.execute(
        sa_delete(MeetingPreference).where(
            MeetingPreference.room_id == room_id,
            MeetingPreference.user_id == user_id,
        )
    )
    await session.execute(
        sa_delete(RoomMember).where(
            RoomMember.room_id == room_id,
            RoomMember.user_id == user_id,
        )
    )
    await session.commit()

    # 다른 멤버에게 본인 퇴장 알림.
    try:
        await _publish_finalization_event(
            redis,
            room_id,
            {
                "type": "member_left",
                "room_id": room_id,
                "user_id": user_id,
            },
        )
    except Exception:
        logger.warning(
            "Failed to broadcast member_left (room_id=%s, user_id=%s)",
            room_id, user_id, exc_info=True,
        )

    # 멤버 탈퇴 → free-slots 캐시 무효화 (분모 즉시 감소).
    try:
        from app.api.routes.calendar import invalidate_free_slots_cache
        await invalidate_free_slots_cache(room_id)
    except Exception:
        logger.warning("free-slots cache invalidate failed (leave) room=%s", room_id, exc_info=True)

    return LeaveRoomResponse(
        room_id=room_id,
        cancelled_meeting_ids=cancelled_meeting_ids,
        triggered_meeting_cancellation=triggered_cancellation,
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
