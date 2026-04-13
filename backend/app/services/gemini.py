import asyncio

import google.generativeai as genai

from app.core.config import settings


async def call_gemini(content: str) -> str:
    """Gemini API를 호출하고 응답 텍스트를 반환합니다."""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        system_instruction=(
            "당신은 매듭(Maedeup) AI 어시스턴트입니다. 한국인 사용자들의 모임 일정과 "
            "장소 조율을 돕는 친근하고 전문적인 어시스턴트입니다. 항상 한국어로 "
            "간결하고 자연스럽게 답변하세요."
        ),
    )
    response = await asyncio.to_thread(model.generate_content, content)
    return response.text
