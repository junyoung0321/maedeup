from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class RoomStatus(str, Enum):
    active = "active"
    archived = "archived"


class MemberRole(str, Enum):
    owner = "owner"
    member = "member"


class Room(SQLModel, table=True):
    __tablename__ = "rooms"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    description: Optional[str] = None
    created_by: int = Field(foreign_key="users.id")
    status: RoomStatus = Field(default=RoomStatus.active)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RoomMember(SQLModel, table=True):
    __tablename__ = "room_members"

    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="rooms.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    role: MemberRole = Field(default=MemberRole.member)
    joined_at: datetime = Field(default_factory=datetime.utcnow)
