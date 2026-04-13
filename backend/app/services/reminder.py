import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import redis.asyncio as aioredis
from sqlmodel import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.meeting import MeetingSchedule, MeetingStatus

KST = ZoneInfo("Asia/Seoul")


async def send_today_meeting_reminders() -> None:
    now_kst = datetime.now(KST)
    today_start = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

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
                await redis_client.publish(
                    f"social:{meeting.room_id}",
                    json.dumps(payload, ensure_ascii=False),
                )
                meeting.reminder_sent = True
                meeting.updated_at = datetime.utcnow()
                session.add(meeting)

            if meetings:
                await session.commit()
    finally:
        await redis_client.aclose()
