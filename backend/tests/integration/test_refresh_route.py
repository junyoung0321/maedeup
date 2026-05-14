"""Integration tests for POST /meetings/{meeting_id}/recommendations/refresh.

PR-Z1 — Q5/Q7 hybrid 토글 refresh 라우트.
S15.1~S15.5 + 권한 / idempotency / rate limit / Q7-c 차단 커버.

External dependencies (run_pipeline, gemini) are monkeypatched — this test
exercises the route's auth + Q7-c + Redis idempotency + rate-limit plumbing,
not the LLM pipeline itself.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import AsyncIterator

import fakeredis.aioredis as fake_aioredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.api.routes.finalization import get_redis
from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.main import app


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures (mirror test_finalization_api.py pattern)
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
async def seeded_db(db_engine):
    """Seed:
      - users: owner (id=1), member (id=2), outsider (id=3), speaker-only (id=4)
      - room id=10, owner=1, members={1,2,4}
      - meeting id=100 in room 10, scheduled future
      - user 4 has full prefs + home_base (speaker eligible)
      - user 2 has share_food_data=False (Q7-c C1 trigger)
    """
    from app.models.meeting import MeetingSchedule, MeetingStatus
    from app.models.room import Room, RoomMember
    from app.models.user import User

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        session.add_all([
            User(
                id=1, email="owner@test", name="Owner",
                home_base="서울 강남",
                share_food_data=True, share_location_data=True, share_schedule_data=True,
            ),
            User(
                id=2, email="mem@test", name="Member",
                home_base=None,
                share_food_data=False,  # C1
                share_location_data=True, share_schedule_data=True,
            ),
            User(
                id=3, email="out@test", name="Outsider",
                share_food_data=True, share_location_data=True, share_schedule_data=True,
            ),
            User(
                id=4, email="speaker@test", name="Speaker",
                home_base="서울 종로",
                food_preferences=["한식"],
                share_food_data=True, share_location_data=True, share_schedule_data=True,
            ),
        ])
        await session.commit()
        session.add(Room(id=10, name="test room", created_by=1, status="active"))
        await session.commit()
        session.add_all([
            RoomMember(room_id=10, user_id=1, role="owner"),
            RoomMember(room_id=10, user_id=2, role="member"),
            RoomMember(room_id=10, user_id=4, role="member"),
        ])
        await session.commit()
        future = (datetime.utcnow() + timedelta(days=3)).replace(microsecond=0)
        session.add(MeetingSchedule(
            id=100,
            room_id=10,
            title="저녁 모임",
            scheduled_at=future,
            end_at=future + timedelta(hours=2),
            status=MeetingStatus.confirmed,
            created_by=1,
            vote_options=None,
            votes={},
        ))
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
async def client(db_engine, redis_client, seeded_db, monkeypatch) -> AsyncIterator[AsyncClient]:
    """HTTP client with deps overridden + run_pipeline stubbed.

    Stub returns a deterministic vote_card_payload + place_recommendation_payload
    so we can assert routing without invoking Gemini.
    """
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_session_override() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    def _get_redis_override():
        return redis_client

    app.dependency_overrides[get_session] = _get_session_override
    app.dependency_overrides[get_redis] = _get_redis_override

    async def _fake_run_pipeline(*args, **kwargs):
        slot_ctx = kwargs.get("slot_context") or {}
        return {
            "status": "vote_card_created",
            "vote_card_payload": {
                "type": "vote_card",
                "room_id": "10",
                "meeting_id": 100,
                "preference_source": slot_ctx.get("preference_source", "group"),
                "preference_toggle_enabled": True,
            },
            "place_recommendation_payload": {
                "type": "place_recommendation",
                "room_id": "10",
                "meeting_id": 100,
                "preference_source": slot_ctx.get("preference_source", "group"),
                "preference_toggle_enabled": True,
            },
        }

    monkeypatch.setattr(
        "app.api.routes.meetings.run_pipeline",
        _fake_run_pipeline,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def _set_current_user(user_id: int) -> None:
    app.dependency_overrides[get_current_user] = lambda: _as_auth_user(user_id)


# ---------------------------------------------------------------------------
# S15.1 — 권한 OK (발화자 또는 방장)
# ---------------------------------------------------------------------------


async def test_refresh_speaker_succeeds(client):
    """viewer == requester_user_id → 200, narrator에 발화자 실명 포함."""
    _set_current_user(4)  # speaker
    resp = await client.post(
        "/api/v1/meetings/100/recommendations/refresh",
        json={
            "scope": "both",
            "preference_source": "speaker",
            "requester_user_id": 4,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["vote_card"] is not None
    assert body["place_recommendation"] is not None
    assert "Speaker" in body["narrator"]
    assert body["cached"] is False


async def test_refresh_owner_can_toggle_for_member(client):
    """viewer=owner, requester=다른 멤버 → 200."""
    _set_current_user(1)  # owner
    resp = await client.post(
        "/api/v1/meetings/100/recommendations/refresh",
        json={
            "scope": "vote_card",
            "preference_source": "speaker",
            "requester_user_id": 4,  # speaker
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["vote_card"] is not None
    assert body["place_recommendation"] is None  # scope=vote_card


# ---------------------------------------------------------------------------
# S15.2 — 권한 거부 (발화자 아님 + 방장 아님)
# ---------------------------------------------------------------------------


async def test_refresh_non_speaker_non_owner_returns_403(client):
    """일반 멤버(viewer=2)가 다른 발화자(4)의 토글을 하면 403."""
    _set_current_user(2)  # plain member
    resp = await client.post(
        "/api/v1/meetings/100/recommendations/refresh",
        json={
            "scope": "vote_card",
            "preference_source": "speaker",
            "requester_user_id": 4,
        },
    )
    assert resp.status_code == 403
    assert "permission" in resp.json()["detail"].lower()


async def test_refresh_non_member_returns_403(client):
    """방 멤버가 아닌 외부 유저는 403."""
    _set_current_user(3)  # outsider
    resp = await client.post(
        "/api/v1/meetings/100/recommendations/refresh",
        json={
            "scope": "both",
            "preference_source": "speaker",
            "requester_user_id": 4,
        },
    )
    assert resp.status_code == 403
    assert "member" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# S15.3 — Idempotency (Q14=C)
# ---------------------------------------------------------------------------


async def test_refresh_idempotency_cache_hit(client):
    """같은 (viewer, meeting, scope, preference_source)로 두 번 호출하면 2번째는 cached=True."""
    _set_current_user(4)
    payload = {
        "scope": "vote_card",
        "preference_source": "speaker",
        "requester_user_id": 4,
    }
    resp1 = await client.post(
        "/api/v1/meetings/100/recommendations/refresh", json=payload
    )
    assert resp1.status_code == 200
    assert resp1.json()["cached"] is False

    resp2 = await client.post(
        "/api/v1/meetings/100/recommendations/refresh", json=payload
    )
    assert resp2.status_code == 200
    assert resp2.json()["cached"] is True


# ---------------------------------------------------------------------------
# S15.4 — Daily rate limit (Q14=C: 100/day)
# ---------------------------------------------------------------------------


async def test_refresh_daily_rate_limit_429(client, redis_client):
    """일일 카운트가 100을 넘기면 429."""
    from app.api.routes.meetings import (
        REFRESH_DAILY_LIMIT,
        _refresh_count_key,
    )

    _set_current_user(4)
    # Pre-seed the counter to the limit; next request should hit 429.
    await redis_client.set(_refresh_count_key(4), REFRESH_DAILY_LIMIT)

    # 매번 다른 source로 idempotency 회피.
    resp = await client.post(
        "/api/v1/meetings/100/recommendations/refresh",
        json={
            "scope": "place_recommendation",
            "preference_source": "speaker",
            "requester_user_id": 4,
        },
    )
    assert resp.status_code == 429
    assert "daily_limit" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# S15.5 — Q7-c 차단 (toggle_disabled → 422)
# ---------------------------------------------------------------------------


async def test_refresh_toggle_disabled_returns_422_share_food_off(client):
    """발화자 본인(user 2)이 share_food_data=False → C1 발동 → 422.

    user 2는 방 멤버이므로 멤버십·권한은 통과 (viewer == requester == 2).
    """
    _set_current_user(2)
    resp = await client.post(
        "/api/v1/meetings/100/recommendations/refresh",
        json={
            "scope": "both",
            "preference_source": "speaker",
            "requester_user_id": 2,
        },
    )
    assert resp.status_code == 422
    assert "toggle_disabled" in resp.json()["detail"]


async def test_refresh_meeting_not_found_returns_404(client):
    """존재하지 않는 meeting_id는 404."""
    _set_current_user(4)
    resp = await client.post(
        "/api/v1/meetings/9999/recommendations/refresh",
        json={
            "scope": "both",
            "preference_source": "speaker",
            "requester_user_id": 4,
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Codex P2 (2026-05-15) — refresh route C3 활성화 회귀 방지
# ---------------------------------------------------------------------------


async def test_refresh_c3_blocks_when_group_matches_speaker(
    client, db_engine
):
    """Codex P2: refresh route probe_state에 group context가 주입되어 C3가 발동.

    Seed: user 4 (speaker)의 home_base="서울 종로" + food_preferences=["한식"].
    MeetingPreference 두 건을 동일 location/foods로 추가하면 group 다수결도
    같아져 C3 lightweight 비교가 "동일"로 판정 → toggle_disabled → 422.
    """
    from app.models.meeting_preference import MeetingPreference

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        # user 4 home_base와 같은 location, food_preferences와 같은 foods로 다수결 형성.
        session.add_all([
            MeetingPreference(
                room_id=10, user_id=4,
                preferred_location="서울 종로",
                preferred_foods=["한식"],
                disliked_foods=[],
            ),
            MeetingPreference(
                room_id=10, user_id=1,
                preferred_location="서울 종로",
                preferred_foods=["한식"],
                disliked_foods=[],
            ),
        ])
        await session.commit()

    _set_current_user(4)
    resp = await client.post(
        "/api/v1/meetings/100/recommendations/refresh",
        json={
            "scope": "both",
            "preference_source": "speaker",
            "requester_user_id": 4,
        },
    )
    assert resp.status_code == 422, resp.text
    assert "toggle_disabled" in resp.json()["detail"]
