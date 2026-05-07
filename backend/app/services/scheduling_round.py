"""
Scheduling round service — orchestrates the AI-proposal + host-approval flow.

Redis keys:
  finalization_proposal:{room_id}           — proposal state JSON, TTL 30min
  finalization_proposal:version:{room_id}   — monotonic INCR counter
  finalization_proposal:lock:{room_id}      — SETNX lock, TTL 5s
  finalization_proposal:ratelimit:{room_id} — sliding window, 1 per 30s

Called from both the WS handler (peer_time_selection aggregation) and the
REST endpoint (/finalization/{proposal_id}/vote, /meetings/{id}/confirm).
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Literal, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


PROPOSAL_DEADLINE_SECONDS = 24 * 3600   # Approach D: default deadline = +24h
PROPOSAL_TTL_SECONDS = PROPOSAL_DEADLINE_SECONDS  # Redis 키 수명 = deadline
AVAILABILITY_TTL_SECONDS = 6 * 3600     # room availability cache
LOCK_TTL_SECONDS = 5
RATE_LIMIT_WINDOW_SECONDS = 30
RATE_LIMIT_MAX_CALLS = 1
VOTE_DECAY_SECONDS = 15                 # can switch vote within this window
TIME_SLOT_FIRST_HOUR = 9                # TimeBar starts at 09:00 (matches frontend)
TIME_SLOT_MINUTES = 30                  # 30-minute cells
TIME_SLOT_MAX = 26                      # 09:00 .. 22:00 = 26 cells


VoteChoice = Literal["like", "other"]


class ProposalStatus(str, Enum):
    pending_ai = "pending_ai"
    active = "active"
    majority_reached = "majority_reached"
    confirmed = "confirmed"
    superseded = "superseded"


@dataclass
class Proposal:
    """In-memory proposal state, serialized to Redis JSON."""

    proposal_id: str
    room_id: int
    version: int
    proposed_slot: dict[str, Any]           # {slot_id, start_at, end_at, label}
    alternate_slot: Optional[dict[str, Any]] = None   # for tie cases (top-2)
    reason: str = ""                        # AI-generated narrator line
    status: ProposalStatus = ProposalStatus.active
    host_user_id: int = 0                   # rooms.created_by
    total_eligible_voters: int = 0          # room member count
    votes: dict[str, VoteChoice] = field(default_factory=dict)
    snapshot_hash: str = ""                 # hash of availability distribution
    superseded_by: Optional[str] = None     # proposal_id of the newer one
    created_at: float = field(default_factory=time.time)
    deadline_at: float = 0.0                # epoch seconds; Approach D reminder target

    def __post_init__(self) -> None:
        if self.deadline_at <= 0:
            self.deadline_at = self.created_at + PROPOSAL_DEADLINE_SECONDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "room_id": self.room_id,
            "version": self.version,
            "proposed_slot": self.proposed_slot,
            "alternate_slot": self.alternate_slot,
            "reason": self.reason,
            "status": self.status.value,
            "host_user_id": self.host_user_id,
            "total_eligible_voters": self.total_eligible_voters,
            "votes": dict(self.votes),
            "snapshot_hash": self.snapshot_hash,
            "superseded_by": self.superseded_by,
            "created_at": self.created_at,
            "deadline_at": self.deadline_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Proposal":
        return cls(
            proposal_id=data["proposal_id"],
            room_id=int(data["room_id"]),
            version=int(data["version"]),
            proposed_slot=data["proposed_slot"],
            alternate_slot=data.get("alternate_slot"),
            reason=data.get("reason", ""),
            status=ProposalStatus(data.get("status", "active")),
            host_user_id=int(data.get("host_user_id", 0)),
            total_eligible_voters=int(data.get("total_eligible_voters", 0)),
            votes=dict(data.get("votes", {})),
            snapshot_hash=data.get("snapshot_hash", ""),
            superseded_by=data.get("superseded_by"),
            created_at=float(data.get("created_at", time.time())),
            deadline_at=float(data.get("deadline_at", 0.0)),
        )

    @property
    def like_count(self) -> int:
        return sum(1 for v in self.votes.values() if v == "like")

    @property
    def other_count(self) -> int:
        return sum(1 for v in self.votes.values() if v == "other")

    @property
    def is_majority_reached(self) -> bool:
        """>50% of eligible voters chose 'like'."""
        if self.total_eligible_voters <= 0:
            return False
        return self.like_count * 2 > self.total_eligible_voters


class SchedulingRoundError(Exception):
    """Base exception for scheduling-round domain errors."""


class NotFoundError(SchedulingRoundError):
    """Proposal not in Redis (expired or never existed)."""


class SupersededError(SchedulingRoundError):
    """Proposal was replaced by a newer one; client must refresh."""


class BelowMajorityError(SchedulingRoundError):
    """Host tried to confirm before majority 'like' reached."""


class NotHostError(SchedulingRoundError):
    """User is not the room host (rooms.created_by)."""


class RateLimitedError(SchedulingRoundError):
    """Per-room propose rate limit hit."""


# ---------------------------------------------------------------------------
# Key builders
# ---------------------------------------------------------------------------


def _key_proposal(room_id: int) -> str:
    return f"finalization_proposal:{room_id}"


def _key_version(room_id: int) -> str:
    return f"finalization_proposal:version:{room_id}"


def _key_lock(room_id: int) -> str:
    return f"finalization_proposal:lock:{room_id}"


def _key_ratelimit(room_id: int) -> str:
    return f"finalization_proposal:ratelimit:{room_id}"


# ---------------------------------------------------------------------------
# Snapshot hashing
# ---------------------------------------------------------------------------


def compute_snapshot_hash(availability: dict[int, list[dict[str, Any]]]) -> str:
    """
    Hash the room's availability distribution for dedupe.

    availability: {user_id: [{date, start, end}, ...]}
    Hashing strategy: sort by (user_id, date, start, end), join, sha1.
    Identical distributions → identical hash, regardless of insertion order.
    """
    rows: list[tuple[int, str, int, int]] = []
    for user_id, slots in availability.items():
        for slot in slots:
            rows.append(
                (
                    int(user_id),
                    str(slot.get("date", "")),
                    int(slot.get("start", 0) or 0),
                    int(slot.get("end", 0) or 0),
                )
            )
    rows.sort()
    payload = "|".join(f"{uid}:{d}:{s}:{e}" for uid, d, s, e in rows)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Rate limit (per-room sliding window)
# ---------------------------------------------------------------------------


async def _check_room_rate_limit(redis: aioredis.Redis, room_id: int) -> bool:
    """
    Per-room propose rate limit: max 1 call per RATE_LIMIT_WINDOW_SECONDS.
    Returns True if allowed, False if limited. Redis outage → allow (graceful).
    """
    key = _key_ratelimit(room_id)
    now = time.time()
    try:
        async with redis.pipeline(transaction=True) as pipe:
            window_start = now - RATE_LIMIT_WINDOW_SECONDS
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, RATE_LIMIT_WINDOW_SECONDS + 1)
            results = await pipe.execute()
        count = int(results[2])
        return count <= RATE_LIMIT_MAX_CALLS
    except Exception:
        logger.debug("Room rate limiter skipped (Redis unavailable)")
        return True


# ---------------------------------------------------------------------------
# Lock (SETNX, 5s TTL)
# ---------------------------------------------------------------------------


async def _acquire_lock(redis: aioredis.Redis, room_id: int) -> bool:
    """Redis SETNX lock with short TTL. True if acquired."""
    try:
        acquired = await redis.set(_key_lock(room_id), "1", ex=LOCK_TTL_SECONDS, nx=True)
        return bool(acquired)
    except Exception:
        logger.warning("Lock acquire failed (Redis unavailable)", exc_info=True)
        return True  # degraded: proceed without lock


async def _release_lock(redis: aioredis.Redis, room_id: int) -> None:
    try:
        await redis.delete(_key_lock(room_id))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Versioning (monotonic INCR)
# ---------------------------------------------------------------------------


async def _next_version(redis: aioredis.Redis, room_id: int) -> int:
    try:
        return int(await redis.incr(_key_version(room_id)))
    except Exception:
        logger.warning("Version INCR failed, falling back to timestamp", exc_info=True)
        return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Proposal CRUD
# ---------------------------------------------------------------------------


async def _save_proposal(redis: aioredis.Redis, proposal: Proposal) -> None:
    await redis.set(
        _key_proposal(proposal.room_id),
        json.dumps(proposal.to_dict()),
        ex=PROPOSAL_TTL_SECONDS,
    )


async def _load_proposal_by_room(
    redis: aioredis.Redis, room_id: int
) -> Optional[Proposal]:
    try:
        raw = await redis.get(_key_proposal(room_id))
    except Exception:
        logger.warning("Redis GET failed", exc_info=True)
        return None
    if not raw:
        return None
    try:
        return Proposal.from_dict(json.loads(raw))
    except (json.JSONDecodeError, KeyError, ValueError):
        logger.exception("Proposal decode failed for room_id=%s", room_id)
        return None


async def _load_proposal_by_id(
    redis: aioredis.Redis, room_id: int, proposal_id: str
) -> Optional[Proposal]:
    proposal = await _load_proposal_by_room(redis, room_id)
    if proposal and proposal.proposal_id == proposal_id:
        return proposal
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# Type alias for the reason-generator injected from the LangGraph pipeline.
# Signature: (room_id, slot, alternate_slot, like_count, total) -> reason_str
ReasonGenerator = Callable[
    [int, dict[str, Any], Optional[dict[str, Any]], int, int],
    Awaitable[str],
]


async def propose(
    redis: aioredis.Redis,
    *,
    room_id: int,
    host_user_id: int,
    total_eligible_voters: int,
    proposed_slot: dict[str, Any],
    snapshot_hash: str,
    alternate_slot: Optional[dict[str, Any]] = None,
    reason_generator: Optional[ReasonGenerator] = None,
) -> Optional[Proposal]:
    """
    Generate a new proposal, or return the existing one if the snapshot hash
    is unchanged (dedupe). Returns None on rate limit.

    Raises no domain errors: callers treat None as "no-op, come back later".
    """
    if not await _check_room_rate_limit(redis, room_id):
        logger.info("propose rate-limited for room_id=%s", room_id)
        # Even when rate-limited, surface existing proposal so clients stay synced.
        return await _load_proposal_by_room(redis, room_id)

    if not await _acquire_lock(redis, room_id):
        logger.info("propose lock held for room_id=%s", room_id)
        return await _load_proposal_by_room(redis, room_id)

    try:
        existing = await _load_proposal_by_room(redis, room_id)
        if existing and existing.snapshot_hash == snapshot_hash and existing.status in (
            ProposalStatus.active,
            ProposalStatus.majority_reached,
            ProposalStatus.pending_ai,
        ):
            # Same distribution → reuse current proposal.
            return existing

        version = await _next_version(redis, room_id)

        reason = ""
        if reason_generator is not None:
            try:
                reason = await reason_generator(
                    room_id, proposed_slot, alternate_slot, 0, total_eligible_voters
                )
            except Exception:
                logger.exception("reason_generator failed, using template fallback")
                reason = _template_reason(proposed_slot, 0, total_eligible_voters)
        else:
            reason = _template_reason(proposed_slot, 0, total_eligible_voters)

        new_proposal = Proposal(
            proposal_id=str(uuid.uuid4()),
            room_id=room_id,
            version=version,
            proposed_slot=proposed_slot,
            alternate_slot=alternate_slot,
            reason=reason,
            status=ProposalStatus.active,
            host_user_id=host_user_id,
            total_eligible_voters=total_eligible_voters,
            snapshot_hash=snapshot_hash,
        )

        if existing is not None and existing.proposal_id != new_proposal.proposal_id:
            # Mark the old one as superseded for any subscribers still referencing it.
            existing.status = ProposalStatus.superseded
            existing.superseded_by = new_proposal.proposal_id
            # The main key is overwritten below; we keep the new one authoritative.

        await _save_proposal(redis, new_proposal)
        return new_proposal
    finally:
        await _release_lock(redis, room_id)


def _template_reason(
    slot: dict[str, Any], like_count: int, total: int
) -> str:
    label = slot.get("label") or "이 시간"
    if total > 0:
        return f"{total}명 중 {like_count}명이 {label}를 선택했어요."
    return f"{label} 어떠세요?"


async def record_vote(
    redis: aioredis.Redis,
    *,
    room_id: int,
    proposal_id: str,
    user_id: int,
    choice: VoteChoice,
) -> Proposal:
    """
    Atomically update a user's vote on the proposal.

    Raises NotFoundError / SupersededError if state is not writable.
    """
    if choice not in ("like", "other"):
        raise ValueError(f"Invalid vote choice: {choice}")

    if not await _acquire_lock(redis, room_id):
        raise SchedulingRoundError("propose_lock_contention")

    try:
        proposal = await _load_proposal_by_id(redis, room_id, proposal_id)
        if proposal is None:
            raise NotFoundError(f"proposal {proposal_id} not found")
        if proposal.status in (ProposalStatus.superseded, ProposalStatus.confirmed):
            raise SupersededError(f"proposal {proposal_id} not writable (status={proposal.status.value})")

        proposal.votes[str(user_id)] = choice
        if proposal.is_majority_reached and proposal.status == ProposalStatus.active:
            proposal.status = ProposalStatus.majority_reached

        await _save_proposal(redis, proposal)
        return proposal
    finally:
        await _release_lock(redis, room_id)


async def host_confirm(
    redis: aioredis.Redis,
    *,
    room_id: int,
    proposal_id: str,
    user_id: int,
    room_host_id: int,
) -> Proposal:
    """
    Host finalizes the proposal. Does NOT call the /meetings/confirm DB write —
    the caller (REST handler) is responsible for that, then transitions status
    via mark_confirmed() after DB success.

    Raises NotHostError / NotFoundError / SupersededError / BelowMajorityError.
    """
    if user_id != room_host_id:
        raise NotHostError(f"user {user_id} is not host (host={room_host_id})")

    proposal = await _load_proposal_by_id(redis, room_id, proposal_id)
    if proposal is None:
        raise NotFoundError(f"proposal {proposal_id} not found")
    if proposal.status == ProposalStatus.superseded:
        raise SupersededError(f"proposal {proposal_id} superseded by {proposal.superseded_by}")
    if proposal.status == ProposalStatus.confirmed:
        return proposal   # idempotent
    if not proposal.is_majority_reached:
        raise BelowMajorityError(
            f"likes={proposal.like_count} / eligible={proposal.total_eligible_voters}"
        )
    return proposal


async def mark_confirmed(
    redis: aioredis.Redis,
    *,
    room_id: int,
    proposal_id: str,
) -> Optional[Proposal]:
    """Called by the REST handler after /meetings/confirm DB write succeeds."""
    proposal = await _load_proposal_by_id(redis, room_id, proposal_id)
    if proposal is None:
        return None
    proposal.status = ProposalStatus.confirmed
    await _save_proposal(redis, proposal)
    return proposal


async def restore_for_room(
    redis: aioredis.Redis, *, room_id: int
) -> Optional[Proposal]:
    """WS reconnect helper: return current proposal state from Redis, if any."""
    return await _load_proposal_by_room(redis, room_id)


# ---------------------------------------------------------------------------
# Availability aggregation (server-side majority detector for WS handler)
# ---------------------------------------------------------------------------


def _key_availability(room_id: int) -> str:
    return f"room_availability:{room_id}"


async def record_availability(
    redis: aioredis.Redis,
    *,
    room_id: int,
    user_id: int,
    date: Optional[str],
    start: Optional[int],
    end: Optional[int],
) -> None:
    """
    Persist a single user's latest availability selection in Redis.

    If `date` is None → treat as "cleared", remove that user's entry.
    Otherwise overwrite the user's entry with {date, start, end}.
    """
    key = _key_availability(room_id)
    try:
        if date is None or start is None or end is None:
            await redis.hdel(key, str(user_id))
        else:
            entry = json.dumps({"date": date, "start": int(start), "end": int(end)})
            await redis.hset(key, str(user_id), entry)
            await redis.expire(key, AVAILABILITY_TTL_SECONDS)
    except Exception:
        logger.warning(
            "Availability write failed room_id=%s user_id=%s",
            room_id, user_id, exc_info=True,
        )


async def load_room_availability(
    redis: aioredis.Redis, *, room_id: int
) -> dict[int, list[dict[str, Any]]]:
    """Return {user_id: [{date, start, end}]} — one entry per user currently tracked."""
    key = _key_availability(room_id)
    try:
        entries = await redis.hgetall(key)
    except Exception:
        logger.warning("Availability read failed room_id=%s", room_id, exc_info=True)
        return {}

    result: dict[int, list[dict[str, Any]]] = {}
    for user_key, raw in entries.items():
        try:
            uid = int(user_key)
            parsed = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            continue
        result[uid] = [parsed]
    return result


def slot_idx_to_time(idx: int) -> str:
    """TimeBar slot index (0..25) → 'HH:MM' starting at TIME_SLOT_FIRST_HOUR.

    C7 contract (2026-05-08): public API. backend/frontend 양쪽이 동일한 매핑 사용해야 함.
    frontend 미러: `frontend/src/components/meeting/TimeBarSelector.tsx::slotToTime` (HOUR_START/SLOT_MINUTES).
    상수 변경 시 양쪽 동기화 필수.
    """
    total_minutes = TIME_SLOT_FIRST_HOUR * 60 + idx * TIME_SLOT_MINUTES
    hh = total_minutes // 60
    mm = total_minutes % 60
    return f"{hh:02d}:{mm:02d}"


# 후방 호환 — 기존 private 호출자가 점진적으로 public으로 이전.
_slot_idx_to_time = slot_idx_to_time


def _format_slot(date: str, start_idx: int, end_idx: int) -> dict[str, Any]:
    """Convert a cell range into a slot dict for the proposal payload."""
    start_str = slot_idx_to_time(start_idx)
    # end_idx is INCLUSIVE; bump by one cell to get the exclusive end time.
    end_str = slot_idx_to_time(end_idx + 1)
    return {
        "date": date,
        "start_idx": start_idx,
        "end_idx": end_idx,
        "start_at": f"{date}T{start_str}:00",
        "end_at": f"{date}T{end_str}:00",
        "label": f"{date} {start_str}-{end_str}",
    }


@dataclass
class MajoritySlotResult:
    """Result of computing the majority slot over room availability."""

    primary: dict[str, Any]
    alternate: Optional[dict[str, Any]]  # tie case (top-2 runs, equal length/count)


def compute_majority_slot(
    availability: dict[int, list[dict[str, Any]]],
    total_eligible_voters: int,
    unavailability: Optional[dict[int, list[str]]] = None,
) -> Optional[MajoritySlotResult]:
    """
    Find the longest consecutive run of 30-min cells that has strict majority
    availability. Returns MajoritySlotResult with primary + optional alternate
    (when two runs tie on length AND coverage).

    When `unavailability` is provided ({user_id: [date, ...]}), per-date threshold
    is adjusted: on date D, eligible voters = total - |users who marked D as blocked|,
    and availability cells from unavailable users on D are dropped defensively.

    Returns None if no run meets the majority threshold.
    """
    if total_eligible_voters <= 0:
        return None

    unavailability = unavailability or {}
    # Per-date set of user_ids who flagged the date as unavailable.
    blocked_by_date: dict[str, set[int]] = {}
    for uid, dates in unavailability.items():
        for d in dates:
            if isinstance(d, str):
                blocked_by_date.setdefault(d, set()).add(int(uid))

    # cells[date][slot_idx] = set of user_ids
    cells: dict[str, dict[int, set[int]]] = {}
    for user_id, slots in availability.items():
        for sel in slots:
            date = sel.get("date")
            start = sel.get("start")
            end = sel.get("end")
            if not isinstance(date, str) or start is None or end is None:
                continue
            # Defensive: if the user also marked this date unavailable, drop their
            # slot cells for that date — treat explicit "불가능" as authoritative.
            if int(user_id) in blocked_by_date.get(date, set()):
                continue
            try:
                s, e = int(start), int(end)
            except (TypeError, ValueError):
                continue
            # In the TimeBar protocol, end is INCLUSIVE: slots [s..e].
            if s > e:
                s, e = e, s
            s = max(0, s)
            e = min(TIME_SLOT_MAX - 1, e)
            by_cell = cells.setdefault(date, {})
            for idx in range(s, e + 1):
                by_cell.setdefault(idx, set()).add(int(user_id))

    def _threshold_for(date: str) -> int:
        effective = total_eligible_voters - len(blocked_by_date.get(date, set()))
        if effective <= 0:
            # 모두 불가능하면 과반 자체가 불가 — 사실상 차단.
            return total_eligible_voters + 1
        return effective // 2 + 1

    # Find all runs with count >= threshold, pick longest(+top-2 for tie).
    best_runs: list[tuple[str, int, int, int]] = []   # (date, start, end, min_count)
    for date, by_cell in cells.items():
        if not by_cell:
            continue
        threshold = _threshold_for(date)
        sorted_idxs = sorted(by_cell.keys())
        i = 0
        while i < len(sorted_idxs):
            if len(by_cell[sorted_idxs[i]]) >= threshold:
                j = i
                while (
                    j + 1 < len(sorted_idxs)
                    and sorted_idxs[j + 1] == sorted_idxs[j] + 1
                    and len(by_cell[sorted_idxs[j + 1]]) >= threshold
                ):
                    j += 1
                start_idx = sorted_idxs[i]
                end_idx = sorted_idxs[j]
                min_count = min(len(by_cell[k]) for k in sorted_idxs[i:j + 1])
                best_runs.append((date, start_idx, end_idx, min_count))
                i = j + 1
            else:
                i += 1

    if not best_runs:
        return None

    # Rank by (length desc, min_count desc) so longer, more-covered wins.
    best_runs.sort(key=lambda r: (-(r[2] - r[1]), -r[3]))

    primary_run = best_runs[0]
    primary = _format_slot(primary_run[0], primary_run[1], primary_run[2])

    alternate: Optional[dict[str, Any]] = None
    if len(best_runs) > 1:
        a = best_runs[1]
        same_length = (a[2] - a[1]) == (primary_run[2] - primary_run[1])
        same_count = a[3] == primary_run[3]
        if same_length and same_count:
            alternate = _format_slot(a[0], a[1], a[2])

    return MajoritySlotResult(primary=primary, alternate=alternate)


async def clear_availability(redis: aioredis.Redis, *, room_id: int) -> None:
    """Reset the room's availability hash (called on meeting confirmation)."""
    try:
        await redis.delete(_key_availability(room_id))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Per-meeting unavailability (red-bordered dates on calendar)
