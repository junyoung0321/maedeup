# Audit P1 Security And Vote Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the three verified P1 findings from `docs/handoff/code-audit-2026-06-03`: `chat-1`, `chat-2`, and scheduling `slot-1`.

**Architecture:** Make `/api/v1/chat/messages` server-enforce a context boundary: room-scoped panes require `room_id` plus membership, while `personal_assistant` history is scoped to the authenticated user's personal session. Map finalization vote lock contention to a retryable `409` instead of leaking an unhandled `SchedulingRoundError`.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy async sessions, pytest-asyncio, httpx `ASGITransport`, fakeredis.

---

## Scope

This is the first fix wave for the verified P1 audit items only.

Included:
- `chat-1`: `GET /chat/messages` without `room_id` leaks messages across rooms.
- `chat-2`: `GET /chat/messages` without `pane_type` can expose other users' `personal_assistant` messages.
- scheduling `slot-1`: finalization vote lock contention returns HTTP 500 instead of a retryable client error.

Excluded from this wave:
- `chat-3` message spoofing. It is a real adjacent P2 trust-boundary issue, but changing `POST /chat/messages` can affect tooling or seed flows differently from the read endpoint. Handle it in a separate P2 security pass after checking callers.
- Unverified P2/P3 audit findings. They need reproduction or downgrade before implementation.

## File Structure

- Create `backend/tests/integration/test_chat_messages_security.py`
  - Integration coverage for room IDOR and `personal_assistant` privacy boundaries.
- Modify `backend/app/api/routes/chat.py`
  - Add a small helper for personal assistant session IDs.
  - Require `room_id` for room-scoped chat reads.
  - Restrict `personal_assistant` reads to the current user's own session.
- Modify `backend/tests/integration/test_finalization_api.py`
  - Add a regression test for `SchedulingRoundError("propose_lock_contention")`.
- Modify `backend/app/api/routes/finalization.py`
  - Convert base `SchedulingRoundError` from `record_vote` into HTTP 409.
- Optionally update `docs/superpowers/plans/2026-06-03-audit-p1-security-and-vote-fixes.md`
  - Add implementation status and verification output after code changes.

---

### Task 1: Add Chat Read Security Tests

**Files:**
- Create: `backend/tests/integration/test_chat_messages_security.py`
- Reference: `backend/app/api/routes/chat.py`
- Reference: `backend/app/models/chat.py`

- [ ] **Step 1: Write the failing integration tests**

Create `backend/tests/integration/test_chat_messages_security.py` with this content:

