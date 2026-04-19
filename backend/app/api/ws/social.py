import asyncio
from contextlib import suppress
import json
import logging
import re
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlmodel import select

from app.api.ws.manager import manager
from app.core.config import settings
from app.core.security import verify_token
from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMessage, PaneType
from app.models.room import RoomMember
from app.services.intent_classifier import classify_intent
from app.services.stalemate_judge import judge_stalemate

router = APIRouter()
logger = logging.getLogger(__name__)

# 의도 감지 알림을 트리거할 의도 목록
_NOTIFIABLE_INTENTS = {"meeting_schedule", "place_suggestion"}


async def _publish_social_message(
    redis_client: aioredis.Redis | None,
    channel: str,
    message: str,
) -> None:
    try:
        if redis_client is not None:
            await redis_client.publish(channel, message)
            return
    except Exception:
        logger.warning("Redis publish failed for social channel %s", channel, exc_info=True)

    await manager.broadcast(channel, message)


async def _redis_subscriber(
    channel: str,
    websocket: WebSocket,
    stop_event: asyncio.Event,
) -> None:
    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
    except Exception:
        logger.exception("Redis subscriber unavailable for social channel %s", channel)
        return
    try:
        while not stop_event.is_set():
            try:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.01
                )
            except Exception:
                logger.exception("Redis subscriber read failed for social channel %s", channel)
                break
            if msg:
                data = msg["data"]
                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    try:
                        await websocket.send_text(data)
                    except WebSocketDisconnect:
                        break
                    continue

                try:
                    if parsed.get("type") in ("reminder", "vote_reminder"):
                        await websocket.send_text(json.dumps(parsed, ensure_ascii=False))
                    else:
                        await websocket.send_text(data)
                except WebSocketDisconnect:
                    break
            else:
                await asyncio.sleep(0.01)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await r.aclose()


@router.websocket("/ws/social/{room_id}")
async def social_ws(
    websocket: WebSocket,
    room_id: str,
    token: Optional[str] = Query(default=None),
) -> None:
    await websocket.accept()

    # 토큰 검증
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return
    try:
        token_payload = verify_token(token)
    except Exception:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    try:
        room_pk: Optional[int] = int(room_id)
    except (TypeError, ValueError):
        room_pk = None

    # 룸 멤버십 확인
    if room_pk is not None:
        try:
            user_id_check = int(token_payload["sub"])
            async with AsyncSessionLocal() as _session:
                member_result = await _session.execute(
                    select(RoomMember).where(
                        RoomMember.room_id == room_pk,
                        RoomMember.user_id == user_id_check,
                    )
                )
                if member_result.scalar_one_or_none() is None:
                    await websocket.close(code=4003, reason="Not a member of this room")
                    return
        except (TypeError, ValueError):
            await websocket.close(code=4003, reason="Invalid user token")
            return
    else:
        await websocket.close(code=4003, reason="Invalid room_id")
        return

    stop_event = asyncio.Event()
    channel = f"social:{room_id}"
    manager.add(channel, websocket)
    subscriber_task = asyncio.create_task(
        _redis_subscriber(channel, websocket, stop_event)
    )

    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception:
        logger.exception("Redis client unavailable for social room %s", room_id)
        r = None
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            role = payload.get("role", "user")
            content = payload.get("content", "")
            sender = payload.get("sender")

            # 메시지 길이 제한 (2000자)
            if len(content) > 2000:
                content = content[:2000]

            async with AsyncSessionLocal() as session:
                msg = ChatMessage(
                    pane_type=PaneType.social,
                    role=role,
                    content=content,
                    sender=sender,
                    room_id=room_pk,
                )
                session.add(msg)
                await session.commit()
                await session.refresh(msg)

            out = json.dumps(
                {
                    "id": msg.id,
                    "pane_type": msg.pane_type,
                    "role": msg.role,
                    "content": msg.content,
                    "sender": msg.sender,
                    "created_at": msg.created_at.isoformat(),
                }
            )
            await _publish_social_message(r, channel, out)

            # ── 의도 감지 (백그라운드로 실행해 응답 지연 최소화) ──────────
            if settings.GEMINI_API_KEY and r is not None and role == "user" and content.strip():
                asyncio.create_task(
                    _detect_and_notify_intent(r, channel, content, msg.id)
                )

    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        with suppress(Exception):
            await subscriber_task
        manager.remove(channel, websocket)
        if r is not None:
            await r.aclose()


# ── 합의/결론 감지 패턴 ──────────────────────────────────────────────
_CONCLUSION_PATTERNS = re.compile(
    r"확정|그걸로\s*하자|그때\s*보자|오케이.*보자|ㅇㅋ.*보자|그러자|좋아.*하자|"
    r"그렇게\s*하자|그날로\s*하자|거기로\s*하자|거기서\s*보자|그럼\s*그때|"
    r"콜|ㅇㅇ.*하자|결정|최종|fix"
)


def _is_conclusion(text: str) -> bool:
    """메시지가 모임 합의/결론에 해당하는지 판별합니다."""
    return bool(_CONCLUSION_PATTERNS.search(text))


