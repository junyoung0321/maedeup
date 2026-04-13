from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class PaneType(str, Enum):
    social = "social"
    agent = "agent"


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    pane_type: PaneType = Field(index=True)
    role: str = Field(max_length=32)           # "user" | "assistant" | "system"
    content: str
    sender: Optional[str] = Field(default=None, max_length=64)
    session_id: Optional[str] = Field(default=None, index=True, max_length=64)
    room_id: Optional[int] = Field(default=None, foreign_key="rooms.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
