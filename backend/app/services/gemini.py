import asyncio
from typing import Any

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted

from app.core.config import settings


# 결정성 강화 (2026-05-16): temperature=0.0 단독으론 Gemini 2.5 Flash가 stochastic.
#   top_p=0.1, top_k=1 추가로 분류·추출·요약 작업의 결정성 ↑. narrator 응답이
#   다양성 필요한 경우 호출자가 generation_config 인자로 override 가능.
_DEFAULT_GENERATION_CONFIG: dict[str, Any] = {
    "temperature": 0.0,
    "top_p": 0.1,
    "top_k": 1,
}


async def call_gemini(
    content: str,
    timeout: float = 15.0,
    generation_config: dict[str, Any] | None = None,
) -> str:
    """Gemini API를 호출하고 응답 텍스트를 반환합니다.

    Fix 5 (2026-05-14): 기본 15s timeout. SDK hang → 백엔드 멈춤 위험 차단.
    결정성 강화 (2026-05-16): default generation_config (temp=0, top_p=0.1, top_k=1).
      override 원하면 generation_config 인자로 전달 (예: narrator 다양성 필요 시).
    quick_classify는 자체 1.5s wait_for 사용 — 호환.
    """
    if not settings.GEMINI_API_KEY.strip():
        return ""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    cfg = generation_config if generation_config is not None else _DEFAULT_GENERATION_CONFIG
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        system_instruction=(
            "당신은 매듭(Maedeup) AI 어시스턴트입니다. 한국인 사용자들의 모임 일정과 "
            "장소 조율을 돕는 친근하고 전문적인 어시스턴트입니다. 항상 한국어로 "
            "간결하고 자연스럽게 답변하세요."
        ),
        generation_config=cfg,
    )
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, content),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return ""
    except (ResourceExhausted, GoogleAPICallError):
        return ""
    except Exception:
        return ""

    if response is None:
        return ""

    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    candidates = getattr(response, "candidates", None) or []
    parts: list[str] = []
    for candidate in candidates:
        content_obj = getattr(candidate, "content", None)
        for part in getattr(content_obj, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                parts.append(part_text)
    return "\n".join(parts).strip()
