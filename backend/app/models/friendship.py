from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class FriendshipStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    blocked = "blocked"


class Friendship(SQLModel, table=True):
    __tablename__ = "friendships"

    id: Optional[int] = Field(default=None, primary_key=True)
    requester_id: int = Field(foreign_key="users.id", index=True)
    addressee_id: int = Field(foreign_key="users.id", index=True)
    status: FriendshipStatus = Field(default=FriendshipStatus.pending)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
