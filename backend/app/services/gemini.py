import asyncio
import logging
from typing import Any

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted

from app.core.config import settings

logger = logging.getLogger(__name__)


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
    timeout: float = 25.0,
    generation_config: dict[str, Any] | None = None,
) -> str:
    """Gemini API를 호출하고 응답 텍스트를 반환합니다.

    Fix 5 (2026-05-14): timeout. SDK hang → 백엔드 멈춤 위험 차단.
    결정성 강화 (2026-05-16): default generation_config (temp=0, top_p=0.1, top_k=1).
      override 원하면 generation_config 인자로 전달 (예: narrator 다양성 필요 시).
    quick_classify는 자체 1.5s wait_for 사용 — 호환.
    Fix 6 (2026-05-26): timeout 15s→25s 상향 + TimeoutError/ResourceExhausted/
      GoogleAPICallError 발생 시 1회 retry. 두 번째도 실패면 기존 fallback (return "").
    Fix 7 REVERTED (2026-05-30): timeout 25s→10s 시도 → 실측에서 정상 응답이 10s
      초과 (시연 2회 19회 timeout 발생). 25s 원복. 단축은 Gemini 응답 환경 개선 후 재시도.
    """
    if not settings.effective_gemini_api_key:
        return ""
    cfg = generation_config if generation_config is not None else _DEFAULT_GENERATION_CONFIG

    for attempt in range(2):  # 0=첫 호출, 1=retry
        genai.configure(api_key=settings.effective_gemini_api_key)
        model = genai.GenerativeModel(
            settings.GEMINI_MODEL,
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
            if attempt == 0:
                logger.warning("gemini_timeout attempt=%d retrying", attempt + 1)
                continue
            logger.warning("gemini_call_failed type=TimeoutError after retry timeout=%.1fs", timeout)
            return ""
        except ResourceExhausted as e:
            retry_after = getattr(e, "retry_after", None)
            if attempt == 0:
                logger.warning(
                    "gemini_ResourceExhausted attempt=%d retry_after=%s retrying",
                    attempt + 1,
                    retry_after,
                )
                continue
            logger.warning(
                "gemini_call_failed type=ResourceExhausted retry_after=%s model=gemini-2.5-flash",
                retry_after,
            )
            return ""
        except GoogleAPICallError as e:
            if attempt == 0:
                logger.warning(
                    "gemini_%s attempt=%d retrying", type(e).__name__, attempt + 1
                )
                continue
            logger.warning("gemini_call_failed type=%s msg=%s", type(e).__name__, str(e)[:200])
            return ""
        except Exception as e:
            logger.warning("gemini_call_failed type=%s msg=%s", type(e).__name__, str(e)[:200])
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

    return ""  # unreachable — loop exhausted
