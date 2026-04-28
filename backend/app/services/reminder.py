import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import redis.asyncio as aioredis
from sqlmodel import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.meeting import MeetingSchedule, MeetingStatus
from app.models.room import RoomMember
from app.models.user import User

KST = ZoneInfo("Asia/Seoul")
VOTE_REMINDER_DELAY_HOURS = 6
logger = logging.getLogger(__name__)


async def send_today_meeting_reminders() -> None:
    now_kst = datetime.now(KST)
    today_start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start_kst = today_start_kst + timedelta(days=1)
    # DB stores scheduled_at as UTC-naive datetimes, so convert to UTC and strip tzinfo
    today_start = today_start_kst.astimezone(timezone.utc).replace(tzinfo=None)
    tomorrow_start = tomorrow_start_kst.astimezone(timezone.utc).replace(tzinfo=None)
    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MeetingSchedule).where(
                    MeetingSchedule.status == MeetingStatus.confirmed,
                    MeetingSchedule.reminder_sent == False,  # noqa: E712
                    MeetingSchedule.scheduled_at >= today_start,
                    MeetingSchedule.scheduled_at < tomorrow_start,
                )
            )
            meetings = result.scalars().all()

            for meeting in meetings:
                place_name = meeting.location_name or "약속 장소"
                payload = {
                    "type": "reminder",
                    "message": f"오늘 [{place_name}]에서 모임이 있습니다! 잊지 마세요 😊",
                    "meeting_id": meeting.id,
                }
                published = False
                try:
                    await redis_client.publish(
                        f"social:{meeting.room_id}",
                        json.dumps(payload, ensure_ascii=False),
                    )
                    published = True
                except Exception:
                    logger.warning("Redis publish failed for reminder meeting_id=%s", meeting.id, exc_info=True)
                if published:
                    meeting.reminder_sent = True
                    meeting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    session.add(meeting)

            if meetings:
                await session.commit()
    finally:
        await redis_client.aclose()


async def check_pending_votes() -> None:
    """투표가 시작된 지 6시간이 지났지만 아직 투표하지 않은 멤버에게 리마인드 메시지를 발송합니다."""
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=VOTE_REMINDER_DELAY_HOURS)
    # DB stores created_at as UTC-naive datetimes
    cutoff_naive = cutoff.replace(tzinfo=None)

    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )

    try:
        async with AsyncSessionLocal() as session:
            # pending 상태이고, vote_options가 있고, 아직 vote_reminder를 보내지 않은 모임 조회
            result = await session.execute(
                select(MeetingSchedule).where(
                    MeetingSchedule.status == MeetingStatus.pending,
                    MeetingSchedule.vote_reminder_sent == False,  # noqa: E712
                    MeetingSchedule.created_at <= cutoff_naive,
                )
            )
            meetings = result.scalars().all()

            for meeting in meetings:
                # vote_options가 없으면 투표 대상이 아님
                if not meeting.vote_options:
                    continue

                # room_members 전체 조회
                member_result = await session.execute(
                    select(RoomMember).where(RoomMember.room_id == meeting.room_id)
                )
                members = member_result.scalars().all()
                all_user_ids = {m.user_id for m in members}

                # 이미 투표한 유저 식별
                votes = meeting.votes or {}
                voted_user_ids = set()
                for user_id_str in votes.keys():
                    try:
                        voted_user_ids.add(int(user_id_str))
                    except (TypeError, ValueError):
                        continue

                # 미투표자 식별
                non_voters = all_user_ids - voted_user_ids
                if not non_voters:
                    # 모두 투표 완료 → 플래그만 설정
                    meeting.vote_reminder_sent = True
                    meeting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    session.add(meeting)
                    continue

                # 미투표자 이름 조회
                user_result = await session.execute(
                    select(User).where(User.id.in_(list(non_voters)))
                )
                non_voter_users = user_result.scalars().all()
                non_voter_names = [u.name for u in non_voter_users if u.name]

                if not non_voter_names:
                    meeting.vote_reminder_sent = True
                    meeting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    session.add(meeting)
                    continue

                # 멘션 문자열 생성
                mentions = " ".join(f"@{name}" for name in non_voter_names)
                reminder_message = (
                    f"아직 투표 안 하신 분이 있어요! {mentions} 투표해주세요~ 🗳️"
                )

                payload = {
                    "type": "vote_reminder",
                    "message": reminder_message,
                    "meeting_id": meeting.id,
                    "non_voters": non_voter_names,
                }
                published = False
                try:
                    await redis_client.publish(
                        f"social:{meeting.room_id}",
                        json.dumps(payload, ensure_ascii=False),
                    )
                    published = True
                except Exception:
                    logger.warning(
                        "Redis publish failed for vote reminder meeting_id=%s",
                        meeting.id,
                        exc_info=True,
                    )

                if published:
                    meeting.vote_reminder_sent = True
                    meeting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    session.add(meeting)

            if meetings:
                await session.commit()
    finally:
        await redis_client.aclose()


async def run_reminder_job() -> None:
    """AsyncIOScheduler가 직접 await할 수 있는 reminder 엔트리포인트."""
    await send_today_meeting_reminders()


async def run_vote_reminder_job() -> None:
    """AsyncIOScheduler가 직접 await할 수 있는 vote reminder 엔트리포인트."""
    await check_pending_votes()
