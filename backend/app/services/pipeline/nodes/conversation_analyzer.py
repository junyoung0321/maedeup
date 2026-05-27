"""_analyze_conversation + suggest_alternative_slots — graph 외부에서 호출되는 함수들.

원본 위치: langgraph_pipeline.py 라인 5042~5207 (_analyze_conversation),
  5210~5301 (suggest_alternative_slots).

Phase 4 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

특이사항:
  - `_analyze_conversation`은 agent.py가 외부 import 사용 (private prefix지만 외부 의존).
  - `suggest_alternative_slots`은 meetings.py가 외부 import 사용.
  - 둘 다 graph 노드는 아니지만 pipeline 안에서 관리.

의존:
  - constants.settings (GOOGLE_CLIENT_ID)
  - helpers.json_extract._extract_json_object
  - helpers.formatting._user_calendar_key
  - helpers.slots._get_user_busy_periods, _find_free_slots
  - app.services.gemini.call_gemini
  - app.models: ChatMessage, PaneType, RoomMember, User
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.models.chat import ChatMessage, PaneType
from app.models.room import RoomMember
from app.models.user import User
from app.services.gemini import call_gemini
from app.services.pipeline.helpers.formatting import _user_calendar_key
from app.services.pipeline.helpers.json_extract import _extract_json_object
from app.services.pipeline.helpers.slots import (
    _find_free_slots,
    _get_user_busy_periods,
)

logger = logging.getLogger(__name__)

_CONV_CACHE_TTL = 300  # 5분


def _build_conv_cache_key(room_id: str, last_message_id: int) -> str:
    return f"maedeup:conv_cache:{room_id}:{last_message_id}"


async def _analyze_conversation(
    room_id: str,
    db: AsyncSession,
    today_kst: str,
    redis_client: Optional[Any] = None,
) -> dict[str, Any] | None:
    """최근 소셜 채팅에서 카드 표시 정보와 파이프라인 신호를 한 번에 추출합니다."""
    try:
        room_pk = int(room_id)
    except (TypeError, ValueError):
        return None

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.room_id == room_pk)
        .where(ChatMessage.pane_type == PaneType.social)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(50)
    )
    recent_messages = list(reversed(result.scalars().all()))

    if not recent_messages:
        return None

    # Redis 캐싱: last_message_id 기반으로 cache hit 시 Gemini 호출 skip.
    last_msg_id: int = recent_messages[-1].id
    cache_key = _build_conv_cache_key(room_id, last_msg_id)
    if redis_client is not None:
        try:
            cached_raw = await redis_client.get(cache_key)
            if cached_raw is not None:
                cached = json.loads(cached_raw)
                logger.info("[conv_cache] HIT room=%s last_msg=%d", room_id, last_msg_id)
                return cached
        except (TypeError, ValueError, AttributeError, NameError) as exc:
            raise
        except Exception:
            logger.warning("[conv_cache] GET failed room=%s, falling through", room_id, exc_info=True)

    conversation = "\n".join(
        f"{msg.sender or msg.role}: {msg.content.strip()}"
        for msg in recent_messages
        if msg.content and msg.content.strip()
    )

    if not conversation:
        return None

    prompt = (
        "당신은 매듭 AI입니다. 한국인들의 모임 조율 대화를 분석합니다.\n"
        f"오늘 날짜는 {today_kst}입니다.\n"
        "아래 대화에서 카드 표시용 요약(card)과 파이프라인 신호(signals)를 한 번에 추출하세요.\n"
        "반드시 JSON 객체만 출력하고, 다른 텍스트는 포함하지 마세요.\n"
        "정보가 없는 필드는 null 또는 빈 배열로 채우세요.\n\n"
        "출력 형식:\n"
        "{\n"
        '  "card": {\n'
        '    "date": "자연어 날짜/시간 요약 또는 null (예: \"이번 주 금/토/일 거부됨\")",\n'
        '    "place": "표시용 장소 또는 null",\n'
        '    "headcount": "표시용 인원 또는 null",\n'
        '    "type": "모임 유형(식사/카페/술 등) 또는 null",\n'
        '    "notes": ["멤버별 거부/선호 사실만 1-3개 bullet (결론·일반화 금지)"]\n'
        "  },\n"
        '  "signals": {\n'
        '    "date_hint": "YYYY-MM-DD 또는 YYYY-MM-DD~YYYY-MM-DD 또는 null",\n'
        '    "date_hints": ["YYYY-MM-DD"],\n'
        '    "preferred_dates": [{"date": "YYYY-MM-DD"}],\n'
        '    "rejected_dates": ['
        '{"date": "YYYY-MM-DD", "user": "발신자 또는 null", "reason": "거부 이유 또는 null"}'
        "],\n"
        '    "accepted_dates": ['
        '{"date": "YYYY-MM-DD", "user": "발신자 또는 null"}'
        "],\n"
        '    "place_hint": "구체적 장소 힌트 또는 null",\n'
        '    "headcount": 0,\n'
        '    "meeting_type": "모임 유형 또는 null",\n'
        '    "conflict_detected": false,\n'
        '    "conflict_type": "date 또는 place 또는 time 또는 null",\n'
        '    "conflict_options": ["충돌 선택지"],\n'
        '    "conflict_users": ["충돌 사용자"],\n'
        '    "parsed_time_hint": "시간 표현 또는 null",\n'
        '    "date_is_flexible": false,\n'
        '    "date_hint_source_text": "원문 날짜 표현 또는 null"\n'
        "  }\n"
        "}\n\n"
        "signals 작성 규칙:\n"
        "- 날짜는 가능하면 ISO 형식(YYYY-MM-DD)으로 변환하세요. 요일만 언급되면 오늘 이후 가장 가까운 미래 날짜로 변환하세요.\n"
        "- date_hints는 여러 날짜 선택지가 있을 때 모두 담고, preferred_dates는 가능/선호로 표현된 날짜를 담으세요.\n"
        "- **card에 자연어로 적은 모든 날짜 표현은 signals에 ISO로 반드시 변환해 담을 것.** card.date/notes만 채우고\n"
        "  signals.preferred_dates 또는 signals.date_hints를 비워두면 후속 슬롯 빌드가 실패함.\n"
        "  preferred_dates 각 항목은 반드시 `{\"date\": \"YYYY-MM-DD\"}` dict 형태. plain string array 금지.\n"
        "  예: card.date='다음 주 평일에 대안 모색' → signals.preferred_dates=[{\"date\":\"2026-05-11\"}, {\"date\":\"2026-05-12\"}, ...] (다음 주 월~금 ISO 5개).\n"
        "  예: card.date='5/12 화요일 저녁으로 좁혀짐' → signals.date_hint='2026-05-12'.\n"
        "- 거부된 날짜는 rejected_dates에만, 가능/선호 날짜는 preferred_dates에. 서로 배타.\n"
        "[필드 의미 구분 - 반드시 따를 것]\n\n"
        "rejected_dates: 어떤 사람이라도 다음 거부 표현을 명시적으로 사용한 날짜.\n"
        "  거부 키워드: \"안 돼\", \"못 가\", \"힘들어\", \"불가능\", \"어려워\", \"패스\", \"어렵다\"\n"
        "  - 한 명이라도 거부하면 무조건 여기. 다른 사람의 선호와 충돌하더라도 거부 우선.\n"
        "  - 단순한 미언급/무관심은 거부 아님.\n\n"
        "accepted_dates: 이전에 거부했던 날짜를 명시적으로 번복한 경우.\n"
        "  번복 키워드: \"그날 가능해\", \"일정 취소됐어\", \"괜찮아졌어\", \"다시 생각해보니\"\n"
        "  - 명시적 번복 없이 단순 재언급은 포함하지 않음.\n\n"
        "conflict_options: 서로 다른 사람이 서로 다른 날짜를 선호하지만, 누구도 거부하지 않은 옵션들만.\n"
        "  - \"A는 X를 원함\" + \"B는 Y를 원함\" + 둘 다 명시적 거부 없음 → conflict_options=[X, Y]\n"
        "  - 단 한 명이라도 어떤 옵션에 거부를 표시하면 그 날짜는 conflict_options에서 빠지고 rejected_dates로.\n\n"
        "상호 배타성:\n"
        "  - 같은 날짜가 rejected_dates와 conflict_options에 동시에 들어가면 안 됨.\n"
        "  - 충돌 시 우선순위: rejected_dates가 conflict_options를 이김.\n\n"
        "분류 예시:\n"
        "  대화1: \"금요일 좋아\" / \"금요일 안 돼\"\n"
        "    → rejected_dates=[금요일 ISO], conflict_options=[]\n\n"
        "  대화2: \"목요일이 좋아\" / \"금요일이 좋아\" (둘 다 명시적 거부 없음)\n"
        "    → rejected_dates=[], conflict_options=[\"목요일\", \"금요일\"]\n\n"
        "  대화3: \"금요일 안 돼\" / \"토요일 안 돼\"\n"
        "    → rejected_dates=[금요일 ISO, 토요일 ISO], conflict_options=[]\n\n"
        "  대화4: \"금요일 좋아\" / \"금요일도 OK인데 토요일이 더 좋아\"\n"
        "    → rejected_dates=[], conflict_options=[\"금요일\", \"토요일\"]\n"
        "- place_hint는 구체적 지명/역/동/구/장소명만 담으세요. 아무데나, 근처, 다시 추천, 장소 정하자 같은 모호한 표현은 null입니다.\n\n"
        "card 작성 가이드:\n"
        "- card.date는 \"시험 끝나고 모임\" 같은 한 줄 요약 X. **거부된 날짜 사실만** 묘사.\n"
        "  좋은 예: \"이번 주 금/토/일 거부됨\"\n"
        "  좋은 예: \"5/12 화요일로 좁혀짐\"\n"
        "  ⚠️ **card.date 에도 결론·추측 표현 금지**: \"유일한 후보\", \"~만 가능\", \"~만이 후보\",\n"
        "    \"가장 가능성 높음\", \"다음 주가 후보\" 같은 일반화·확정 표현은 사용 금지.\n"
        "    호스트 캘린더·시간 선호가 prompt에 주어지지 않아 부정확하기 때문. 거부 사실만 진술할 것.\n"
        "- card.notes는 **멤버별 거부/선호 사실만** 별도 bullet으로 분리:\n"
        "  - 거부 1건당 \"{멤버이름}: {날짜} {사유}\" 형태로 1 bullet\n"
        "  - ⚠️ **합의 흐름·결론·일반화 bullet 절대 금지** (card.date와 동일 원칙).\n"
        "  - 1~3개 bullet (멤버별 거부 사실만). 너무 많으면 카드 길어짐.\n\n"
        "전체 예시 input → output (오늘=2026-05-07 가정):\n"
        "  대화:\n"
        "    지민: 다들 시험 끝나고 한번 보자!\n"
        "    수현: 5월 8일 금요일은 동아리 MT라 안 돼\n"
        "    민수: 9일은 본가 내려가야 해서 패스\n"
        "    예린: 10일 토요일은 좀 쉬고 싶다… 다음주 어때?\n"
        "  card 출력:\n"
        "    date: \"이번 주 금/토/일 거부됨\"\n"
        "    place: null\n"
        "    headcount: null\n"
        "    type: \"회식\"\n"
        "    notes: [\n"
        "      \"수현: 5/8 동아리 MT로 불가\",\n"
        "      \"민수: 5/9 본가 일정\",\n"
        "      \"예린: 5/10 휴식 원함, 다음 주 제안\"\n"
        "    ]  // ⚠️ \"~가 후보\", \"~만 가능\" 같은 결론 bullet 추가 금지\n"
        "  signals 출력 (card에 자연어로 적은 날짜를 ISO로 변환해 짝지어 채울 것):\n"
        "    date_hint: null\n"
        "    date_hints: []\n"
        "    preferred_dates: [\n"
        "      {\"date\": \"2026-05-11\"}, {\"date\": \"2026-05-12\"}, {\"date\": \"2026-05-13\"},\n"
        "      {\"date\": \"2026-05-14\"}, {\"date\": \"2026-05-15\"}\n"
        "    ]  // 다음 주 월~금 ISO, 각 항목은 {\"date\": \"YYYY-MM-DD\"} dict 형태로\n"
        "    rejected_dates: [\n"
        "      {\"date\": \"2026-05-08\", \"user\": \"수현\", \"reason\": \"동아리 MT\"},\n"
        "      {\"date\": \"2026-05-09\", \"user\": \"민수\", \"reason\": \"본가\"},\n"
        "      {\"date\": \"2026-05-10\", \"user\": \"예린\", \"reason\": \"휴식 원함\"}\n"
        "    ]\n"
        "    accepted_dates: []\n"
        "    place_hint: null\n"
        "    headcount: 0\n"
        "    meeting_type: \"회식\"\n"
        "    conflict_detected: false\n\n"
        "    ⚠️ card.notes의 \"다음 주 제안\"이 signals.preferred_dates에 ISO 5개로 변환되어 들어가야 함.\n"
        "    signals만 비우면 슬롯 빌드 실패 + 다음주 자동 확장 발동 못 함.\n\n"
        f"대화:\n{conversation}"
    )

    raw = await call_gemini(prompt)
    if not raw:
        return None

    parsed = _extract_json_object(raw)
    if not parsed:
        logger.warning("Failed to parse unified conversation analysis JSON: %s", raw[:200])
        return None

    card = parsed.get("card")
    signals = parsed.get("signals")
    if not isinstance(card, dict) or not isinstance(signals, dict):
        return None

    conv_result: dict[str, Any] = {
        "card": {
            "date": card.get("date"),
            "place": card.get("place"),
            "headcount": card.get("headcount"),
            "type": card.get("type"),
            "notes": card.get("notes") or [],
        },
        "signals": signals,
    }

    # Redis 캐싱: 결과를 SET (TTL 300s). Redis 실패는 graceful fallback (로그만).
    if redis_client is not None:
        try:
            await redis_client.set(cache_key, json.dumps(conv_result, ensure_ascii=False), ex=_CONV_CACHE_TTL)
            logger.info("[conv_cache] SET room=%s last_msg=%d ttl=%ds", room_id, last_msg_id, _CONV_CACHE_TTL)
        except (TypeError, ValueError, AttributeError, NameError) as exc:
            raise
        except Exception:
            logger.warning("[conv_cache] SET failed room=%s", room_id, exc_info=True)

    return conv_result


async def suggest_alternative_slots(
    room_id: int,
    dissenting_user_ids: list[int],
    session: AsyncSession,
) -> dict[str, Any] | None:
    """투표 결과 만장일치가 아닐 때, 불참자 캘린더를 포함해 전원 가능한 대안 시간대를 검색합니다.

    Returns:
        전원 가능한 대안 슬롯 dict (label, start_at, end_at 등) 또는 None.
    """
    if not settings.GOOGLE_CLIENT_ID:
        return None

    # 룸 멤버 전원 조회
    member_result = await session.execute(
        select(RoomMember).where(RoomMember.room_id == room_id)
    )
    members = member_result.scalars().all()
    user_ids = [m.user_id for m in members]

    if not user_ids:
        return None

    user_result = await session.execute(
        select(User).where(
            User.id.in_(user_ids),
            User.calendar_consent == True,  # noqa: E712
        )
    )
    consenting_users = [
        user
        for user in user_result.scalars().all()
        if user.google_access_token or user.google_refresh_token
    ]

    if not consenting_users:
        return None

    now = datetime.now(timezone.utc)
    time_min = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    time_max = time_min + timedelta(days=14)

    # 전원(불참자 포함)의 busy 기간 조회
    busy_by_user: dict[str, list[dict[str, Any]]] = {}
    for user in consenting_users:
        busy_by_user[_user_calendar_key(user)] = await _get_user_busy_periods(
            user, time_min, time_max, session
        )

    if not busy_by_user:
        return None

    # 전원 가능한 슬롯만 검색 (require_exact_absent_count=0)
    full_slots = _find_free_slots(
        busy_by_user=busy_by_user,
        time_min=time_min,
        time_max=time_max,
        minimum_available=len(busy_by_user),
        require_exact_absent_count=0,
    )

    if not full_slots:
        # 14일 내 없으면 21일까지 확장
        extended_time_max = time_max + timedelta(days=7)
        for user in consenting_users:
            busy_by_user[_user_calendar_key(user)] = await _get_user_busy_periods(
                user, time_min, extended_time_max, session
            )
        full_slots = _find_free_slots(
            busy_by_user=busy_by_user,
            time_min=time_min,
            time_max=extended_time_max,
            minimum_available=len(busy_by_user),
            require_exact_absent_count=0,
        )

    if not full_slots:
        return None

    # 가장 빠른 전원 가능 슬롯 반환
    best = full_slots[0]
    return {
        "slot_id": best.get("slot_id"),
        "label": best.get("label"),
        "start_at": best.get("start_at"),
        "end_at": best.get("end_at"),
        "available_count": best.get("available_count"),
        "total_count": best.get("total_count"),
        "is_holiday": best.get("is_holiday", False),
        "is_weekend": best.get("is_weekend", False),
    }
