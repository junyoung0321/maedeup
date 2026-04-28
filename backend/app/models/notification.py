from datetime import datetime, timezone
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy import JSON
from sqlmodel import Field, SQLModel


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    type: str = Field(sa_column=sa.Column(sa.String(32), nullable=False))
    title: str = Field(max_length=255)
    body: Optional[str] = Field(default=None, max_length=1024)
    room_id: Optional[int] = Field(default=None, foreign_key="rooms.id", index=True)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=sa.Column(JSON(), nullable=False, server_default="{}"),
    )
    read_at: Optional[datetime] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        index=True,
    )
