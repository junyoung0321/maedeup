from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=255)
    description: Optional[str] = None
    location_name: Optional[str] = Field(default=None, max_length=255)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    kakao_place_id: Optional[str] = Field(default=None, max_length=64)
    kakao_place_url: Optional[str] = Field(default=None, max_length=512)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EventCreate(SQLModel):
    title: str
    description: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    kakao_place_id: Optional[str] = None
    kakao_place_url: Optional[str] = None


class EventRead(SQLModel):
    id: int
    title: str
    description: Optional[str]
    location_name: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    starts_at: datetime
    ends_at: Optional[datetime]
    kakao_place_id: Optional[str]
    kakao_place_url: Optional[str]
    created_at: datetime
    updated_at: datetime
