"""
Personal data extractor service.

모임 종료 시점에 chat transcript에서 멤버별 personal data 후보를 추출.
- 6 카테고리: food_restrictions / food_preferences / liked_areas / disliked_areas / time_preference / transport_mode
- 활성화 순서:
    1) force_demo=True (호출자가 명시) → canned fallback
    2) settings.DEMO_FALLBACK_ENABLED → canned fallback
    3) 그 외 → 실 Gemini 호출 (실패 시 자동 fallback)

이번 구현 단계 (Hour 0-2): canned fallback path만 동작 가능. 실 Gemini 호출은
NotImplementedError stub. 즉 "fallback이 먼저 작동하는 상태"를 0번째 commit으로 박음.
시연 단일 최대 실패점이 라이브 Gemini 호출이라는 사실을 build 순서로 못 박는 것.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.models.chat import ChatMessage
from app.models.user import User

logger = logging.getLogger(__name__)


CANNED_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "demo_extraction_canned.json"
)

CATEGORY_FIELDS: frozenset[str] = frozenset(
    {
        "food_restrictions",
        "food_preferences",
        "liked_areas",
        "disliked_areas",
        "time_preference",
        "transport_mode",
    }
)


class CategoryExtraction(BaseModel):
    """단일 카테고리 추출 결과."""

    value: Union[list[str], str]
    confidence: float
    source_quote: str
    source_message_id: Optional[int] = None


class MemberExtraction(BaseModel):
    """한 멤버의 6 카테고리 추출 결과 (없는 카테고리는 None). Gemini response_schema."""

    member_id: int
    food_restrictions: Optional[CategoryExtraction] = None
    food_preferences: Optional[CategoryExtraction] = None
    liked_areas: Optional[CategoryExtraction] = None
    disliked_areas: Optional[CategoryExtraction] = None
    time_preference: Optional[CategoryExtraction] = None
    transport_mode: Optional[CategoryExtraction] = None


class ExtractionResponse(BaseModel):
    """Gemini가 반환하는 최상위 응답."""

    members: list[MemberExtraction]


async def extract_personal_data(
    *,
    transcript: list[ChatMessage],
    member_ids: list[int],
    db: AsyncSession,
    force_demo: bool = False,
) -> dict[int, dict[str, CategoryExtraction]]:
    """
    Transcript + 멤버 ID 리스트 → 멤버별 카테고리별 추출 결과.

    반환: {member_id: {category_name: CategoryExtraction}}.
    추출이 없는 멤버/카테고리는 결과 dict에서 빈 값 또는 누락.
    """
    if force_demo or settings.DEMO_FALLBACK_ENABLED:
        logger.info(
            "personal_data_extractor: using canned fallback (force_demo=%s, settings=%s)",
            force_demo,
            settings.DEMO_FALLBACK_ENABLED,
        )
        return await _load_canned_extraction(member_ids=member_ids, db=db)

    try:
        return await _gemini_extract(
            transcript=transcript, member_ids=member_ids, db=db
        )
    except NotImplementedError:
        # 개발 단계 — 실 호출이 아직 stub이라는 신호. 호출자에게 그대로 노출.
        raise
    except Exception as exc:  # noqa: BLE001 — 모든 외부 호출 실패는 fallback으로 흡수
        logger.warning(
            "personal_data_extractor: Gemini call failed, falling back to canned. error=%s",
            exc,
        )
        return await _load_canned_extraction(member_ids=member_ids, db=db)


async def _gemini_extract(
    *,
    transcript: list[ChatMessage],
    member_ids: list[int],
    db: AsyncSession,
) -> dict[int, dict[str, CategoryExtraction]]:
    """실 Gemini 호출 (Hour 5-9에서 구현 예정). 현재 stub.

    구현 시 해야 할 것:
    - transcript + member_ids → Gemini prompt 조립 (멤버별 발화 ID 매핑 포함)
    - response_schema=ExtractionResponse 강제, JSON-only 응답
    - 응답 후 source_quote substring match로 source_message_id resolve
    - confidence < 0.7 카테고리 drop
    - parse 실패 / partial 응답 시 caller가 except로 fallback 받음
    """
    raise NotImplementedError(
        "Real Gemini extraction not yet implemented. "
        "Set DEMO_FALLBACK_ENABLED=true (env) or pass force_demo=True for canned fallback."
    )


async def _load_canned_extraction(
    *,
    member_ids: list[int],
    db: AsyncSession,
) -> dict[int, dict[str, CategoryExtraction]]:
    """
    Canned JSON 읽고 member_ids에 매칭되는 user의 데이터만 반환.

    매칭은 User.email로 — JSON의 user_email이 DB의 User.email과 일치하는 멤버만 결과 포함.
    매칭 안 되는 멤버는 빈 dict.
    """
    if not CANNED_DATA_PATH.is_file():
        logger.error(
            "personal_data_extractor: canned data file not found at %s",
            CANNED_DATA_PATH,
        )
        return {member_id: {} for member_id in member_ids}

    with CANNED_DATA_PATH.open(encoding="utf-8") as fh:
        canned = json.load(fh)

    extractions: list[dict] = canned.get("extractions", [])

    # member_id → email 매핑 (DB 1회 lookup)
    user_rows = (
        await db.execute(select(User).where(User.id.in_(member_ids)))
    ).scalars().all()
    email_to_id: dict[str, int] = {u.email: u.id for u in user_rows}

    result: dict[int, dict[str, CategoryExtraction]] = {mid: {} for mid in member_ids}

    for entry in extractions:
        email = entry.get("user_email")
        category = entry.get("category")
        if email not in email_to_id:
            continue
        if category not in CATEGORY_FIELDS:
            logger.warning(
                "personal_data_extractor: canned entry has unknown category %r — skipped",
                category,
            )
            continue

        member_id = email_to_id[email]
        result[member_id][category] = CategoryExtraction(
            value=entry.get("value"),
            confidence=float(entry.get("confidence", 0.0)),
            source_quote=entry.get("source_quote", ""),
            source_message_id=None,  # canned 데이터는 message id resolve 안 함
        )

    matched_members = sum(1 for v in result.values() if v)
    total_extractions = sum(len(v) for v in result.values())
    logger.info(
        "personal_data_extractor: canned fallback loaded — %d/%d members matched, %d extractions total",
        matched_members,
        len(member_ids),
        total_extractions,
    )
    return result
