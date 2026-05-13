"""캘린더 슬롯 빌더 + 필터.

원본 위치: langgraph_pipeline.py 라인 906~939 (_build_time_option_slots),
  1335~1390 (_get_user_busy_periods), 1393~1457 (_find_free_slots),
  1584~1607 (_load_blocked_dates), 1610~1618 (_filter_out_blocked),
  1655~1666 (_filter_out_rejected), 1669~1708 (_load_busy_by_user_for_state),
  1711~1935 (get_free_slots), 3420~3503 (_build_multi_date_slots),
  3506~3530 (_is_busy_during), 3533~3667 (_build_preference_time_slots).

Phase 3 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

가장 큰 헬퍼 모듈 — 약 600줄. get_free_slots 단독 225줄.

의존:
  - state.GraphState
  - constants: KST, SLOT_MINUTES, WORK_HOUR_START, WORK_HOUR_END, PREFERRED_TIME_RANGES, GOOGLE_FREEBUSY_URL
  - dates: _get_korean_holiday, _is_weekend, _is_specific_iso_date,
    _fallback_parse_natural_date, _parse_iso_datetime
  - formatting: _format_slot_label, _room_id_as_int, _user_calendar_key, _user_display_name
  - slot_state: _normalize_preferred_times, _preference_score_for_start
  - 외부: scheduling_round, google_calendar, models (User, RoomMember)
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.models.room import RoomMember
from app.models.user import User
from app.services import scheduling_round as sr
from app.services.google_calendar import GoogleCalendarAuthError, get_google_access_token
from app.services.pipeline.constants import (
    GOOGLE_FREEBUSY_URL,
    KST,
    PREFERRED_TIME_RANGES,
    SLOT_MINUTES,
    WORK_HOUR_END,
    WORK_HOUR_START,
)
from app.services.pipeline.helpers.dates import (
    _fallback_parse_natural_date,
    _get_korean_holiday,
    _is_specific_iso_date,
    _is_weekend,
    _parse_iso_datetime,
)
from app.services.pipeline.helpers.formatting import (
    _format_slot_label,
    _room_id_as_int,
    _user_calendar_key,
    _user_display_name,
)
from app.services.pipeline.helpers.slot_state import (
    _normalize_preferred_times,
    _preference_score_for_start,
)
from app.services.pipeline.state import GraphState

logger = logging.getLogger(__name__)


def _build_time_option_slots(state: GraphState) -> list[dict[str, Any]]:
    date_hint = state.get("date_hint")
    time_options = list(state.get("time_options") or [])
    if not _is_specific_iso_date(date_hint) or not time_options:
        return []

    try:
        base_date = datetime.strptime(str(date_hint), "%Y-%m-%d").replace(tzinfo=KST)
    except ValueError:
        return []

    holiday = _get_korean_holiday(base_date)
    slots: list[dict[str, Any]] = []
    for index, time_value in enumerate(time_options, start=1):
        try:
            hour, minute = map(int, str(time_value).split(":"))
        except ValueError:
            continue
        start_at = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        end_at = start_at + timedelta(minutes=SLOT_MINUTES)
        slots.append({
            "slot_id": f"time-option-{index}",
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "label": _format_slot_label(start_at, []),
            "available_count": state.get("headcount"),
            "total_count": state.get("headcount"),
            "has_conflict": False,
            "unavailable_users": [],
            "is_holiday": bool(holiday),
            "holiday_name": holiday,
            "is_weekend": _is_weekend(start_at),
        })
    return slots


async def _get_user_busy_periods(
    user: User,
    time_min: datetime,
    time_max: datetime,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Google Calendar freeBusy API로 특정 유저의 바쁜 시간대(시작/종료)만 조회합니다."""
    try:
        access_token = await get_google_access_token(user, db)
    except GoogleCalendarAuthError:
        return []
    except Exception:
        return []

    try:

        payload = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "timeZone": "Asia/Seoul",
            "items": [{"id": "primary"}],
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(GOOGLE_FREEBUSY_URL, json=payload, headers=headers)

            if resp.status_code == 401:
                refreshed_token = await get_google_access_token(user, db, force_refresh=True)
                headers = {"Authorization": f"Bearer {refreshed_token}"}
                resp = await client.post(
                    GOOGLE_FREEBUSY_URL,
                    json=payload,
                    headers=headers,
                )

            if resp.status_code != 200:
                return []

        try:
            busy_periods = resp.json().get("calendars", {}).get("primary", {}).get("busy", [])
        except ValueError:
            return []

        result = []
        for item in busy_periods:
            start_raw = item.get("start")
            end_raw = item.get("end")
            if not start_raw or not end_raw:
                continue
            start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            result.append({"start": start, "end": end})
        return result
    except Exception:
        return []


