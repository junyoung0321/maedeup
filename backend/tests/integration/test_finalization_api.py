"""
Integration tests for finalization REST endpoints + /meetings/confirm host auth.

Uses an in-memory SQLite DB and FakeRedis. Auth is overridden via
FastAPI dependency_overrides so each test can swap the "current user".
"""
from __future__ import annotations

from typing import AsyncIterator

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlmodel import SQLModel

from app.api.routes.finalization import get_redis
from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.main import app
from app.services import scheduling_round as sr


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def redis_client():
    r = fake_aioredis.FakeRedis(decode_responses=True)
    try:
        yield r
    finally:
        await r.flushall()
        await r.aclose()


@pytest_asyncio.fixture
async def db_engine():
    from app.models import chat, meeting, room, user, vote  # noqa: F401

    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_db(db_engine):
    """
    Seed the schema with:
      - 3 users: host (id=1), member2 (id=2), outsider (id=3)
      - 1 room (id=10) owned by host, with host + member2 as members
    """
    from app.models.room import Room, RoomMember
    from app.models.user import User

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        session.add_all([
            User(id=1, email="host@test", name="Host", google_sub="g-1"),
            User(id=2, email="mem@test", name="Member", google_sub="g-2"),
            User(id=3, email="out@test", name="Outsider", google_sub="g-3"),
        ])
        await session.commit()
        session.add(
            Room(
                id=10,
                name="test room",
                created_by=1,
                status="active",
            )
        )
        await session.commit()
        session.add_all([
            RoomMember(room_id=10, user_id=1, role="owner"),
            RoomMember(room_id=10, user_id=2, role="member"),
        ])
        await session.commit()
    yield


def _as_auth_user(user_id: int) -> AuthUser:
    return AuthUser(
        sub=str(user_id),
        email=f"user{user_id}@test",
        name=f"User{user_id}",
        picture=None,
        calendar_consent=False,
    )


@pytest_asyncio.fixture
async def client(db_engine, redis_client, seeded_db) -> AsyncIterator[AsyncClient]:
    """HTTP client with overridden get_session + get_redis. Auth is set per-test."""
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_session_override() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    def _get_redis_override():
        return redis_client

    app.dependency_overrides[get_session] = _get_session_override
    app.dependency_overrides[get_redis] = _get_redis_override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def _set_current_user(user_id: int) -> None:
    app.dependency_overrides[get_current_user] = lambda: _as_auth_user(user_id)


async def _seed_proposal(
    redis_client,
    *,
    room_id: int = 10,
    host_user_id: int = 1,
    total_eligible_voters: int = 2,
) -> sr.Proposal:
    proposal = await sr.propose(
        redis_client,
        room_id=room_id,
        host_user_id=host_user_id,
        total_eligible_voters=total_eligible_voters,
        proposed_slot={"label": "토요일 15:00", "start_at": "2026-05-02T15:00:00"},
        snapshot_hash="seeded_hash",
    )
    assert proposal is not None
    return proposal


# ---------------------------------------------------------------------------
# POST /finalization/{proposal_id}/vote
# ---------------------------------------------------------------------------


