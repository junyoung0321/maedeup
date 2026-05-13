"""memory_extraction 노드 + personal data 발행 헬퍼.

원본 위치: langgraph_pipeline.py 라인 4565~4573 (_is_empty_personal_data),
  4576~4604 (_publish_personal_data_updates),
  4607~4623 (_spawn_memory_extraction_async),
  4626~4769 (memory_extraction).

Phase 4 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

특이사항: memory_extraction은 graph에서 분리됨 (P0-2). maedeup_card_creation이
asyncio.create_task로 fire-and-forget 호출. 외부 (meetings.py)에서도 import.

의존:
  - state.GraphState
  - helpers.messaging._has_node_error
  - app.core.config.settings
  - app.db.session.AsyncSessionLocal
  - app.models: AIMemory, ChatMessage, PaneType, RoomMember, User
  - app.services.personal_data_extractor.extract_personal_data
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.ai_memory import AIMemory
from app.models.chat import ChatMessage, PaneType
from app.models.room import RoomMember
from app.models.user import User
from app.services.personal_data_extractor import extract_personal_data
from app.services.pipeline.helpers.messaging import _has_node_error
from app.services.pipeline.state import GraphState

logger = logging.getLogger(__name__)


def _is_empty_personal_data(value: Any) -> bool:
    """Personal data 필드가 '비어있다'고 볼 수 있는 값인지."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


async def _publish_personal_data_updates(user_ids: list[int]) -> None:
    """홈 PersonalData 패널 fade-in을 위한 user-scoped Redis publish.

    실패는 logging만. extraction 자체를 깨지 않음.
    """
    if not user_ids:
        return
    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        try:
            for uid in user_ids:
                envelope = {
                    "type": "personal_data:updated",
                    "user_id": uid,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                await r.publish(
                    f"personal_data:user:{uid}:updated",
                    json.dumps(envelope, ensure_ascii=False),
                )
        finally:
            await r.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.warning("personal_data Redis publish failed: %s", exc)


async def _spawn_memory_extraction_async(state_snapshot: GraphState) -> None:
    """P0-2 (2026-05-08): maedeup_card_creation 후 memory_extraction을 fire-and-forget으로 실행.

    Graph가 이걸 sequential로 돌면 ACT 4 latency가 4.5s → ~0.05s 차이로 사용자 인식 침묵 발생.
    분리해서 카드는 즉시 emit, ✨ 학습 카드는 ~4s 후 별도 emit (자연스러운 flow).

    state['db'] 세션은 graph 종결 후 close 가능성 → 새 session 필수.
    state 자체는 shallow copy로 detached task와 분리 (graph 이후 변경되어도 task 영향 X).
    실패는 silent log only — 모임 카드는 이미 발행된 상태라 회복 불가능 + 모임 자체를 깨뜨리면 안 됨.
    """
    try:
        async with AsyncSessionLocal() as new_session:
            detached_state: GraphState = dict(state_snapshot)  # type: ignore[assignment]
            detached_state["db"] = new_session
            await memory_extraction(detached_state)
    except Exception:
        logger.exception("Detached memory_extraction failed")


async def memory_extraction(state: GraphState) -> GraphState:
    """모임 종료(maedeup_card_creation) 직후 transcript에서 멤버별 personal data 추출.

    Write 정책 (디자인 P5):
    - User 필드가 비어있으면 → setattr + is_ai_filled[cat]=True (Case A)
    - User 필드가 AI로 채워진 적 있으면 → 새 값으로 update + is_ai_filled[cat]=True (Case B)
    - User 필드를 사용자가 직접 입력했으면 → User 건드리지 않음, AIMemory만 status='superseded_by_manual' (Case C)

    매 추출에 대해 AIMemory row INSERT (값 동일해도 — 시점 기록 가치).
    실패는 log only — 모임 자체를 깨뜨리지 않음.
    """
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state
        if not state.get("maedeup_card_payload"):
            # 매듭 카드가 안 만들어졌으면 모임이 종결된 게 아니므로 skip
            return state

        room_id_raw = state.get("room_id")
        try:
            room_id = int(room_id_raw)
        except (TypeError, ValueError):
            logger.warning("memory_extraction: invalid room_id=%r", room_id_raw)
            return state

        db: AsyncSession = state["db"]

        # 1. room members
        member_rows = (
            await db.execute(
                select(RoomMember).where(RoomMember.room_id == room_id)
            )
        ).scalars().all()
        member_ids: list[int] = [m.user_id for m in member_rows]
        if not member_ids:
            logger.info("memory_extraction: room=%s has no members, skip", room_id)
            return state

        # 2. transcript — 사용자 발화만 (assistant/system 제외, social pane만)
        transcript_rows = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.room_id == room_id)
                .where(ChatMessage.pane_type == PaneType.social.value)
                .where(ChatMessage.role == "user")
                .order_by(ChatMessage.created_at.asc())
            )
        ).scalars().all()
        if not transcript_rows:
            logger.info("memory_extraction: room=%s has no user messages, skip", room_id)
            return state

        # 3. extract (Gemini 또는 canned fallback)
        try:
            extractions = await extract_personal_data(
                transcript=transcript_rows,
                member_ids=member_ids,
                db=db,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory_extraction: extract failed: %s", exc)
            return state

        # 4. write — 단일 트랜잭션. 부분 실패 시 롤백, 부분 상태 금지.
        affected_user_ids: list[int] = []
        try:
            users_by_id = {
                u.id: u
                for u in (
                    await db.execute(select(User).where(User.id.in_(member_ids)))
                ).scalars().all()
            }

            for member_id, cat_results in extractions.items():
                if not cat_results:
                    continue
                user = users_by_id.get(member_id)
                if user is None:
                    continue

                user_changed = False
                is_ai_filled = dict(user.is_ai_filled or {})

                for category, ext in cat_results.items():
                    current_value = getattr(user, category, None)
                    already_ai = bool(is_ai_filled.get(category, False))

                    if _is_empty_personal_data(current_value):
                        # Case A
                        setattr(user, category, ext.value)
                        is_ai_filled[category] = True
                        status = "active"
                        user_changed = True
                    elif already_ai:
                        # Case B
                        setattr(user, category, ext.value)
                        is_ai_filled[category] = True
                        status = "active"
                        user_changed = True
                    else:
                        # Case C — manual entry, do not overwrite
                        status = "superseded_by_manual"

                    content_payload = {
                        "value": ext.value,
                        "confidence": ext.confidence,
                        "source_quote": ext.source_quote,
                        "status": status,
                    }
                    db.add(
                        AIMemory(
                            user_id=member_id,
                            memory_type=category,
                            content=json.dumps(content_payload, ensure_ascii=False),
                            source_room_id=room_id,
                            source_message_id=ext.source_message_id,
                        )
                    )

                if user_changed:
                    user.is_ai_filled = is_ai_filled
                    db.add(user)
                    affected_user_ids.append(member_id)

            await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("memory_extraction: write failed, rolling back: %s", exc)
            await db.rollback()
            return state

        # 5. Redis publish (트랜잭션 성공 후)
        await _publish_personal_data_updates(affected_user_ids)

        logger.info(
            "[TIMING] memory_extraction: %.2fs (room=%s, %d users affected)",
            time.monotonic() - _t0,
            room_id,
            len(affected_user_ids),
        )
        return state
    except Exception as exc:
        logger.exception("memory_extraction unexpected failure: %s", exc)
        return state
