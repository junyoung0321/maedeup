"""홈 화면 'AI 추천' 카드용 엔드포인트.

- /available-friends: 지금 시간대에 모임 가능한 친구
- /nearby-places: home_base 기반 카페/장소 추천
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.calendar import _get_busy_periods
from app.api.routes.users import FriendInfo
from app.core.config import settings
from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User
from app.services.kakao_maps import search_keyword

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


# ── 친구 가용성 ─────────────────────────────────────────────


AvailabilityState = Literal["free", "busy_now", "free_in", "unknown"]


class AvailableFriend(BaseModel):
    user: FriendInfo
    state: AvailabilityState
    available_at: Optional[datetime] = None  # busy_now → 다음 free 시각


class AvailableFriendsResponse(BaseModel):
    window_minutes: int
    now: datetime
    friends: list[AvailableFriend]


def _classify_friend(
    busy_periods: list[dict], now: datetime, until: datetime
) -> tuple[AvailabilityState, Optional[datetime]]:
    """busy 구간 리스트를 보고 현재 가용성을 분류."""
    if not busy_periods:
        return "free", None

    # naive UTC 로 정규화
    def _to_naive(d: datetime) -> datetime:
        if d.tzinfo is not None:
            return d.astimezone(timezone.utc).replace(tzinfo=None)
        return d

    now_naive = _to_naive(now)
    until_naive = _to_naive(until)

    overlapping_now = [
        p for p in busy_periods
        if _to_naive(p["start"]) <= now_naive < _to_naive(p["end"])
    ]

    if not overlapping_now:
        return "free", None

    # 지금 바쁜데 window 내에 끝나는지
    earliest_end = min(_to_naive(p["end"]) for p in overlapping_now)
    if earliest_end <= until_naive:
        return "free_in", earliest_end

    return "busy_now", None


@router.get("/available-friends", response_model=AvailableFriendsResponse)
async def get_available_friends(
    window_minutes: int = Query(120, ge=15, le=720),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """현재 유저의 친구들 중 지금/곧 모임 가능한 사람 분류.

    - state=free: 현재 일정 없음
    - state=free_in: 현재 일정 있지만 window 내에 끝남 (available_at 채워짐)
    - state=busy_now: 현재부터 window 끝까지 계속 바쁨
    - state=unknown: 친구가 캘린더 미연동
    """
    user_id = int(current_user.sub)

    # 친구 조회 (accepted)
    rel_result = await session.execute(
        select(Friendship).where(
            or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            ),
            Friendship.status == FriendshipStatus.accepted,
        )
    )
    friendships = rel_result.scalars().all()
    friend_ids = [
        f.addressee_id if f.requester_id == user_id else f.requester_id
        for f in friendships
    ]
    if not friend_ids:
        return AvailableFriendsResponse(window_minutes=window_minutes, now=datetime.now(timezone.utc), friends=[])

    user_result = await session.execute(select(User).where(User.id.in_(friend_ids)))
    friends = user_result.scalars().all()

    now_utc = datetime.now(timezone.utc)
    until_utc = now_utc + timedelta(minutes=window_minutes)

    # 캘린더 동의한 친구만 GCal 호출 (병렬)
    consenting = [u for u in friends if u.calendar_consent and u.google_refresh_token]
    unconsenting = [u for u in friends if not (u.calendar_consent and u.google_refresh_token)]

    async def _safe_busy(user: User) -> tuple[int, list[dict]]:
        try:
            periods = await _get_busy_periods(user, now_utc, until_utc, session)
            return user.id, periods
        except Exception as exc:  # noqa: BLE001
            logger.warning("[RECO] busy fetch failed user_id=%s err=%s", user.id, exc)
            return user.id, []

    busy_results: dict[int, list[dict]] = {}
    if consenting:
        gathered = await asyncio.gather(*(_safe_busy(u) for u in consenting))
        busy_results = dict(gathered)

    out: list[AvailableFriend] = []
    for u in consenting:
        state, available_at = _classify_friend(busy_results.get(u.id, []), now_utc, until_utc)
        out.append(
            AvailableFriend(
                user=FriendInfo(id=u.id, name=u.name, email=u.email, picture=u.picture),
                state=state,
                available_at=available_at,
            )
        )
    for u in unconsenting:
        out.append(
            AvailableFriend(
                user=FriendInfo(id=u.id, name=u.name, email=u.email, picture=u.picture),
                state="unknown",
                available_at=None,
            )
        )

    # 정렬: free → free_in → busy_now → unknown
    state_order = {"free": 0, "free_in": 1, "busy_now": 2, "unknown": 3}
    out.sort(key=lambda f: (state_order[f.state], f.user.name))

    return AvailableFriendsResponse(
        window_minutes=window_minutes,
        now=now_utc,
        friends=out,
    )


# ── 근처 장소 추천 ───────────────────────────────────────────


class RecommendedPlace(BaseModel):
    id: str
    name: str
    address: str
    distance_label: Optional[str] = None
    category: str
    url: str
    x: str
    y: str


class NearbyPlacesResponse(BaseModel):
    home_base: Optional[str]
    category: str
    places: list[RecommendedPlace]
    reason: Optional[str] = None  # 빈 결과 사유


@router.get("/nearby-places", response_model=NearbyPlacesResponse)
async def get_nearby_places(
    category: str = Query("카페", description="검색 카테고리/키워드"),
    limit: int = Query(3, ge=1, le=10),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """현재 유저의 home_base 근처 장소 추천.

    home_base 미설정 시 places=[]+reason 반환.
    """
    user = await session.get(User, int(current_user.sub))
    if user is None:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")

    home = (user.home_base or "").strip()
    if not home:
        return NearbyPlacesResponse(
            home_base=None,
            category=category,
            places=[],
            reason="동네를 먼저 등록해주세요",
        )

    if not (settings.KAKAO_API_KEY or settings.KAKAO_REST_API_KEY):
        return NearbyPlacesResponse(
            home_base=home,
            category=category,
            places=[],
            reason="장소 검색이 일시적으로 불가합니다",
        )

    query = f"{home} {category}"
    try:
        documents = await search_keyword(query)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[RECO] kakao search failed: %s", exc)
        documents = []

    places = [
        RecommendedPlace(
            id=doc["id"],
            name=doc["place_name"],
            address=doc.get("road_address_name") or doc.get("address_name", ""),
            distance_label=doc.get("distance") or None,
            category=doc.get("category_name", ""),
            url=doc.get("place_url", ""),
            x=doc.get("x", ""),
            y=doc.get("y", ""),
        )
        for doc in documents[:limit]
    ]

    return NearbyPlacesResponse(home_base=home, category=category, places=places)
