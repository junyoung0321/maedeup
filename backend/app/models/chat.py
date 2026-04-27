from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class PaneType(str, Enum):
    social = "social"
    agent = "agent"
    # 홈 화면 비서 어시스턴트 — room_id NULL, 사용자 단위 1:1 대화.
    # `agent`(룸 내부)와 구분하기 위해 별도 값.
    personal_assistant = "personal_assistant"


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    pane_type: str = Field(sa_column=sa.Column(sa.String(32), index=True, nullable=False))
    role: str = Field(max_length=32)           # "user" | "assistant" | "system"
    content: str
    sender: Optional[str] = Field(default=None, max_length=64)
    session_id: Optional[str] = Field(default=None, index=True, max_length=64)
    room_id: Optional[int] = Field(default=None, foreign_key="rooms.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class ChatMessageCreate(SQLModel):
    pane_type: PaneType
    role: str
    content: str
    sender: Optional[str] = None
    session_id: Optional[str] = None
    room_id: Optional[int] = None


class ChatMessageRead(SQLModel):
    id: int
    pane_type: PaneType
    role: str
    content: str
    sender: Optional[str]
    session_id: Optional[str]
    room_id: Optional[int]
    created_at: datetime
