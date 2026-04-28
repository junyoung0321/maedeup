from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.room import MemberRole, Room, RoomMember
from app.models.user import User

router = APIRouter(prefix="/rooms", tags=["rooms"])


# ── 요청/응답 모델 ──────────────────────────────────────────


class CreateRoomRequest(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    member_emails: list[str] = []


class RoomResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    category: Optional[str]
    created_by: int
    created_at: datetime


# ── 엔드포인트 ─────────────────────────────────────────────


@router.post("/", response_model=RoomResponse, status_code=201)
async def create_room(
    body: CreateRoomRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """모임을 생성하고 초대 멤버를 room_members에 추가합니다."""
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
