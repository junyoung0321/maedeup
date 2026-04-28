import json
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import AuthUser, get_current_user, issue_jwt
from app.db.session import get_session
from app.models.ai_memory import AIMemory
from app.models.friendship import Friendship, FriendshipStatus
from app.models.room import Room
from app.models.user import User
from app.services.notify import notify

router = APIRouter(prefix="/users", tags=["users"])

# AI가 채울 수 있고 사용자도 직접 수정할 수 있는 personal data 카테고리.
# PATCH /me/preferences가 이 중 한 카테고리에 대해 update를 받으면
# is_ai_filled[category] = False로 마크 (사용자 수동 입력 = ✨ 안 보임).
PERSONAL_DATA_CATEGORIES: frozenset[str] = frozenset(
    {
        "food_restrictions",
        "food_preferences",
        "liked_areas",
        "disliked_areas",
        "time_preference",
        "transport_mode",
    }
)


class ConsentUpdate(BaseModel):
    calendar_consent: bool


class ConsentResponse(BaseModel):
    token: str
    calendar_consent: bool


class FriendInfo(BaseModel):
    id: int
    name: str
    email: str
    picture: Optional[str]


class FriendRequest(BaseModel):
    addressee_id: int


class FriendRequestResponse(BaseModel):
    id: int
    status: str


class FriendRequestInfo(BaseModel):
    """받은/보낸 친구 요청 정보. 상대방의 프로필이 `user` 필드에 담긴다."""

    id: int
    status: str
    created_at: datetime
    direction: Literal["incoming", "outgoing"]
    user: FriendInfo


class FriendRequestAction(BaseModel):
    action: Literal["accept", "reject"]


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    picture: Optional[str]
    home_base: Optional[str]
    food_preferences: Optional[list[str]]
    food_preference_note: Optional[str]
    # Personal data extension — 홈 PersonalData UI가 fetch.
    food_restrictions: Optional[list[str]] = None
    liked_areas: Optional[list[str]] = None
    disliked_areas: Optional[list[str]] = None
    time_preference: Optional[str] = None
    transport_mode: Optional[str] = None
    is_ai_filled: dict[str, bool] = Field(default_factory=dict)
    calendar_consent: bool
    # QuickPreferences 토글 상태 — opt-out 모델, 기본 True.
    share_food_data: bool = True
    share_location_data: bool = True
    share_schedule_data: bool = True


class UserPreferencesUpdate(BaseModel):
    home_base: Optional[str] = Field(default=None, max_length=128)
    food_preferences: Optional[list[str]] = None
    food_preference_note: Optional[str] = Field(default=None, max_length=255)
    # Personal data extension. 사용자가 직접 수정한 필드는 is_ai_filled[cat]=False로 마크.
    food_restrictions: Optional[list[str]] = None
    liked_areas: Optional[list[str]] = None
    disliked_areas: Optional[list[str]] = None
    time_preference: Optional[str] = Field(default=None, max_length=255)
    transport_mode: Optional[str] = Field(default=None, max_length=32)
    # QuickPreferences 토글 (개인 데이터와 별도 — share consent만 변경, ✨에 영향 없음).
    share_food_data: Optional[bool] = None
    share_location_data: Optional[bool] = None
    share_schedule_data: Optional[bool] = None


class PersonalDataSourceResponse(BaseModel):
    """✨ 클릭 시 받는 receipts 데이터."""

    memory_type: str
    content: dict[str, Any]
    source_room_id: Optional[int]
    source_room_name: Optional[str]
    source_message_id: Optional[int]
    created_at: datetime


