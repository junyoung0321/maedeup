from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class FriendshipStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    blocked = "blocked"


class Friendship(SQLModel, table=True):
    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint(
            "requester_id",
            "addressee_id",
            name="uq_friendships_requester_id_addressee_id",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    requester_id: int = Field(foreign_key="users.id", index=True)
    addressee_id: int = Field(foreign_key="users.id", index=True)
    status: str = Field(sa_column=sa.Column(sa.String(32), nullable=False, server_default="pending"))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
