import google.generativeai as genai

from app.core.config import settings

_SYSTEM_PROMPT = (
    "당신은 매듭 앱의 AI 어시스턴트입니다.\n"
    "모임 일정 조율, 장소 추천, 그룹 관리를 도와줍니다.\n"
    "항상 한국어로 대답하세요."
)


class GeminiService:
    def __init__(self) -> None:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=_SYSTEM_PROMPT,
        )

    async def chat(self, message: str) -> str:
        """사용자 메시지를 받아 Gemini 응답 문자열을 반환합니다."""
        response = await self._model.generate_content_async(message)
        return response.text


gemini_service = GeminiService()
