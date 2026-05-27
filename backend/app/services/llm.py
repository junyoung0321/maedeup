"""LLM provider 선택 abstraction (K1-2).

call_llm(prompt, provider="gemini"|"openai", **kwargs) 로 호출.
provider 기본값은 "gemini" — 기존 동작 유지.
dominant cost site 3개가 이 함수를 통해 toggle 분기.
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
