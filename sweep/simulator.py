"""페르소나 발화 생성 — gemini_call 주입, 실패/빈 응답 시 템플릿 fallback (스펙 §4)."""
from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from sweep.personas import Persona, fallback_utterance

GeminiCall = Callable[[str], Awaitable[str]]


def _build_prompt(persona: Persona, history: list[str]) -> str:
    convo = "\n".join(history[-8:]) if history else "(아직 대화 없음)"
    return (
        f"{persona.system_prompt}\n"
        f"너의 숨은 목표: {persona.hidden_goal}\n"
        f"지금까지의 대화:\n{convo}\n\n"
        f"위 페르소나로서 한국어 채팅 메시지 한 줄만 출력해. 따옴표/이름표 없이 내용만."
    )


async def generate_utterance(
    persona: Persona,
    history: list[str],
    turn_index: int,
    *,
    gemini_call: GeminiCall,
) -> str:
    """Gemini로 발화 생성. 예외/빈 응답이면 템플릿 뱅크로 fallback."""
    try:
        text = (await gemini_call(_build_prompt(persona, history))).strip()
    except Exception:
        text = ""
    if not text:
        return fallback_utterance(persona, turn_index)
    return text


def default_gemini_call() -> GeminiCall:
    """google-generativeai 직접 사용 (백엔드 import 없이). GEMINI_API_KEY 필요."""
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(os.environ.get("SWEEP_GEMINI_MODEL", "gemini-2.5-flash"))

    async def _call(prompt: str) -> str:
        resp = await model.generate_content_async(prompt)
        return resp.text or ""

    return _call
