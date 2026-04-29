"""
채팅방 교착 상태 판정기 (Stalemate Judge)

최근 메시지 N개를 Gemini에게 문맥째 보내 AI가 개입해야 할 상황인지 판정합니다.
regex/키워드 휴리스틱은 false positive/negative가 많아서 LLM에 맡기는 방식.
"""

import json
import logging
import re
from typing import Iterable

from app.services.gemini import call_gemini

logger = logging.getLogger(__name__)

_NOTIFIABLE_INTENTS = ("meeting_schedule", "place_suggestion", "none")

_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}", re.MULTILINE)


def _format_messages(messages: Iterable[dict]) -> str:
    lines = []
    for m in messages:
        sender = (m.get("sender") or "익명").strip()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{sender}: {content}")
    return "\n".join(lines)


def _parse_json_response(raw: str) -> dict | None:
    if not raw:
        return None
    match = _JSON_BLOCK_RE.search(raw)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


async def judge_stalemate(messages: list[dict]) -> dict:
    """
    최근 대화가 AI 개입이 필요한 '교착 상태'인지 판정.

    Args:
        messages: [{"sender": str, "content": str}, ...] — 최근 메시지 (시간순, 최신 뒤)

    Returns:
        {
            "stalemate": bool,
            "intent": "meeting_schedule" | "place_suggestion" | "none",
            "reason": str,
        }
        LLM 실패 시 안전한 기본값 (stalemate=False) 반환.
    """
    if not messages:
        return {"stalemate": False, "intent": "none", "reason": "empty"}

    conversation = _format_messages(messages)
    if not conversation:
        return {"stalemate": False, "intent": "none", "reason": "empty"}

    prompt = f"""다음은 그룹 채팅방의 최근 대화입니다. 참여자들이 모임 일정이나 장소를 조율 중인데, AI가 개입해서 조율을 도와줘야 할 '교착 상태'인지 판정해주세요.

[대화]
{conversation}

[개입이 필요한 상황]
- 여러 사람이 일정/장소 의견을 내지만 아직 합의가 안 되고 거절/충돌이 반복됨
- 누군가 AI나 조율을 명시적·암묵적으로 요청 (예: "누가 좀 정해줘", "조율 좀", "AI가 해줘")
- 같은 주제로 3턴 이상 핑퐁하며 결정을 못 내림

[개입이 불필요한 상황]
- 이미 합의/결론이 나서 확정된 상태
- 일정·장소와 무관한 잡담
- 한두 마디만 오간 초기 상태 (아직 충분한 맥락 없음)

다음 JSON 형식으로만 답하세요. 다른 설명·코드블록 금지:
{{"stalemate": true 또는 false, "intent": "meeting_schedule" 또는 "place_suggestion" 또는 "none", "reason": "한 문장으로 판정 근거"}}"""

    raw = await call_gemini(prompt)
    parsed = _parse_json_response(raw)
    if parsed is None:
        logger.debug("Stalemate judge: failed to parse response: %r", raw[:200])
        return {"stalemate": False, "intent": "none", "reason": "parse_failed"}

    stalemate = bool(parsed.get("stalemate"))
    intent = parsed.get("intent")
    if intent not in _NOTIFIABLE_INTENTS:
        intent = "none"
    reason = str(parsed.get("reason", ""))[:200]

    return {"stalemate": stalemate, "intent": intent, "reason": reason}
