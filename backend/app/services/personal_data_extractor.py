"""
Personal data extractor service.

모임 종료 시점에 chat transcript에서 멤버별 personal data 후보를 추출.
- 6 카테고리: food_restrictions / food_preferences / liked_areas / disliked_areas / time_preference / transport_mode
- 활성화 순서:
    1) force_demo=True (호출자가 명시) → canned fallback
    2) settings.DEMO_FALLBACK_ENABLED → canned fallback
    3) 그 외 → 실 Gemini 호출 (실패 시 자동 fallback)

이 모듈은 *추출만* 담당. User 칼럼 update + AIMemory INSERT + Redis publish는
langgraph_pipeline.memory_extraction 노드가 책임진다.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, Optional, Union

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted
from pydantic import BaseModel, ValidationError
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

# confidence 미만은 drop (디자인 P4 partial response 정책).
MIN_CONFIDENCE = 0.7


class CategoryExtraction(BaseModel):
    """단일 카테고리 추출 결과."""

    value: Union[list[str], str]
    confidence: float
    source_quote: str
    source_message_id: Optional[int] = None


class MemberExtraction(BaseModel):
    """한 멤버의 6 카테고리 추출 결과 (없는 카테고리는 None). Gemini 응답 schema."""

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
        return await _load_canned_extraction(
            transcript=transcript, member_ids=member_ids, db=db
        )

    try:
        return await _gemini_extract(
            transcript=transcript, member_ids=member_ids, db=db
        )
    except Exception as exc:  # noqa: BLE001 — 외부 호출/parse 실패는 fallback으로 흡수
        logger.warning(
            "personal_data_extractor: Gemini extraction failed, falling back to canned. error=%s",
            exc,
        )
        return await _load_canned_extraction(
            transcript=transcript, member_ids=member_ids, db=db
        )


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _build_quote_resolver(
    transcript: list[ChatMessage],
) -> Callable[[str], Optional[int]]:
    """source_quote 부분 문자열 → ChatMessage.id 매핑 (가장 최신 메시지 우선)."""
    indexed: list[tuple[int, str]] = sorted(
        (
            (m.id, m.content or "")
            for m in transcript
            if m.id is not None
        ),
        key=lambda t: t[0],
        reverse=True,  # id 큰 게 일반적으로 최신 (auto-increment)
    )

    def resolve(quote: str) -> Optional[int]:
        if not quote:
            return None
        q = quote.strip()
        if not q:
            return None
        # 정확 substring 매치
        for mid, content in indexed:
            if q in content:
                return mid
        # 짧은 quote는 fuzzy 시도 (단어 단위 부분 매치). 데모 안전망.
        if len(q) <= 8:
            return None
        first_token = q.split()[0] if q.split() else q[:6]
        for mid, content in indexed:
            if first_token in content:
                return mid
        return None

    return resolve


def _build_extraction_object(
    *,
    value: Union[list[str], str, None],
    confidence: float,
    source_quote: str,
    resolver: Callable[[str], Optional[int]],
) -> Optional[CategoryExtraction]:
    """raw dict/일반 값을 CategoryExtraction으로 변환. confidence 미만이면 None."""
    if value is None:
        return None
    if confidence < MIN_CONFIDENCE:
        return None
    return CategoryExtraction(
        value=value,
        confidence=float(confidence),
        source_quote=source_quote or "",
        source_message_id=resolver(source_quote or ""),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Real Gemini extraction
# ─────────────────────────────────────────────────────────────────────────────


_PROMPT_TEMPLATE = """\
당신은 한국어 그룹 채팅에서 멤버 개인의 personal data를 추출하는 분석가입니다.
명시적 발화에서만 추출하세요. 추측은 금지.

# 멤버 (이름 옆이 member_id):
{member_list_text}

# 추출할 6 카테고리
- food_restrictions: 알레르기 / 못 먹는 음식 (list[str])
- food_preferences: 좋아하는 음식 카테고리 (list[str], 예: 한식/양식/일식/중식/카페/술집)
- liked_areas: 자주 가고 싶은 동네/지역 (list[str])
- disliked_areas: 멀어서/안 가고 싶은 지역 (list[str])
- time_preference: 선호 시간대 자유 텍스트 (str, 예: "주말 오후", "평일 저녁 7시 이후")
- transport_mode: 이동수단 (str, 예: "대중교통", "자차", "도보")

# 규칙
1. 발화에 명시적으로 나타난 정보만 추출.
2. confidence 0~1, 명시적이면 0.9+, 애매하면 0.5~0.7.
3. source_quote: 발화에서 정확히 80자 이내 발췌.
4. 멤버가 발화 안 했으면 그 멤버는 결과에서 누락 OK.
5. 응답은 반드시 JSON. 다른 텍스트 금지.