def _find_free_slots(
    busy_by_user: dict[str, list[dict[str, Any]]],
    time_min: datetime,
    time_max: datetime,
    minimum_available: int,
    require_exact_absent_count: int | None,
    preferred_times: list[str] | None = None,
) -> list[dict[str, Any]]:
    """참여자 가용성을 기준으로 시간대를 SLOT_MINUTES 단위로 탐색합니다."""
    total = len(busy_by_user)
    free_slots: list[dict[str, Any]] = []
    fallback_slots: list[dict[str, Any]] = []
    normalized_preferred_times = _normalize_preferred_times(preferred_times)
    current = time_min
    slot_idx = 1

    while current < time_max and len(free_slots) < 5:
        slot_end = current + timedelta(minutes=SLOT_MINUTES)
        current_kst = current.astimezone(KST)

        if WORK_HOUR_START <= current_kst.hour < WORK_HOUR_END:
            unavailable_names = [
                name
                for name, periods in busy_by_user.items()
                if any(bp["start"] < slot_end and bp["end"] > current for bp in periods)
            ]
            available_count = total - len(unavailable_names)

            absent_count_matches = (
                require_exact_absent_count is None
                or len(unavailable_names) == require_exact_absent_count
            )
            if available_count >= minimum_available and absent_count_matches:
                s = current.astimezone(KST)
                holiday = _get_korean_holiday(s)
                slot = {
                    "slot_id": f"slot-{slot_idx}",
                    "start_at": current.isoformat(),
                    "end_at": slot_end.isoformat(),
                    "label": _format_slot_label(
                        s,
                        [_user_display_name(name) for name in unavailable_names],
                    ),
                    "available_count": available_count,
                    "total_count": total,
                    "has_conflict": bool(unavailable_names),
                    "unavailable_users": [_user_display_name(name) for name in unavailable_names],
                    "is_holiday": bool(holiday),
                    "holiday_name": holiday,
                    "is_weekend": _is_weekend(s),
                }
                if normalized_preferred_times:
                    if _preference_score_for_start(s, normalized_preferred_times) > 0:
                        free_slots.append(slot)
                    elif len(fallback_slots) < 5:
                        fallback_slots.append(slot)
                else:
                    free_slots.append(slot)
                slot_idx += 1

        current = current + timedelta(minutes=SLOT_MINUTES)

    if normalized_preferred_times and free_slots:
        return free_slots
    return free_slots if free_slots else fallback_slots


async def _load_blocked_dates(room_pk: Optional[int]) -> set[str]:
    """방의 '불가능 날짜' 집합을 Redis에서 조회. 한 명이라도 불가능이면 해당 날짜 제외.
    Redis 실패 시 빈 set 반환 (pipeline은 graceful degradation)."""
    if room_pk is None:
        return set()
    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        try:
            unavail = await sr.load_room_unavailability(r, room_id=room_pk)
        finally:
            await r.aclose()
    except Exception:
        return set()
    blocked: set[str] = set()
    for dates in unavail.values():
        for d in dates:
            if isinstance(d, str):
                blocked.add(d)
    return blocked


def _filter_out_blocked(
    slots: list[dict[str, Any]], blocked_dates: set[str]
) -> list[dict[str, Any]]:
    if not blocked_dates:
        return slots
    return [
        s for s in slots
        if isinstance(s.get("start_at"), str) and s["start_at"][:10] not in blocked_dates
    ]


