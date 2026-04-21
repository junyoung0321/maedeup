from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    body: Optional[str]
    room_id: Optional[int]
    payload: dict[str, Any]
    read_at: Optional[datetime]
    created_at: datetime


class UnreadCountResponse(BaseModel):
    unread: int


class OkResponse(BaseModel):
    ok: bool = True


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """현재 유저의 알림을 최신순으로 반환한다."""
    user_id = int(current_user.sub)
    result = await session.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
    )
    return [
        NotificationResponse(
            id=n.id,
            type=n.type,
            title=n.title,
            body=n.body,
            room_id=n.room_id,
            payload=n.payload or {},
            read_at=n.read_at,
            created_at=n.created_at,
        )
        for n in result.scalars().all()
    ]


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """벨 배지용 미읽음 카운트. 초기 마운트 1회만 호출하고 이후는 WS push로 갱신."""
    user_id = int(current_user.sub)
    result = await session.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
    )
    count = result.scalar_one() or 0
    return UnreadCountResponse(unread=count)


@router.post("/{notification_id}/read", response_model=OkResponse)
async def mark_read(
    notification_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """개별 알림을 읽음 처리."""
    user_id = int(current_user.sub)
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(notification)
        await session.commit()
    return OkResponse()


@router.post("/read-all", response_model=OkResponse)
async def mark_all_read(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """현재 유저의 모든 미읽음 알림을 읽음으로 일괄 변경."""
    user_id = int(current_user.sub)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    await session.commit()
    return OkResponse()
