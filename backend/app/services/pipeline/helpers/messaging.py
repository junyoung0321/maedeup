"""AI 메시지 emit + 에러 처리 + 대화 요약.

원본 위치: langgraph_pipeline.py 라인 312~355 (_compress_message_history),
  416~417 (_has_node_error), 420~433 (_handle_node_exception),
  1250~1309 (_emit_assistant_message).

Phase 3 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

가장 자주 호출되는 헬퍼:
  - _has_node_error: 16회
  - _emit_assistant_message: 15회
  - _handle_node_exception: 10회

의존:
  - state.GraphState
  - constants: FRIENDLY_ERROR_MESSAGE, RECENT_MESSAGE_LIMIT, SUMMARY_TRIGGER_INTERVAL
  - formatting._room_id_as_int
  - state._message_to_text
  - app.services.gemini.call_gemini
  - app.models.chat.ChatMessage, PaneType
  - sqlalchemy AsyncSession
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, PaneType
from app.core.config import settings
from app.services.llm import call_llm
from app.services.pipeline.constants import (
    FRIENDLY_ERROR_MESSAGE,
    RECENT_MESSAGE_LIMIT,
    SUMMARY_TRIGGER_INTERVAL,
)
from app.services.pipeline.helpers.formatting import _room_id_as_int
from app.services.pipeline.state import GraphState, _message_to_text

logger = logging.getLogger(__name__)


async def _compress_message_history(state: GraphState) -> None:
    raw_text_messages = [_message_to_text(message) for message in state["message_records"] if message.get("content")]
    state["recent_messages"] = raw_text_messages[-RECENT_MESSAGE_LIMIT:]
    total_message_count = len(raw_text_messages)
    last_summary_count = int(state.get("summary_message_count") or 0)

    if total_message_count == 0:
        return
    if total_message_count - last_summary_count < SUMMARY_TRIGGER_INTERVAL:
        return

    messages_for_summary = raw_text_messages[last_summary_count:total_message_count]
    if not messages_for_summary:
        return

    prompt = (
        "당신은 모임 대화 메모를 구조화해서 정리하는 요약기입니다.\n"
        "아래 형식을 그대로 유지한 구조화된 문자열만 반환하세요.\n"
        "각 항목은 비어 있으면 '없음'으로 적으세요.\n\n"
        "[확정된 결정]\n"
        "- 날짜: ...\n"
        "- 장소: ...\n"
        "- 모임 종류: ...\n"
        "[남은 질문]\n"
        "- ...\n"
        "[멤버 선호]\n"
        "- ...\n"
        "[핵심 맥락]\n"
        "- ...\n\n"
        "기존 요약:\n"
        f"{state.get('conversation_summary') or '없음'}\n\n"
        "새로 반영할 대화:\n"
        f"{chr(10).join(messages_for_summary)}"
    )

    try:
        summary = (await call_llm(prompt, provider=settings.LLM_PROVIDER_FOR_SUMMARY)).strip()
    except Exception as exc:
        logger.exception("Failed to summarize conversation memory: %s", exc)
        summary = ""

    if summary:
        state["conversation_summary"] = summary
        state["summary_message_count"] = total_message_count


def _has_node_error(state: GraphState) -> bool:
    return str(state.get("status", "")).endswith("_error")


async def _handle_node_exception(
    node_name: str,
    state: GraphState,
    exc: Exception,
) -> GraphState:
    logger.exception("LangGraph node failed: %s", node_name, exc_info=exc)
    state["status"] = f"{node_name}_error"
    state["validation_passed"] = False
    state["awaiting_user_reply"] = False
    try:
        await _emit_assistant_message(state["room_id"], state["db"], FRIENDLY_ERROR_MESSAGE, state)
    except Exception:
        logger.exception("Failed to emit recovery message for node: %s", node_name)
    return state


async def _emit_assistant_message(
    room_id: str,
    db: AsyncSession,
    content: str,
    state: GraphState,
    *,
    shared: bool = False,
) -> None:
    room_pk = _room_id_as_int(room_id)
    timestamp = datetime.now(timezone.utc).isoformat()
    state["message_records"].append(
        {
            "role": "assistant",
            "content": content,
            "sender": "매듭 AI",
            "created_at": timestamp,
        }
    )
    await _compress_message_history(state)

    if room_pk is None:
        return

    viewer_user_id = state.get("viewer_user_id")
    if shared:
        vis = "shared"
        uid = None
    else:
        vis = "private" if viewer_user_id is not None else "shared"
        uid = viewer_user_id
    message = ChatMessage(
        pane_type=PaneType.agent,
        role="assistant",
        content=content,
        sender="매듭 AI",
        room_id=room_pk,
        user_id=uid,
        visibility=vis,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    if message.id is not None:
        state["seen_message_ids"].append(message.id)
        # 새 어시스턴트 메시지 추적 (agent.py가 Redis로 발행할 수 있도록)
        if "new_assistant_messages" not in state:
            state["new_assistant_messages"] = []  # type: ignore[typeddict-unknown-key]
        state["new_assistant_messages"].append(  # type: ignore[typeddict-unknown-key]
            {
                "id": message.id,
                "pane_type": message.pane_type,
                "role": message.role,
                "content": message.content,
                "sender": message.sender,
                "created_at": message.created_at.isoformat(),
                "visibility": message.visibility,
                "user_id": message.user_id,
            }
        )