def _filter_out_rejected(
    slots: list[dict[str, Any]], rejected_dates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not rejected_dates:
        return slots
    rejected_set = {r["date"] for r in rejected_dates if isinstance(r.get("date"), str)}
    if not rejected_set:
        return slots
    return [
        s for s in slots
        if isinstance(s.get("start_at"), str) and s["start_at"][:10] not in rejected_set
    ]


async def _load_busy_by_user_for_state(
    state: GraphState,
) -> dict[str, list[dict[str, Any]]]:
    """function_calling preference_based path 등에서 사용할 busy_by_user 빌더.
    get_free_slots의 consenting_users + GCal freeBusy 패턴 재사용 (4주 range 고정).
    GCal 연결된 멤버 0명이거나 room/user 없으면 빈 dict."""
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    if room_pk is None or not settings.GOOGLE_CLIENT_ID:
        return {}

    member_result = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room_pk)
    )
    members = member_result.scalars().all()
    user_ids = [m.user_id for m in members]
    if not user_ids:
        return {}

    user_result = await db.execute(
        select(User).where(User.id.in_(user_ids)).where(User.calendar_consent == True)  # noqa: E712
    )
    consenting_users = [
        user
        for user in user_result.scalars().all()
        if user.google_access_token or user.google_refresh_token
    ]
    if not consenting_users:
        return {}

    now = datetime.now(timezone.utc)
    time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = time_min + timedelta(days=29)

    busy_by_user: dict[str, list[dict[str, Any]]] = {}
    for user in consenting_users:
        busy_by_user[_user_calendar_key(user)] = await _get_user_busy_periods(
            user, time_min, time_max, db
        )
    return busy_by_user


