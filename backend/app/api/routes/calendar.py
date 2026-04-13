from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.room import RoomMember
from app.models.user import User

router = APIRouter(prefix="/calendar", tags=["calendar"])

KST = ZoneInfo("Asia/Seoul")
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
SLOT_MINUTES = 30
WORK_HOUR_START = 9
WORK_HOUR_END = 22
LOOKAHEAD_DAYS = 90


# ── 응답 모델 ──────────────────────────────────────────────


class DayInfo(BaseModel):
    count: int              # 해당 날 가능한 멤버 수
    total: int              # 전체 연동 멤버 수
    available: list[str]    # 가능한 멤버 이름 목록
    busy: list[str]         # 바쁜 멤버 이름 목록
    unconnected: list[str]  # 캘린더 미연동 멤버 이름 목록


class FreeSlot(BaseModel):
    label: str           # "3월 21일 (월) 오후 3:00 ~ 5:00"
    available_count: int
    total_count: int
    is_recommended: bool  # available_count == total_count


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

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


def _format_label(start: datetime, end: datetime) -> str:
    """datetime → "3월 21일 (월) 오후 3:00 ~ 5:00" 형태의 한국어 문자열"""
    s = start.astimezone(KST)
    e = end.astimezone(KST)
    weekday = WEEKDAY_KR[s.weekday()]
    ampm = "오전" if s.hour < 12 else "오후"
    s_hour = s.hour if s.hour <= 12 else s.hour - 12
    e_hour = e.hour if e.hour <= 12 else e.hour - 12
    return (
        f"{s.month}월 {s.day}일 ({weekday}) "
        f"{ampm} {s_hour}:{s.minute:02d} ~ {e_hour}:{e.minute:02d}"
    )


def _has_event_on_day(busy_periods: list[dict], kst_date: date) -> bool:
    """해당 날짜(KST 00:00~24:00) 안에 일정이 하나라도 있는지 확인합니다."""
    day_start = datetime(kst_date.year, kst_date.month, kst_date.day, tzinfo=KST)
    day_end = day_start + timedelta(days=1)
    return any(bp["start"] < day_end and bp["end"] > day_start for bp in busy_periods)


def _compute_dates(
    busy_by_user: dict[str, list[dict]],
    start_date: date,
    lookahead_days: int = LOOKAHEAD_DAYS,
    unconnected_names: list[str] | None = None,
) -> dict[str, DayInfo]:
    """날짜별 가용 인원(count/total) 및 멤버별 가능/불가능 목록을 계산합니다."""
    total = len(busy_by_user)
    unconnected = unconnected_names or []
    result: dict[str, DayInfo] = {}
    for offset in range(lookahead_days):
        kst_date = start_date + timedelta(days=offset)
        available_names = [
            name for name, periods in busy_by_user.items()
            if not _has_event_on_day(periods, kst_date)
        ]
        busy_names = [
            name for name, periods in busy_by_user.items()
            if _has_event_on_day(periods, kst_date)
        ]
        result[kst_date.isoformat()] = DayInfo(
            count=len(available_names),
            total=total,
            available=available_names,
            busy=busy_names,
            unconnected=unconnected,
        )
    return result


def _compute_free_slots(
    busy_by_user: dict[str, list[dict]],
    time_min: datetime,
    time_max: datetime,
) -> list[FreeSlot]:
    total = len(busy_by_user)
    slots: list[dict] = []
    current = time_min

    while current < time_max:
        slot_end = current + timedelta(minutes=SLOT_MINUTES)
        current_kst = current.astimezone(KST)
        if not (WORK_HOUR_START <= current_kst.hour < WORK_HOUR_END):
            current = slot_end
            continue

        available_count = sum(
            1 for periods in busy_by_user.values()
            if not any(bp["start"] < slot_end and bp["end"] > current for bp in periods)
        )

        if available_count > 0:
            slots.append({"start": current, "end": slot_end, "available_count": available_count})

        current = slot_end

    merged: list[dict] = []
    for slot in slots:
        if (
            merged
            and merged[-1]["available_count"] == slot["available_count"]
            and merged[-1]["end"] == slot["start"]
        ):
            merged[-1]["end"] = slot["end"]
        else:
            merged.append(dict(slot))

    return [
        FreeSlot(
            label=_format_label(s["start"], s["end"]),
            available_count=s["available_count"],
            total_count=total,
            is_recommended=(s["available_count"] == total),
        )
        for s in merged
    ]


# ── 엔드포인트 ────────────────────────────────────────────


@router.get("/free-slots", response_model=FreeSlotsResponse)
async def get_free_slots(
    response: Response,
    room_id: str = Query(..., description="채팅방 ID"),
    year: int = Query(default=None, description="조회 연도 (없으면 오늘 기준)"),
    month: int = Query(default=None, description="조회 월 (없으면 오늘 기준)"),
    _current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    캘린더 수집 동의 멤버의 가능 시간대와 날짜별 가용 현황을 반환합니다.
    일정 제목/내용은 수집하지 않으며, year/month 지정 시 해당 월, 없으면 오늘부터 90일 범위를 조회합니다.
    """
    # 브라우저·프록시 캐싱 방지 — 항상 구글 캘린더 API 실시간 호출
    response.headers["Cache-Control"] = "no-store"

    today_kst = datetime.now(tz=KST).date()

    if year and month:
        start_date = date(year, month, 1)
        # 해당 월의 마지막 날 계산 (다음 달 1일 - 1일)
        if month == 12:
            next_month_start = date(year + 1, 1, 1)
        else:
            next_month_start = date(year, month + 1, 1)
        days_in_month = (next_month_start - start_date).days
        time_min = datetime(year, month, 1, tzinfo=KST).astimezone(timezone.utc)
        time_max = datetime(next_month_start.year, next_month_start.month, next_month_start.day, tzinfo=KST).astimezone(timezone.utc)
        lookahead = days_in_month
    else:
        start_date = today_kst
        time_min = datetime(today_kst.year, today_kst.month, today_kst.day, tzinfo=KST).astimezone(timezone.utc)
        time_max = time_min + timedelta(days=LOOKAHEAD_DAYS)
        lookahead = LOOKAHEAD_DAYS

    try:
        room_pk = int(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="유효하지 않은 채팅방 ID입니다.") from exc

    member_result = await session.execute(
        select(User)
        .join(RoomMember, RoomMember.user_id == User.id)
        .where(RoomMember.room_id == room_pk)
    )
    all_users: list[User] = list(member_result.scalars().all())

    consenting = [u for u in all_users if u.calendar_consent]
    unconnected_names = [u.name for u in all_users if not u.calendar_consent]

    # 동의 유저별 바쁜 시간대 수집 (제목/내용 없이 시간만)
    busy_by_user: dict[str, list[dict]] = {}
    for user in consenting:
        busy_by_user[user.name] = await _get_busy_periods(user, time_min, time_max, session)

    dates = _compute_dates(busy_by_user, start_date, lookahead, unconnected_names)
    free_slots = _compute_free_slots(busy_by_user, time_min, time_max)

    return FreeSlotsResponse(free_slots=free_slots, dates=dates)
