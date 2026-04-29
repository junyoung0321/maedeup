"""Concurrent share TOCTOU smoke — 5 parallel shares on the same message
must produce exactly 1 shared row (docs/ai-separation.md §9.1 + Phase 3 §3.5 A1).
"""
import asyncio
import httpx

from app.core.security import issue_jwt
from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMessage, PaneType, Visibility
from app.models.room import MemberRole, Room, RoomMember
from app.models.user import User
from sqlalchemy import delete
from sqlmodel import select

BASE_URL = "http://localhost:8000"


async def main() -> int:
    async with AsyncSessionLocal() as session:
        # purge
        room = (await session.execute(select(Room).where(Room.name == "QA-TOCTOU"))).scalar_one_or_none()
        if room:
            await session.execute(delete(ChatMessage).where(ChatMessage.room_id == room.id))
            await session.execute(delete(RoomMember).where(RoomMember.room_id == room.id))
            await session.execute(delete(Room).where(Room.id == room.id))
            await session.commit()

        user = (await session.execute(select(User).where(User.email == "qa-a@example.com"))).scalar_one_or_none()
        if not user:
            print("seed user missing — run qa_privacy_boundary.py first")
            return 1

        room = Room(name="QA-TOCTOU", description="toctou", category="test", created_by=user.id)
        session.add(room)
        await session.commit()
        await session.refresh(room)
        session.add(RoomMember(room_id=room.id, user_id=user.id, role=MemberRole.member))
        await session.commit()

        msg = ChatMessage(
            pane_type=PaneType.agent, role="assistant", content="race target",
            sender="매듭 AI", room_id=room.id, user_id=user.id,
            visibility=Visibility.private.value,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        msg_id = msg.id

    token = issue_jwt(
        user_id=user.id, email=user.email, name=user.name,
        picture=None, calendar_consent=False,
    )

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        async def hit():
            return await client.post(
                f"/api/v1/chat/messages/{msg_id}/share",
                headers={"Authorization": f"Bearer {token}"},
                json={},
            )

        results = await asyncio.gather(*[hit() for _ in range(5)], return_exceptions=True)

    shared_ids = set()
    already_count = 0
    fresh_count = 0
    errors = []
    for r in results:
        if isinstance(r, Exception):
            errors.append(str(r))
            continue
        if r.status_code != 200:
            errors.append(f"status={r.status_code} body={r.text[:80]}")
            continue
        body = r.json()
        shared_ids.add(body["id"])
        if body.get("already_shared"):
            already_count += 1
        else:
            fresh_count += 1

    print(f"shared_ids={shared_ids} fresh={fresh_count} already={already_count} errors={errors}")

    async with AsyncSessionLocal() as session:
        count_q = await session.execute(
            select(ChatMessage).where(ChatMessage.shared_from_id == msg_id)
        )
        shared_rows = count_q.scalars().all()
    print(f"DB shared rows for source={msg_id}: {len(shared_rows)}")

    ok = len(shared_ids) == 1 and len(shared_rows) == 1 and fresh_count == 1 and already_count == 4
    print(f"\n{'OK' if ok else 'FAIL'}  — exactly 1 shared row, 1 fresh + 4 already_shared")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
