"""
Dev utility: seed a finalization proposal into Redis for the demo room.

Usage (from maedeup-cr stack):
  docker exec maedeup-cr-api python /app/scripts/seed_demo_proposal.py
"""
from __future__ import annotations

import asyncio
import json

import redis.asyncio as aioredis

from app.core.config import settings
from app.services import scheduling_round as sr


async def main() -> None:
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        for uid in (1, 2, 3):
            await sr.record_availability(
                r, room_id=1, user_id=uid, date="2026-05-02", start=12, end=14
            )
        availability = await sr.load_room_availability(r, room_id=1)
        print(f"availability: {availability}")

        result = sr.compute_majority_slot(availability, total_eligible_voters=3)
        print(f"slot: {result.primary if result else None}")
        if result is None:
            return

        proposal = await sr.propose(
            r,
            room_id=1,
            host_user_id=1,
            total_eligible_voters=3,
            proposed_slot=result.primary,
            snapshot_hash=sr.compute_snapshot_hash(availability),
        )
        if proposal is None:
            print("propose returned None (rate-limited or no majority)")
            return

        print(f"proposal_id={proposal.proposal_id}")
        print(f"status={proposal.status.value}")
        print(f"label={proposal.proposed_slot.get('label')}")
        print(f"reason={proposal.reason[:120]}")

        payload = {
            "type": "finalization_proposal",
            "room_id": 1,
            "proposal_id": proposal.proposal_id,
            "version": proposal.version,
            "status": proposal.status.value,
            "proposed_slot": proposal.proposed_slot,
            "alternate_slot": proposal.alternate_slot,
            "reason": proposal.reason,
            "host_user_id": proposal.host_user_id,
            "total_eligible_voters": proposal.total_eligible_voters,
            "votes": dict(proposal.votes),
            "deadline_at": proposal.deadline_at,
            "created_at": proposal.created_at,
        }
        await r.publish("social:1", json.dumps(payload, ensure_ascii=False))
        print("Published on social:1")
    finally:
        await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
