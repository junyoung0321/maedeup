from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import logging

import httpx
from fastapi import APIRouter, Depends, Query, Response

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.user import User

router = APIRouter(prefix="/calendar", tags=["calendar"])

KST = ZoneInfo("Asia/Seoul")
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
SLOT_MINUTES = 30
WORK_HOUR_START = 9
WORK_HOUR_END = 22
LOOKAHEAD_DAYS = 14


# ── 응답 모델 ──────────────────────────────────────────────


class FreeSlot(BaseModel):
    start: str
    end: str
    available_members: list[str]


class DayInfo(BaseModel):
    available: list[str]
    busy: list[str]
    unconnected: list[str]


class FreeSlotsResponse(BaseModel):
    free_slots: list[FreeSlot]
    dates: dict[str, DayInfo]


# ── Google API 헬퍼 ────────────────────────────────────────


async def _refresh_access_token(refresh_token: str) -> Optional[str]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code == 200:
        return resp.json().get("access_token")
    return None


async def _get_busy_periods(
    user: User,
    time_min: datetime,
    time_max: datetime,
    session: AsyncSession,
) -> list[dict]:
    """
    Google Calendar API로 바쁜 시간대(시작/종료)만 조회합니다.
    일정 제목·내용은 수집하지 않습니다.
    """
    logger.warning(f"[CALENDAR] _get_busy_periods called for {user.name}, has_token={bool(user.google_access_token)}")
    if not user.google_access_token:
        return []

    params = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "fields": "items(start,end)",
    }
    headers = {"Authorization": f"Bearer {user.google_access_token}"}

    logger.warning(f"[CALENDAR] Calling Google Events API for {user.name}")
    async with httpx.AsyncClient() as client:
        resp = await client.get(EVENTS_URL, params=params, headers=headers)
        logger.warning(f"[CALENDAR] Events API status: {resp.status_code}")
        logger.warning(f"[CALENDAR] Events API response: {resp.text[:500]}")

        if resp.status_code == 401 and user.google_refresh_token:
            logger.debug("Refreshing token for %s", user.name)
            new_token = await _refresh_access_token(user.google_refresh_token)
            if new_token:
                user.google_access_token = new_token
                session.add(user)
                await session.commit()
                headers = {"Authorization": f"Bearer {new_token}"}
                resp = await client.get(EVENTS_URL, params=params, headers=headers)
                logger.debug("Google API response: %s", resp.status_code)

        if resp.status_code != 200:
            return []

    items = resp.json().get("items", [])
    logger.warning(f"[CALENDAR] Google API status: {resp.status_code}, busy count: {len(items)}")

    result = []
    for item in items:
        start_raw = item.get("start", {})
        end_raw = item.get("end", {})

        # 종일 일정은 start.date / end.date, 시간 일정은 start.dateTime / end.dateTime
        if "dateTime" in start_raw:
            start = datetime.fromisoformat(start_raw["dateTime"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_raw["dateTime"].replace("Z", "+00:00"))
        else:
            # 종일 일정: date 문자열 → 해당 날 00:00 KST
            start = datetime.fromisoformat(start_raw["date"]).replace(tzinfo=KST)
            end = datetime.fromisoformat(end_raw["date"]).replace(tzinfo=KST)

        result.append({"start": start, "end": end})

    return result


# ── 계산 헬퍼 ─────────────────────────────────────────────


def _day_utc_range(kst_date: date) -> tuple[datetime, datetime]:
    """KST 날짜의 시작/종료 UTC datetime을 반환합니다."""
    day_start = datetime(kst_date.year, kst_date.month, kst_date.day, tzinfo=KST)
    day_end = day_start + timedelta(days=1)
    return day_start.astimezone(timezone.utc), day_end.astimezone(timezone.utc)


def _is_busy_on_day(busy_periods: list[dict], kst_date: date) -> bool:
    day_start_utc, day_end_utc = _day_utc_range(kst_date)
    return any(
        bp["start"] < day_end_utc and bp["end"] > day_start_utc
        for bp in busy_periods
    )


def _compute_dates(
    busy_by_user: dict[str, list[dict]],
    unconnected_names: list[str],
    start_date: date,
) -> dict[str, DayInfo]:
    """날짜별 available/busy/unconnected 멤버를 계산합니다."""
    result: dict[str, DayInfo] = {}
    for offset in range(LOOKAHEAD_DAYS):
        kst_date = start_date + timedelta(days=offset)
        available, busy = [], []
        for name, periods in busy_by_user.items():
            if _is_busy_on_day(periods, kst_date):
                busy.append(name)
            else:
                available.append(name)
        result[kst_date.isoformat()] = DayInfo(
            available=sorted(available),
            busy=sorted(busy),
            unconnected=sorted(unconnected_names),
        )
    return result


def _compute_free_slots(
    busy_by_user: dict[str, list[dict]],
    time_min: datetime,
    time_max: datetime,
) -> list[FreeSlot]:
    slots: list[dict] = []
    current = time_min

    while current < time_max:
        slot_end = current + timedelta(minutes=SLOT_MINUTES)
        current_kst = current.astimezone(KST)
        if not (WORK_HOUR_START <= current_kst.hour < WORK_HOUR_END):
            current = slot_end
            continue

        available = [
            name
            for name, periods in busy_by_user.items()
            if not any(bp["start"] < slot_end and bp["end"] > current for bp in periods)
        ]

        if available:
            slots.append({"start": current, "end": slot_end, "available_members": sorted(available)})

        current = slot_end

    merged: list[dict] = []
    for slot in slots:
        if (
            merged
            and merged[-1]["available_members"] == slot["available_members"]
            and merged[-1]["end"] == slot["start"]
        ):
            merged[-1]["end"] = slot["end"]
        else:
            merged.append(dict(slot))

    return [
        FreeSlot(
            start=s["start"].astimezone(KST).isoformat(),
            end=s["end"].astimezone(KST).isoformat(),
            available_members=s["available_members"],
        )
        for s in merged
    ]


# ── 엔드포인트 ────────────────────────────────────────────


@router.get("/free-slots", response_model=FreeSlotsResponse)
async def get_free_slots(
    response: Response,
    room_id: str = Query(..., description="채팅방 ID"),
    _current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    캘린더 수집 동의 멤버의 가능 시간대와 날짜별 가용 현황을 반환합니다.
    일정 제목/내용은 수집하지 않으며, 오늘부터 14일 범위를 조회합니다.
    """
    # 브라우저·프록시 캐싱 방지 — 항상 구글 캘린더 API 실시간 호출
    response.headers["Cache-Control"] = "no-store"

    today_kst = datetime.now(tz=KST).date()
    time_min = datetime(today_kst.year, today_kst.month, today_kst.day, tzinfo=KST).astimezone(timezone.utc)
    time_max = time_min + timedelta(days=LOOKAHEAD_DAYS)

    # 전체 유저 조회
    all_users_result = await session.execute(select(User))
    all_users: list[User] = list(all_users_result.scalars().all())

    consenting = [u for u in all_users if u.calendar_consent]
    unconnected_names = [u.name for u in all_users if not u.calendar_consent]

    # 동의 유저별 바쁜 시간대 수집 (제목/내용 없이 시간만)
    busy_by_user: dict[str, list[dict]] = {}
    for user in consenting:
        busy_by_user[user.name] = await _get_busy_periods(user, time_min, time_max, session)

    dates = _compute_dates(busy_by_user, unconnected_names, today_kst)
    free_slots = _compute_free_slots(busy_by_user, time_min, time_max)

    return FreeSlotsResponse(free_slots=free_slots, dates=dates)
