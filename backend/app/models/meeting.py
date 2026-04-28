from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class MeetingStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"


class ParticipantStatus(str, Enum):
    invited = "invited"
    accepted = "accepted"
    declined = "declined"


class MeetingSchedule(SQLModel, table=True):
    __tablename__ = "meeting_schedules"

    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="rooms.id", index=True)
    title: str = Field(max_length=255)
    scheduled_at: datetime = Field(index=True)
    end_at: Optional[datetime] = None
    location_name: Optional[str] = Field(default=None, max_length=255)
    location_address: Optional[str] = Field(default=None, max_length=512)
    kakao_place_id: Optional[str] = Field(default=None, max_length=64)
    kakao_place_url: Optional[str] = Field(default=None, max_length=512)
    reminder_sent: bool = Field(default=False)
    vote_reminder_sent: bool = Field(default=False)
    vote_options: Optional[list[dict[str, Any]]] = Field(default=None, sa_column=Column(JSON(), nullable=True))
    votes: Optional[dict[str, int]] = Field(default=None, sa_column=Column(JSON(), nullable=True))
    status: str = Field(sa_column=sa.Column(sa.String(32), nullable=False, server_default="pending"))
    created_by: int = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class MeetingParticipant(SQLModel, table=True):
    __tablename__ = "meeting_participants"
    __table_args__ = (
        UniqueConstraint(
            "meeting_id",
            "user_id",
            name="uq_meeting_participants_meeting_id_user_id",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    meeting_id: int = Field(foreign_key="meeting_schedules.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    status: str = Field(sa_column=sa.Column(sa.String(32), nullable=False, server_default="invited"))
    responded_at: Optional[datetime] = None
