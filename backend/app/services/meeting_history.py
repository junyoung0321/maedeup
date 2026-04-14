"""모임 히스토리(meeting history) 서비스.

완료된 모임 기록을 ai_memories에 저장하고,
자연어 질의로 과거 모임을 검색할 수 있도록 지원합니다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.ai_memory import AIMemory
from app.models.meeting import MeetingSchedule
from app.models.room import RoomMember
from app.models.user import User
from app.services.gemini import call_gemini

logger = logging.getLogger(__name__)


async def save_meeting_record(meeting_id: int, db: AsyncSession) -> None:
    """완료(장소 확정)된 모임을 ai_memories에 기록합니다."""
    result = await db.execute(
        select(MeetingSchedule).where(MeetingSchedule.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        logger.warning("save_meeting_record: meeting %s not found", meeting_id)
        return

    # 참여자 조회
    participant_result = await db.execute(
        select(User)
        .join(RoomMember, RoomMember.user_id == User.id)
        .where(RoomMember.room_id == meeting.room_id)
    )
    participants = participant_result.scalars().all()
    participant_names = [p.name for p in participants]

    record = {
        "meeting_id": meeting.id,
        "title": meeting.title,
        "scheduled_at": meeting.scheduled_at.isoformat() if meeting.scheduled_at else None,
        "end_at": meeting.end_at.isoformat() if meeting.end_at else None,
        "location_name": meeting.location_name,
        "location_address": meeting.location_address,
        "kakao_place_url": meeting.kakao_place_url,
        "participants": participant_names,
        "recorded_at": datetime.utcnow().isoformat(),
    }

    content_json = json.dumps(record, ensure_ascii=False)

    # 각 참여자에 대해 메모리 저장
    for participant in participants:
        memory = AIMemory(
            user_id=participant.id,
            memory_type="meeting_record",
            content=content_json,
            source_room_id=meeting.room_id,
        )
        db.add(memory)

    await db.commit()
    logger.info(
        "Saved meeting record for meeting_id=%s, room_id=%s, participants=%s",
        meeting.id,
        meeting.room_id,
        participant_names,
    )


async def search_meeting_history(
    room_id: int, query: str, db: AsyncSession
) -> list[dict]:
    """모임 히스토리에서 관련 기록을 검색합니다.

    ai_memories에서 해당 room의 meeting_record를 가져온 뒤,
    Gemini를 사용해 질문과 관련된 기록만 필터링합니다.
    """
    result = await db.execute(
        select(AIMemory)
        .where(
            AIMemory.source_room_id == room_id,
            AIMemory.memory_type == "meeting_record",
        )
        .order_by(AIMemory.created_at.desc())
        .limit(50)
    )
    memories = result.scalars().all()
    if not memories:
        return []

    # 중복 제거 (같은 meeting_id의 레코드가 여러 유저에게 저장되므로)
    seen_meeting_ids: set[int] = set()
    unique_records: list[dict] = []
    for mem in memories:
        try:
            record = json.loads(mem.content)
        except (json.JSONDecodeError, TypeError):
            continue
        mid = record.get("meeting_id")
        if mid in seen_meeting_ids:
            continue
        seen_meeting_ids.add(mid)
        unique_records.append(record)

    if not unique_records:
        return []

    # Gemini로 관련성 판단
    records_text = json.dumps(unique_records, ensure_ascii=False, indent=2)
    prompt = (
        "아래는 모임 히스토리 목록이야. 사용자의 질문과 관련 있는 기록만 골라서 "
        "JSON 배열로 반환해줘. 관련 있는 기록이 없으면 빈 배열 []을 반환해.\n"
        "반드시 유효한 JSON 배열만 출력하고, 다른 텍스트는 포함하지 마.\n\n"
        f"사용자 질문: {query}\n\n"
        f"모임 히스토리:\n{records_text}"
    )

    try:
        response = (await call_gemini(prompt)).strip()
        # JSON 블록 마커 제거
        if response.startswith("```"):
            response = response.split("\n", 1)[-1]
            response = response.rsplit("```", 1)[0].strip()
        filtered = json.loads(response)
        if isinstance(filtered, list):
            return filtered
    except Exception:
        logger.warning(
            "Failed to filter meeting history with Gemini, returning all records",
            exc_info=True,
        )
        # 폴백: 전체 기록 반환
        return unique_records

    return unique_records


async def get_recent_meeting_records(
    room_id: int, db: AsyncSession, limit: int = 10
) -> list[dict]:
    """최근 모임 기록을 반환합니다 (컨텍스트 주입용)."""
    result = await db.execute(
        select(AIMemory)
        .where(
            AIMemory.source_room_id == room_id,
            AIMemory.memory_type == "meeting_record",
        )
        .order_by(AIMemory.created_at.desc())
        .limit(limit * 3)  # 중복 고려해 넉넉하게 조회
    )
    memories = result.scalars().all()

    seen_meeting_ids: set[int] = set()
    records: list[dict] = []
    for mem in memories:
        try:
            record = json.loads(mem.content)
        except (json.JSONDecodeError, TypeError):
            continue
        mid = record.get("meeting_id")
        if mid in seen_meeting_ids:
            continue
        seen_meeting_ids.add(mid)
        records.append(record)
        if len(records) >= limit:
            break

    return records