```python
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.main import app
from app.models.chat import ChatMessage, PaneType, Visibility


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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
    from app.models.room import Room, RoomMember
    from app.models.user import User

    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        session.add_all(
            [
                # User 모델엔 google_sub 필드 없음(google_access_token/refresh_token만 존재).
                # email/name 만 필수, id 는 명시 지정.
                User(id=1, email="owner@test", name="Owner"),
                User(id=2, email="member@test", name="Member"),
                User(id=3, email="outsider@test", name="Outsider"),
            ]
        )
        await session.commit()

        session.add_all(
            [
                Room(id=10, name="room ten", created_by=1, status="active"),
                Room(id=20, name="room twenty", created_by=3, status="active"),
            ]
        )
        await session.commit()

        session.add_all(
            [
                RoomMember(room_id=10, user_id=1, role="owner"),
                RoomMember(room_id=10, user_id=2, role="member"),
                RoomMember(room_id=20, user_id=3, role="owner"),
            ]
        )
        await session.commit()

        session.add_all(
            [
                ChatMessage(
                    pane_type=PaneType.social.value,
                    role="user",
                    content="room10 social",
                    sender="Owner",
                    room_id=10,
                    user_id=1,
                    visibility=Visibility.shared.value,
                ),
                ChatMessage(
                    pane_type=PaneType.social.value,
                    role="user",
                    content="room20 secret",
                    sender="Outsider",
                    room_id=20,
                    user_id=3,
                    visibility=Visibility.shared.value,
                ),
                ChatMessage(
                    pane_type=PaneType.agent.value,
                    role="assistant",
                    content="room10 shared agent",
                    sender="AI",
                    room_id=10,
                    user_id=None,
                    visibility=Visibility.shared.value,
                ),
                ChatMessage(
                    pane_type=PaneType.agent.value,
                    role="assistant",
                    content="owner private agent",
                    sender="AI",
                    room_id=10,
                    user_id=1,
                    visibility=Visibility.private.value,
                ),
                ChatMessage(
                    pane_type=PaneType.agent.value,
                    role="assistant",
                    content="member private agent",
                    sender="AI",
                    room_id=10,
                    user_id=2,
                    visibility=Visibility.private.value,
                ),
                ChatMessage(
                    pane_type=PaneType.personal_assistant.value,
                    role="user",
                    content="owner personal assistant",
                    sender="Owner",
                    room_id=None,
                    session_id="personal_assistant:1",
                    visibility=Visibility.shared.value,
                ),
                ChatMessage(
                    pane_type=PaneType.personal_assistant.value,
                    role="user",
                    content="outsider personal assistant",
                    sender="Outsider",
                    room_id=None,
                    session_id="personal_assistant:3",
                    visibility=Visibility.shared.value,
                ),
            ]
        )
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
async def client(db_engine, seeded_db) -> AsyncIterator[AsyncClient]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_session_override() -> AsyncIterator[AsyncSession]:
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _get_session_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _set_current_user(user_id: int) -> None:
    app.dependency_overrides[get_current_user] = lambda: _as_auth_user(user_id)


async def test_social_messages_require_room_id(client):
    _set_current_user(1)

    resp = await client.get("/api/v1/chat/messages", params={"pane_type": "social"})

    assert resp.status_code == 400
    assert resp.json()["detail"] == "room_id_required"


async def test_room_messages_reject_non_member(client):
    _set_current_user(1)

    resp = await client.get(
        "/api/v1/chat/messages",
        params={"pane_type": "social", "room_id": 20},
    )

    assert resp.status_code == 403


async def test_room_messages_do_not_leak_other_rooms_or_other_private_agent(client):
    _set_current_user(1)

    resp = await client.get("/api/v1/chat/messages", params={"room_id": 10})

    assert resp.status_code == 200, resp.text
    contents = [row["content"] for row in resp.json()]
    assert "room10 social" in contents
    assert "room10 shared agent" in contents
    assert "owner private agent" in contents
    assert "room20 secret" not in contents
    assert "member private agent" not in contents
    assert "owner personal assistant" not in contents
    assert "outsider personal assistant" not in contents


async def test_personal_assistant_read_is_scoped_to_current_user(client):
    _set_current_user(1)

    resp = await client.get(
        "/api/v1/chat/messages",
        params={"pane_type": "personal_assistant"},
    )

    assert resp.status_code == 200, resp.text
    contents = [row["content"] for row in resp.json()]
    assert contents == ["owner personal assistant"]


async def test_personal_assistant_rejects_other_user_session_id(client):
    _set_current_user(1)

    resp = await client.get(
        "/api/v1/chat/messages",
        params={
            "pane_type": "personal_assistant",
            "session_id": "personal_assistant:3",
        },
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "personal_assistant_forbidden"
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
cd backend
pytest tests/integration/test_chat_messages_security.py -q
```

Expected before implementation:
- `test_social_messages_require_room_id` fails because the endpoint currently returns `200`.
- `test_personal_assistant_read_is_scoped_to_current_user` fails because the endpoint currently includes the other user's personal assistant message.
- Other tests may also fail depending on query ordering; the important red signal is that the privacy boundary is not enforced.

---

### Task 2: Harden `GET /chat/messages`

**Files:**
- Modify: `backend/app/api/routes/chat.py`
- Test: `backend/tests/integration/test_chat_messages_security.py`

