from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import AuthUser, get_current_user

router = APIRouter(prefix="/places", tags=["places"])

KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class PlaceSearchRequest(BaseModel):
    query: str
    x: Optional[str] = None  # 경도 (longitude)
    y: Optional[str] = None  # 위도 (latitude)


class PlaceResult(BaseModel):
    id: str
    name: str
    address: str
    phone: str
    url: str
    x: str  # 경도
    y: str  # 위도
    category: str


@router.post("/search", response_model=list[PlaceResult])
async def search_places(
    payload: PlaceSearchRequest,
    _current_user: AuthUser = Depends(get_current_user),
):
    if not settings.KAKAO_REST_API_KEY:
        raise HTTPException(status_code=503, detail="KAKAO_REST_API_KEY not configured")

    params: dict = {"query": payload.query, "size": 10}
    if payload.x:
        params["x"] = payload.x
    if payload.y:
        params["y"] = payload.y

    headers = {"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(KAKAO_KEYWORD_URL, params=params, headers=headers)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Kakao API error")

    documents = resp.json().get("documents", [])
    return [
        PlaceResult(
            id=doc["id"],
            name=doc["place_name"],
            address=doc.get("road_address_name") or doc.get("address_name", ""),
            phone=doc.get("phone", ""),
            url=doc.get("place_url", ""),
            x=doc.get("x", ""),
            y=doc.get("y", ""),
            category=doc.get("category_name", ""),
        )
        for doc in documents
    ]
