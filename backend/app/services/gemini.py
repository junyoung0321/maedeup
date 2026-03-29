import asyncio

import google.generativeai as genai

from app.core.config import settings


async def call_gemini(content: str) -> str:
    """Gemini API를 호출하고 응답 텍스트를 반환합니다."""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = await asyncio.to_thread(model.generate_content, content)
    return response.text
