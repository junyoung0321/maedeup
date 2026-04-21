from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    name: str = Field(max_length=128)
    picture: Optional[str] = Field(default=None)
    home_base: Optional[str] = Field(default=None, max_length=128)
    food_preferences: Optional[list[str]] = Field(default=None, sa_column=Column(JSON(), nullable=True))
    food_preference_note: Optional[str] = Field(default=None, max_length=255)
    google_access_token: Optional[str] = Field(default=None, sa_column=Column(Text(), nullable=True))
    google_refresh_token: Optional[str] = Field(default=None, sa_column=Column(Text(), nullable=True))
    calendar_consent: bool = Field(default=False, index=True)
    # 게스트 유저: 구글 로그인 없이 방 링크만으로 생성된 pseudo-user. email은 synthetic.
    is_guest: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