@router.patch("/me/consent", response_model=ConsentResponse)
async def update_consent(
    body: ConsentUpdate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    캘린더 수집 동의 여부를 업데이트하고 갱신된 JWT를 반환합니다.
    """
    user = await session.get(User, int(current_user.sub))
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    user.calendar_consent = body.calendar_consent
    session.add(user)
    await session.commit()
    await session.refresh(user)

    new_token = issue_jwt(
        user_id=user.id,
        email=user.email,
        name=user.name,
        picture=user.picture,
        calendar_consent=user.calendar_consent,
    )
    return ConsentResponse(token=new_token, calendar_consent=user.calendar_consent)


@router.get("/me", response_model=UserProfileResponse)
async def get_me(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, int(current_user.sub))
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return user


@router.patch("/me/preferences", response_model=UserProfileResponse)
async def update_preferences(
    body: UserPreferencesUpdate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, int(current_user.sub))
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)

    # personal data 카테고리에 해당하는 필드를 사용자가 수동 수정하면
    # is_ai_filled[category] = False로 마크 (✨ 사라짐).
    is_ai_filled = dict(user.is_ai_filled or {})
    for field_name, value in updates.items():
        setattr(user, field_name, value)
        if field_name in PERSONAL_DATA_CATEGORIES:
            is_ai_filled[field_name] = False
    user.is_ai_filled = is_ai_filled

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.get(
    "/me/personal-data/source/{category}",
    response_model=Optional[PersonalDataSourceResponse],
)
async def get_personal_data_source(
    category: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    홈 PersonalData UI에서 ✨ 아이콘 클릭 시 호출.
    해당 카테고리의 가장 최신 active AIMemory row를 반환.

    `superseded_by_manual` 상태 row는 제외 — 그 row의 값은 User 필드에 반영되지
    않았으므로 receipts에 노출하면 사용자 혼동 (가짜 출처처럼 보임).

    매칭되는 active row가 없으면 None 반환 (예: AI가 추출한 적 없는 카테고리).
    """
    if category not in PERSONAL_DATA_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown personal data category: {category}",
        )

    user_id = int(current_user.sub)

    # 최신 순으로 최대 20개 fetch — 그 중 status='active'인 첫 row를 반환.
    # active 비율이 압도적으로 높으므로 보통 첫 row에서 끝남.
    result = await session.execute(
        select(AIMemory)
        .where(AIMemory.user_id == user_id)
        .where(AIMemory.memory_type == category)
        .order_by(AIMemory.created_at.desc())
        .limit(20)
    )
    memories = result.scalars().all()

    for memory in memories:
        try:
            content_dict = json.loads(memory.content) if memory.content else {}
        except (json.JSONDecodeError, TypeError):
            continue
        if content_dict.get("status", "active") != "active":
            continue

        # source room name lookup (tooltip 표시용)
        room_name: Optional[str] = None
        if memory.source_room_id is not None:
            room = await session.get(Room, memory.source_room_id)
            if room is not None:
                room_name = room.name

        return PersonalDataSourceResponse(
            memory_type=memory.memory_type,
            content=content_dict,
            source_room_id=memory.source_room_id,
            source_room_name=room_name,
            source_message_id=memory.source_message_id,
            created_at=memory.created_at,
        )

    return None


@router.get("/friends", response_model=list[FriendInfo])
async def get_friends(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """현재 로그인한 유저의 수락된 친구 목록을 반환합니다."""
    user_id = int(current_user.sub)

    result = await session.execute(
        select(Friendship).where(
            or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            ),
            Friendship.status == FriendshipStatus.accepted,
        )
    )
    friendships = result.scalars().all()

    friend_ids = [
        f.addressee_id if f.requester_id == user_id else f.requester_id
        for f in friendships
    ]
    if not friend_ids:
        return []

    result = await session.execute(select(User).where(User.id.in_(friend_ids)))
    return [
        FriendInfo(id=u.id, name=u.name, email=u.email, picture=u.picture)
        for u in result.scalars().all()
    ]


