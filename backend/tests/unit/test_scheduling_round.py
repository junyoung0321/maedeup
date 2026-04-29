"""
Unit tests for app.services.scheduling_round.

Uses fakeredis (from conftest) so no live Redis required. Tests cover:
- snapshot hashing determinism
- propose majority/dedupe/rate-limit/lock paths
- record_vote atomic updates + state transitions
- host_confirm auth + state checks
- restore_for_room WS reconnect flow
"""
from __future__ import annotations

import asyncio

import pytest

from app.services import scheduling_round as sr


# ---------------------------------------------------------------------------
# Snapshot hash
# ---------------------------------------------------------------------------


def test_snapshot_hash_deterministic():
    a = {1: [{"date": "2026-05-01", "start": 900, "end": 1100}]}
    b = {1: [{"date": "2026-05-01", "start": 900, "end": 1100}]}
    assert sr.compute_snapshot_hash(a) == sr.compute_snapshot_hash(b)


def test_snapshot_hash_order_independent():
    a = {
        1: [{"date": "2026-05-01", "start": 900, "end": 1100}],
        2: [{"date": "2026-05-01", "start": 900, "end": 1100}],
    }
    b = {
        2: [{"date": "2026-05-01", "start": 900, "end": 1100}],
        1: [{"date": "2026-05-01", "start": 900, "end": 1100}],
    }
    assert sr.compute_snapshot_hash(a) == sr.compute_snapshot_hash(b)


def test_snapshot_hash_differs_on_slot_change():
    a = {1: [{"date": "2026-05-01", "start": 900, "end": 1100}]}
    b = {1: [{"date": "2026-05-01", "start": 1000, "end": 1200}]}
    assert sr.compute_snapshot_hash(a) != sr.compute_snapshot_hash(b)


# ---------------------------------------------------------------------------
# propose
# ---------------------------------------------------------------------------


async def test_propose_creates_new_proposal(fake_redis):
    slot = {"slot_id": "s1", "label": "토요일 15:00", "start_at": "2026-05-02T15:00:00"}
    proposal = await sr.propose(
        fake_redis,
        room_id=10,
        host_user_id=1,
        total_eligible_voters=5,
        proposed_slot=slot,
        snapshot_hash="hash_v1",
    )
    assert proposal is not None
    assert proposal.room_id == 10
    assert proposal.host_user_id == 1
    assert proposal.total_eligible_voters == 5
    assert proposal.status == sr.ProposalStatus.active
    assert proposal.version >= 1
    assert proposal.proposal_id


async def test_propose_dedupes_same_snapshot(fake_redis):
    slot = {"slot_id": "s1", "label": "토요일 15:00"}
    first = await sr.propose(
        fake_redis,
        room_id=11,
        host_user_id=1,
        total_eligible_voters=5,
        proposed_slot=slot,
        snapshot_hash="hash_same",
    )
    # Allow rate-limit window to clear
    await fake_redis.delete(sr._key_ratelimit(11))
    second = await sr.propose(
        fake_redis,
        room_id=11,
        host_user_id=1,
        total_eligible_voters=5,
        proposed_slot=slot,
        snapshot_hash="hash_same",
    )
    assert first is not None
    assert second is not None
    assert first.proposal_id == second.proposal_id
    assert first.version == second.version


async def test_propose_new_version_on_hash_change(fake_redis):
    slot_a = {"slot_id": "s1", "label": "토요일 15:00"}
    slot_b = {"slot_id": "s2", "label": "일요일 14:00"}
    first = await sr.propose(
        fake_redis,
        room_id=12,
        host_user_id=1,
        total_eligible_voters=5,
        proposed_slot=slot_a,
        snapshot_hash="hash_v1",
    )
    await fake_redis.delete(sr._key_ratelimit(12))
    second = await sr.propose(
        fake_redis,
        room_id=12,
        host_user_id=1,
        total_eligible_voters=5,
        proposed_slot=slot_b,
        snapshot_hash="hash_v2",
    )
    assert first is not None and second is not None
    assert first.proposal_id != second.proposal_id
    assert second.version > first.version


