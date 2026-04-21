from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import AuthUser, get_current_user, issue_jwt
from app.db.session import get_session
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


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


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    picture: Optional[str]
    home_base: Optional[str]
    food_preferences: Optional[list[str]]
    food_preference_note: Optional[str]
    calendar_consent: bool


class UserPreferencesUpdate(BaseModel):
    home_base: Optional[str] = Field(default=None, max_length=128)
    food_preferences: Optional[list[str]] = None
    food_preference_note: Optional[str] = Field(default=None, max_length=255)


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
    for field_name, value in updates.items():
        setattr(user, field_name, value)

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/friends", response_model=list[FriendInfo])
async def get_friends(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """현재 로그인한 유저의 수락된 친구 목록을 반환합니다."""
    if current_user.is_guest:
        return []
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
    if current_user.is_guest:
        raise HTTPException(status_code=403, detail="게스트는 유저 검색을 할 수 없습니다.")
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
    if current_user.is_guest:
        raise HTTPException(status_code=403, detail="게스트는 친구를 추가할 수 없습니다.")
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

    return FriendRequestResponse(id=friendship.id, status=friendship.status)
