from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
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
    category: Optional[str] = Field(default=None, max_length=64)
    created_by: int = Field(foreign_key="users.id")
    status: str = Field(sa_column=sa.Column(sa.String(32), nullable=False, server_default="active"))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class RoomMember(SQLModel, table=True):
    __tablename__ = "room_members"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_members_room_id_user_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="rooms.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    role: str = Field(sa_column=sa.Column(sa.String(32), nullable=False, server_default="member"))
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
