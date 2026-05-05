from typing import Optional

from pydantic import BaseModel, Field


class PlacePatchRequest(BaseModel):
    place: str = Field(min_length=1, max_length=80)
    place_id: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    url: Optional[str] = None


class PlacePatchResponse(BaseModel):
    meeting_id: int
    place: str
    calendar_registered: bool