- [ ] **Step 1: Add a local personal assistant session helper**

In `backend/app/api/routes/chat.py`, add this helper near `_message_to_event_dict`:

```python
def _personal_assistant_session_id(user_id: int) -> str:
    return f"personal_assistant:{user_id}"
```

- [ ] **Step 2: Replace `list_messages` authorization and query construction**

Replace the body of `list_messages` after `user_id = int(_current_user.sub)` with:

```python
    is_personal_assistant = pane_type == PaneType.personal_assistant

    if is_personal_assistant:
        if room_id is not None:
            raise HTTPException(status_code=400, detail="personal_assistant_has_no_room")
        own_session_id = _personal_assistant_session_id(user_id)
        if session_id is not None and session_id != own_session_id:
            raise HTTPException(status_code=403, detail="personal_assistant_forbidden")
    else:
        if room_id is None:
            raise HTTPException(status_code=400, detail="room_id_required")

        member_result = await session.execute(
            select(RoomMember).where(
                RoomMember.room_id == room_id,
                RoomMember.user_id == user_id,
            )
        )
        if member_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Not a member of this room")

    stmt = select(ChatMessage).order_by(ChatMessage.created_at.asc()).limit(limit)

    if is_personal_assistant:
        stmt = stmt.where(ChatMessage.pane_type == PaneType.personal_assistant.value)
        stmt = stmt.where(ChatMessage.room_id.is_(None))
        stmt = stmt.where(ChatMessage.session_id == _personal_assistant_session_id(user_id))
    else:
        stmt = stmt.where(ChatMessage.room_id == room_id)
        if pane_type:
            stmt = stmt.where(ChatMessage.pane_type == pane_type.value)
        if session_id:
            stmt = stmt.where(ChatMessage.session_id == session_id)
        stmt = stmt.where(
            or_(
                ChatMessage.pane_type != PaneType.agent.value,
                ChatMessage.visibility == Visibility.shared.value,
                and_(
                    ChatMessage.visibility == Visibility.private.value,
                    ChatMessage.user_id == user_id,
                ),
            )
        )

    result = await session.execute(stmt)
    return result.scalars().all()
```

This keeps room chat and personal assistant chat as separate data planes:
- Room panes require `room_id` and membership.
- `personal_assistant` ignores arbitrary `session_id` and always uses the current user's own `personal_assistant:{user_id}` session.
- Room queries still allow shared agent messages and the current user's own private agent messages, but not another user's private agent messages.

- [ ] **Step 3: Run the chat security tests**

Run:

```bash
cd backend
pytest tests/integration/test_chat_messages_security.py -q
```

Expected:

```text
5 passed
```

---

### Task 3: Add Finalization Lock Contention Regression Test

**Files:**
- Modify: `backend/tests/integration/test_finalization_api.py`
- Reference: `backend/app/api/routes/finalization.py`

- [ ] **Step 1: Add a failing test to `test_finalization_api.py`**

Append this test in the `POST /finalization/{proposal_id}/vote` section, after `test_vote_on_unknown_proposal_404`:

```python
async def test_vote_lock_contention_returns_retryable_409(
    client, redis_client, monkeypatch
):
    proposal = await _seed_proposal(redis_client)

    async def _raise_lock_contention(*args, **kwargs):
        raise sr.SchedulingRoundError("propose_lock_contention")

    monkeypatch.setattr(sr, "record_vote", _raise_lock_contention)
    _set_current_user(2)

    resp = await client.post(
        f"/api/v1/finalization/{proposal.proposal_id}/vote",
        json={"choice": "like", "room_id": 10},
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == "vote_contention_retry"
```

- [ ] **Step 2: Run the single test and verify it fails**

Run:

```bash
cd backend
pytest tests/integration/test_finalization_api.py::test_vote_lock_contention_returns_retryable_409 -q
```

