from datetime import datetime
from enum import Enum
from typing import Optional

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
    scheduled_at: datetime
    location_name: Optional[str] = Field(default=None, max_length=255)
    location_address: Optional[str] = Field(default=None, max_length=512)
    kakao_place_id: Optional[str] = Field(default=None, max_length=64)
    kakao_place_url: Optional[str] = Field(default=None, max_length=512)
    status: MeetingStatus = Field(default=MeetingStatus.pending)
    created_by: int = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MeetingParticipant(SQLModel, table=True):
    __tablename__ = "meeting_participants"

    id: Optional[int] = Field(default=None, primary_key=True)
    meeting_id: int = Field(foreign_key="meeting_schedules.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    status: ParticipantStatus = Field(default=ParticipantStatus.invited)
    responded_at: Optional[datetime] = None
