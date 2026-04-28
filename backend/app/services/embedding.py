import asyncio
import logging

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted

from app.core.config import settings

_EMBEDDING_MODEL = "models/gemini-embedding-001"
_EMBEDDING_DIM = 768
logger = logging.getLogger(__name__)


async def get_embedding(text: str) -> list[float]:
    """텍스트를 768차원 벡터로 변환합니다 (embedding-001)."""
    if not settings.GEMINI_API_KEY.strip():
        logger.warning("GEMINI_API_KEY not set, returning zero embedding")
        return [0.0] * _EMBEDDING_DIM

    genai.configure(api_key=settings.GEMINI_API_KEY)
    try:
        result = await asyncio.to_thread(
            genai.embed_content,
            model=_EMBEDDING_MODEL,
            content=text,
        )
        return result["embedding"]
    except (ResourceExhausted, GoogleAPICallError) as exc:
        logger.warning("Embedding API error: %s", exc)
        return [0.0] * _EMBEDDING_DIM
    except Exception as exc:
        logger.error("Unexpected embedding error: %s", exc)
        return [0.0] * _EMBEDDING_DIM