async def _detect_and_notify_intent(
    r: aioredis.Redis,
    channel: str,
    content: str,
    trigger_message_id: int,
) -> None:
    """
    메시지 의도를 분류하고, 대화 흐름에 개입이 필요한지 판정합니다.

    1단계 — 경량 필터 (비용 0):
        - classify_intent로 의도 추출 (meeting_schedule / place_suggestion / general)
        - 모임 관련 의도면 intent_detected 이벤트 발행 (프론트 배너용)
        - 모든 user 메시지에 대해 카운터 +1

    2단계 — 조건부 LLM 판정 (쿨다운 있음):
        - 카운터 >= 3 이고 60초 쿨다운 해제된 상태에서
        - 최근 10개 메시지를 judge_stalemate에 보내 교착 여부 판정
        - yes → auto_trigger 발행 + 카운터 리셋
        - no → 쿨다운만 설정 (카운터 유지, 다음 메시지 기다림)

    3단계 — 합의 감지 (regex 폴백):
        - 확정/결정 패턴이 명확히 보이면 즉시 정리 카드 트리거
    """
    try:
        result = await classify_intent(content)
        room_id = channel.split(":", 1)[1] if ":" in channel else channel
        counter_key = f"social_msg_count:{room_id}"
        cooldown_key = f"social_judge_cooldown:{room_id}"
        agent_channel = f"agent:{room_id}"

        # ── 배너 알림: 모임 관련 의도면 프론트로 발행 ───────────────────
        if (
            result["intent"] in _NOTIFIABLE_INTENTS
            and result["confidence"] >= 0.6
        ):
            await _publish_social_message(
                r,
                channel,
                json.dumps(
                    {
                        "type": "intent_detected",
                        "intent": result["intent"],
                        "confidence": result["confidence"],
                        "method": result["method"],
                        "trigger_message_id": trigger_message_id,
                    }
                ),
            )

        # ── 결론 감지: 명시적 합의 패턴 → 즉시 정리 카드 ────────────────
        if _is_conclusion(content) and result["intent"] in _NOTIFIABLE_INTENTS:
            await r.delete(counter_key)
            try:
                await r.publish(
                    agent_channel,
                    json.dumps(
                        {
                            "type": "ai_auto_trigger",
                            "intent": result["intent"],
                            "confidence": result["confidence"],
                            "content": content,
                            "trigger_message_id": trigger_message_id,
                            "trigger_reason": "conclusion_detected",
                        },
                        ensure_ascii=False,
                    ),
                )
            except Exception:
                logger.warning(
                    "Failed to publish conclusion auto_trigger to %s",
                    agent_channel,
                    exc_info=True,
                )
            return

        # ── 카운터 증가 (모든 user 메시지 대상) ──────────────────────────
        count = await r.incr(counter_key)
        await r.expire(counter_key, 600)

        if count < 3:
            logger.debug(
                "Social msg count for room %s: %d (threshold: 3, skipping judge)",
                room_id,
                count,
            )
            return

        # ── 쿨다운 체크: 최근 60초 내 judge 호출이 있었다면 skip ─────────
        if await r.get(cooldown_key):
            logger.debug("Stalemate judge cooldown active for room %s", room_id)
            return

        # ── 최근 10개 메시지 로드 ────────────────────────────────────
        try:
            room_pk = int(room_id)
        except (TypeError, ValueError):
            return

        async with AsyncSessionLocal() as session:
            rs = await session.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.room_id == room_pk,
                    ChatMessage.pane_type == PaneType.social,
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(10)
            )
            recent = list(reversed(rs.scalars().all()))

        msgs_for_judge = [
            {"sender": m.sender or "익명", "content": m.content}
            for m in recent
            if m.content and m.content.strip()
        ]
        if not msgs_for_judge:
            return

        # ── LLM 판정 ────────────────────────────────────────────────
        judgment = await judge_stalemate(msgs_for_judge)
        # 판정 결과와 무관하게 60초 쿨다운 (연속 호출 방지)
        await r.setex(cooldown_key, 60, "1")

        if not judgment.get("stalemate"):
            logger.debug(
                "Stalemate judge says no for room %s: %s",
                room_id,
                judgment.get("reason"),
            )
            return

        # ── 교착 확정 → auto_trigger 발행 + 카운터 리셋 ──────────────────
        await r.delete(counter_key)

        judged_intent = judgment.get("intent")
        if judged_intent not in _NOTIFIABLE_INTENTS:
            judged_intent = (
                result["intent"]
                if result["intent"] in _NOTIFIABLE_INTENTS
                else "meeting_schedule"
            )

        try:
            await r.publish(
                agent_channel,
                json.dumps(
                    {
                        "type": "ai_auto_trigger",
                        "intent": judged_intent,
                        "confidence": result["confidence"],
                        "content": content,
                        "trigger_message_id": trigger_message_id,
                        "trigger_reason": "stalemate_judged",
                        "judge_reason": judgment.get("reason", ""),
                    },
                    ensure_ascii=False,
                ),
            )
            logger.info(
                "Stalemate judge triggered for room %s: %s",
                room_id,
                judgment.get("reason"),
            )
        except Exception:
            logger.warning(
                "Failed to publish stalemate auto_trigger to %s",
                agent_channel,
                exc_info=True,
            )
    except Exception:
        # 의도 감지 실패는 채팅 흐름에 영향을 주지 않도록 무시
        logger.debug("Intent detection failed for channel %s", channel, exc_info=True)