async def get_free_slots(state: GraphState) -> list[dict[str, Any]]:
    """구글 캘린더 API로 룸 멤버 전원의 빈 시간대를 조회합니다.
    불가능 날짜(방 내 누군가 명시한 날)는 결과에서 제외."""
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    blocked_dates = await _load_blocked_dates(room_pk)
    preferred_times = state.get("preference_common_times") or []
    normalized_preferred_times = _normalize_preferred_times(preferred_times)
    minimum_preferred_slots = 3

    def _matching_preference_slots(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not normalized_preferred_times:
            return slots
        matching: list[dict[str, Any]] = []
        for slot in slots:
            start_at = slot.get("start_at")
            if not isinstance(start_at, str):
                continue
            try:
                slot_start = datetime.fromisoformat(start_at)
            except ValueError:
                continue
            if _preference_score_for_start(slot_start, normalized_preferred_times) > 0:
                matching.append(slot)
        return matching

    if room_pk is None or not settings.GOOGLE_CLIENT_ID:
        if preferred_times:
            return _build_preference_time_slots(state, preferred_times, blocked_dates)
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        base = now + timedelta(days=2, hours=10)
        return [
            {
                "slot_id": f"slot-{i+1}",
                "start_at": (base + timedelta(days=i)).isoformat(),
                "end_at": (base + timedelta(days=i, hours=2)).isoformat(),
                "label": _format_slot_label((base + timedelta(days=i)).astimezone(KST), []),
                "has_conflict": False,
            }
            for i in range(3)
        ]

    member_result = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room_pk)
    )
    members = member_result.scalars().all()
    user_ids = [m.user_id for m in members]

    if not user_ids:
        return []

    user_result = await db.execute(
        select(User).where(User.id.in_(user_ids)).where(User.calendar_consent == True)  # noqa: E712
    )
    consenting_users = [
        user
        for user in user_result.scalars().all()
        if user.google_access_token or user.google_refresh_token
    ]

    now = datetime.now(timezone.utc)
    date_hint = state.get("date_hint")

    # 멤버 날짜 선택을 Redis에서 읽어 활용 (캘린더 클릭 + 시간바 선택 모두)
    user_dates: dict[str, str] = {}
    if not date_hint and room_pk is not None:
        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
            try:
                date_sels = await sr.load_room_date_selections(r, room_id=room_pk)
                for uid, d in date_sels.items():
                    if d:
                        user_dates[str(uid)] = d
                avail = await sr.load_room_availability(r, room_id=room_pk)
                for uid, entries in avail.items():
                    for entry in entries:
                        d = entry.get("date")
                        if d:
                            user_dates[str(uid)] = d
            finally:
                await r.aclose()
        except Exception:
            logger.debug("Failed to read member selections from Redis", exc_info=True)

    if not date_hint and not user_dates:
        state["no_date_selection"] = True
        return []

    if not date_hint and user_dates:
        date_counts = Counter(user_dates.values())
        most_common_date, count = date_counts.most_common(1)[0]

        date_hint = most_common_date
        state["date_hint"] = date_hint
        if len(date_counts) > 1:
            state["date_conflict"] = True
            state["date_selection_summary"] = dict(date_counts)
            logger.info("Date conflict: %s (picked %s with %d/%d)", dict(date_counts), date_hint, count, len(user_dates))
        else:
            logger.info("All %d members selected %s", len(user_dates), date_hint)

    if date_hint and re.match(r"\d{4}-\d{2}-\d{2}", str(date_hint)):
        hint_date = datetime.fromisoformat(str(date_hint)).replace(tzinfo=timezone.utc)
        time_min = hint_date.replace(hour=0, minute=0, second=0, microsecond=0)
        time_max = time_min + timedelta(days=1)
    else:
        time_min = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        time_max = time_min + timedelta(days=14)

    busy_by_user: dict[str, list[dict[str, Any]]] = {}
    for user in consenting_users:
        busy_by_user[_user_calendar_key(user)] = await _get_user_busy_periods(user, time_min, time_max, db)

    if not busy_by_user:
        if preferred_times:
            return _build_preference_time_slots(
                state, preferred_times, blocked_dates, busy_by_user=busy_by_user
            )
        return []

    full_slots = _find_free_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
        minimum_available=len(busy_by_user),
        require_exact_absent_count=0,
        preferred_times=preferred_times,
    )
    full_slots = _filter_out_blocked(full_slots, blocked_dates)
    full_slots = _matching_preference_slots(full_slots)
    if full_slots and (
        not normalized_preferred_times or len(full_slots) >= minimum_preferred_slots
    ):
        state["calendar_strategy"] = "all_members_available"
        return full_slots

    n_minus_one_slots = _find_free_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
        minimum_available=max(len(busy_by_user) - 1, 1),
        require_exact_absent_count=1 if len(busy_by_user) > 1 else 0,
        preferred_times=preferred_times,
    )
    n_minus_one_slots = _filter_out_blocked(n_minus_one_slots, blocked_dates)
    n_minus_one_slots = _matching_preference_slots(n_minus_one_slots)
    if n_minus_one_slots and (
        not normalized_preferred_times or len(n_minus_one_slots) >= minimum_preferred_slots
    ):
        state["calendar_strategy"] = "n_minus_one"
        return n_minus_one_slots

    extended_time_max = time_max + timedelta(days=14 if normalized_preferred_times else 7)
    refreshed_busy_by_user: dict[str, list[dict[str, Any]]] = {}
    for user in consenting_users:
        refreshed_busy_by_user[_user_calendar_key(user)] = await _get_user_busy_periods(
            user,
            time_min,
            extended_time_max,
            db,
        )

    extended_full_slots = _find_free_slots(
        busy_by_user=refreshed_busy_by_user,
        time_min=time_min,
        time_max=extended_time_max,
        minimum_available=len(refreshed_busy_by_user),
        require_exact_absent_count=0,
        preferred_times=preferred_times,
    )
    extended_full_slots = _filter_out_blocked(extended_full_slots, blocked_dates)
    extended_full_slots = _matching_preference_slots(extended_full_slots)
    if extended_full_slots and (
        not normalized_preferred_times or len(extended_full_slots) >= minimum_preferred_slots
    ):
        state["calendar_strategy"] = "all_members_available_extended"
        return extended_full_slots

    final_slots = _find_free_slots(
        busy_by_user=refreshed_busy_by_user,
        time_min=time_min,
        time_max=extended_time_max,
        minimum_available=max(len(refreshed_busy_by_user) - 1, 1),
        require_exact_absent_count=1 if len(refreshed_busy_by_user) > 1 else 0,
        preferred_times=preferred_times,
    )
    final_slots = _filter_out_blocked(final_slots, blocked_dates)
    final_slots = _matching_preference_slots(final_slots)
    if normalized_preferred_times and len(final_slots) < minimum_preferred_slots:
        matching_slots: list[dict[str, Any]] = []
        seen_matching_start_ats: set[str] = set()
        for slot in extended_full_slots + final_slots:
            start_at = slot.get("start_at")
            if isinstance(start_at, str) and start_at not in seen_matching_start_ats:
                seen_matching_start_ats.add(start_at)
                matching_slots.append(slot)

        fallback_slots = _find_free_slots(
            busy_by_user=refreshed_busy_by_user,
            time_min=time_min,
            time_max=extended_time_max,
            minimum_available=max(len(refreshed_busy_by_user) - 1, 1),
            require_exact_absent_count=1 if len(refreshed_busy_by_user) > 1 else 0,
            preferred_times=preferred_times,
        )
        fallback_slots = _filter_out_blocked(fallback_slots, blocked_dates)
        fallback_slots = _matching_preference_slots(fallback_slots)
        final_slots = matching_slots + [
            slot for slot in fallback_slots
            if slot.get("start_at") not in seen_matching_start_ats
        ]
        final_slots.sort(
            key=lambda slot: (
                -_preference_score_for_start(
                    datetime.fromisoformat(str(slot.get("start_at"))).astimezone(KST),
                    normalized_preferred_times,
                ),
                str(slot.get("start_at")),
            )
        )

    if final_slots:
        state["calendar_strategy"] = "n_minus_one_extended"
    return final_slots


