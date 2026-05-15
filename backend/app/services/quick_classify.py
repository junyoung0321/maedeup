from __future__ import annotations

import asyncio
import logging
import re
from typing import Literal

from app.services.gemini import call_gemini

logger = logging.getLogger(__name__)

QuickKind = Literal["schedule", "place", "schedule+place", "general"]

_SCHEDULE_RE = re.compile(
    r"(일정|날짜|언제|시간).*(추천|뽑|정리|제안|잡|정하|확인|조율|맞추)"
    r"|(언제\s*(만날|만나|볼|모일|모이|갈|할|보자))",
    re.IGNORECASE,
)
# 해결점 A5-1 보강 (2026-05-07): "강남에서 갈만한 한식집" 같은 자연어 미발동 사각지대 차단.
# 세 갈래 OR — (1) 장소 키워드 + 추천 동사, (2) cuisine 키워드 단독, (3) 장소 방문 동사 단독.
_PLACE_RE = re.compile(
    r"(장소|어디|맛집|카페|식당|근처|음식점).*(추천|뽑|정리|제안|알려|찾)"
    r"|(한식|중식|일식|양식|분식|이자카야|포차|호프|이탈리안|디저트|베이커리|브런치)"
    r"|(갈\s*만|갈만|먹을|먹기|놀러|가볼|어딘가|어디서)",
    re.IGNORECASE,
)
_VALID_KINDS: set[str] = {"schedule", "place", "schedule+place", "general"}


def _result(kind: QuickKind, confidence: float, method: Literal["regex", "gemini"]) -> dict:
    logger.info("quick_classify method=%s kind=%s confidence=%.2f", method, kind, confidence)
    return {"kind": kind, "confidence": confidence, "method": method}


async def quick_classify(text: str) -> dict:
    schedule_match = bool(_SCHEDULE_RE.search(text or ""))
    place_match = bool(_PLACE_RE.search(text or ""))

    if schedule_match and place_match:
        return _result("schedule+place", 0.95, "regex")
    if schedule_match:
        return _result("schedule", 0.9, "regex")
    if place_match:
        return _result("place", 0.9, "regex")

    prompt = (
        "사용자의 AI 패널 입력을 하나로 분류하세요.\n"
        "반드시 다음 네 값 중 하나만 출력하세요: schedule, place, schedule+place, general\n\n"
        "기준:\n"
        "- schedule: 일정/날짜/시간 추천이나 정리 요청\n"
        "- place: 장소/맛집/카페/식당 추천이나 정리 요청\n"
        "- schedule+place: 일정과 장소를 둘 다 요청\n"
        "- general: 그 외 일반 대화\n\n"
        f"입력: {text or ''}"
    )

    try:
        raw = await asyncio.wait_for(call_gemini(prompt), timeout=1.5)
    except Exception:
        return _result("general", 0.0, "gemini")

    kind = (raw or "").strip().lower()
    if kind not in _VALID_KINDS:
        kind = "general"
    confidence = 0.8 if kind != "general" else 0.5
    return _result(kind, confidence, "gemini")
