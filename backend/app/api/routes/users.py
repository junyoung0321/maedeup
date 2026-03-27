from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.auth import _issue_jwt
from app.core.security import AuthUser, get_current_user
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
    user.calendar_consent = body.calendar_consent
    session.add(user)
    await session.commit()
    await session.refresh(user)

    new_token = _issue_jwt(user)
    return ConsentResponse(token=new_token, calendar_consent=user.calendar_consent)


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
