"""Demo seed — 졸업 시연용 demo-a@maedeup.app / demo-b@maedeup.app 계정 부트스트랩.

목적: 시연 전 두 계정을 깨끗한 baseline 상태로 reset.
- 두 user (없으면 생성, 있으면 personal_data 비우기 + is_ai_filled={})
- 친구 관계 (없으면 accepted로 생성, 있으면 status=accepted 보장)

사용:
    docker exec maedeup-api python -m scripts.seed_demo
    docker exec maedeup-api python -m scripts.seed_demo --reset-personal-data
    docker exec maedeup-api python -m scripts.seed_demo --reset-all   # 추가로 두 user의 chat_message / room 멤버 등도 정리

Idempotent — 여러 번 돌려도 안전.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.session import AsyncSessionLocal
from app.models.ai_memory import AIMemory
from app.models.chat import ChatMessage
from app.models.friendship import Friendship, FriendshipStatus
from app.models.room import RoomMember
from app.models.user import User

logger = logging.getLogger("seed_demo")
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


DEMO_A_EMAIL = "demo-a@maedeup.app"
DEMO_A_NAME = "Demo A"
DEMO_B_EMAIL = "demo-b@maedeup.app"
DEMO_B_NAME = "Demo B"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _get_or_create_user(session: AsyncSession, *, email: str, name: str) -> User:
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalars().first()
    if user is not None:
        logger.info("user exists: %s (id=%s)", email, user.id)
        return user
    user = User(email=email, name=name)
    session.add(user)
    await session.flush()
    logger.info("user created: %s (id=%s)", email, user.id)
    return user


async def _reset_personal_data(session: AsyncSession, user: User) -> None:
    user.food_preferences = None
    user.food_preference_note = None
    user.food_restrictions = None
    user.liked_areas = None
    user.disliked_areas = None
    user.time_preference = None
    user.transport_mode = None
    user.is_ai_filled = {}
    user.home_base = None
    session.add(user)
    logger.info("  → personal_data cleared for %s", user.email)


async def _ensure_friendship(
    session: AsyncSession, *, user_a: User, user_b: User
) -> None:
    fr = (
        await session.execute(
            select(Friendship).where(
                or_(
                    (Friendship.requester_id == user_a.id)
                    & (Friendship.addressee_id == user_b.id),
                    (Friendship.requester_id == user_b.id)
                    & (Friendship.addressee_id == user_a.id),
                )
            )
        )
    ).scalars().first()
    if fr is None:
        fr = Friendship(
            requester_id=user_a.id,
            addressee_id=user_b.id,
            status=FriendshipStatus.accepted.value,
            updated_at=_now(),
        )
        session.add(fr)
        logger.info("friendship created: %s ↔ %s (accepted)", user_a.email, user_b.email)
    else:
        if fr.status != FriendshipStatus.accepted.value:
            fr.status = FriendshipStatus.accepted.value
            fr.updated_at = _now()
            session.add(fr)
            logger.info(
                "friendship found, forced to accepted: %s ↔ %s", user_a.email, user_b.email
            )
        else:
            logger.info(
                "friendship exists (accepted): %s ↔ %s", user_a.email, user_b.email
            )


async def _purge_user_artifacts(session: AsyncSession, user: User) -> None:
    """--reset-all 시: user의 AIMemory + RoomMember 정리. user/Room 자체는 보존."""
    mem_result = await session.execute(
        select(AIMemory).where(AIMemory.user_id == user.id)
    )
    memories = mem_result.scalars().all()
    for m in memories:
        await session.delete(m)
    if memories:
        logger.info("  → deleted %d AIMemory rows for %s", len(memories), user.email)

    rm_result = await session.execute(
        select(RoomMember).where(RoomMember.user_id == user.id)
    )
    rms = rm_result.scalars().all()
    for rm in rms:
        await session.delete(rm)
    if rms:
        logger.info("  → deleted %d RoomMember rows for %s", len(rms), user.email)


async def _purge_user_chat(session: AsyncSession, user: User) -> None:
    """--reset-all 시: user.name으로 보낸 chat_messages 정리.

    ChatMessage에는 user_id 필드가 없고 sender(name)만 있으므로 name 매칭.
    """
    result = await session.execute(
        select(ChatMessage).where(ChatMessage.sender == user.name)
    )
    rows = result.scalars().all()
    for r in rows:
        await session.delete(r)
    if rows:
        logger.info("  → deleted %d ChatMessage rows by sender=%s", len(rows), user.name)


async def main(*, reset_personal_data: bool, reset_all: bool) -> None:
    async with AsyncSessionLocal() as session:
        user_a = await _get_or_create_user(session, email=DEMO_A_EMAIL, name=DEMO_A_NAME)
        user_b = await _get_or_create_user(session, email=DEMO_B_EMAIL, name=DEMO_B_NAME)

        if reset_personal_data or reset_all:
            await _reset_personal_data(session, user_a)
            await _reset_personal_data(session, user_b)

        if reset_all:
            logger.info("--reset-all: purging chat / memories / room memberships for demo users")
            await _purge_user_chat(session, user_a)
            await _purge_user_chat(session, user_b)
            await _purge_user_artifacts(session, user_a)
            await _purge_user_artifacts(session, user_b)

        await _ensure_friendship(session, user_a=user_a, user_b=user_b)

        await session.commit()

        logger.info("─" * 60)
        logger.info("Demo seed complete.")
        logger.info("  %s (id=%s) ↔ %s (id=%s)", DEMO_A_EMAIL, user_a.id, DEMO_B_EMAIL, user_b.id)
        logger.info("  Status: friends accepted")
        if reset_personal_data or reset_all:
            logger.info("  Personal data: cleared")
        if reset_all:
            logger.info("  Chat / AIMemory / RoomMember rows: purged")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Maedeup demo seed.")
    p.add_argument(
        "--reset-personal-data",
        action="store_true",
        help="두 demo user의 personal_data 칼럼을 모두 비움 (홈 PersonalData 빈 상태로 시연 시작).",
    )
    p.add_argument(
        "--reset-all",
        action="store_true",
        help="--reset-personal-data + chat 메시지 / AIMemory / RoomMember 정리.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        asyncio.run(main(reset_personal_data=args.reset_personal_data, reset_all=args.reset_all))
    except KeyboardInterrupt:
        sys.exit(1)
