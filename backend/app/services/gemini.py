import asyncio

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted

from app.core.config import settings


async def call_gemini(content: str, timeout: float = 15.0) -> str:
    """Gemini API를 호출하고 응답 텍스트를 반환합니다.

    Fix 5 (2026-05-14): 기본 15s timeout 추가.
      SDK가 hang하면 백엔드 전체 멈춤 위험. asyncio.wait_for로 worst case 차단.
      호출처에서 timeout 명시 가능 (quick_classify는 자체 1.5s wait_for 사용 중 — 호환).
    """
    if not settings.GEMINI_API_KEY.strip():
        return ""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        system_instruction=(
            "당신은 매듭(Maedeup) AI 어시스턴트입니다. 한국인 사용자들의 모임 일정과 "
            "장소 조율을 돕는 친근하고 전문적인 어시스턴트입니다. 항상 한국어로 "
            "간결하고 자연스럽게 답변하세요."
        ),
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