Expected before implementation:
- The request returns HTTP 500 or raises an unhandled exception from `sr.SchedulingRoundError("propose_lock_contention")`.

---

### Task 4: Map Scheduling Lock Contention To HTTP 409

**Files:**
- Modify: `backend/app/api/routes/finalization.py`
- Test: `backend/tests/integration/test_finalization_api.py`

- [ ] **Step 1: Add a base `SchedulingRoundError` handler**

In `vote_on_proposal`, add this exception block after `except sr.SupersededError as exc:` and before `except ValueError as exc:`:

```python
    except sr.SchedulingRoundError as exc:
        detail = (
            "vote_contention_retry"
            if str(exc) == "propose_lock_contention"
            else str(exc) or "scheduling_round_error"
        )
        raise HTTPException(status_code=409, detail=detail)
```

The resulting exception section should be:

```python
    except sr.NotFoundError:
        raise HTTPException(status_code=404, detail="proposal_not_found")
    except sr.SupersededError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except sr.SchedulingRoundError as exc:
        detail = (
            "vote_contention_retry"
            if str(exc) == "propose_lock_contention"
            else str(exc) or "scheduling_round_error"
        )
        raise HTTPException(status_code=409, detail=detail)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

- [ ] **Step 2: Run the lock contention test**

Run:

```bash
cd backend
pytest tests/integration/test_finalization_api.py::test_vote_lock_contention_returns_retryable_409 -q
```

Expected:

```text
1 passed
```

- [ ] **Step 3: Run the finalization integration tests**

Run:

```bash
cd backend
pytest tests/integration/test_finalization_api.py -q
```

Expected:

```text
all tests pass
```

---

### Task 5: Verification And Documentation Update

**Files:**
- Modify: `docs/superpowers/plans/2026-06-03-audit-p1-security-and-vote-fixes.md`

- [ ] **Step 1: Run targeted verification**

Run:

```bash
cd backend
pytest tests/integration/test_chat_messages_security.py tests/integration/test_finalization_api.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 2: Run backend compile verification**

Run:

```bash
cd backend
python -m compileall app
```

Expected:

```text
0 compile errors
```

- [ ] **Step 3: Run full backend suite as a non-blocking signal**

Run:

```bash
cd backend
pytest -q
```

Expected current baseline:
- The P1-related integration tests pass.
- `tests/unit/test_finalization_reason.py` was a pre-existing failure (the test patched the removed `call_gemini` symbol; the module uses `call_llm_tier` since d705b87 2026-05-27). It has **already been fixed separately** to patch `call_llm_tier` — those 6 tests now pass and are unrelated to this P1 patch.
- Note: the container env (`maedeup-api`) shows extra full-suite failures from test-isolation pollution (deprecated `event_loop` fixture in pytest-asyncio 0.23) and `PREFERENCE_TOGGLE_ENABLED=false` in `.env`. These are env artifacts, not regressions — run targeted files (as in Steps 1-2) for a clean signal.

- [ ] **Step 4: Add implementation status to this plan**

After implementation, append an `Implementation Status` section that states the exact fixed audit IDs and the concrete command outcomes from this workspace. Use the command names from Steps 1-3 and record the observed pass/fail counts, including any unrelated full-suite baseline failure.

---

## Rollout Notes

- Frontend happy path already sends `room_id` for room chat history, so requiring `room_id` should not break normal room screens.
- `/api/v1/assistant/history` remains the preferred API for home assistant history. Supporting `pane_type=personal_assistant` in `/chat/messages` is kept only as a safe compatibility path.
- The finalization change intentionally returns `409` instead of retrying inside the route. This keeps the critical section short and lets the client retry without hiding contention.

## Self-Review

- Spec coverage: all verified P1 audit items are mapped to tasks with tests and code changes.
- Placeholder scan: no implementation step depends on unspecified code or unspecified paths.
- Type consistency: query enum comparisons use `PaneType.*.value` when comparing against stored string columns; response models continue using existing `ChatMessageRead`.
