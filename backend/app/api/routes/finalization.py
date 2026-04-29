"""
REST endpoints for the finalization proposal flow.

Two surfaces:
- POST /finalization/{proposal_id}/vote — member casts [좋아요]/[다른 시간] on the active proposal
- GET  /finalization/room/{room_id}   — WS reconnect fallback, returns current proposal state

The actual proposal *creation* happens inside the WS handler when the majority
of the room's availability snapshot is detected; see `app.api.ws.social`.
Clients never call "propose" directly — it is a server-triggered reaction to
availability-selection activity.
"""
from __future__ import annotations

import json
import logging
from typing import Literal, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.security import AuthUser, get_current_user
from app.db.session import get_session
from app.models.room import Room, RoomMember
from app.services import scheduling_round as sr

router = APIRouter(tags=["finalization"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Redis client factory (overridable in tests)
# ---------------------------------------------------------------------------


def get_redis() -> aioredis.Redis:
    """FastAPI dependency returning a Redis client. Overridden in tests."""
    return aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class VoteBody(BaseModel):
    choice: Literal["like", "other"]
    room_id: int


class ProposalPayload(BaseModel):
    proposal_id: str
    version: int
    status: str
    proposed_slot: dict
    alternate_slot: Optional[dict] = None
    reason: str
    host_user_id: int
    total_eligible_voters: int
    like_count: int
    other_count: int
    votes: dict[str, str]
    my_vote: Optional[Literal["like", "other"]] = None


def _to_payload(proposal: sr.Proposal, me_user_id: int) -> ProposalPayload:
    return ProposalPayload(
        proposal_id=proposal.proposal_id,
        version=proposal.version,
        status=proposal.status.value,
        proposed_slot=proposal.proposed_slot,
        alternate_slot=proposal.alternate_slot,
        reason=proposal.reason,
        host_user_id=proposal.host_user_id,
        total_eligible_voters=proposal.total_eligible_voters,
        like_count=proposal.like_count,
        other_count=proposal.other_count,
        votes=dict(proposal.votes),
        my_vote=proposal.votes.get(str(me_user_id)),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _verify_room_membership(
    session: AsyncSession, user_id: int, room_id: int
) -> None:
    row = await session.execute(
        select(RoomMember).where(
            RoomMember.user_id == user_id,
            RoomMember.room_id == room_id,
        )
    )
    if row.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not a room member")


async def _publish_finalization_event(
    redis: aioredis.Redis,
    room_id: int,
    payload: dict,
) -> None:
    """Broadcast on the social channel. Redis outage → silent log, not fatal."""
    try:
        await redis.publish(
            f"social:{room_id}",
            json.dumps(payload, ensure_ascii=False),
        )
    except Exception:
        logger.warning(
            "Redis publish failed for finalization event room_id=%s",
            room_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# POST /finalization/{proposal_id}/vote
# ---------------------------------------------------------------------------


@router.post("/{proposal_id}/vote", response_model=ProposalPayload)
async def vote_on_proposal(
    proposal_id: str,
    body: VoteBody,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> ProposalPayload:
    user_id = int(current_user.sub)
    await _verify_room_membership(session, user_id, body.room_id)

    try:
        proposal = await sr.record_vote(
            redis,
            room_id=body.room_id,
            proposal_id=proposal_id,
            user_id=user_id,
            choice=body.choice,
        )
    except sr.NotFoundError:
        raise HTTPException(status_code=404, detail="proposal_not_found")
    except sr.SupersededError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    payload = _to_payload(proposal, user_id)

    # Broadcast updated state to all room members so live tallies stay in sync.
    await _publish_finalization_event(
        redis,
        body.room_id,
        {
            "type": "finalization_vote_update",
            "room_id": body.room_id,
            **payload.model_dump(),
        },
    )

    return payload


# ---------------------------------------------------------------------------
# GET /finalization/room/{room_id}
# ---------------------------------------------------------------------------


@router.get("/room/{room_id}", response_model=Optional[ProposalPayload])
async def get_current_proposal_for_room(
    room_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis: aioredis.Redis = Depends(get_redis),
) -> Optional[ProposalPayload]:
    user_id = int(current_user.sub)
    await _verify_room_membership(session, user_id, room_id)

    proposal = await sr.restore_for_room(redis, room_id=room_id)
    if proposal is None:
        return None
    return _to_payload(proposal, user_id)
