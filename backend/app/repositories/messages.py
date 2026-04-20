"""Typed access layer for ChatMessage privacy boundary.

docs/ai-separation.md §9.4 — the LLM context filter is the single point where
private-by-default can break. To make it impossible to forget, every pipeline call
MUST load its context through `MessageReader.load_agent_context`, which returns a
branded `AgentContextMessages` value. `run_pipeline` refuses any other input type.

Raw `select(ChatMessage)` outside this module is banned. If you need ChatMessage
rows for a non-pipeline purpose, add a new classmethod here with its own filter
semantics — do not bypass.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, or_
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, PaneType, Visibility


@dataclass(frozen=True)
class AgentContextMessages:
    """Branded container. `run_pipeline` accepts no other type.

    viewer_user_id = None → shared-only view (auto-trigger path)
    viewer_user_id = int  → viewer's private + all shared
    """

    messages: list[ChatMessage]
    viewer_user_id: int | None

    def __iter__(self):  # pragma: no cover — convenience only
        return iter(self.messages)

    def __len__(self) -> int:
        return len(self.messages)


class MessageReader:
    """Only sanctioned way to read ChatMessage rows for agent pipelines."""

    @staticmethod
    async def load_agent_context(
        session: AsyncSession,
        room_id: int,
        viewer_user_id: int | None,
        limit: int = 20,
    ) -> AgentContextMessages:
        """Load the last `limit` agent-pane messages visible to `viewer_user_id`.

        - Always excludes other users' private messages.
        - viewer_user_id=None caps the view to visibility='shared' (auto-trigger).
        - Returns rows oldest-first (same order the previous inline queries did).
        """
        q = (
            select(ChatMessage)
            .where(ChatMessage.room_id == room_id)
            .where(ChatMessage.pane_type == PaneType.agent)
        )

        if viewer_user_id is None:
            q = q.where(ChatMessage.visibility == Visibility.shared.value)
        else:
            q = q.where(
                or_(
                    ChatMessage.visibility == Visibility.shared.value,
                    and_(
                        ChatMessage.visibility == Visibility.private.value,
                        ChatMessage.user_id == viewer_user_id,
                    ),
                )
            )

        q = q.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit)
        result = await session.execute(q)
        rows = list(reversed(result.scalars().all()))
        return AgentContextMessages(messages=rows, viewer_user_id=viewer_user_id)

    @staticmethod
    def ensure_branded(value: Any) -> AgentContextMessages:
        """Runtime guard for run_pipeline — raise if caller bypassed the reader."""
        if not isinstance(value, AgentContextMessages):
            raise TypeError(
                "run_pipeline requires AgentContextMessages. "
                "Use MessageReader.load_agent_context() to build context. "
                f"Got: {type(value).__name__}"
            )
        return value