async def test_propose_rate_limited_returns_existing(fake_redis):
    slot = {"slot_id": "s1", "label": "토요일 15:00"}
    first = await sr.propose(
        fake_redis,
        room_id=13,
        host_user_id=1,
        total_eligible_voters=5,
        proposed_slot=slot,
        snapshot_hash="hash_a",
    )
    # Immediate second call (no ratelimit key cleared) — should hit the limiter.
    second = await sr.propose(
        fake_redis,
        room_id=13,
        host_user_id=1,
        total_eligible_voters=5,
        proposed_slot={"slot_id": "s2", "label": "다른시간"},
        snapshot_hash="hash_b",
    )
    assert first is not None
    # Rate-limited response: returns the existing proposal, not a new one.
    assert second is not None
    assert second.proposal_id == first.proposal_id


async def test_propose_uses_reason_generator(fake_redis):
    async def custom_reason(room_id, slot, alt, likes, total):
        return f"custom reason for room {room_id}"

    proposal = await sr.propose(
        fake_redis,
        room_id=14,
        host_user_id=1,
        total_eligible_voters=3,
        proposed_slot={"label": "test"},
        snapshot_hash="h1",
        reason_generator=custom_reason,
    )
    assert proposal is not None
    assert proposal.reason == "custom reason for room 14"


async def test_propose_falls_back_on_reason_generator_exception(fake_redis):
    async def broken_reason(*args, **kwargs):
        raise RuntimeError("gemini timeout")

    proposal = await sr.propose(
        fake_redis,
        room_id=15,
        host_user_id=1,
        total_eligible_voters=3,
        proposed_slot={"label": "토요일 15:00"},
        snapshot_hash="h1",
        reason_generator=broken_reason,
    )
    assert proposal is not None
    # Template fallback kicks in when the generator raises.
    assert "토요일 15:00" in proposal.reason or "3명" in proposal.reason


# ---------------------------------------------------------------------------
# record_vote
# ---------------------------------------------------------------------------


async def test_record_vote_happy_path(fake_redis):
    proposal = await sr.propose(
        fake_redis,
        room_id=20,
        host_user_id=1,
        total_eligible_voters=5,
        proposed_slot={"label": "15:00"},
        snapshot_hash="h1",
    )
    assert proposal is not None
    updated = await sr.record_vote(
        fake_redis,
        room_id=20,
        proposal_id=proposal.proposal_id,
        user_id=3,
        choice="like",
    )
    assert updated.votes["3"] == "like"
    assert updated.like_count == 1


async def test_record_vote_rejects_invalid_choice(fake_redis):
    proposal = await sr.propose(
        fake_redis,
        room_id=21,
        host_user_id=1,
        total_eligible_voters=3,
        proposed_slot={"label": "15:00"},
        snapshot_hash="h1",
    )
    assert proposal is not None
    with pytest.raises(ValueError):
        await sr.record_vote(
            fake_redis,
            room_id=21,
            proposal_id=proposal.proposal_id,
            user_id=2,
            choice="maybe",  # type: ignore[arg-type]
        )


async def test_record_vote_transitions_to_majority_reached(fake_redis):
    proposal = await sr.propose(
        fake_redis,
        room_id=22,
        host_user_id=1,
        total_eligible_voters=3,   # majority = 2
        proposed_slot={"label": "15:00"},
        snapshot_hash="h1",
    )
    assert proposal is not None

    p1 = await sr.record_vote(
        fake_redis,
        room_id=22,
        proposal_id=proposal.proposal_id,
        user_id=1,
        choice="like",
    )
    assert p1.status == sr.ProposalStatus.active

    p2 = await sr.record_vote(
        fake_redis,
        room_id=22,
        proposal_id=proposal.proposal_id,
        user_id=2,
        choice="like",
    )
    assert p2.status == sr.ProposalStatus.majority_reached
    assert p2.is_majority_reached


async def test_record_vote_404_on_unknown_proposal(fake_redis):
    with pytest.raises(sr.NotFoundError):
        await sr.record_vote(
            fake_redis,
            room_id=99,
            proposal_id="does-not-exist",
            user_id=1,
            choice="like",
        )


async def test_record_vote_allows_switch(fake_redis):
    proposal = await sr.propose(
        fake_redis,
        room_id=23,
        host_user_id=1,
        total_eligible_voters=5,
        proposed_slot={"label": "15:00"},
        snapshot_hash="h1",
    )
    assert proposal is not None
    await sr.record_vote(
        fake_redis, room_id=23, proposal_id=proposal.proposal_id, user_id=4, choice="like"
    )
    switched = await sr.record_vote(
        fake_redis, room_id=23, proposal_id=proposal.proposal_id, user_id=4, choice="other"
    )
    assert switched.votes["4"] == "other"
    assert switched.like_count == 0
    assert switched.other_count == 1