async def test_vote_happy_path_returns_updated_state(client, redis_client):
    proposal = await _seed_proposal(redis_client)
    _set_current_user(2)

    resp = await client.post(
        f"/api/v1/finalization/{proposal.proposal_id}/vote",
        json={"choice": "like", "room_id": 10},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["proposal_id"] == proposal.proposal_id
    assert body["like_count"] == 1
    assert body["my_vote"] == "like"


async def test_vote_rejects_non_member(client, redis_client):
    proposal = await _seed_proposal(redis_client)
    _set_current_user(3)  # outsider (not in room 10)

    resp = await client.post(
        f"/api/v1/finalization/{proposal.proposal_id}/vote",
        json={"choice": "like", "room_id": 10},
    )

    assert resp.status_code == 403


async def test_vote_on_unknown_proposal_404(client, redis_client):
    _set_current_user(2)
    resp = await client.post(
        "/api/v1/finalization/nope-never-existed/vote",
        json={"choice": "like", "room_id": 10},
    )
    assert resp.status_code == 404


async def test_vote_invalid_choice_422(client, redis_client):
    proposal = await _seed_proposal(redis_client)
    _set_current_user(2)
    resp = await client.post(
        f"/api/v1/finalization/{proposal.proposal_id}/vote",
        json={"choice": "banana", "room_id": 10},
    )
    # Pydantic Literal validation → 422.
    assert resp.status_code == 422


async def test_vote_transitions_to_majority_reached(client, redis_client):
    # 2 eligible voters → majority = 2.
    proposal = await _seed_proposal(redis_client, total_eligible_voters=2)

    _set_current_user(1)
    resp1 = await client.post(
        f"/api/v1/finalization/{proposal.proposal_id}/vote",
        json={"choice": "like", "room_id": 10},
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "active"

    _set_current_user(2)
    resp2 = await client.post(
        f"/api/v1/finalization/{proposal.proposal_id}/vote",
        json={"choice": "like", "room_id": 10},
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "majority_reached"


# ---------------------------------------------------------------------------
# GET /finalization/room/{room_id}
# ---------------------------------------------------------------------------


async def test_get_room_proposal_returns_null_when_empty(client, redis_client):
    _set_current_user(1)
    resp = await client.get("/api/v1/finalization/room/10")
    assert resp.status_code == 200
    assert resp.json() is None


async def test_get_room_proposal_rejects_non_member(client, redis_client):
    _set_current_user(3)
    resp = await client.get("/api/v1/finalization/room/10")
    assert resp.status_code == 403


async def test_get_room_proposal_includes_my_vote(client, redis_client):
    proposal = await _seed_proposal(redis_client)
    await sr.record_vote(
        redis_client,
        room_id=10,
        proposal_id=proposal.proposal_id,
        user_id=2,
        choice="like",
    )
    _set_current_user(2)
    resp = await client.get("/api/v1/finalization/room/10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposal_id"] == proposal.proposal_id
    assert body["my_vote"] == "like"
    assert body["like_count"] == 1


# ---------------------------------------------------------------------------
# POST /api/v1/meetings/confirm — host auth + proposal integration
# ---------------------------------------------------------------------------


async def test_confirm_rejects_non_member(client, redis_client):
    """룸 멤버가 아닌 외부 유저는 confirm 차단.
    멤버라면 누구나 확정 가능하도록 host-only 제한이 해제됐으므로 비-멤버만 검증."""
    _set_current_user(3)   # outsider — not a room member
    resp = await client.post(
        "/api/v1/meetings/confirm",
        json={
            "room_id": 10,
            "title": "저녁 모임",
            "scheduled_at": "2026-05-02T15:00:00",
            "end_at": "2026-05-02T17:00:00",
        },
    )
    assert resp.status_code == 403
    assert "member" in resp.json()["detail"].lower()


async def test_confirm_succeeds_for_member(client, redis_client):
    """host가 아닌 룸 멤버도 confirm 가능."""
    _set_current_user(2)   # member, not host
    resp = await client.post(
        "/api/v1/meetings/confirm",
        json={
            "room_id": 10,
            "title": "저녁 모임",
            "scheduled_at": "2026-05-02T15:00:00",
            "end_at": "2026-05-02T17:00:00",
        },
    )
    assert resp.status_code in (200, 201), resp.text


async def test_confirm_succeeds_for_host_without_proposal(client, redis_client):
    _set_current_user(1)   # host
    resp = await client.post(
        "/api/v1/meetings/confirm",
        json={
            "room_id": 10,
            "title": "저녁 모임",
            "scheduled_at": "2026-05-02T15:00:00",
            "end_at": "2026-05-02T17:00:00",
        },
    )
    assert resp.status_code == 201
    assert "id" in resp.json()


async def test_confirm_with_proposal_below_majority_409(client, redis_client):
    proposal = await _seed_proposal(redis_client, total_eligible_voters=5)
    # Only 1 like out of 5 → below majority.
    await sr.record_vote(
        redis_client, room_id=10, proposal_id=proposal.proposal_id,
        user_id=2, choice="like",
    )
    _set_current_user(1)
    resp = await client.post(
        "/api/v1/meetings/confirm",
        json={
            "room_id": 10,
            "title": "저녁 모임",
            "scheduled_at": "2026-05-02T15:00:00",
            "end_at": "2026-05-02T17:00:00",
            "proposal_id": proposal.proposal_id,
        },
    )
    assert resp.status_code == 409
    assert "below_majority" in resp.json()["detail"]


async def test_confirm_with_unknown_proposal_404(client, redis_client):
    _set_current_user(1)
    resp = await client.post(
        "/api/v1/meetings/confirm",
        json={
            "room_id": 10,
            "title": "저녁 모임",
            "scheduled_at": "2026-05-02T15:00:00",
            "end_at": "2026-05-02T17:00:00",
            "proposal_id": "does-not-exist",
        },
    )
    assert resp.status_code == 404


async def test_confirm_with_majority_proposal_succeeds(client, redis_client):
    proposal = await _seed_proposal(redis_client, total_eligible_voters=2)
    # Both members vote like → majority reached.
    await sr.record_vote(
        redis_client, room_id=10, proposal_id=proposal.proposal_id,
        user_id=1, choice="like",
    )
    await sr.record_vote(
        redis_client, room_id=10, proposal_id=proposal.proposal_id,
        user_id=2, choice="like",
    )

    _set_current_user(1)
    resp = await client.post(
        "/api/v1/meetings/confirm",
        json={
            "room_id": 10,
            "title": "저녁 모임",
            "scheduled_at": "2026-05-02T15:00:00",
            "end_at": "2026-05-02T17:00:00",
            "proposal_id": proposal.proposal_id,
        },
    )
    assert resp.status_code == 201

    # Proposal should now be marked confirmed in Redis.
    restored = await sr.restore_for_room(redis_client, room_id=10)
    assert restored is not None
    assert restored.status == sr.ProposalStatus.confirmed


async def test_confirm_clears_room_availability(client, redis_client):
    """확정 후 availability 캐시가 비워져야, 다음 선택이 새 proposal을 만들지 않음."""
    proposal = await _seed_proposal(redis_client, total_eligible_voters=2)
    # Seed availability for both members BEFORE confirming.
    await sr.record_availability(
        redis_client, room_id=10, user_id=1, date="2026-05-02", start=0, end=4,
    )
    await sr.record_availability(
        redis_client, room_id=10, user_id=2, date="2026-05-02", start=0, end=4,
    )
    pre = await sr.load_room_availability(redis_client, room_id=10)
    assert len(pre) == 2, "seed guard: availability should be present before confirm"

    await sr.record_vote(
        redis_client, room_id=10, proposal_id=proposal.proposal_id,
        user_id=1, choice="like",
    )
    await sr.record_vote(
        redis_client, room_id=10, proposal_id=proposal.proposal_id,
        user_id=2, choice="like",
    )

    _set_current_user(1)
    resp = await client.post(
        "/api/v1/meetings/confirm",
        json={
            "room_id": 10,
            "title": "저녁 모임",
            "scheduled_at": "2026-05-02T15:00:00",
            "end_at": "2026-05-02T17:00:00",
            "proposal_id": proposal.proposal_id,
        },
    )
    assert resp.status_code == 201

    post = await sr.load_room_availability(redis_client, room_id=10)
    assert post == {}, f"availability should be cleared after confirm, got {post}"
