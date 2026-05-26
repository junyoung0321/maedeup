"""시연용 PersonalData 시드 스크립트 — D-1 사전 작업 자동화.

목적: 시연 룸 멤버에게 시나리오 박힌 PersonalData(`is_ai_filled=True` 포함) + AIMemory 시드.
- ACT 0 메인화면 ✨ 노출용 (is_ai_filled[cat]==true)
- ACT 5 reasoning 이름 인용 ("수현님 채식 ✨ 반영")용
- ACT 6 ✨ 클릭 → 출처 모달 quote 노출용 (AIMemory active row 필수)

사용:
    docker exec maedeup-api python -m scripts.seed_demo_personal_data --room 28
    docker exec maedeup-api python -m scripts.seed_demo_personal_data --room 28 --dry-run

룸의 RoomMember를 조회 후, User.name이 SEED_MAP 키와 매칭되면 해당 시드 적용.
- 매칭되지 않는 멤버는 skip (게스트 예린 등)
- is_ai_filled[category]=True로 ✨ 마크 표시
- AIMemory active row를 함께 INSERT (없는 카테고리만, idempotent)
- Idempotent — 여러 번 돌려도 같은 결과
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.session import AsyncSessionLocal
from app.models.ai_memory import AIMemory
from app.models.room import Room, RoomMember
from app.models.user import User

logger = logging.getLogger("seed_demo_personal_data")
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


# 시나리오 박힌 시드. user.name 매칭 (정확한 표기 가정).
#
# ACT 5.5 토글 활성 조건 (compute_preference_toggle_enabled):
#   - C4 회피: home_base 또는 prefs 둘 중 하나라도 존재 → OK
#   - C1 회피: share_food_data / share_location_data / share_schedule_data 모두 True → OK
#   - C3 회피: requester_home_base(방장="신촌") ≠ default_place_hint(그룹 다수결="강남") → home_matches=False → C3 false → OK
#
# 그룹(게스트 3명) 다수결: preferred_location 다수 = "강남" → default_place_hint = "강남"
# 방장 home_base = "신촌" → 불일치 → C3 차단되지 않음 → 토글 노출 ✓
#
# food Jaccard: 방장=["일식","양식","디저트"] vs 그룹union=["한식","중식"] → 교집합=0 → 0% < 70% → C3 해당 없음 ✓
_지민_DATA: dict[str, object] = {
    "food_preferences": ["일식", "양식", "디저트"],  # 그룹(한식·중식)과 교집합 0% → C3 food 조건 불충족
    "liked_areas": ["신촌", "홍대"],
    "home_base": "신촌",           # 그룹 다수결 "강남"과 불일치 → C3 home_matches=False → 토글 활성
    "time_preference": "저녁형",
    "share_food_data": True,
    "share_location_data": True,
    "share_schedule_data": True,   # C1 완전 회피
}

SEED_MAP: dict[str, dict[str, object]] = {
    "지민": _지민_DATA,
    "김창윤": _지민_DATA,         # 실제 host alias — 동일 시드 적용
    "수현": {
        "food_preferences": ["한식"],   # 그룹 다수결 형성용 (한식)
        "food_restrictions": ["채식"],
        "liked_areas": ["강남"],
        "disliked_areas": ["홍대"],     # ACT 5 reasoning 인용용 (보존)
        "home_base": "강남",           # 그룹 다수결 → preferred_location "강남" 기여
        "share_food_data": True,
        "share_location_data": True,
        "share_schedule_data": True,
    },
    "민수": {
        "food_preferences": ["중식"],   # 그룹 union 기여 (중식)
        "transport_mode": "지하철",
        "home_base": "강남",           # 강남 다수결 강화
        "share_food_data": True,
        "share_location_data": True,
        "share_schedule_data": True,
    },
    "예린": {
        "food_preferences": ["한식"],   # 그룹 union — 한식 빈도 높여 다수결 안정화
        "home_base": "강남역",          # "강남역" ≠ "강남" (별도 값)이라 다수결 계산에 따라 강남 우세 유지
        "share_food_data": True,
        "share_location_data": True,
        "share_schedule_data": True,
    },
    # [refresh route] default_place_hint = MeetingPreference.preferred_location 다수결.
    #   방장이 ACT 1 팝업에서 "강남" 입력 → MeetingPreference.preferred_location="강남" 저장.
    #   requester_home_base(User.home_base)="신촌" ≠ default_place_hint="강남" → C3 home_matches=False → 토글 활성 ✓
    # [pipeline/agent] default_place_hint = owner.home_base.
    #   owner.home_base="신촌" == requester_home_base="신촌" → home_matches=True,
    #   BUT preference_common_foods는 pipeline state에 미주입 → food 비교 skip → C3=False → 토글 활성 ✓
    # group food union = ["한식","중식"], 방장 food = ["일식","양식","디저트"] → Jaccard = 0% < 70% → C3 food도 safe ✓
}

# User 모델에 실제로 존재하는 personal data 필드
_USER_PD_FIELDS = {
    "food_preferences",
    "food_restrictions",
    "liked_areas",
    "disliked_areas",
    "time_preference",
    "transport_mode",
}


def _content_matches(existing_content: str, category: str, value: Any) -> bool:
    """기존 AIMemory content가 동일 active row인지 비교."""
    try:
        d = json.loads(existing_content)
    except (json.JSONDecodeError, TypeError):
        return False
    if d.get("status") != "active":
        return False
    return d.get("value") == value


async def _ensure_ai_memory(
    session: AsyncSession,
    user: User,
    category: str,
    value: Any,
    quote: str,
    dry_run: bool,
) -> str:
    """
    user_id + memory_type + status='active' + value 동일한 row가 있으면 'exists'.
    없으면 INSERT 후 'inserted'.
    다른 status (superseded_by_manual 등)는 건드리지 않음.
    """
    existing_rows = (
        await session.execute(
            select(AIMemory)
            .where(AIMemory.user_id == user.id)
            .where(AIMemory.memory_type == category)
        )
    ).scalars().all()

    for row in existing_rows:
        if _content_matches(row.content, category, value):
            return "exists"

    # active row 없음 → INSERT
    if not dry_run:
        mem = AIMemory(
            user_id=user.id,
            memory_type=category,
            content=json.dumps(
                {
                    "value": value,
                    "confidence": 0.95,
                    "source_quote": quote,
                    "status": "active",
                },
                ensure_ascii=False,
            ),
            source_room_id=None,
            source_message_id=None,
            created_at=datetime.utcnow(),
        )
        session.add(mem)

    return "inserted"


async def _apply_seed(
    session: AsyncSession,
    user: User,
    seed: dict[str, dict[str, Any]],
    dry_run: bool,
) -> dict[str, dict[str, str]]:
    """user에 seed 적용. is_ai_filled[cat]=True + AIMemory INSERT.
    Returns: { category: { "user_field": "unchanged"|"updated", "memory": "exists"|"inserted" } }
    """
    applied: dict[str, dict[str, str]] = {}
    is_ai_filled = dict(user.is_ai_filled or {})
    user_field_changed = False

    for category, spec in seed.items():
        value = spec["value"]
        quote = spec["quote"]

        # -- User 필드 업데이트 --
        if category in _USER_PD_FIELDS:
            current = getattr(user, category, None)
            if current == value and is_ai_filled.get(category) is True:
                field_result = "unchanged"
            else:
                field_result = "updated"
                if not dry_run:
                    setattr(user, category, value)
                    is_ai_filled[category] = True
                    user_field_changed = True
        else:
            field_result = "n/a"

        # -- AIMemory 보장 --
        memory_result = await _ensure_ai_memory(
            session, user, category, value, quote, dry_run
        )

        applied[category] = {"user_field": field_result, "memory": memory_result}

    if not dry_run and user_field_changed:
        # is_ai_filled은 mutable JSON dict — 새 dict 할당해야 SQLModel이 감지
        user.is_ai_filled = is_ai_filled
        session.add(user)

    return applied


async def main(room_id: int, dry_run: bool) -> int:
    async with AsyncSessionLocal() as session:
        room = (
            await session.execute(select(Room).where(Room.id == room_id))
        ).scalar_one_or_none()
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
            room_id,
            room.name,
            len(member_rows),
            dry_run,
        )

        applied_users = 0
        total_inserted = 0
        total_exists = 0

        for user in member_rows:
            seed = SEED_MAP.get(user.name)
            if seed is None:
                logger.info(
                    "  [skip] %s (id=%s) — no seed for this name", user.name, user.id
                )
                continue

            applied = await _apply_seed(session, user, seed, dry_run)

            # 실제 변경이 있는 카테고리만 집계
            any_change = any(
                v["user_field"] != "unchanged" or v["memory"] != "exists"
                for v in applied.values()
            )

            for category, result in applied.items():
                mem_status = result["memory"]
                field_status = result["user_field"]
                tag = "DRY" if dry_run else "OK"
                if mem_status == "inserted":
                    total_inserted += 1
                    logger.info(
                        "  [%s] %s (id=%s): %s user_field=%s | AIMemory inserted (active)",
                        tag,
                        user.name,
                        user.id,
                        category,
                        field_status,
                    )
                else:
                    total_exists += 1
                    logger.info(
                        "  [%s] %s (id=%s): %s user_field=%s | AIMemory exists, skip",
                        "==" if not any_change else tag,
                        user.name,
                        user.id,
                        category,
                        field_status,
                    )

            if any_change:
                applied_users += 1

        if not dry_run and (applied_users or total_inserted):
            await session.commit()
            logger.info(
                "Committed. %d user(s) updated. Inserted %d AIMemory rows.",
                applied_users,
                total_inserted,
            )
        elif dry_run:
            logger.info(
                "Dry-run complete — no DB changes. %d users would update. "
                "Would insert %d AIMemory rows.",
                applied_users,
                total_inserted,
            )
        else:
            logger.info(
                "All target users already seeded — no changes. "
                "%d AIMemory rows already exist.",
                total_exists,
            )

        return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="시연용 PersonalData 시드 (AIMemory 포함)")
    parser.add_argument("--room", type=int, required=True, help="시연 룸 ID")
    parser.add_argument(
        "--dry-run", action="store_true", help="DB 쓰기 없이 미리 확인만"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(asyncio.run(main(args.room, args.dry_run)))