# ---------------------------------------------------------------------------
# host_confirm
# ---------------------------------------------------------------------------


async def test_host_confirm_rejects_non_host(fake_redis):
    proposal = await sr.propose(
        fake_redis,
        room_id=30,
        host_user_id=1,
        total_eligible_voters=3,
        proposed_slot={"label": "15:00"},
        snapshot_hash="h1",
    )
    assert proposal is not None
    await sr.record_vote(
        fake_redis, room_id=30, proposal_id=proposal.proposal_id, user_id=1, choice="like"
    )
    await sr.record_vote(
        fake_redis, room_id=30, proposal_id=proposal.proposal_id, user_id=2, choice="like"
    )
    with pytest.raises(sr.NotHostError):
        await sr.host_confirm(
            fake_redis,
            room_id=30,
            proposal_id=proposal.proposal_id,
            user_id=99,   # not the host
            room_host_id=1,
        )


async def test_host_confirm_rejects_below_majority(fake_redis):
    proposal = await sr.propose(
        fake_redis,
        room_id=31,
        host_user_id=1,
        total_eligible_voters=5,
        proposed_slot={"label": "15:00"},
        snapshot_hash="h1",
    )
    assert proposal is not None
    # Only 1 like out of 5 → not majority.
    await sr.record_vote(
        fake_redis, room_id=31, proposal_id=proposal.proposal_id, user_id=2, choice="like"
    )
    with pytest.raises(sr.BelowMajorityError):
        await sr.host_confirm(
            fake_redis,
            room_id=31,
            proposal_id=proposal.proposal_id,
            user_id=1,
            room_host_id=1,
        )


async def test_host_confirm_succeeds_after_majority(fake_redis):
    proposal = await sr.propose(
        fake_redis,
        room_id=32,
        host_user_id=1,
        total_eligible_voters=3,
        proposed_slot={"label": "15:00"},
        snapshot_hash="h1",
    )
    assert proposal is not None
    await sr.record_vote(
        fake_redis, room_id=32, proposal_id=proposal.proposal_id, user_id=1, choice="like"
    )
    await sr.record_vote(
        fake_redis, room_id=32, proposal_id=proposal.proposal_id, user_id=2, choice="like"
    )
    authorized = await sr.host_confirm(
        fake_redis,
        room_id=32,
        proposal_id=proposal.proposal_id,
        user_id=1,
        room_host_id=1,
    )
    assert authorized.is_majority_reached

    marked = await sr.mark_confirmed(
        fake_redis, room_id=32, proposal_id=proposal.proposal_id
    )
    assert marked is not None
    assert marked.status == sr.ProposalStatus.confirmed


async def test_host_confirm_idempotent_after_confirmed(fake_redis):
    proposal = await sr.propose(
        fake_redis,
        room_id=33,
        host_user_id=1,
        total_eligible_voters=3,
        proposed_slot={"label": "15:00"},
        snapshot_hash="h1",
    )
    assert proposal is not None
    for uid in (1, 2):
        await sr.record_vote(
            fake_redis, room_id=33, proposal_id=proposal.proposal_id, user_id=uid, choice="like"
        )
    await sr.host_confirm(
        fake_redis, room_id=33, proposal_id=proposal.proposal_id, user_id=1, room_host_id=1
    )
    await sr.mark_confirmed(fake_redis, room_id=33, proposal_id=proposal.proposal_id)

    # Second call should return same proposal, not raise.
    second = await sr.host_confirm(
        fake_redis, room_id=33, proposal_id=proposal.proposal_id, user_id=1, room_host_id=1
    )
    assert second.status == sr.ProposalStatus.confirmed


# ---------------------------------------------------------------------------
# restore_for_room
# ---------------------------------------------------------------------------


async def test_restore_returns_none_when_empty(fake_redis):
    result = await sr.restore_for_room(fake_redis, room_id=404)
    assert result is None


async def test_restore_returns_active_proposal(fake_redis):
    proposal = await sr.propose(
        fake_redis,
        room_id=40,
        host_user_id=1,
        total_eligible_voters=3,
        proposed_slot={"label": "15:00"},
        snapshot_hash="h1",
    )
    assert proposal is not None
    restored = await sr.restore_for_room(fake_redis, room_id=40)
    assert restored is not None
    assert restored.proposal_id == proposal.proposal_id


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


