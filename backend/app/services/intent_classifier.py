"""
RAG 기반 의도 분류기 (2단계)

1단계 - 벡터 유사도 검색:
  - 입력 발화를 임베딩 → 저장된 예시들과 코사인 유사도 비교
  - 유사도 >= HIGH_THRESHOLD (0.85): RAG 결과 바로 확정

2단계 - Gemini 폴백:
  - 유사도 >= LOW_THRESHOLD (0.60): 상위 예시를 컨텍스트로 Gemini에게 최종 판단 위임
  - 유사도 < LOW_THRESHOLD: general로 분류
"""

import math
import re
from typing import Optional

from sqlmodel import select

from app.db.session import AsyncSessionLocal
from app.models.intent import IntentExample
from app.services.embedding import get_embedding
from app.services.llm import call_llm_tier

HIGH_THRESHOLD = 0.85   # RAG로 바로 확정
LOW_THRESHOLD = 0.60    # Gemini 폴백 구간

VALID_INTENTS = {"meeting_schedule", "place_suggestion", "general"}

_KOREAN_PLACE_PATTERN = re.compile(r'[가-힣]{1,10}(?:동|구|역|로|리|면|읍|시|군)')

INTENT_DESCRIPTIONS = {
    "meeting_schedule": "모임/만남 일정을 잡거나 제안하는 내용",
    "place_suggestion": "장소를 제안하거나 묻는 내용",
    "general": "그 외 일반 대화",
}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def classify_intent(text_input: str) -> dict:
    """
    Returns:
        {
            "intent": str,          # meeting_schedule | place_suggestion | general
            "confidence": float,    # 상위 유사도 점수
            "method": str,          # "rag" | "gemini" | "default"
        }
    """
    # 입력 임베딩
    query_embedding = await get_embedding(text_input)

    # DB에서 모든 예시 로드 (예시 수가 적으므로 전체 로드 후 Python에서 유사도 계산)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(IntentExample).where(IntentExample.embedding.isnot(None))
        )
        examples = result.scalars().all()

    if not examples:
        return {"intent": "general", "confidence": 0.0, "method": "default"}

    # 코사인 유사도 계산
    scored = [
        (ex, _cosine_similarity(query_embedding, ex.embedding))
        for ex in examples
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    top3 = scored[:3]

    top_example, top_similarity = top3[0]

    # ── 1단계: 유사도가 충분히 높으면 바로 확정 ──────────────────────────
    if top_similarity >= HIGH_THRESHOLD:
        return {
            "intent": top_example.intent,
            "confidence": round(top_similarity, 4),
            "method": "rag",
        }

    # ── 2단계: 중간 구간 → Gemini 폴백 ──────────────────────────────────
    if top_similarity >= LOW_THRESHOLD:
        context_lines = "\n".join(
            f'  - "{ex.text}" → {ex.intent} (유사도 {sim:.2f})'
            for ex, sim in top3
        )
        intent_list = "\n".join(
            f"  - {k}: {v}" for k, v in INTENT_DESCRIPTIONS.items()
        )
        prompt = f"""다음 채팅 메시지의 의도를 분류하세요.

메시지: "{text_input}"

유사 사례:
{context_lines}

의도 종류:
{intent_list}

위 사례들을 참고해서 메시지가 어떤 의도에 해당하는지 판단하세요.
반드시 다음 중 하나만 출력하세요: meeting_schedule, place_suggestion, general

답변:"""
        gemini_response = await call_llm_tier(prompt, tier="low")
        if not gemini_response or not gemini_response.strip():
            # Gemini 실패 시에도 패턴 매칭 시도
            if _contains_korean_place(text_input):
                return {
                    "intent": "place_suggestion",
                    "confidence": round(max(top_similarity, 0.7), 4),
                    "method": "pattern",
                }
            if _contains_schedule_keyword(text_input):
                return {
                    "intent": "meeting_schedule",
                    "confidence": round(max(top_similarity, 0.7), 4),
                    "method": "pattern",
                }
            return {
                "intent": "general",
                "confidence": round(top_similarity, 4),
                "method": "default",
            }
        intent = gemini_response.strip().lower().split()[0]
        if intent not in VALID_INTENTS:
            intent = "general"

        # Gemini가 general로 판단했지만 패턴 매칭으로 override
        if intent == "general":
            if _contains_korean_place(text_input):
                intent = "place_suggestion"
            elif _contains_schedule_keyword(text_input):
                intent = "meeting_schedule"

        return {
            "intent": intent,
            "confidence": round(top_similarity, 4),
            "method": "gemini" if intent != "general" else "pattern",
        }

    # 유사도 너무 낮음 → 한국 지명 패턴 체크 후 일반 대화로 처리
    if _contains_korean_place(text_input):
        return {
            "intent": "place_suggestion",
            "confidence": round(max(top_similarity, 0.7), 4),
            "method": "pattern",
        }

    # 날짜/시간 관련 키워드 체크
    if _contains_schedule_keyword(text_input):
        return {
            "intent": "meeting_schedule",
            "confidence": round(max(top_similarity, 0.7), 4),
            "method": "pattern",
        }

    return {
        "intent": "general",
        "confidence": round(top_similarity, 4),
        "method": "default",
    }


def _contains_korean_place(text: str) -> bool:
    """한국 지명 패턴(XX동, XX역, XX구 등)이 포함되어 있는지 확인합니다."""
    meeting_keywords = ("만나", "보자", "가자", "갈까", "어때", "ㄱㄱ", "추천", "맛집", "카페", "식당", "근처", "쪽")
    has_place = bool(_KOREAN_PLACE_PATTERN.search(text))
    has_meeting = any(kw in text for kw in meeting_keywords)
    return has_place and has_meeting


def _contains_schedule_keyword(text: str) -> bool:
    """날짜/시간 관련 키워드가 포함되어 있는지 확인합니다."""
    schedule_keywords = ("만나자", "보자", "모이자", "언제", "시간", "날짜", "주말", "평일", "다음주", "이번주", "내일", "모레", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")
    return any(kw in text for kw in schedule_keywords)
