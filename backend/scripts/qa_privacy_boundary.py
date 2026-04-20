"""Manual QA for docs/ai-separation.md — privacy boundary smoke tests.

Runs inside the maedeup-api container:
    docker exec maedeup-api python scripts/qa_privacy_boundary.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone

import httpx

from app.core.security import issue_jwt
from app.db.session import AsyncSessionLocal
from app.models.chat import ChatMessage, PaneType, Visibility
from app.models.room import MemberRole, Room, RoomMember
from app.models.user import User
from app.repositories.messages import MessageReader
from sqlmodel import select

BASE_URL = "http://localhost:8000"


def log(title: str, ok: bool, detail: str = "") -> None:
    marker = "OK " if ok else "FAIL"
    print(f"[{marker}] {title}{(' — ' + detail) if detail else ''}")


async def ensure_user(session, email: str, name: str) -> User:
    result = await session.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    user = User(
        email=email,
        name=name,
        picture=None,
        home_base="서울 강남",
        calendar_consent=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def ensure_room(session, user_a: User, user_b: User) -> Room:
    result = await session.execute(select(Room).where(Room.name == "QA-AI-SEP-ROOM"))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    room = Room(
        name="QA-AI-SEP-ROOM",
        description="privacy boundary smoke test",
        category="test",
        created_by=user_a.id,
    )
    session.add(room)
    await session.commit()
    await session.refresh(room)
    for u in (user_a, user_b):
        session.add(
            RoomMember(room_id=room.id, user_id=u.id, role=MemberRole.member)
        )
    await session.commit()
    return room


async def insert_private_msg(session, room_id: int, user_id: int, content: str, role: str = "user") -> ChatMessage:
    msg = ChatMessage(
        pane_type=PaneType.agent,
        role=role,
        content=content,
        sender=role,
        room_id=room_id,
        user_id=user_id,
        visibility=Visibility.private.value,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def insert_shared_msg(session, room_id: int, content: str) -> ChatMessage:
    msg = ChatMessage(
        pane_type=PaneType.agent,
        role="assistant",
        content=content,
        sender="매듭 AI",
        room_id=room_id,
        user_id=None,
        visibility=Visibility.shared.value,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def purge_test_data(session) -> None:
    """Remove anything we made on previous runs to keep tests idempotent."""
    room = (await session.execute(select(Room).where(Room.name == "QA-AI-SEP-ROOM"))).scalar_one_or_none()
    if room:
        from sqlalchemy import delete
        await session.execute(delete(ChatMessage).where(ChatMessage.room_id == room.id))
        await session.execute(delete(RoomMember).where(RoomMember.room_id == room.id))
        await session.execute(delete(Room).where(Room.id == room.id))
        await session.commit()


async def main() -> int:
    failures = 0

    async with AsyncSessionLocal() as session:
        await purge_test_data(session)

        user_a = await ensure_user(session, "qa-a@example.com", "QA사용자A")
        user_b = await ensure_user(session, "qa-b@example.com", "QA사용자B")
        room = await ensure_room(session, user_a, user_b)

        # Seed: A's private, B's private, one shared
        a_msg = await insert_private_msg(session, room.id, user_a.id, "A의 비밀 일정: 금요일 저녁 약속 있음")
        b_msg = await insert_private_msg(session, room.id, user_b.id, "B의 비밀: 토요일 가족 행사")
        shared_msg = await insert_shared_msg(session, room.id, "모두 볼 수 있는 AI 제안")

        print(f"Seeded: A_msg={a_msg.id}, B_msg={b_msg.id}, shared={shared_msg.id}, room={room.id}")

        # ── T1+T2+T3: MessageReader boundary ──────────────────────────────
        ctx_a = await MessageReader.load_agent_context(session, room.id, viewer_user_id=user_a.id, limit=50)
        a_ids = {m.id for m in ctx_a.messages}
        t1_ok = b_msg.id not in a_ids
        t2_ok = a_msg.id in a_ids
        t3a_ok = shared_msg.id in a_ids
        log("T1 — A의 파이프라인에 B의 private 제외", t1_ok, f"a_ids={sorted(a_ids)}")
        log("T2 — A의 파이프라인에 A의 private 포함", t2_ok)
        log("T3a — A의 파이프라인에 shared 포함", t3a_ok)
        failures += sum(not x for x in (t1_ok, t2_ok, t3a_ok))

        ctx_b = await MessageReader.load_agent_context(session, room.id, viewer_user_id=user_b.id, limit=50)
        b_ids = {m.id for m in ctx_b.messages}
        t1b_ok = a_msg.id not in b_ids
        log("T1b — B의 파이프라인에 A의 private 제외", t1b_ok, f"b_ids={sorted(b_ids)}")
        failures += (0 if t1b_ok else 1)

        # ── T4: auto-trigger view (viewer_user_id=None) sees shared only ──
        ctx_auto = await MessageReader.load_agent_context(session, room.id, viewer_user_id=None, limit=50)
        auto_ids = {m.id for m in ctx_auto.messages}
        t4_ok = a_msg.id not in auto_ids and b_msg.id not in auto_ids and shared_msg.id in auto_ids
        log("T4 — auto-trigger는 shared만 조회", t4_ok, f"auto_ids={sorted(auto_ids)}")
        failures += (0 if t4_ok else 1)

        # ── run_pipeline type guard ───────────────────────────────────────
        from app.services.langgraph_pipeline import run_pipeline
        guard_ok = False
        try:
            await run_pipeline("1", [], session)  # raw list — must raise
        except TypeError:
            guard_ok = True
        log("Guard — run_pipeline이 raw list 거부", guard_ok)
        failures += (0 if guard_ok else 1)

        # ── HTTP: GET /chat/messages + POST .../share ─────────────────────
        token_a = issue_jwt(
            user_id=user_a.id, email=user_a.email, name=user_a.name,
            picture=None, calendar_consent=False,
        )
        token_b = issue_jwt(
            user_id=user_b.id, email=user_b.email, name=user_b.name,
            picture=None, calendar_consent=False,
        )

        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
            # GET messages as A
            r_a = await client.get(
                "/api/v1/chat/messages",
                headers={"Authorization": f"Bearer {token_a}"},
                params={"room_id": room.id, "pane_type": "agent", "limit": 100},
            )
            data_a = r_a.json() if r_a.status_code == 200 else []
            a_api_ids = {m["id"] for m in data_a}
            t_api_a_ok = b_msg.id not in a_api_ids and a_msg.id in a_api_ids and shared_msg.id in a_api_ids
            log("API — A GET /messages boundary", t_api_a_ok, f"got={sorted(a_api_ids)}")
            failures += (0 if t_api_a_ok else 1)

            r_b = await client.get(
                "/api/v1/chat/messages",
                headers={"Authorization": f"Bearer {token_b}"},
                params={"room_id": room.id, "pane_type": "agent", "limit": 100},
            )
            data_b = r_b.json() if r_b.status_code == 200 else []
            b_api_ids = {m["id"] for m in data_b}
            t_api_b_ok = a_msg.id not in b_api_ids and b_msg.id in b_api_ids
            log("API — B GET /messages boundary", t_api_b_ok, f"got={sorted(b_api_ids)}")
            failures += (0 if t_api_b_ok else 1)

            # Share: owner A shares A's private message → 200
            r_share = await client.post(
                f"/api/v1/chat/messages/{a_msg.id}/share",
                headers={"Authorization": f"Bearer {token_a}"},
                json={},
            )
            t_share_ok = r_share.status_code == 200 and r_share.json().get("already_shared") is False
            log("Share — 소유자 A의 공유 요청 성공", t_share_ok, f"status={r_share.status_code} body={r_share.text[:120]}")
            failures += (0 if t_share_ok else 1)
            shared_response_id = r_share.json().get("id") if r_share.status_code == 200 else None

            # Idempotency: A shares the same message again → 200 + already_shared=true
            r_share_again = await client.post(
                f"/api/v1/chat/messages/{a_msg.id}/share",
                headers={"Authorization": f"Bearer {token_a}"},
                json={},
            )
            t_idem_ok = (
                r_share_again.status_code == 200
                and r_share_again.json().get("already_shared") is True
                and r_share_again.json().get("id") == shared_response_id
            )
            log("Share — 동일 메시지 재공유 멱등", t_idem_ok, f"body={r_share_again.text[:120]}")
            failures += (0 if t_idem_ok else 1)

            # Non-owner B tries to share A's private → 403
            r_forbidden = await client.post(
                f"/api/v1/chat/messages/{b_msg.id}/share",  # B's own — should succeed
                headers={"Authorization": f"Bearer {token_a}"},  # A trying
                json={},
            )
            t_forbidden_ok = r_forbidden.status_code == 403
            log("Share — 비소유자 A가 B의 메시지 공유 시도 → 403", t_forbidden_ok, f"status={r_forbidden.status_code}")
            failures += (0 if t_forbidden_ok else 1)

            # After share: B should now see the shared copy (not A's original private)
            r_after = await client.get(
                "/api/v1/chat/messages",
                headers={"Authorization": f"Bearer {token_b}"},
                params={"room_id": room.id, "pane_type": "agent", "limit": 100},
            )
            after_ids = {m["id"] for m in (r_after.json() if r_after.status_code == 200 else [])}
            t_after_ok = (
                shared_response_id in after_ids  # shared copy visible
                and a_msg.id not in after_ids  # original private still hidden
            )
            log("Share — 공유 후 B가 shared copy는 보고 원본 private은 못 봄", t_after_ok, f"got={sorted(after_ids)}")
            failures += (0 if t_after_ok else 1)

    print()
    print(f"TOTAL FAILURES: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
