"""방 멤버 선호도 + personal data lookup.

원본 위치: langgraph_pipeline.py 라인 1464~1581 (_load_social_context),
  1938~1980 (_get_room_member_food_preferences),
  1983~2051 (_get_room_member_constraints),
  2054~2078 (_build_group_constraints_summary),
  2081~2147 (_get_room_member_constraints_named),
  2150~2217 (_build_named_constraints_summary),
  2220~2317 (_load_meeting_preferences).

Phase 3 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

의존:
  - state.GraphState
  - constants: _SOCIAL_RECENT_LIMIT, _SOCIAL_SUMMARY_THRESHOLD
  - formatting._room_id_as_int
  - slot_state._normalize_preferred_times
  - app.models: ChatMessage, PaneType, MeetingPreference, RoomMember, User
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.models.chat import ChatMessage, PaneType
from app.models.meeting_preference import MeetingPreference
from app.models.room import RoomMember
from app.models.user import User
from app.services.gemini import call_gemini
from app.services.pipeline.constants import _SOCIAL_RECENT_LIMIT, _SOCIAL_SUMMARY_THRESHOLD
from app.services.pipeline.helpers.formatting import _room_id_as_int
from app.services.pipeline.helpers.slot_state import _normalize_preferred_times
from app.services.pipeline.state import GraphState

logger = logging.getLogger(__name__)


async def _load_social_context(
    db: AsyncSession, room_pk: Optional[int]
) -> tuple[list[str], str]:
    """방의 소셜 채팅 최근 N개 + 더 오래된 메시지가 충분하면 Redis-캐시된 요약을 반환.
    실패해도 pipeline은 계속 — 빈 값 반환."""
    if room_pk is None:
        return [], ""
    try:
        result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.room_id == room_pk,
                ChatMessage.pane_type == PaneType.social,
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(_SOCIAL_RECENT_LIMIT)
        )
        recent_rows = list(reversed(result.scalars().all()))
    except Exception:
        logger.debug("social recent load failed room=%s", room_pk, exc_info=True)
        return [], ""

    recent_lines = [
        f"{m.sender or '익명'}: {m.content}"
        for m in recent_rows if m.content and m.content.strip()
    ]

    summary = ""
    try:
        total_result = await db.execute(
            select(sa_func.count())
            .select_from(ChatMessage)
            .where(
                ChatMessage.room_id == room_pk,
                ChatMessage.pane_type == PaneType.social,
            )
        )
        total = int(total_result.scalar() or 0)
    except Exception:
        total = 0

    if total >= _SOCIAL_SUMMARY_THRESHOLD and recent_rows:
        # Redis 캐시: last_id 기준으로 10개 이상 밀렸을 때만 재생성.
        # P0 fix (2026-05-16 review): try/finally로 감싸서 connection leak 차단.
        #   이전엔 call_gemini(중간 라인)에서 예외 던지면 r.aclose() 호출 안 됨 → pool 고갈.
        r = None
        try:
            try:
                r = aioredis.from_url(
                    settings.REDIS_URL, decode_responses=True,
                    socket_connect_timeout=1, socket_timeout=1,
                )
            except Exception:
                r = None

            cache_key = f"social_summary:{room_pk}"
            oldest_recent_id = recent_rows[0].id or 0
            cached = None
            if r is not None:
                try:
                    raw = await r.get(cache_key)
                    if raw:
                        cached = json.loads(raw)
                except Exception:
                    cached = None

            if (
                cached
                and isinstance(cached, dict)
                and cached.get("summary")
                and int(cached.get("boundary_id") or 0) >= oldest_recent_id
            ):
                summary = str(cached["summary"]).strip()
            else:
                # 최근 N개보다 오래된 메시지를 모아 요약.
                try:
                    older_res = await db.execute(
                        select(ChatMessage)
                        .where(
                            ChatMessage.room_id == room_pk,
                            ChatMessage.pane_type == PaneType.social,
                            ChatMessage.id < oldest_recent_id,
                        )
                        .order_by(ChatMessage.created_at)
                    )
                    older = older_res.scalars().all()
                except Exception:
                    older = []

                joined = "\n".join(
                    f"{m.sender or '익명'}: {m.content}"
                    for m in older
                    if m.content and m.content.strip()
                )
                if joined.strip():
                    prompt = (
                        "다음은 모임 채팅방의 과거 대화입니다. 합의/진행 중인 결정/"
                        "멤버 선호·불만을 3줄 이내로 간결히 요약하세요. 가십 제외.\n\n"
                        f"{joined}"
                    )
                    try:
                        summary = (await call_gemini(prompt) or "").strip()
                    except Exception:
                        summary = ""

                if r is not None and summary:
                    try:
                        await r.setex(
                            cache_key,
                            6 * 3600,
                            json.dumps({"summary": summary, "boundary_id": oldest_recent_id}),
                        )
                    except Exception:
                        pass
        finally:
            if r is not None:
                try:
                    await r.aclose()
                except Exception:
                    pass

    return recent_lines, summary


async def _get_room_member_food_preferences(state: GraphState) -> list[str]:
    """비선호 음식 목록을 반환합니다. meeting_preferences 우선, 없으면 User 프로필 사용."""
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    if room_pk is None:
        return []

    # 1. meeting_preferences에서 비선호 음식 로드 (팝업 데이터)
    pref_result = await db.execute(
        select(MeetingPreference).where(MeetingPreference.room_id == room_pk)
    )
    prefs = pref_result.scalars().all()

    disliked_foods: list[str] = []
    seen: set[str] = set()

    if prefs:
        for pref in prefs:
            for item in pref.disliked_foods or []:
                normalized = str(item).strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    disliked_foods.append(normalized)
        if disliked_foods:
            return disliked_foods

    # 2. fallback: User 프로필의 food_restrictions (식이 제한 — 비선호와 시맨틱 일치)
    #    Fix (2026-05-20): 이전 코드는 food_preferences(선호)를 disliked_foods에 append →
    #      "한식 선호"가 "한식 제거"로 동작하던 모순 수정.
    member_result = await db.execute(select(RoomMember).where(RoomMember.room_id == room_pk))
    members = member_result.scalars().all()
    user_ids = [member.user_id for member in members]
    if not user_ids:
        return []

    user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = user_result.scalars().all()

    for user in users:
        for item in user.food_restrictions or []:
            normalized = str(item).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                disliked_foods.append(normalized)
    return disliked_foods


async def _get_room_member_constraints(state: GraphState) -> dict[str, list[str]]:
    """모임 멤버 전체의 6 카테고리 personal data를 합성.

    프라이버시 모델 (디자인 P1, P2): 누가 어떤 값을 가지는지 식별 가능한 형태로
    반환하지 않음. 모든 멤버의 값을 union해서 익명 합산만 노출. 호출자는 이걸
    Gemini prompt에 컨텍스트로 넘기거나 reasoning summary 합성에 쓴다.

    반환 dict의 키는 6 카테고리 이름. 값은 누적 string list (deduplicated).
    time_preference / transport_mode는 단일 string 칼럼이지만 멤버별로 다를 수
    있으므로 list로 모음.
    """
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    empty: dict[str, list[str]] = {
        "food_restrictions": [],
        "food_preferences": [],
        "liked_areas": [],
        "disliked_areas": [],
        "time_preference": [],
        "transport_mode": [],
    }
    if room_pk is None:
        return empty

    member_result = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room_pk)
    )
    members = member_result.scalars().all()
    user_ids = [member.user_id for member in members]
    if not user_ids:
        return empty

    user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = user_result.scalars().all()

    constraints: dict[str, list[str]] = {k: [] for k in empty}
    seen: dict[str, set[str]] = {k: set() for k in empty}

    def _push(category: str, value: str) -> None:
        v = str(value or "").strip()
        if not v or v in seen[category]:
            return
        seen[category].add(v)
        constraints[category].append(v)

    for user in users:
        # QuickPreferences 토글 respect — OFF면 해당 카테고리 skip.
        # opt-out 모델이므로 None이면 True로 간주 (기존 row backfill 안 됐어도 안전).
        share_food = bool(getattr(user, "share_food_data", True) if getattr(user, "share_food_data", True) is not None else True)
        share_location = bool(getattr(user, "share_location_data", True) if getattr(user, "share_location_data", True) is not None else True)
        share_schedule = bool(getattr(user, "share_schedule_data", True) if getattr(user, "share_schedule_data", True) is not None else True)

        if share_food:
            for item in user.food_restrictions or []:
                _push("food_restrictions", str(item))
            for item in user.food_preferences or []:
                _push("food_preferences", str(item))
        if share_location:
            for item in user.liked_areas or []:
                _push("liked_areas", str(item))
            for item in user.disliked_areas or []:
                _push("disliked_areas", str(item))
        if share_schedule:
            if user.time_preference:
                _push("time_preference", user.time_preference)
            if user.transport_mode:
                _push("transport_mode", user.transport_mode)

    return constraints


def _build_group_constraints_summary(constraints: dict[str, list[str]]) -> str:
    """추천 reasoning에 붙는 익명 group constraint 요약 (디자인 P2 가운데 톤).

    Count 없음, 누구인지도 없음. 멤버 수가 0이면 빈 문자열.
    예: "모임 멤버 중 갑각류 회피 / 강남 회피 / 대중교통 선호 고려"
    """
    parts: list[str] = []
    if constraints.get("food_restrictions"):
        joined = ", ".join(constraints["food_restrictions"])
        parts.append(f"{joined} 회피")
    if constraints.get("disliked_areas"):
        joined = ", ".join(constraints["disliked_areas"])
        parts.append(f"{joined} 지역 회피")
    if constraints.get("liked_areas"):
        joined = ", ".join(constraints["liked_areas"])
        parts.append(f"{joined} 지역 선호")
    if constraints.get("time_preference"):
        joined = " · ".join(constraints["time_preference"])
        parts.append(f"선호 시간대: {joined}")
    if constraints.get("transport_mode"):
        joined = ", ".join(constraints["transport_mode"])
        parts.append(f"이동수단: {joined}")
    if not parts:
        return ""
    return "모임 멤버 중 " + " / ".join(parts) + " 고려"


async def _get_room_member_constraints_named(state: GraphState) -> list[dict[str, Any]]:
    """해결점 A5-2: per-user constraints with name. 강도순 차등 처리용.

    공유 토글(share_food/location/schedule_data) 존중. 토글 OFF면 해당 카테고리 빈 값.
    이름이 없는 user는 제외. 빈 entry(어떤 값도 없는)도 제외.
    """
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    if room_pk is None:
        return []

    member_result = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room_pk)
    )
    members = member_result.scalars().all()
    user_ids = [member.user_id for member in members]
    if not user_ids:
        return []

    user_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = user_result.scalars().all()

    per_user: list[dict[str, Any]] = []
    for user in users:
        name = (getattr(user, "name", None) or "").strip()
        if not name:
            continue

        share_food = bool(
            getattr(user, "share_food_data", True)
            if getattr(user, "share_food_data", True) is not None
            else True
        )
        share_location = bool(
            getattr(user, "share_location_data", True)
            if getattr(user, "share_location_data", True) is not None
            else True
        )
        share_schedule = bool(
            getattr(user, "share_schedule_data", True)
            if getattr(user, "share_schedule_data", True) is not None
            else True
        )

        food_restrictions = list(user.food_restrictions or []) if share_food else []
        food_preferences = list(user.food_preferences or []) if share_food else []
        liked_areas = list(user.liked_areas or []) if share_location else []
        disliked_areas = list(user.disliked_areas or []) if share_location else []
        time_preference = user.time_preference if share_schedule else None
        transport_mode = user.transport_mode if share_schedule else None

        if not any([
            food_restrictions, food_preferences, liked_areas, disliked_areas,
            time_preference, transport_mode,
        ]):
            continue

        per_user.append({
            "name": name,
            "food_restrictions": food_restrictions,
            "food_preferences": food_preferences,
            "liked_areas": liked_areas,
            "disliked_areas": disliked_areas,
            "time_preference": time_preference,
            "transport_mode": transport_mode,
        })
    return per_user


def _build_named_constraints_summary(per_user: list[dict[str, Any]]) -> str:
    """해결점 A5-2: 이름 인용 + 강도순 차등 reasoning summary.

    - 강 (food_restrictions, disliked_areas) → 이름 명시 + ✨
    - 중 (food_preferences) → 이름 명시 (강한 제약 없는 멤버 한정)
    - 약 (liked_areas, time_preference, transport_mode) → 익명 합산
    - 같은 강도에 3명 이상이면 "외 N명" 표기

    예: "수현님 채식·홍대 비선호 ✨ + 다른 멤버 매운맛 선호 반영"
    """
    if not per_user:
        return ""

    # 강한 제약: food_restrictions / disliked_areas.
    # food_restrictions와 disliked_areas는 의미가 다르므로(식단 제약 vs 지역 회피)
    # 분리해서 표기 — "수현님 채식 비선호"처럼 의미 반전 방지.
    strong_phrases: list[str] = []
    strong_names: set[str] = set()
    for u in per_user:
        bits: list[str] = []
        if u.get("food_restrictions"):
            bits.append(f"{', '.join(u['food_restrictions'])} 식단")
        if u.get("disliked_areas"):
            bits.append(f"{', '.join(u['disliked_areas'])} 비선호")
        if bits:
            strong_phrases.append(f"{u['name']}님 " + " · ".join(bits))
            strong_names.add(u["name"])

    # 중간: food_preferences (강한 제약 가진 멤버는 제외)
    mid_phrases: list[str] = []
    for u in per_user:
        if u["name"] in strong_names:
            continue
        if u.get("food_preferences"):
            mid_phrases.append(f"{u['name']}님 {'·'.join(u['food_preferences'])} 선호")

    # 약한 선호: liked_areas, time_preference, transport_mode (익명 합산)
    liked = sorted({a for u in per_user for a in (u.get("liked_areas") or [])})
    times = sorted({
        u["time_preference"] for u in per_user if u.get("time_preference")
    })
    trans = sorted({
        u["transport_mode"] for u in per_user if u.get("transport_mode")
    })
    weak_pieces: list[str] = []
    if liked:
        weak_pieces.append(f"{', '.join(liked)} 선호 지역")
    if times:
        weak_pieces.append(f"선호 시간 {', '.join(times)}")
    if trans:
        weak_pieces.append(f"이동수단 {', '.join(trans)}")

    def _join_named(phrases: list[str], marker: str = "") -> str:
        if len(phrases) <= 2:
            return " + ".join(phrases) + marker
        return " + ".join(phrases[:2]) + f" 외 {len(phrases) - 2}명" + marker

    parts: list[str] = []
    if strong_phrases:
        parts.append(_join_named(strong_phrases, " ✨"))
    if mid_phrases:
        parts.append(_join_named(mid_phrases))
    if weak_pieces:
        parts.append("다른 멤버 " + " / ".join(weak_pieces))

    if not parts:
        return ""
    return " · ".join(parts) + " 반영"


async def _load_meeting_preferences(state: GraphState) -> dict[str, Any]:
    """meeting_preferences 테이블에서 모임별 선호 정보를 로드하고 집계합니다.

    Returns:
        {
            "has_preferences": bool,
            "all_submitted": bool,
            "total_members": int,
            "submitted_count": int,
            "best_location": str | None,       # 다수결 장소
            "common_times": list[str],          # 교차 시간대
            "all_disliked_foods": list[str],    # 모든 비선호 음식
            "all_preferred_foods": list[str],   # 모든 선호 음식
            "notes": list[str],                 # 메모들
        }
    """
    db = state["db"]
    room_pk = _room_id_as_int(state["room_id"])
    if room_pk is None:
        return {"has_preferences": False, "all_submitted": False}

    # 멤버 수
    member_result = await db.execute(select(RoomMember).where(RoomMember.room_id == room_pk))
    members = member_result.scalars().all()
    total_members = len(members)

    # 선호 정보 로드
    pref_result = await db.execute(
        select(MeetingPreference).where(MeetingPreference.room_id == room_pk)
    )
    prefs = pref_result.scalars().all()

    if not prefs:
        return {
            "has_preferences": False,
            "all_submitted": False,
            "total_members": total_members,
            "submitted_count": 0,
        }

    # 장소 다수결
    location_counts: dict[str, int] = {}
    for p in prefs:
        loc = (p.preferred_location or "").strip()
        if loc:
            location_counts[loc] = location_counts.get(loc, 0) + 1
    best_location = max(location_counts, key=location_counts.get) if location_counts else None

    # 시간대 교차 (모든 멤버가 공통으로 선택한 시간대)
    time_sets = [
        set(_normalize_preferred_times(p.preferred_times))
        for p in prefs
        if _normalize_preferred_times(p.preferred_times)
    ]
    if time_sets:
        common_times = list(time_sets[0].intersection(*time_sets[1:]))
        if not common_times:
            # 교차 없으면 가장 많이 선택된 시간대 상위 3개
            time_counts: dict[str, int] = {}
            for p in prefs:
                for t in _normalize_preferred_times(p.preferred_times):
                    time_counts[t] = time_counts.get(t, 0) + 1
            common_times = sorted(time_counts, key=time_counts.get, reverse=True)[:3]
    else:
        common_times = []

    # 비선호 음식 합집합
    all_disliked: list[str] = []
    seen_disliked: set[str] = set()
    for p in prefs:
        for food in p.disliked_foods or []:
            if food not in seen_disliked:
                seen_disliked.add(food)
                all_disliked.append(food)

    # 선호 음식 합집합
    all_preferred: list[str] = []
    seen_preferred: set[str] = set()
    for p in prefs:
        for food in p.preferred_foods or []:
            if food not in seen_preferred:
                seen_preferred.add(food)
                all_preferred.append(food)

    # 메모 수집
    notes = [p.note for p in prefs if p.note and p.note.strip()]

    return {
        "has_preferences": True,
        "all_submitted": len(prefs) >= total_members,
        "total_members": total_members,
        "submitted_count": len(prefs),
        "best_location": best_location,
        "common_times": common_times,
        "all_disliked_foods": all_disliked,
        "all_preferred_foods": all_preferred,
        "notes": notes,
    }
