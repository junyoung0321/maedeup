import asyncio

import google.generativeai as genai

from app.core.config import settings

_EMBEDDING_MODEL = "models/text-embedding-004"


async def get_embedding(text: str) -> list[float]:
    """텍스트를 768차원 벡터로 변환합니다 (text-embedding-004)."""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    result = await asyncio.to_thread(
        genai.embed_content,
        model=_EMBEDDING_MODEL,
        content=text,
    )
    return result["embedding"]
