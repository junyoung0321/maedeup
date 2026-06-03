from __future__ import annotations

import asyncio
import logging
import re
from typing import Literal

from app.services.llm import call_llm_tier

logger = logging.getLogger(__name__)

QuickKind = Literal["schedule", "place", "schedule+place", "general"]

# Fix 12 (2026-05-14): regex 확장 — "내일/모레/저녁" 같은 자연어 직접 입력도 매칭.
# 이전 패턴은 "시간" / "식당" 같은 명사가 명시되어야 매칭. "내일 친구들이랑
# 저녁 식사 추천해줘" 같은 자연스러운 입력은 Gemini fallback → general 분류 →
# 카드 안 뜨고 되묻기만 하는 버그 발생.
# /review fix (2026-05-18): "모임 이름 추천", "약속 이미지 정리" 같은 비-일정 입력
#   오분류 방지 — 모임/약속은 schedule-context verb (잡|만나|볼까)와만 매칭.
# 통합 머지 (2026-05-18 main): sanigod의 verb 확장(정하|확인|조율|맞추) + "언제 만날/볼/모일"
#   그룹 모두 흡수. 양쪽 expansion union.
_SCHEDULE_RE = re.compile(
    r"(일정|날짜|언제|시간|"
    r"내일|모레|오늘|"
    r"다음\s*주|이번\s*주|다음\s*주말|이번\s*주말|"
    r"[월화수목금토일]요일)"
    r".*(추천|뽑|정리|제안|잡|어때|만나|볼까|찾|정하|확인|조율|맞추)"
    # demo-stab BE-1: 모임/약속은 schedule-context verb만 (이름 추천/이미지 정리 같은 오탐 차단).
    r"|(모임|약속).*(잡|만나|볼까|언제|어때)"
    # sanigod main 백포팅: "언제 만날/만나/볼/모일/...".
    r"|(언제\s*(만날|만나|볼|모일|모이|갈|할|보자))",
    re.IGNORECASE,
)
# 해결점 A5-1 보강 (2026-05-07) + Fix 12 (2026-05-14) + demo-stab BE-1 (2026-05-13 백포팅):
# 세 갈래 OR — (1) 장소/식사 키워드 + 추천 동사, (2) cuisine 키워드 단독, (3) 장소 방문 동사 단독.
# demo-stab BE-1 추가 키워드: 한식집/일식집/중식집/양식집/레스토랑/술집/고기집/맥주집/밥집/술자리/모임/약속, 동사 "어때/골라"
_PLACE_RE = re.compile(
    r"(장소|어디|맛집|카페|식당|근처|음식점|"
    r"식사|회식|점심|저녁|아침|브런치|간식|디저트|"
    r"한식집|일식집|중식집|양식집|레스토랑|술집|고기집|맥주집|밥집|술자리)"
    r".*(추천|뽑|정리|제안|알려|찾|먹|마실|어때|골라)"
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

    # 타임아웃 (2026-06-03 bug fix): 이전 1.5s는 tier=low(gemini) 실측 분류
    # 지연(~2.3–3.0s)보다 짧아, regex에 안 걸린 정상 장소/일정 요청
    # ("천안 신부동 추천해줘" 등)이 정답이 나오기 전에 잘려 general로 떨어지고
    # 파이프라인이 안 돌아 카드가 안 떴다. 실측 지연을 충분히 덮도록 4.0s로
    # 상향. 데모 happy-path 표현은 regex로 즉시 분류되므로 영향 없음. 진짜
    # 응답 못 하는 경우엔 여전히 general로 fail-safe.
    try:
        raw = await asyncio.wait_for(call_llm_tier(prompt, tier="low"), timeout=4.0)
    except Exception:
        return _result("general", 0.0, "gemini")

    kind = (raw or "").strip().lower()
    if kind not in _VALID_KINDS:
        kind = "general"
    confidence = 0.8 if kind != "general" else 0.5
    return _result(kind, confidence, "gemini")
