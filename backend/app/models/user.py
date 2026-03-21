from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    name: str = Field(max_length=128)
    picture: Optional[str] = Field(default=None)
    google_access_token: Optional[str] = Field(default=None, sa_column=Column(Text(), nullable=True))
    google_refresh_token: Optional[str] = Field(default=None, sa_column=Column(Text(), nullable=True))
    calendar_consent: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