def test_proposal_serialization_round_trip():
    p = sr.Proposal(
        proposal_id="pid-1",
        room_id=7,
        version=3,
        proposed_slot={"label": "15:00"},
        status=sr.ProposalStatus.majority_reached,
        host_user_id=2,
        total_eligible_voters=4,
        votes={"1": "like", "2": "like", "3": "other"},
        snapshot_hash="h",
    )
    round_tripped = sr.Proposal.from_dict(p.to_dict())
    assert round_tripped.proposal_id == p.proposal_id
    assert round_tripped.status == sr.ProposalStatus.majority_reached
    assert round_tripped.votes == {"1": "like", "2": "like", "3": "other"}
    assert round_tripped.like_count == 2
    assert round_tripped.other_count == 1


async def test_proposal_redis_key_ttl_matches_deadline(fake_redis):
    """Redis 키 수명이 deadline(24h)과 일치해야 프론트 카운터가 거짓말이 아님."""
    await sr.propose(
        fake_redis,
        room_id=90,
        host_user_id=1,
        total_eligible_voters=2,
        proposed_slot={"label": "19:00"},
        snapshot_hash="h-ttl",
    )
    ttl = await fake_redis.ttl(f"finalization_proposal:90")
    # Allow small skew for time elapsed between SET and TTL read.
    assert sr.PROPOSAL_DEADLINE_SECONDS - 5 <= ttl <= sr.PROPOSAL_DEADLINE_SECONDS
    assert sr.PROPOSAL_TTL_SECONDS == sr.PROPOSAL_DEADLINE_SECONDS


def test_compute_majority_slot_respects_all_blocked():
    """모든 유저가 한 날짜를 불가능으로 표시하면 그 날짜는 제안 후보에서 빠져야 한다."""
    availability = {
        1: [{"date": "2026-05-02", "start": 0, "end": 10}],
        2: [{"date": "2026-05-02", "start": 0, "end": 10}],
        3: [{"date": "2026-05-02", "start": 0, "end": 10}],
    }
    unavailability = {
        1: ["2026-05-02"],
        2: ["2026-05-02"],
        3: ["2026-05-02"],
    }
    result = sr.compute_majority_slot(
        availability, total_eligible_voters=3, unavailability=unavailability
    )
    assert result is None


def test_compute_majority_slot_drops_blocked_user_from_day():
    """특정 유저가 해당 날짜 불가능이면, 그 유저의 availability 셀도 그 날엔 무시된다."""
    availability = {
        1: [{"date": "2026-05-02", "start": 0, "end": 4}],
        2: [{"date": "2026-05-02", "start": 0, "end": 4}],
    }
    # 유저 2는 5/2 불가능 → effective voter = 1, threshold = 1, 유저 1이 모든 셀 점유 → 통과.
    unavailability = {2: ["2026-05-02"]}
    result = sr.compute_majority_slot(
        availability, total_eligible_voters=2, unavailability=unavailability
    )
    assert result is not None
    assert result.primary["date"] == "2026-05-02"


async def test_record_unavailable_toggle_round_trip(fake_redis):
    """토글 on/off 후 load_room_unavailability가 일관된 상태를 반환하는지."""
    dates_after_on = await sr.record_unavailable_toggle(
        fake_redis, room_id=77, user_id=1, date="2026-05-02", unavailable=True
    )
    assert dates_after_on == ["2026-05-02"]

    dates_after_on_2 = await sr.record_unavailable_toggle(
        fake_redis, room_id=77, user_id=1, date="2026-05-03", unavailable=True
    )
    assert dates_after_on_2 == ["2026-05-02", "2026-05-03"]

    loaded = await sr.load_room_unavailability(fake_redis, room_id=77)
    assert loaded == {1: ["2026-05-02", "2026-05-03"]}

    dates_after_off = await sr.record_unavailable_toggle(
        fake_redis, room_id=77, user_id=1, date="2026-05-02", unavailable=False
    )
    assert dates_after_off == ["2026-05-03"]

    # 마지막 날짜도 해제하면 유저 엔트리 자체 삭제
    final = await sr.record_unavailable_toggle(
        fake_redis, room_id=77, user_id=1, date="2026-05-03", unavailable=False
    )
    assert final == []
    loaded_after = await sr.load_room_unavailability(fake_redis, room_id=77)
    assert loaded_after == {}
