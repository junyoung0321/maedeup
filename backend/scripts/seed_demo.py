"""Demo seed — 졸업 시연 통합 시나리오용 4명 계정 부트스트랩.

목적: 시연 전 4명을 깨끗한 baseline 상태로 reset 하거나 사전 학습된 Personal Data 시드.

시나리오 멤버:
- 지민 (방장, jimin@maedeup.app) — 한식·강남·저녁형·지하철 ✨
- 수현 (멤버, suhyun@maedeup.app) — 채식·홍대 비선호 ✨
- 민수 (멤버, minsu@maedeup.app) — 지하철 ✨
- 예린은 게스트라 시드 X (시연 중 카톡 링크로 동적 입장)

사용:
    docker exec maedeup-api python -m scripts.seed_demo                       # 계정 + 친구만
    docker exec maedeup-api python -m scripts.seed_demo --reset-personal-data # personal_data 비우기
    docker exec maedeup-api python -m scripts.seed_demo --seed-personal-data  # 시연 ✨ 박기
    docker exec maedeup-api python -m scripts.seed_demo --reset-all           # 모든 자료 정리

Idempotent — 여러 번 돌려도 안전.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from itertools import combinations
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


# 시연 통합 시나리오 멤버 (게스트 예린은 동적 입장이라 시드 X)
DEMO_USERS = [
    {"email": "jimin@maedeup.app", "name": "지민"},
    {"email": "suhyun@maedeup.app", "name": "수현"},
    {"email": "minsu@maedeup.app", "name": "민수"},
]

# 사전 학습된 Personal Data ✨ (시연 ACT 0/5 reasoning 활용용)
PERSONAL_DATA_SEED = {
    "jimin@maedeup.app": {
        "food_preferences": ["한식"],
        "liked_areas": ["강남"],
        "time_preference": "평일 저녁",
        "transport_mode": "지하철",
        "is_ai_filled": {
            "food_preferences": True,
            "liked_areas": True,
            "time_preference": True,
            "transport_mode": True,
        },
    },
    "suhyun@maedeup.app": {
        "food_restrictions": ["채식"],
        "disliked_areas": ["홍대"],
        "is_ai_filled": {
            "food_restrictions": True,
            "disliked_areas": True,
        },
    },
    "minsu@maedeup.app": {
        "transport_mode": "지하철",
        "is_ai_filled": {
            "transport_mode": True,
        },
    },
}


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


async def _seed_personal_data(session: AsyncSession, user: User) -> None:
    """사전 학습된 ✨ Personal Data 박기 (시연 ACT 0 메인 투어용)."""
    seed = PERSONAL_DATA_SEED.get(user.email)
    if seed is None:
        logger.info("  → no personal data seed defined for %s, skip", user.email)
        return

    if "food_preferences" in seed:
        user.food_preferences = seed["food_preferences"]
    if "food_restrictions" in seed:
        user.food_restrictions = seed["food_restrictions"]
    if "liked_areas" in seed:
        user.liked_areas = seed["liked_areas"]
    if "disliked_areas" in seed:
        user.disliked_areas = seed["disliked_areas"]
    if "time_preference" in seed:
        user.time_preference = seed["time_preference"]
    if "transport_mode" in seed:
        user.transport_mode = seed["transport_mode"]
    if "is_ai_filled" in seed:
        user.is_ai_filled = seed["is_ai_filled"]

    session.add(user)
    logger.info(
        "  → personal_data ✨ seeded for %s (categories=%s)",
        user.email,
        list(seed.get("is_ai_filled", {}).keys()),
    )


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
    """--reset-all 시: user.name으로 보낸 chat_messages 정리."""
    result = await session.execute(
        select(ChatMessage).where(ChatMessage.sender == user.name)
    )
    rows = result.scalars().all()
    for r in rows:
        await session.delete(r)
    if rows:
        logger.info("  → deleted %d ChatMessage rows by sender=%s", len(rows), user.name)


async def main(
    *,
    reset_personal_data: bool,
    seed_personal_data: bool,
    reset_all: bool,
) -> None:
    async with AsyncSessionLocal() as session:
        # 모든 데모 유저 생성/조회
        users: list[User] = []
        for spec in DEMO_USERS:
            user = await _get_or_create_user(session, email=spec["email"], name=spec["name"])
            users.append(user)

        # 데이터 정리
        if reset_personal_data or reset_all:
            for user in users:
                await _reset_personal_data(session, user)

        if reset_all:
            logger.info("--reset-all: purging chat / memories / room memberships for demo users")
            for user in users:
                await _purge_user_chat(session, user)
                await _purge_user_artifacts(session, user)

        # 사전 학습 ✨ 시드
        if seed_personal_data:
            logger.info("--seed-personal-data: seeding ✨ Personal Data for demo users")
            # 시드 전에 기존 데이터 비움 (idempotency 보장)
            for user in users:
                await _reset_personal_data(session, user)
            for user in users:
                await _seed_personal_data(session, user)

        # 모든 페어 친구 관계 보장
        for user_a, user_b in combinations(users, 2):
            await _ensure_friendship(session, user_a=user_a, user_b=user_b)

        await session.commit()

        logger.info("─" * 60)
        logger.info("Demo seed complete.")
        for user in users:
            logger.info("  %s (id=%s, name=%s)", user.email, user.id, user.name)
        logger.info("  Status: all pairs friends (accepted)")
        if reset_personal_data or reset_all:
            logger.info("  Personal data: cleared")
        if seed_personal_data:
            logger.info("  Personal data: ✨ seeded")
        if reset_all:
            logger.info("  Chat / AIMemory / RoomMember rows: purged")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Maedeup demo seed (4-person scenario).")
    p.add_argument(
        "--reset-personal-data",
        action="store_true",
        help="모든 demo user의 personal_data 칼럼을 비움 (홈 PersonalData 빈 상태로 시연 시작).",
    )
    p.add_argument(
        "--seed-personal-data",
        action="store_true",
        help="사전 학습된 ✨ Personal Data 박기 (ACT 0 메인 투어 + ACT 5 reasoning 활용용).",
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
        asyncio.run(
            main(
                reset_personal_data=args.reset_personal_data,
                seed_personal_data=args.seed_personal_data,
                reset_all=args.reset_all,
            )
        )
    except KeyboardInterrupt:
        sys.exit(1)