def _build_multi_date_slots(
    state: GraphState,
    busy_by_user: Optional[dict[str, list[dict[str, Any]]]] = None,
) -> list[dict[str, Any]]:
    """여러 날짜 힌트로부터 투표용 슬롯을 생성합니다.
    busy_by_user가 주어지면 멤버 GCal busy를 라벨/카운트에 반영하고 전원 불참 슬롯은 skip
    (b56aa4b _build_preference_time_slots 패턴 재사용)."""
    date_hints = state.get("date_hints") or []
    now_kst = datetime.now(KST)
    slots: list[dict[str, Any]] = []
    preferred_times = _normalize_preferred_times(state.get("preference_common_times"))
    headcount_total = state.get("headcount") or 0

    for index, hint in enumerate(date_hints, start=1):
        target_date: datetime | None = None

        # ISO date (YYYY-MM-DD)
        if _is_specific_iso_date(hint):
            try:
                target_date = datetime.strptime(hint, "%Y-%m-%d").replace(tzinfo=KST)
            except ValueError:
                pass
        else:
            # Try fallback natural date parsing (synchronous)
            parsed = _fallback_parse_natural_date(hint, now_kst)
            if parsed and parsed.get("date"):
                try:
                    target_date = datetime.strptime(parsed["date"], "%Y-%m-%d").replace(tzinfo=KST)
                except ValueError:
                    pass

        if target_date is None:
            continue

        start_hour = 14
        end_hour = 17
        is_weekend = target_date.weekday() >= 5
        for pref_time in preferred_times:
            if pref_time.startswith("평일") and is_weekend:
                continue
            if pref_time.startswith("주말") and not is_weekend:
                continue
            pref_range = PREFERRED_TIME_RANGES[pref_time]
            start_hour, end_hour = pref_range
            break

        end_of_pref = target_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        # 오늘 + 현재 시각이 선호 시간대 시작 이후면 now+1h로 시작 (즉시 약속 UX).
        # 1시간짜리 슬롯이 선호 시간대 안에 못 들어가면 오늘 후보 스킵.
        if target_date.date() == now_kst.date() and now_kst.hour >= start_hour:
            bumped = (now_kst + timedelta(hours=1)).replace(second=0, microsecond=0)
            if bumped + timedelta(minutes=SLOT_MINUTES) > end_of_pref:
                continue
            start_at = bumped
        else:
            start_at = target_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end_at = min(start_at + timedelta(minutes=SLOT_MINUTES), end_of_pref)
        holiday = _get_korean_holiday(target_date)

        # F-8 v2 후속 #2 (2026-05-08): GCal busy 정밀 반영 — b56aa4b _build_preference_time_slots 패턴.
        unavailable: list[str] = []
        if busy_by_user:
            for user_key, busy_periods in busy_by_user.items():
                if _is_busy_during(busy_periods, start_at, end_at):
                    unavailable.append(_user_display_name(user_key))
            # 모두 못 가는 슬롯 skip — 의미 없는 추천 회피
            if len(unavailable) == len(busy_by_user):
                continue

        slots.append({
            "slot_id": f"date-option-{index}",
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "label": _format_slot_label(start_at, unavailable),
            "available_count": max(headcount_total - len(unavailable), 0) if headcount_total else None,
            "total_count": headcount_total or None,
            "has_conflict": bool(unavailable),
            "unavailable_users": unavailable,
            "is_holiday": bool(holiday),
            "holiday_name": holiday,
            "is_weekend": _is_weekend(target_date),
        })

    return slots


