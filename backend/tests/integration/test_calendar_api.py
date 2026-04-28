"""
Integration tests for /api/v1/calendar/free-slots — guest aggregation + Redis fail-safe.

Redis 로드 실패 시 unavailability 폴백이 동작하고 dates/free_slots가 정상 반환됨을 검증.

`db_engine` fixture는 `tests/conftest.py`에서 재사용. 다른 통합 테스트와의 이름 충돌을
피하기 위해 모듈 로컬 fixture는 `_calendar` 접미사를 사용한다.
"""
from __future__ import annotations

from typing import AsyncIterator

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.main import app


@pytest_asyncio.fixture
async def seeded_db_calendar(db_engine):
    """방 1개 + 동의자 1명(host) + 게스트 1명. 게스트는 calendar_consent=False, is_guest=True."""
    from app.models.room import Room, RoomMember
    from app.models.user import User

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        session.add_all([
            User(id=1, email="host@test", name="Host"),  # 토큰 없음 → 미연동 처리
            User(id=2, email="guest-2@test", name="Guest", is_guest=True),
        ])
        await session.commit()
        session.add(Room(id=10, name="test room", created_by=1, status="active"))
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
async def client_calendar(db_engine, seeded_db_calendar) -> AsyncIterator[AsyncClient]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_session_override() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _get_session_override
    app.dependency_overrides[get_current_user] = lambda: _as_auth_user(1)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 게스트 집계 — endpoint 통합
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_slots_includes_guest_in_total(client_calendar, monkeypatch):
    """엔드포인트 응답: 게스트가 total과 dates의 unconnected에 포함."""
    # Redis는 fake로 두되 빈 상태 → blocked_by_date 비어있음
    fake_redis = fake_aioredis.FakeRedis(decode_responses=True)

    def _fake_from_url(*args, **kwargs):
        return fake_redis

    monkeypatch.setattr("app.api.routes.calendar.aioredis.from_url", _fake_from_url)

    resp = await client_calendar.get("/api/v1/calendar/free-slots?room_id=10")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert "dates" in body
    # 임의 날짜 하나 — 둘 다 캘린더 토큰 없음 → unconnected로 잡힘
    sample = next(iter(body["dates"].values()))
    assert sample["total"] == 2, "동의자 1 + 게스트 1 (둘 다 미연동 처리)"
    assert sample["count"] == 2, "기본 가능"
    assert "Host" in sample["unconnected"]
    assert "Guest" in sample["unconnected"]

    await fake_redis.aclose()


@pytest.mark.asyncio
async def test_free_slots_redis_failure_falls_back(client_calendar, monkeypatch):
    """Redis 로드가 실패해도 200 + 빈 blocked_by_date로 정상 반환."""
    def _raise_from_url(*args, **kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.api.routes.calendar.aioredis.from_url", _raise_from_url)

    resp = await client_calendar.get("/api/v1/calendar/free-slots?room_id=10")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    sample = next(iter(body["dates"].values()))
    # blocked_by_date 비어있는 채로 폴백 → 게스트 정상 카운트
    assert sample["total"] == 2
    assert sample["count"] == 2
    assert sample["blocked"] == []


@pytest.mark.asyncio
async def test_free_slots_load_unavailability_failure_falls_back(client_calendar, monkeypatch):
    """load_room_unavailability 자체가 던져도 200으로 폴백."""
    fake_redis = fake_aioredis.FakeRedis(decode_responses=True)

    def _fake_from_url(*args, **kwargs):
        return fake_redis

    async def _raise_load(*args, **kwargs):
        raise RuntimeError("load failed")

    monkeypatch.setattr("app.api.routes.calendar.aioredis.from_url", _fake_from_url)
    monkeypatch.setattr("app.api.routes.calendar.sr.load_room_unavailability", _raise_load)

    resp = await client_calendar.get("/api/v1/calendar/free-slots?room_id=10")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    sample = next(iter(body["dates"].values()))
    assert sample["total"] == 2
    assert sample["blocked"] == []

    await fake_redis.aclose()