# JSON 응답 schema (예시)
{{
  "members": [
    {{
      "member_id": 1,
      "food_restrictions": {{"value": ["갑각류"], "confidence": 0.95, "source_quote": "나 갑각류 못 먹어"}},
      "transport_mode": {{"value": "대중교통", "confidence": 0.85, "source_quote": "지하철 타고 갈게"}}
    }}
  ]
}}

# 채팅 transcript
{transcript_text}
"""


async def _gemini_extract(
    *,
    transcript: list[ChatMessage],
    member_ids: list[int],
    db: AsyncSession,
) -> dict[int, dict[str, CategoryExtraction]]:
    """실 Gemini 호출. JSON-only 응답 강제."""
    if not settings.GEMINI_API_KEY.strip():
        raise RuntimeError("GEMINI_API_KEY is empty — cannot do real extraction")
    if not transcript:
        return {mid: {} for mid in member_ids}

    # member_id → name 매핑 + 역매핑
    user_rows = (
        await db.execute(select(User).where(User.id.in_(member_ids)))
    ).scalars().all()
    id_to_name = {u.id: u.name for u in user_rows}
    name_to_id = {u.name: u.id for u in user_rows if u.name}

    member_list_text = ", ".join(
        f"{name}({mid})" for mid, name in id_to_name.items()
    )

    transcript_lines = []
    for msg in transcript:
        sender_name = msg.sender or "(unknown)"
        sender_id = name_to_id.get(sender_name, "?")
        content = (msg.content or "").replace("\n", " ").strip()
        if not content:
            continue
        transcript_lines.append(
            f"[mid={msg.id} {sender_name}({sender_id})] {content}"
        )
    transcript_text = "\n".join(transcript_lines) or "(no messages)"

    prompt = _PROMPT_TEMPLATE.format(
        member_list_text=member_list_text or "(no members)",
        transcript_text=transcript_text,
    )

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    )

    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
    except (ResourceExhausted, GoogleAPICallError) as exc:
        raise RuntimeError(f"Gemini API error: {exc}") from exc

    text = (getattr(response, "text", "") or "").strip()
    if not text:
        raise RuntimeError("Gemini returned empty response")

    try:
        parsed = ExtractionResponse.model_validate_json(text)
    except ValidationError as exc:
        # parse 실패는 raw text와 함께 전파 — 호출자가 fallback으로 흡수
        raise RuntimeError(f"Gemini response parse failed: {exc.error_count()} errors") from exc

    resolver = _build_quote_resolver(transcript)
    result: dict[int, dict[str, CategoryExtraction]] = {mid: {} for mid in member_ids}

    for member in parsed.members:
        if member.member_id not in result:
            continue
        for category in CATEGORY_FIELDS:
            ext = getattr(member, category, None)
            if ext is None or ext.confidence < MIN_CONFIDENCE:
                continue
            # source_message_id resolve (quote substring match against transcript)
            ext.source_message_id = resolver(ext.source_quote)
            result[member.member_id][category] = ext

    matched = sum(1 for v in result.values() if v)
    total = sum(len(v) for v in result.values())
    logger.info(
        "personal_data_extractor: gemini extracted %d members, %d categories total",
        matched,
        total,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Canned fallback
# ─────────────────────────────────────────────────────────────────────────────


async def _load_canned_extraction(
    *,
    transcript: list[ChatMessage],
    member_ids: list[int],
    db: AsyncSession,
) -> dict[int, dict[str, CategoryExtraction]]:
    """
    Canned JSON 읽고 member_ids에 매칭되는 user 데이터만 반환.

    매칭은 User.email로 — JSON의 user_email이 DB User.email과 일치하는 멤버만 결과 포함.
    transcript가 주어지면 source_message_id를 substring 매치로 resolve.
    """
    if not CANNED_DATA_PATH.is_file():
        logger.error(
            "personal_data_extractor: canned data file not found at %s",
            CANNED_DATA_PATH,
        )
        return {member_id: {} for member_id in member_ids}

    with CANNED_DATA_PATH.open(encoding="utf-8") as fh:
        canned = json.load(fh)

    entries: list[dict] = canned.get("extractions", [])

    user_rows = (
        await db.execute(select(User).where(User.id.in_(member_ids)))
    ).scalars().all()
    email_to_id: dict[str, int] = {u.email: u.id for u in user_rows}

    resolver = _build_quote_resolver(transcript)
    result: dict[int, dict[str, CategoryExtraction]] = {mid: {} for mid in member_ids}

    for entry in entries:
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

        ext = _build_extraction_object(
            value=entry.get("value"),
            confidence=float(entry.get("confidence", 0.0)),
            source_quote=entry.get("source_quote", ""),
            resolver=resolver,
        )
        if ext is None:
            continue

        member_id = email_to_id[email]
        result[member_id][category] = ext

    matched_members = sum(1 for v in result.values() if v)
    total_extractions = sum(len(v) for v in result.values())
    logger.info(
        "personal_data_extractor: canned fallback loaded — %d/%d members matched, %d extractions",
        matched_members,
        len(member_ids),
        total_extractions,
    )
    return result
