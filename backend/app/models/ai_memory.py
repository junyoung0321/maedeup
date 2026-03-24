from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class MemoryType(str, Enum):
    preference = "preference"
    schedule_pattern = "schedule_pattern"
    location = "location"


class AIMemory(SQLModel, table=True):
    __tablename__ = "ai_memories"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    memory_type: MemoryType
    content: str
    source_room_id: Optional[int] = Field(default=None, foreign_key="rooms.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