def _is_busy_during(
    busy_periods: list[dict[str, Any]],
    start_at: datetime,
    end_at: datetime,
) -> bool:
    """슬롯 [start_at, end_at)이 busy_periods 어느 항목과 겹치면 True.
    busy_periods 항목은 {"start": datetime, "end": datetime} 형식 (aware UTC가 일반).
    문자열로 들어오는 경우도 _parse_iso_datetime로 안전하게 변환."""
    for period in busy_periods:
        ps = period.get("start")
        pe = period.get("end")
        if isinstance(ps, str):
            ps = _parse_iso_datetime(ps)
        if isinstance(pe, str):
            pe = _parse_iso_datetime(pe)
        if not isinstance(ps, datetime) or not isinstance(pe, datetime):
            continue
        # aware/naive 정렬: slot은 KST aware, busy도 보통 aware. naive면 UTC 가정.
        if ps.tzinfo is None:
            ps = ps.replace(tzinfo=timezone.utc)
        if pe.tzinfo is None:
            pe = pe.replace(tzinfo=timezone.utc)
        if ps < end_at and pe > start_at:
            return True
    return False


def _build_preference_time_slots(
    state: GraphState, pref_times: list[str],
    blocked_dates: Optional[set[str]] = None,
    busy_by_user: Optional[dict[str, list[dict[str, Any]]]] = None,
) -> list[dict[str, Any]]:
    """선호 시간대 기반으로 이번 주/다음 주 투표용 슬롯을 생성합니다.
    blocked_dates에 있는 날짜는 애초에 생성하지 않음 (뒤에서 잘라내면 5개 미만 위험).
    busy_by_user가 주어지면 각 슬롯이 멤버 GCal busy와 겹치는지 검사해 라벨/카운트에 반영
    (전원 불참 슬롯은 skip). None/빈 dict면 기존 fallback 동작 유지."""
    now_kst = datetime.now(KST)
    slots: list[dict[str, Any]] = []
    slot_index = 0
    _blocked = blocked_dates or set()
    normalized_pref_times = _normalize_preferred_times(pref_times)
    headcount_total = state.get("headcount") or 0

    # 오늘 포함 향후 4주 — 오늘은 현재 시각 + 1h 룰로 즉시 약속 가능.
    for day_offset in range(0, 29):
        target = now_kst + timedelta(days=day_offset)
        weekday = target.weekday()  # 0=월 6=일
        is_weekend = weekday >= 5
        if target.strftime("%Y-%m-%d") in _blocked:
            continue

        for pref_time in normalized_pref_times:
            # 평일/주말 필터
            if pref_time.startswith("평일") and is_weekend:
                continue
            if pref_time.startswith("주말") and not is_weekend:
                continue

            hours = PREFERRED_TIME_RANGES.get(pref_time)
            if not hours:
                continue

            start_h, end_h = hours
            end_of_pref = target.replace(hour=end_h, minute=0, second=0, microsecond=0)
            # 오늘 + 현재 시각이 선호 시간대 시작 이후면 now+1h로 시작.
            if target.date() == now_kst.date() and now_kst.hour >= start_h:
                bumped = (now_kst + timedelta(hours=1)).replace(second=0, microsecond=0)
                if bumped + timedelta(minutes=SLOT_MINUTES) > end_of_pref:
                    continue
                start_at = bumped
            else:
                start_at = target.replace(hour=start_h, minute=0, second=0, microsecond=0)
            end_at = min(start_at + timedelta(minutes=SLOT_MINUTES), end_of_pref)

            # 과거 시간 건너뛰기 (안전망 — 위 로직이 보통 차단)
            if start_at <= now_kst:
                continue

            holiday = _get_korean_holiday(target)

            unavailable: list[str] = []
            if busy_by_user:
                for user_key, busy_periods in busy_by_user.items():
                    if _is_busy_during(busy_periods, start_at, end_at):
                        unavailable.append(_user_display_name(user_key))
                # 모두 못 가는 슬롯 skip — 의미 없는 추천 회피
                if len(unavailable) == len(busy_by_user):
                    continue

            slot_index += 1
            slots.append({
                "slot_id": f"pref-slot-{slot_index}",
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "label": _format_slot_label(start_at, unavailable),
                "available_count": max(headcount_total - len(unavailable), 0) if headcount_total else None,
                "total_count": headcount_total or None,
                "has_conflict": bool(unavailable),
                "unavailable_users": unavailable,
                "is_holiday": bool(holiday),
                "holiday_name": holiday,
                "is_weekend": is_weekend,
            })

            if len(slots) >= 5:
                break
        if len(slots) >= 5:
            break

    # 최소 3개 슬롯 보장: 선호 시간대가 좁아서 슬롯이 부족하면 같은 시간 창에서 보강
    if len(slots) < 3 and normalized_pref_times:
        fallback_pref = normalized_pref_times[0]
        fallback_hours = PREFERRED_TIME_RANGES[fallback_pref]
        for day_offset in range(1, 29):
            if len(slots) >= 3:
                break
            target = now_kst + timedelta(days=day_offset)
            date_str = target.strftime("%Y-%m-%d")
            if date_str in _blocked:
                continue
            is_weekend = target.weekday() >= 5
            if fallback_pref.startswith("평일") and is_weekend:
                continue
            if fallback_pref.startswith("주말") and not is_weekend:
                continue
            start_at = target.replace(hour=fallback_hours[0], minute=0, second=0, microsecond=0)
            if start_at <= now_kst:
                continue
            end_at = min(
                start_at + timedelta(minutes=SLOT_MINUTES),
                target.replace(hour=fallback_hours[1], minute=0, second=0, microsecond=0),
            )
            # 중복 날짜 체크
            existing_dates = {s["start_at"][:10] for s in slots}
            if date_str in existing_dates:
                continue
            holiday = _get_korean_holiday(target)

            unavailable: list[str] = []
            if busy_by_user:
                for user_key, busy_periods in busy_by_user.items():
                    if _is_busy_during(busy_periods, start_at, end_at):
                        unavailable.append(_user_display_name(user_key))
                if len(unavailable) == len(busy_by_user):
                    continue

            slot_index += 1
            slots.append({
                "slot_id": f"pref-slot-{slot_index}",
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "label": _format_slot_label(start_at, unavailable),
                "available_count": max(headcount_total - len(unavailable), 0) if headcount_total else None,
                "total_count": headcount_total or None,
                "has_conflict": bool(unavailable),
                "unavailable_users": unavailable,
                "is_holiday": bool(holiday),
                "holiday_name": holiday,
                "is_weekend": target.weekday() >= 5,
            })

    return slots[:5]
