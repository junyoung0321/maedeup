from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import AuthUser, get_current_user
from app.services.kakao_maps import search_keyword

router = APIRouter(prefix="/places", tags=["places"])


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
    if not (settings.KAKAO_API_KEY or settings.KAKAO_REST_API_KEY):
        raise HTTPException(status_code=503, detail="KAKAO_API_KEY not configured")

    documents = await search_keyword(payload.query, x=payload.x, y=payload.y)
    if not documents and payload.query.strip():
        # 키워드 검색 실패/빈결과를 기존 API 에러로 구분하지 않고 빈 배열로 반환
        documents = []

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
