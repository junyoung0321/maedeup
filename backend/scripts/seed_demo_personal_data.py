"""시연용 PersonalData 시드 스크립트 — D-1 사전 작업 자동화.

목적: 시연 룸 멤버에게 시나리오 박힌 PersonalData(`is_ai_filled=True` 포함)를 주입.
- ACT 0 메인화면 ✨ 노출용
- ACT 5 reasoning 이름 인용 ("수현님 채식 ✨ 반영")용

사용:
    docker exec maedeup-api python -m scripts.seed_demo_personal_data --room 28
    docker exec maedeup-api python -m scripts.seed_demo_personal_data --room 28 --dry-run

룸의 RoomMember를 조회 후, User.name이 SEED_MAP 키와 매칭되면 해당 시드 적용.
- 매칭되지 않는 멤버는 skip (게스트 예린 등)
- is_ai_filled[category]=True로 ✨ 마크 표시
- Idempotent — 여러 번 돌려도 같은 결과
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.session import AsyncSessionLocal
from app.models.room import Room, RoomMember
from app.models.user import User

logger = logging.getLogger("seed_demo_personal_data")
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


# 시나리오 박힌 시드. user.name 매칭 (정확한 표기 가정).
_지민_DATA: dict[str, object] = {
    "food_preferences": ["한식"],
    "liked_areas": ["강남"],
    "home_base": "강남",          # C3 lightweight: home_base vs default_place_hint 비교용
    "time_preference": "저녁형",
    "share_food_data": True,
    "share_location_data": True,
}

SEED_MAP: dict[str, dict[str, object]] = {
    "지민": _지민_DATA,
    "김창윤": _지민_DATA,         # 실제 host alias — 동일 시드 적용
    "수현": {
        "food_preferences": ["일식"],   # 지민(["한식"])과 distinct → Jaccard < 70%
        "food_restrictions": ["채식"],
        "liked_areas": ["홍대"],
        "disliked_areas": ["홍대"],     # ACT 5 reasoning 인용용 (보존)
        "home_base": "홍대",
        "share_food_data": True,
    },
    "민수": {
        "food_preferences": ["중식"],   # distinct
        "transport_mode": "지하철",
        "home_base": "신촌",
        "share_food_data": True,
    },
    "예린": {
        "food_preferences": ["양식"],   # distinct
        "home_base": "강남역",
        "share_food_data": True,
    },
    # group union = ["한식","일식","중식","양식"], 김창윤 ["한식"] Jaccard = 1/4 = 25% < 70% → C3 toggle 활성
}


async def _apply_seed(session: AsyncSession, user: User, seed: dict[str, object], dry_run: bool) -> dict[str, object]:
    """user에 seed 적용. is_ai_filled[cat]=True. Returns applied changes summary."""
    applied: dict[str, object] = {}
    is_ai_filled = dict(user.is_ai_filled or {})

    for category, value in seed.items():
        current = getattr(user, category, None)
        # 동일 값이면 skip (idempotent + 깔끔한 로그)
        if current == value and is_ai_filled.get(category) is True:
            applied[category] = "unchanged"
            continue
        applied[category] = {"from": current, "to": value}
        if not dry_run:
            setattr(user, category, value)
            is_ai_filled[category] = True

    if not dry_run and applied:
        # is_ai_filled은 mutable JSON dict — 새 dict 할당해야 SQLModel이 감지
        user.is_ai_filled = is_ai_filled
        session.add(user)

    return applied


async def main(room_id: int, dry_run: bool) -> int:
    async with AsyncSessionLocal() as session:
        room = (await session.execute(select(Room).where(Room.id == room_id))).scalar_one_or_none()
        if room is None:
            logger.error("Room %s not found", room_id)
            return 1

        member_rows = (
            await session.execute(
                select(User)
                .join(RoomMember, RoomMember.user_id == User.id)
                .where(RoomMember.room_id == room_id)
            )
        ).scalars().all()

        if not member_rows:
            logger.warning("Room %s has no members", room_id)
            return 0

        logger.info(
            "Room %s '%s' — %d members. dry_run=%s",
            room_id, room.name, len(member_rows), dry_run,
        )

        applied_count = 0
        for user in member_rows:
            seed = SEED_MAP.get(user.name)
            if seed is None:
                logger.info("  [skip] %s (id=%s) — no seed for this name", user.name, user.id)
                continue
            applied = await _apply_seed(session, user, seed, dry_run)
            non_unchanged = {k: v for k, v in applied.items() if v != "unchanged"}
            if non_unchanged:
                logger.info("  [%s] %s (id=%s): %s", "DRY" if dry_run else "OK", user.name, user.id, non_unchanged)
                applied_count += 1
            else:
                logger.info("  [skip] %s (id=%s) — already seeded (idempotent)", user.name, user.id)

        if not dry_run and applied_count:
            await session.commit()
            logger.info("Committed %d user updates.", applied_count)
        elif dry_run:
            logger.info("Dry-run complete — no DB changes. %d users would update.", applied_count)
        else:
            logger.info("All target users already seeded — no changes.")

        return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="시연용 PersonalData 시드")
    parser.add_argument("--room", type=int, required=True, help="시연 룸 ID")
    parser.add_argument("--dry-run", action="store_true", help="DB 쓰기 없이 미리 확인만")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(asyncio.run(main(args.room, args.dry_run)))
