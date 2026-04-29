"""
Tests for the availability aggregation + majority-slot detector.

These are pure-Python helpers (no Redis required for compute_majority_slot).
The record_availability / load_room_availability tests use FakeRedis.
"""
from __future__ import annotations

import pytest

from app.services import scheduling_round as sr


def test_majority_slot_detects_simple_overlap():
    availability = {
        1: [{"date": "2026-05-02", "start": 12, "end": 14}],   # 15:00-16:30
        2: [{"date": "2026-05-02", "start": 12, "end": 14}],
        3: [{"date": "2026-05-02", "start": 12, "end": 14}],
    }
    result = sr.compute_majority_slot(availability, total_eligible_voters=3)
    assert result is not None
    assert result.primary["date"] == "2026-05-02"
    assert result.primary["start_idx"] == 12
    assert result.primary["end_idx"] == 14
    assert result.primary["start_at"] == "2026-05-02T15:00:00"
    # end_idx=14 is INCLUSIVE, so exclusive end = slot 15 = 16:30
    assert result.primary["end_at"] == "2026-05-02T16:30:00"
    assert result.alternate is None


def test_majority_slot_returns_none_below_threshold():
    availability = {
        1: [{"date": "2026-05-02", "start": 12, "end": 14}],
        2: [{"date": "2026-05-03", "start": 12, "end": 14}],
    }
    # 2 voters, threshold = 2. No cell has 2 occupants.
    result = sr.compute_majority_slot(availability, total_eligible_voters=2)
    assert result is None


def test_majority_slot_finds_longest_run():
    # User1 picks 12-18, User2 picks 12-18, User3 picks 12-14
    # Majority (3/3 over threshold=2) runs across 12..18. Expected run = 12..18.
    availability = {
        1: [{"date": "2026-05-02", "start": 12, "end": 18}],
        2: [{"date": "2026-05-02", "start": 12, "end": 18}],
        3: [{"date": "2026-05-02", "start": 12, "end": 14}],
    }
    result = sr.compute_majority_slot(availability, total_eligible_voters=3)
    assert result is not None
    # Threshold = 3/2+1 = 2. All cells 12-18 have >= 2 users (cells 15-18 have 2).
    assert result.primary["start_idx"] == 12
    assert result.primary["end_idx"] == 18


def test_majority_slot_tie_returns_alternate():
    # Two separate runs of equal length with equal min_count.
    availability = {
        1: [{"date": "2026-05-02", "start": 12, "end": 14}],
        2: [{"date": "2026-05-02", "start": 12, "end": 14}],
        3: [{"date": "2026-05-03", "start": 12, "end": 14}],
        4: [{"date": "2026-05-03", "start": 12, "end": 14}],
    }
    # 4 voters, threshold = 3. Run 1: date 05-02, cells 12-14 have 2 users (<3).
    # So no majority. Adjust test: threshold must be lower.
    # Let's set total_eligible_voters=2 so threshold=2 — then BOTH runs qualify.
    result = sr.compute_majority_slot(availability, total_eligible_voters=2)
    assert result is not None
    # Two equal runs → alternate populated.
    assert result.alternate is not None
    dates = {result.primary["date"], result.alternate["date"]}
    assert dates == {"2026-05-02", "2026-05-03"}


def test_majority_slot_handles_reversed_range():
    availability = {
        1: [{"date": "2026-05-02", "start": 14, "end": 12}],
        2: [{"date": "2026-05-02", "start": 12, "end": 14}],
    }
    # Reversed range should normalize to 12..14.
    result = sr.compute_majority_slot(availability, total_eligible_voters=2)
    assert result is not None
    assert result.primary["start_idx"] == 12
    assert result.primary["end_idx"] == 14


async def test_record_and_load_availability(fake_redis):
    await sr.record_availability(
        fake_redis, room_id=50, user_id=1, date="2026-05-02", start=12, end=14
    )
    await sr.record_availability(
        fake_redis, room_id=50, user_id=2, date="2026-05-02", start=12, end=14
    )
    loaded = await sr.load_room_availability(fake_redis, room_id=50)
    assert set(loaded.keys()) == {1, 2}
    assert loaded[1][0]["start"] == 12
    assert loaded[1][0]["end"] == 14


async def test_clear_availability_on_none(fake_redis):
    await sr.record_availability(
        fake_redis, room_id=51, user_id=1, date="2026-05-02", start=12, end=14
    )
    # Clear by passing None
    await sr.record_availability(
        fake_redis, room_id=51, user_id=1, date=None, start=None, end=None
    )
    loaded = await sr.load_room_availability(fake_redis, room_id=51)
    assert 1 not in loaded


async def test_clear_availability_full(fake_redis):
    await sr.record_availability(
        fake_redis, room_id=52, user_id=1, date="2026-05-02", start=12, end=14
    )
    await sr.clear_availability(fake_redis, room_id=52)
    loaded = await sr.load_room_availability(fake_redis, room_id=52)
    assert loaded == {}


def test_proposal_default_deadline_is_24h_later():
    p = sr.Proposal(
        proposal_id="x",
        room_id=1,
        version=1,
        proposed_slot={},
    )
    assert p.deadline_at > p.created_at
    assert abs((p.deadline_at - p.created_at) - 24 * 3600) < 1.0