# ---------------------------------------------------------------------------


def _key_unavailability(room_id: int) -> str:
    return f"room_unavailability:{room_id}"


async def record_unavailable_toggle(
    redis: aioredis.Redis,
    *,
    room_id: int,
    user_id: int,
    date: str,
    unavailable: bool,
) -> list[str]:
    """
    Add/remove a single date to the user's unavailability set for this room.
    Returns the user's full list of unavailable dates after the mutation.
    """
    key = _key_unavailability(room_id)
    try:
        raw = await redis.hget(key, str(user_id))
        current: list[str] = []
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    current = [d for d in parsed if isinstance(d, str)]
            except json.JSONDecodeError:
                current = []
        as_set = set(current)
        if unavailable:
            as_set.add(date)
        else:
            as_set.discard(date)
        new_list = sorted(as_set)
        if new_list:
            await redis.hset(key, str(user_id), json.dumps(new_list))
            await redis.expire(key, AVAILABILITY_TTL_SECONDS)
        else:
            await redis.hdel(key, str(user_id))
        return new_list
    except Exception:
        logger.warning(
            "Unavailability write failed room_id=%s user_id=%s",
            room_id, user_id, exc_info=True,
        )
        return []


async def load_room_unavailability(
    redis: aioredis.Redis, *, room_id: int
) -> dict[int, list[str]]:
    """Return {user_id: [date, ...]} — one list per user currently tracked."""
    key = _key_unavailability(room_id)
    try:
        entries = await redis.hgetall(key)
    except Exception:
        logger.warning("Unavailability read failed room_id=%s", room_id, exc_info=True)
        return {}

    result: dict[int, list[str]] = {}
    for user_key, raw in entries.items():
        try:
            uid = int(user_key)
            parsed = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            continue
        if isinstance(parsed, list):
            result[uid] = [d for d in parsed if isinstance(d, str)]
    return result


