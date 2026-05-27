"""LLM provider 선택 abstraction (K1-2, C구조 B+D).

call_llm(prompt, provider="gemini"|"openai", **kwargs) — B 영역 dominant site.
call_llm_tier(prompt, tier="high"|"mid"|"low", **kwargs) — D 영역 3-tier 자동 매핑.
provider/tier 기본값은 "gemini" — 기존 동작 유지.
"""
from __future__ import annotations

from app.services.gemini import call_gemini
from app.services.openai_client import call_openai


async def call_llm(
    prompt: str,
    *,
    provider: str = "gemini",
    **kwargs,
) -> str:
    """provider 에 따라 call_gemini / call_openai 분기.

    Args:
        prompt: 전달할 프롬프트 문자열.
        provider: "gemini" (기본) 또는 "openai".
        **kwargs: 각 backend 에 그대로 전달 (timeout, max_tokens 등).

    Returns:
        LLM 응답 문자열. 실패 시 빈 문자열 (각 backend 정책에 따름).
    """
    if provider == "openai":
        return await call_openai(prompt, **kwargs)
    return await call_gemini(prompt, **kwargs)


async def call_llm_tier(
    prompt: str,
    *,
    tier: str = "low",
    **kwargs,
) -> str:
    """D 영역: tier (high/mid/low) 에 따라 settings LLM_TIER_* env lookup → provider 분기.

    Args:
        prompt: 전달할 프롬프트 문자열.
        tier: "high" | "mid" | "low". 기본 "low".
        **kwargs: 각 backend 에 그대로 전달.

    Returns:
        LLM 응답 문자열. 실패 시 빈 문자열 (각 backend 정책에 따름).
    """
    from app.core.config import settings

    tier_env_map = {
        "high": settings.LLM_TIER_HIGH,
        "mid": settings.LLM_TIER_MID,
        "low": settings.LLM_TIER_LOW,
    }
    provider = tier_env_map.get(tier, "gemini")
    return await call_llm(prompt, provider=provider, **kwargs)