@router.get("/search", response_model=list[FriendInfo])
async def search_users(
    q: str = Query(..., min_length=1),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """이름 또는 이메일로 유저를 검색합니다. 본인은 제외됩니다."""
    user_id = int(current_user.sub)
    pattern = f"%{q}%"
    result = await session.execute(
        select(User).where(
            or_(User.name.ilike(pattern), User.email.ilike(pattern)),
            User.id != user_id,
        ).limit(20)
    )
    return [
        FriendInfo(id=u.id, name=u.name, email=u.email, picture=u.picture)
        for u in result.scalars().all()
    ]


@router.post("/friends", response_model=FriendRequestResponse, status_code=201)
async def send_friend_request(
    body: FriendRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """친구 요청을 보냅니다. 이미 요청이 존재하면 409를 반환합니다."""
    requester_id = int(current_user.sub)

    if requester_id == body.addressee_id:
        raise HTTPException(status_code=400, detail="자기 자신에게 친구 요청을 보낼 수 없습니다.")

    addressee = await session.get(User, body.addressee_id)
    if not addressee:
        raise HTTPException(status_code=404, detail="존재하지 않는 유저입니다.")

    existing = await session.execute(
        select(Friendship).where(
            or_(
                (Friendship.requester_id == requester_id) & (Friendship.addressee_id == body.addressee_id),
                (Friendship.requester_id == body.addressee_id) & (Friendship.addressee_id == requester_id),
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 친구 요청이 존재합니다.")

    friendship = Friendship(requester_id=requester_id, addressee_id=body.addressee_id)
    session.add(friendship)
    await session.commit()
    await session.refresh(friendship)

    # 친구 요청 도착 알림 (수신자에게)
    requester = await session.get(User, requester_id)
    if requester is not None:
        await notify(
            session,
            user_id=body.addressee_id,
            type="FRIEND_REQUEST_RECEIVED",
            title=f"{requester.name}님이 친구 요청을 보냈습니다",
            payload={
                "from_user_id": requester_id,
                "from_user_name": requester.name,
                "friendship_id": friendship.id,
            },
        )

    return FriendRequestResponse(id=friendship.id, status=friendship.status)


@router.get("/friends/requests", response_model=list[FriendRequestInfo])
async def list_friend_requests(
    direction: Literal["incoming", "outgoing"] = Query("incoming"),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """대기 중(pending) 친구 요청 목록.

    - `direction=incoming` 내가 받은 요청 (수락/거절 대상)
    - `direction=outgoing` 내가 보낸 요청
    """
    user_id = int(current_user.sub)

    if direction == "incoming":
        stmt = select(Friendship).where(
            Friendship.addressee_id == user_id,
            Friendship.status == FriendshipStatus.pending,
        )
    else:
        stmt = select(Friendship).where(
            Friendship.requester_id == user_id,
            Friendship.status == FriendshipStatus.pending,
        )

    result = await session.execute(stmt)
    friendships = result.scalars().all()
    if not friendships:
        return []

    other_ids = [
        f.requester_id if direction == "incoming" else f.addressee_id
        for f in friendships
    ]
    user_result = await session.execute(select(User).where(User.id.in_(other_ids)))
    users_by_id = {u.id: u for u in user_result.scalars().all()}

    out: list[FriendRequestInfo] = []
    for f in friendships:
        other_id = f.requester_id if direction == "incoming" else f.addressee_id
        u = users_by_id.get(other_id)
        if u is None:
            continue
        out.append(
            FriendRequestInfo(
                id=f.id,
                status=f.status,
                created_at=f.created_at,
                direction=direction,
                user=FriendInfo(id=u.id, name=u.name, email=u.email, picture=u.picture),
            )
        )
    return out


@router.patch("/friends/requests/{request_id}", response_model=FriendRequestResponse)
async def respond_to_friend_request(
    request_id: int,
    body: FriendRequestAction,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """받은 친구 요청을 수락하거나 거절합니다. 요청의 addressee만 호출 가능."""
    user_id = int(current_user.sub)
    friendship = await session.get(Friendship, request_id)
    if friendship is None:
        raise HTTPException(status_code=404, detail="친구 요청을 찾을 수 없습니다.")
    if friendship.addressee_id != user_id:
        raise HTTPException(status_code=403, detail="이 요청을 처리할 권한이 없습니다.")
    if friendship.status != FriendshipStatus.pending:
        raise HTTPException(status_code=409, detail="이미 처리된 요청입니다.")

    if body.action == "accept":
        friendship.status = FriendshipStatus.accepted
        friendship.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(friendship)
        await session.commit()
        await session.refresh(friendship)
        return FriendRequestResponse(id=friendship.id, status=friendship.status)

    # reject → row 삭제 (재요청 가능하도록)
    await session.delete(friendship)
    await session.commit()
    return FriendRequestResponse(id=request_id, status="rejected")


@router.delete("/friends/{friend_id}", status_code=204)
async def unfriend(
    friend_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """친구 관계(accepted)를 해제합니다. requester/addressee 어느 쪽이든 호출 가능."""
    user_id = int(current_user.sub)
    result = await session.execute(
        select(Friendship).where(
            or_(
                (Friendship.requester_id == user_id) & (Friendship.addressee_id == friend_id),
                (Friendship.requester_id == friend_id) & (Friendship.addressee_id == user_id),
            ),
            Friendship.status == FriendshipStatus.accepted,
        )
    )
    friendship = result.scalar_one_or_none()
    if friendship is None:
        raise HTTPException(status_code=404, detail="친구 관계가 존재하지 않습니다.")

    await session.delete(friendship)
    await session.commit()
    return None
