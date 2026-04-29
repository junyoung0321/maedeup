from datetime import datetime, timezone
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class MeetingPreference(SQLModel, table=True):
    """모임별 멤버 선호 정보. 채팅방 입장 시 팝업으로 수집."""

    __tablename__ = "meeting_preferences"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_meeting_pref_room_user"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="rooms.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    preferred_times: Optional[list[str]] = Field(
        default=None, sa_column=Column(JSON(), nullable=True),
    )  # ["평일저녁", "주말오후"]
    preferred_location: Optional[str] = Field(default=None, max_length=128)
    preferred_foods: Optional[list[str]] = Field(
        default=None, sa_column=Column(JSON(), nullable=True),
    )  # ["한식", "일식"]
    disliked_foods: Optional[list[str]] = Field(
        default=None, sa_column=Column(JSON(), nullable=True),
    )  # ["중식"]
    note: Optional[str] = Field(default=None, max_length=255)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
