"""시연 ACT 2.5 안정성을 위한 calendar busy 시드 스크립트.

QA v3 D-1 #2 권고: 지민·수현·민수에게 calendar_consent=True + synthetic
google_refresh_token 을 주입해 `_load_busy_by_user_for_state` 가 해당 유저를
consenting_users 에 포함시키도록 함. 이로써 `busy_by_user` non-empty 가 보장되어
ACT 2.5 majority_fallback 자연 발동 안정성이 높아진다.

배경: `busy_by_user` 는 Google Calendar API 에서 실시간 조회된다 — 별도 local DB
테이블은 없다. `_load_busy_by_user_for_state` (slots.py) 는
  `user.calendar_consent == True AND (user.google_access_token OR user.google_refresh_token)`
인 멤버만 consenting_users 로 분류해 freeBusy API 를 호출한다. fake 토큰이면
GoogleCalendarAuthError 로 `[]` 를 반환하지만 busy_by_user[key] 키는 생성되므로
`not busy_by_user` 조건(=calendar_consent_zero 분기)을 통과하고 majority_fallback 로직이
실행된다.

사용법:
    docker exec maedeup-api python -m scripts.seed_demo_calendar_busy \\
        --room 28 --users 지민,수현,민수
    docker exec maedeup-api python -m scripts.seed_demo_calendar_busy \\
        --room 28 --user-ids 1,2,3
    docker exec maedeup-api python -m scripts.seed_demo_calendar_busy \\
        --room 28 --users 지민,수현,민수 --dry-run
    docker exec maedeup-api python -m scripts.seed_demo_calendar_busy \\
        --room 28 --users 지민,수현,민수 --clean

CLI 옵션:
    --room       시연 룸 ID (필수 — 룸 멤버 검증에 사용)
    --users      이름(쉼표 구분) — 이름으로 user_id 조회
    --user-ids   user_id(쉼표 구분) — 직접 지정 (--users 와 상호 배타)
    --token      주입할 synthetic refresh token (기본 "seed_demo_placeholder")
    --dry-run    실제 DB 쓰기 없이 미리보기
    --clean      token 을 None 으로 되돌리고 calendar_consent=True 는 유지

주의:
    - 게스트(is_guest=True) 는 Google OAuth 계정이 없으므로 자동 skip.
    - Idempotent — 여러 번 돌려도 안전.
    - 기존 real google_refresh_token 을 덮어쓰지 않음 (이미 토큰 보유 시 skip).
    - --clean 은 seed_demo_placeholder 값인 경우에만 제거 (real 토큰 보호).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.session import AsyncSessionLocal
from app.models.room import RoomMember
from app.models.user import User

logger = logging.getLogger("seed_demo_calendar_busy")
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")

SEED_TOKEN_MARKER = "seed_demo_placeholder"


async def _resolve_user_ids_by_name(
    session: AsyncSession, names: list[str]
) -> list[int]:
    """이름 목록으로 user_id 배열 조회. 조회 실패 시 sys.exit(1)."""
    ids: list[int] = []
    for name in names:
        result = await session.execute(select(User.id).where(User.name == name.strip()))
        uid = result.scalar_one_or_none()
        if uid is None:
            logger.error("사용자 '%s' 를 DB 에서 찾을 수 없습니다.", name)
            sys.exit(1)
        ids.append(uid)
    return ids


async def _check_room_membership(
    session: AsyncSession, room_id: int, user_ids: list[int]
) -> None:
    """user_id 들이 room_id 의 멤버인지 검증. 비멤버 발견 시 경고만 출력 (abort 안 함)."""
    member_result = await session.execute(
        select(RoomMember.user_id).where(RoomMember.room_id == room_id)
    )
    member_ids = {row for row in member_result.scalars().all()}
    for uid in user_ids:
        if uid not in member_ids:
            logger.warning(
                "user_id=%s 가 room_id=%s 의 멤버가 아닙니다. 시드는 계속 진행합니다.",
                uid,
                room_id,
            )


async def _apply_calendar_consent(
    session: AsyncSession,
    user: User,
    token: str,
    dry_run: bool,
) -> str:
    """user 에 calendar_consent=True + synthetic refresh token 주입.

    반환값:
        "skipped_guest"       — is_guest=True 이므로 skip
        "skipped_real_token"  — 이미 real 토큰(non-placeholder)이 있어 skip
        "unchanged"           — 이미 동일 상태(idempotent)
        "applied"             — 변경 적용
        "dry_applied"         — dry_run 으로 변경 예정
    """
    if user.is_guest:
        return "skipped_guest"

    already_has_real_token = (
        user.google_refresh_token
        and user.google_refresh_token != SEED_TOKEN_MARKER
    )
    if already_has_real_token:
        return "skipped_real_token"

    already_ok = (
        user.calendar_consent
        and user.google_refresh_token == token
    )
    if already_ok:
        return "unchanged"

    if dry_run:
        return "dry_applied"

    user.calendar_consent = True
    user.google_refresh_token = token
    session.add(user)
    return "applied"


async def _clean_seed_token(
    session: AsyncSession,
    user: User,
    dry_run: bool,
) -> str:
    """seed_demo_placeholder 값인 경우에만 google_refresh_token 을 None 으로 복원.

    반환값: "cleaned" | "skipped_not_placeholder" | "unchanged" | "dry_cleaned"
    """
    if user.google_refresh_token != SEED_TOKEN_MARKER:
        return "skipped_not_placeholder"
    if user.google_refresh_token is None:
        return "unchanged"
    if dry_run:
        return "dry_cleaned"
    user.google_refresh_token = None
    session.add(user)
    return "cleaned"


async def main(
    room_id: int,
    user_ids: list[int],
    token: str,
    dry_run: bool,
    clean: bool,
) -> int:
    async with AsyncSessionLocal() as session:
        # 룸 멤버 검증 (경고만)
        await _check_room_membership(session, room_id, user_ids)

        # 유저 로드
        user_result = await session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users: list[User] = list(user_result.scalars().all())
        found_ids = {u.id for u in users}
        for uid in user_ids:
            if uid not in found_ids:
                logger.error("user_id=%s 를 DB 에서 찾을 수 없습니다.", uid)
                return 1

        applied_count = 0

        for user in users:
            if clean:
                status = await _clean_seed_token(session, user, dry_run)
                label = "CLEAN" if not dry_run else "DRY"
                logger.info(
                    "  [%s] %s (id=%s): %s",
                    label,
                    user.name,
                    user.id,
                    status,
                )
                if status in ("cleaned", "dry_cleaned"):
                    applied_count += 1
            else:
                status = await _apply_calendar_consent(session, user, token, dry_run)
                label = "DRY" if dry_run else "OK"
                logger.info(
                    "  [%s] %s (id=%s, is_guest=%s): %s",
                    label,
                    user.name,
                    user.id,
                    user.is_guest,
                    status,
                )
                if status in ("applied", "dry_applied"):
                    applied_count += 1

        if not dry_run and applied_count:
            await session.commit()
            action = "cleaned" if clean else "calendar_consent + token 주입"
            logger.info("Committed %d user updates (%s).", applied_count, action)
        elif dry_run:
            logger.info(
                "Dry-run complete — no DB changes. %d users would update.", applied_count
            )
        else:
            logger.info("All target users already up-to-date — no changes.")

        logger.info("─" * 60)
        if clean:
            logger.info(
                "Calendar busy seed CLEAN 완료. "
                "seed_demo_placeholder 토큰 %d건 제거됨.",
                applied_count,
            )
        else:
            logger.info(
                "Calendar busy seed 완료. %d건 적용. "
                "busy_by_user non-empty → ACT 2.5 majority_fallback 자연 발동 준비됨.",
                applied_count,
            )
        return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="시연 ACT 2.5 안정성을 위한 calendar_consent + synthetic token 시드"
    )
    p.add_argument("--room", type=int, required=True, help="시연 룸 ID (멤버 검증용)")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--users", help="이름(쉼표 구분), 예: 지민,수현,민수")
    group.add_argument("--user-ids", help="user_id(쉼표 구분), 예: 1,2,3")
    p.add_argument(
        "--token",
        default=SEED_TOKEN_MARKER,
        help=f"주입할 synthetic refresh token (기본: '{SEED_TOKEN_MARKER}')",
    )
    p.add_argument("--dry-run", action="store_true", help="DB 쓰기 없이 미리 확인만")
    p.add_argument(
        "--clean",
        action="store_true",
        help=f"'{SEED_TOKEN_MARKER}' 토큰을 None 으로 복원 (real 토큰은 건드리지 않음)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    async def _run() -> int:
        async with AsyncSessionLocal() as session:
            if args.users:
                names = [n.strip() for n in args.users.split(",") if n.strip()]
                user_ids = await _resolve_user_ids_by_name(session, names)
            else:
                user_ids = [int(x) for x in args.user_ids.split(",")]
        return await main(
            room_id=args.room,
            user_ids=user_ids,
            token=args.token,
            dry_run=args.dry_run,
            clean=args.clean,
        )

    sys.exit(asyncio.run(_run()))
