from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class VoteType(str, Enum):
    date = "date"
    place = "place"
    custom = "custom"


class VoteStatus(str, Enum):
    open = "open"
    closed = "closed"


class Vote(SQLModel, table=True):
    __tablename__ = "votes"

    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="rooms.id", index=True)
    title: str = Field(max_length=255)
    vote_type: str = Field(sa_column=sa.Column(sa.String(32), nullable=False))
    status: str = Field(sa_column=sa.Column(sa.String(32), nullable=False, server_default="open"))
    created_by: int = Field(foreign_key="users.id")
    ends_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class VoteOption(SQLModel, table=True):
    __tablename__ = "vote_options"

    id: Optional[int] = Field(default=None, primary_key=True)
    vote_id: int = Field(foreign_key="votes.id", index=True)
    content: str = Field(max_length=512)
    scheduled_at: Optional[datetime] = None


class VoteResponse(SQLModel, table=True):
    __tablename__ = "vote_responses"

    id: Optional[int] = Field(default=None, primary_key=True)
    vote_id: int = Field(foreign_key="votes.id", index=True)
    option_id: int = Field(foreign_key="vote_options.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
