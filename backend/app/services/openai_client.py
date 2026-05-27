"""OpenAI GPT wrapper — gemini.py 와 동일 signature (call_openai).

K1-2 (2026-05-30): dominant cost site 3개를 GPT-4o-mini 로 대체하기 위한 wrapper.
toggle 기본값 = 'gemini' 이라 이 모듈이 import 돼도 API_KEY 없으면 호출 안 됨.
"""
from __future__ import annotations

import asyncio
import logging

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.OPEN_AI_API_KEY:
            raise RuntimeError("OPEN_AI_API_KEY is not set")
        _client = AsyncOpenAI(api_key=settings.OPEN_AI_API_KEY)
    return _client


async def call_openai(
    prompt: str,
    *,
    model: str | None = None,
    timeout: float = 25.0,
    max_tokens: int = 2048,
) -> str:
    """Gemini call_gemini 와 동일 signature. 응답 str 반환, 실패 시 빈 문자열.

    - OPEN_AI_API_KEY 미설정 시 즉시 빈 문자열 반환 (silent warn).
    - TimeoutError / OpenAI SDK 예외 모두 logger.warning + 빈 문자열 반환.
    - ImportError / AttributeError 는 호출자로 re-raise (설정 오류 조기 감지).
    """
    if not settings.OPEN_AI_API_KEY:
        logger.warning("call_openai: OPEN_AI_API_KEY not set, returning empty string")
        return ""
    resolved_model = model or settings.OPENAI_MODEL
    try:
        client = _get_client()
    except RuntimeError:
        logger.warning("call_openai: client init failed (OPEN_AI_API_KEY missing)")
        return ""
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=resolved_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.0,
            ),
            timeout=timeout,
        )
        return resp.choices[0].message.content or ""
    except asyncio.TimeoutError:
        logger.warning(
            "call_openai: timeout model=%s timeout=%.1f", resolved_model, timeout
        )
        return ""
    except Exception:
        logger.warning(
            "call_openai: call failed model=%s", resolved_model, exc_info=True
        )
        return ""