async def clear_unavailability(redis: aioredis.Redis, *, room_id: int) -> None:
    """Reset the room's unavailability hash (called on meeting confirmation)."""
    try:
        await redis.delete(_key_unavailability(room_id))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Per-room date selection (캘린더에서 클릭한 날짜 공유용)
# ---------------------------------------------------------------------------


def _key_date_selection(room_id: int) -> str:
    return f"room_date_selection:{room_id}"


async def record_date_selection(
    redis: aioredis.Redis,
    *,
    room_id: int,
    user_id: int,
    date: Optional[str],
) -> None:
    """한 유저의 현재 선택 날짜를 영속화. date=None이면 삭제."""
    key = _key_date_selection(room_id)
    try:
        if date is None:
            await redis.hdel(key, str(user_id))
        else:
            await redis.hset(key, str(user_id), date)
            await redis.expire(key, AVAILABILITY_TTL_SECONDS)
    except Exception:
        logger.warning(
            "Date selection write failed room_id=%s user_id=%s",
            room_id, user_id, exc_info=True,
        )


async def load_room_date_selections(
    redis: aioredis.Redis, *, room_id: int
) -> dict[int, str]:
    """{user_id: date} — 각 유저의 현재 선택 날짜."""
    key = _key_date_selection(room_id)
    try:
        entries = await redis.hgetall(key)
    except Exception:
        logger.warning("Date selection read failed room_id=%s", room_id, exc_info=True)
        return {}
    result: dict[int, str] = {}
    for user_key, raw in entries.items():
        try:
            uid = int(user_key)
        except (TypeError, ValueError):
            continue
        if isinstance(raw, str):
            result[uid] = raw
    return result


async def clear_date_selections(redis: aioredis.Redis, *, room_id: int) -> None:
    """확정 시 방의 date_selection 해시 비움."""
    try:
        await redis.delete(_key_date_selection(room_id))
    except Exception:
        pass
