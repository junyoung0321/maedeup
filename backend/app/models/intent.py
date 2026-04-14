from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class IntentExample(SQLModel, table=True):
    """RAG 기반 의도 분류를 위한 예시 데이터 저장 모델."""

    __tablename__ = "intent_examples"

    id: Optional[int] = Field(default=None, primary_key=True)
    text: str = Field(index=False, description="예시 발화 텍스트")
    intent: str = Field(
        index=True,
        description="의도 레이블: meeting_schedule | place_suggestion | general",
    )
    embedding: Any = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="text-embedding-004 벡터 (768차원 float 리스트)",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
