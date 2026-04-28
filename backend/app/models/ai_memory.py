from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class MemoryType(str, Enum):
    """
    AIMemory.memory_type에 들어가는 값.

    Note: 칼럼 자체는 String(32)이므로 enum 외 값도 들어갈 수 있지만, 새 코드는
    이 enum의 값만 사용. vestigial 값(preference / schedule_pattern / location)은
    이번 PR에서 정리 — 기존 row가 있으면 그대로 두되 새로 안 씀.
    """

    # personal data 추출 카테고리. memory_extraction 노드에서 INSERT.
    food_restrictions = "food_restrictions"
    food_preferences = "food_preferences"
    liked_areas = "liked_areas"
    disliked_areas = "disliked_areas"
    time_preference = "time_preference"
    transport_mode = "transport_mode"

    # 모임 종료 후 history. meeting_history.save_meeting_record가 INSERT.
    meeting_record = "meeting_record"


class AIMemory(SQLModel, table=True):
    __tablename__ = "ai_memories"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    memory_type: str = Field(sa_column=sa.Column(sa.String(32), nullable=False))
    # Append-only event log이므로 content는 JSON-encoded 문자열. status 키로
    # active / superseded_by_manual 구분 (personal_data 추출 결과).
    content: str
    source_room_id: Optional[int] = Field(default=None, foreign_key="rooms.id", index=True)
    # 추출의 원문 메시지 — receipts ✨ 클릭 시 점프할 메시지.
    # 메시지가 지워지면 audit row는 살아남되 link만 NULL로 (orphan 방지).
    source_message_id: Optional[int] = Field(
        default=None,
        sa_column=sa.Column(
            sa.Integer(),
            sa.ForeignKey("chat_messages.id", ondelete="SET NULL"),
            index=True,
        ),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
