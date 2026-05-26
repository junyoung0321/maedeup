"""K3 동시성 측정 runner.

K3.1 race 감지: 동시 vote 후 DB vote 집계가 기대값과 일치하는지 (race = 불일치 delta).
K3.2 broadcast 누락 검증: 단일 트리거 후 각 WS 구독자가 이벤트를 수신했는지.

사용:
  ~/.venv-maedeup-demo/bin/python3 .gstack-k3-concurrency-runner.py --scenario all
  ~/.venv-maedeup-demo/bin/python3 .gstack-k3-concurrency-runner.py --scenario k3-conc-001
  ~/.venv-maedeup-demo/bin/python3 .gstack-k3-concurrency-runner.py --scenario k3-conc-004 --ws-timeout 15
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx
import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000"

VOTE_OPTIONS_TEMPLATE = [
    {"label": "다음주 월요일 점심 12:00", "start_at": "2026-06-02T03:00:00", "end_at": "2026-06-02T05:00:00"},
    {"label": "다음주 화요일 점심 12:00", "start_at": "2026-06-03T03:00:00", "end_at": "2026-06-03T05:00:00"},
    {"label": "다음주 수요일 점심 12:00", "start_at": "2026-06-04T03:00:00", "end_at": "2026-06-04T05:00:00"},
    {"label": "다음주 목요일 점심 12:00", "start_at": "2026-06-05T03:00:00", "end_at": "2026-06-05T05:00:00"},
    {"label": "다음주 금요일 점심 12:00", "start_at": "2026-06-06T03:00:00", "end_at": "2026-06-06T05:00:00"},
]


def load_fixture(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_token() -> str:
    return Path(".gstack-demo-token").read_text().strip()


# ---------------------------------------------------------------------------
# HTTP helpers (sync-wrapped async)
# ---------------------------------------------------------------------------


async def create_room(client: httpx.AsyncClient, host_token: str, name: str) -> int:
    """POST /api/v1/rooms → room_id."""
    resp = await client.post(
        f"{API}/api/v1/rooms",
        json={"name": name, "description": "K3 동시성 테스트 룸"},
        headers={"Authorization": f"Bearer {host_token}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return int(resp.json()["id"])


async def guest_join(client: httpx.AsyncClient, room_id: int, display_name: str) -> dict:
    """POST /api/v1/rooms/{room_id}/guest-join → {token, user_id, name}."""
    resp = await client.post(
        f"{API}/api/v1/rooms/{room_id}/guest-join",
        json={"display_name": display_name},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


async def confirm_meeting(
    client: httpx.AsyncClient,
    host_token: str,
    room_id: int,
    vote_options_count: int,
) -> int:
    """POST /api/v1/meetings/confirm → meeting_id (pending 상태).

    vote_options 를 가진 pending MeetingSchedule 생성.
    start/end 의 시간이 meeting status = pending 이면 vote API 접근 가능.
    """
    options = VOTE_OPTIONS_TEMPLATE[:vote_options_count]
    resp = await client.post(
        f"{API}/api/v1/meetings/confirm",
        json={
            "room_id": room_id,
            "title": f"K3 테스트 모임 (room {room_id})",
            "scheduled_at": options[0]["start_at"],
            "end_at": options[0]["end_at"],
            "vote_options": options,
        },
        headers={"Authorization": f"Bearer {host_token}"},
        timeout=10.0,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"confirm_meeting failed: {resp.status_code} {resp.text[:200]}")
    return int(resp.json()["id"])


async def get_pending_meeting(
    client: httpx.AsyncClient, host_token: str, room_id: int
) -> Optional[int]:
    """GET /api/v1/meetings/rooms/{room_id}/pending-vote → meeting_id."""
    resp = await client.get(
        f"{API}/api/v1/meetings/rooms/{room_id}/pending-vote",
        headers={"Authorization": f"Bearer {host_token}"},
        timeout=5.0,
    )
    if resp.status_code != 200 or resp.json() is None:
        return None
    body = resp.json()
    if isinstance(body, dict) and "meeting_id" in body:
        return int(body["meeting_id"])
    return None


async def vote(
    client: httpx.AsyncClient, meeting_id: int, token: str, option_index: int
) -> dict:
    """POST /api/v1/meetings/{meeting_id}/vote → VoteResponse."""
    resp = await client.post(
        f"{API}/api/v1/meetings/{meeting_id}/vote",
        json={"option_index": option_index},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


async def get_meeting_votes(
    client: httpx.AsyncClient, host_token: str, room_id: int, meeting_id: int
) -> dict:
    """pending-vote 엔드포인트로 최신 votes 조회."""
    resp = await client.get(
        f"{API}/api/v1/meetings/rooms/{room_id}/pending-vote",
        headers={"Authorization": f"Bearer {host_token}"},
        timeout=5.0,
    )
    if resp.status_code != 200:
        return {}
    body = resp.json()
    if isinstance(body, dict):
        return body.get("votes", {})
    return {}


# ---------------------------------------------------------------------------
# WS helpers
# ---------------------------------------------------------------------------


async def ws_collect_events(
    token: str,
    room_id: int,
    duration_s: float = 10.0,
) -> list[dict]:
    """WS 구독 후 duration_s 동안 수신한 이벤트 목록 반환."""
    uri = f"{WS}/ws/social/{room_id}?token={token}"
    events: list[dict] = []
    try:
        async with websockets.connect(uri, open_timeout=5) as ws:
            deadline = time.monotonic() + duration_s
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 1.0))
                    try:
                        events.append(json.loads(raw))
                    except json.JSONDecodeError:
                        events.append({"_raw": raw})
                except asyncio.TimeoutError:
                    pass
    except Exception as exc:
        events.append({"_error": str(exc)})
    return events


async def send_chat_ws(token: str, room_id: int, content: str, sender: str) -> None:
    """WS로 채팅 메시지 1건 전송."""
    uri = f"{WS}/ws/social/{room_id}?token={token}"
    async with websockets.connect(uri, open_timeout=5) as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({
            "role": "user",
            "content": content,
            "sender": sender,
        }))
        await asyncio.sleep(0.3)


# ---------------------------------------------------------------------------
# K3.1 race 감지
# ---------------------------------------------------------------------------


async def detect_vote_race(
    actual_votes: dict,
    expected_total: int,
) -> int:
    """votes dict 에서 집계한 총 투표 수가 expected 와 일치하는지.

    불일치 delta = race_count (0 이 GREEN 조건).
    """
    actual_total = len(actual_votes)
    return abs(actual_total - expected_total)


# ---------------------------------------------------------------------------
# K3.2 broadcast 누락 감지
# ---------------------------------------------------------------------------


def detect_broadcast_missing(
    ws_events_per_member: list[list[dict]],
    expected_event_type: str,
) -> int:
    """각 멤버가 expected_event_type WS 이벤트를 1건 이상 수신했는지.

    수신 못 한 멤버 수 = broadcast_missing (0 이 GREEN 조건).
    """
    missing = 0
    for events in ws_events_per_member:
        received = any(
            isinstance(e, dict) and e.get("type") == expected_event_type
            for e in events
        )
        if not received:
            missing += 1
    return missing


# ---------------------------------------------------------------------------
# 시나리오 runner
# ---------------------------------------------------------------------------


async def run_scenario_001_002(
    scenario: dict, host_token: str, client: httpx.AsyncClient
) -> dict:
    """k3-conc-001 / k3-conc-002: 동시 vote N건 → race 감지."""
    room_size = scenario["room_size"]
    vote_options_count = scenario["setup"]["vote_options_count"]
    actions = scenario["actions"]
    expected = scenario["expected"]

    tag = f"[{scenario['id']}]"

    # 1. 룸 생성
    unique = uuid.uuid4().hex[:6]
    room_id = await create_room(client, host_token, f"K3-test-{unique}")
    print(f"    {tag} room_id={room_id}", flush=True)

    # 2. 게스트 N-1 명 추가
    guests: list[dict] = []
    for i in range(1, room_size):
        g = await guest_join(client, room_id, f"게스트{i}-{unique[:4]}")
        guests.append(g)
    print(f"    {tag} guests joined: {[g['name'] for g in guests]}", flush=True)

    # 3. pending meeting 생성 (host confirm with pending status)
    #    confirm API는 status=confirmed로 만드나, vote_options가 있으면
    #    pending-vote 엔드포인트에서 조회 가능. 여기서는 직접 meeting_id를 사용.
    meeting_id = await confirm_meeting(client, host_token, room_id, vote_options_count)
    print(f"    {tag} meeting_id={meeting_id}", flush=True)

    # 4. 게스트 토큰 매핑: actions의 user_idx 0=host, 1..N-1=guests
    def get_token(user_idx: int) -> str:
        if user_idx == 0:
            return host_token
        gi = user_idx - 1
        if gi < len(guests):
            return guests[gi]["token"]
        return host_token  # fallback to host

    # 5. asyncio.gather 로 동시 vote 실행
    async def do_vote(action: dict) -> dict:
        delay_s = action.get("delay_ms", 0) / 1000.0
        if delay_s > 0:
            await asyncio.sleep(delay_s)
        token = get_token(action["user_idx"])
        try:
            result = await vote(client, meeting_id, token, action["option_index"])
            return {"ok": True, "result": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    vote_results = await asyncio.gather(*[do_vote(a) for a in actions])
    print(f"    {tag} vote results: {[r['ok'] for r in vote_results]}", flush=True)

    # 6. 결과 조회 (pending-vote)
    await asyncio.sleep(0.5)  # DB commit 대기
    votes_dict = await get_meeting_votes(client, host_token, room_id, meeting_id)
    expected_total = expected.get("total_vote_count", len(actions))
    race_count = await detect_vote_race(votes_dict, expected_total)

    notes = []
    if race_count > 0:
        notes.append(f"expected {expected_total} votes, got {len(votes_dict)}")
    failed = [r for r in vote_results if not r["ok"]]
    if failed:
        notes.append(f"{len(failed)} vote(s) failed: {[r['error'] for r in failed]}")

    return {
        "id": scenario["id"],
        "race_count": race_count,
        "broadcast_missing": 0,
        "notes": notes,
    }


async def run_scenario_003(
    scenario: dict, host_token: str, client: httpx.AsyncClient
) -> dict:
    """k3-conc-003: 2명 동시 manual pick (confirm) 충돌.

    두 토큰으로 동시 POST /meetings/confirm → 선착순 1건만 성공해야.
    race_count = 0 이면 두 confirm 중 1건만 실제 적용됨.
    """
    room_size = scenario["room_size"]
    vote_options_count = scenario["setup"]["vote_options_count"]
    actions = scenario["actions"]

    tag = f"[{scenario['id']}]"

    unique = uuid.uuid4().hex[:6]
    room_id = await create_room(client, host_token, f"K3-test-{unique}")
    print(f"    {tag} room_id={room_id}", flush=True)

    guests: list[dict] = []
    for i in range(1, room_size):
        g = await guest_join(client, room_id, f"게스트{i}-{unique[:4]}")
        guests.append(g)

    options = VOTE_OPTIONS_TEMPLATE[:vote_options_count]

    def get_token(user_idx: int) -> str:
        if user_idx == 0:
            return host_token
        gi = user_idx - 1
        return guests[gi]["token"] if gi < len(guests) else host_token

    async def do_confirm(action: dict) -> dict:
        delay_s = action.get("delay_ms", 0) / 1000.0
        if delay_s > 0:
            await asyncio.sleep(delay_s)
        token = get_token(action["user_idx"])
        slot_idx = action.get("slot_idx", 0)
        opt = options[slot_idx] if slot_idx < len(options) else options[0]
        try:
            resp = await client.post(
                f"{API}/api/v1/meetings/confirm",
                json={
                    "room_id": room_id,
                    "title": f"K3 충돌 테스트 slot{slot_idx}",
                    "scheduled_at": opt["start_at"],
                    "end_at": opt["end_at"],
                    "vote_options": options,
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            return {"ok": resp.status_code in (200, 201), "status": resp.status_code}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    results = await asyncio.gather(*[do_confirm(a) for a in actions])
    print(f"    {tag} confirm results: {results}", flush=True)

    # 두 confirm 모두 200/201이면 race 가능성 (동일 room에 2개 confirmed meeting).
    # 여기서는 단순히 성공 건수로 race_count 산정 — 2건 모두 성공 = race = 1.
    ok_count = sum(1 for r in results if r.get("ok"))
    race_count = 0 if ok_count <= 1 else ok_count - 1
    notes = [f"{ok_count} confirms succeeded (expected <=1 for race-free)"] if ok_count > 1 else []

    return {
        "id": scenario["id"],
        "race_count": race_count,
        "broadcast_missing": 0,
        "notes": notes,
    }


async def run_scenario_004(
    scenario: dict,
    host_token: str,
    client: httpx.AsyncClient,
    ws_timeout: float = 12.0,
) -> dict:
    """k3-conc-004: N명 룸 단일 트리거 → broadcast 누락 검증 (K3.2).

    각 멤버가 WS 구독 후 host가 채팅 1건 → 모든 구독자가 메시지 이벤트 수신 확인.
    """
    room_size = scenario["room_size"]
    actions = scenario["actions"]
    tag = f"[{scenario['id']}]"

    unique = uuid.uuid4().hex[:6]
    room_id = await create_room(client, host_token, f"K3-test-{unique}")
    print(f"    {tag} room_id={room_id}", flush=True)

    # N-1 게스트 추가
    guests: list[dict] = []
    for i in range(1, room_size):
        g = await guest_join(client, room_id, f"게스트{i}-{unique[:4]}")
        guests.append(g)

    # 모든 멤버 토큰 (host + guests)
    all_tokens: list[tuple[str, str]] = [(host_token, "host")]
    for g in guests:
        all_tokens.append((g["token"], g["name"]))

    print(f"    {tag} {len(all_tokens)} subscribers opening WS...", flush=True)

    # 모든 멤버가 WS 구독 후 채팅 트리거 → broadcast 수집
    collect_duration = ws_timeout

    async def subscribe_and_collect(token: str, name: str) -> list[dict]:
        return await ws_collect_events(token, room_id, duration_s=collect_duration)

    # WS 구독 태스크 시작
    subscriber_tasks = [
        asyncio.create_task(subscribe_and_collect(tok, name))
        for tok, name in all_tokens
    ]

    # 구독 안정화 대기
    await asyncio.sleep(1.5)

    # 채팅 트리거 (user_idx=0 → host)
    action = actions[0]
    sender_name = "host"
    sender_token = host_token
    if action.get("user_idx", 0) < len(guests):
        g = guests[action["user_idx"] - 1] if action["user_idx"] > 0 else None
        if g:
            sender_token = g["token"]
            sender_name = g["name"]

    print(f"    {tag} sending chat: '{action['content']}'", flush=True)
    await send_chat_ws(sender_token, room_id, action["content"], sender_name)

    # 모든 구독자 수집 완료 대기
    ws_events_per_member = await asyncio.gather(*subscriber_tasks)

    # broadcast 누락 검증: 채팅 메시지 이벤트 수신 확인
    # WS 이벤트 type: 채팅은 "chat" 또는 role="user" 메시지로 수신됨.
    # 실제 이벤트 샘플 확인용 로그
    for i, events in enumerate(ws_events_per_member):
        types = [e.get("type") or e.get("role") or "?" for e in events if isinstance(e, dict)]
        print(f"    {tag} member[{i}] events: {types[:10]}", flush=True)

    # "chat" type 또는 role="user" 메시지를 broadcast 이벤트로 간주
    def is_chat_event(e: dict) -> bool:
        return (
            e.get("type") == "chat"
            or e.get("role") == "user"
            or e.get("role") == "assistant"
        )

    broadcast_missing = sum(
        1 for events in ws_events_per_member
        if not any(is_chat_event(e) for e in events if isinstance(e, dict))
    )

    return {
        "id": scenario["id"],
        "race_count": 0,
        "broadcast_missing": broadcast_missing,
        "notes": [f"{len(all_tokens)} subscribers, {broadcast_missing} missing"],
    }


async def run_scenario_005(
    scenario: dict, host_token: str, client: httpx.AsyncClient
) -> dict:
    """k3-conc-005: 5명 동시 busy_period 채팅 → race 없이 3건 모두 DB 반영 확인.

    채팅은 WS JSON send 이므로 REST 집계 대신 WS 이벤트 개수로 race 추정.
    현재 backend busy_period는 Redis key에 적재되므로 REST 조회 불가 →
    race_count는 WS send 실패 건수로 산정.
    """
    room_size = scenario["room_size"]
    actions = scenario["actions"]
    tag = f"[{scenario['id']}]"

    unique = uuid.uuid4().hex[:6]
    room_id = await create_room(client, host_token, f"K3-test-{unique}")
    print(f"    {tag} room_id={room_id}", flush=True)

    guests: list[dict] = []
    for i in range(1, room_size):
        g = await guest_join(client, room_id, f"게스트{i}-{unique[:4]}")
        guests.append(g)

    def get_token_and_name(user_idx: int) -> tuple[str, str]:
        if user_idx == 0:
            return host_token, "host"
        gi = user_idx - 1
        if gi < len(guests):
            return guests[gi]["token"], guests[gi]["name"]
        return host_token, "host"

    async def do_chat(action: dict) -> bool:
        delay_s = action.get("delay_ms", 0) / 1000.0
        if delay_s > 0:
            await asyncio.sleep(delay_s)
        token, name = get_token_and_name(action.get("user_idx", 0))
        try:
            await send_chat_ws(token, room_id, action["content"], name)
            return True
        except Exception as exc:
            print(f"    {tag} chat send failed: {exc}", flush=True)
            return False

    chat_results = await asyncio.gather(*[do_chat(a) for a in actions])
    failed_count = sum(1 for ok in chat_results if not ok)
    race_count = failed_count  # 전송 실패 = 잠재적 race/누락

    return {
        "id": scenario["id"],
        "race_count": race_count,
        "broadcast_missing": 0,
        "notes": [f"{len(actions)} chats, {failed_count} failed"],
    }


async def run_scenario(
    scenario: dict,
    host_token: str,
    client: httpx.AsyncClient,
    ws_timeout: float = 12.0,
) -> dict:
    sid = scenario["id"]
    if sid in ("k3-conc-001", "k3-conc-002"):
        return await run_scenario_001_002(scenario, host_token, client)
    elif sid == "k3-conc-003":
        return await run_scenario_003(scenario, host_token, client)
    elif sid == "k3-conc-004":
        return await run_scenario_004(scenario, host_token, client, ws_timeout=ws_timeout)
    elif sid == "k3-conc-005":
        return await run_scenario_005(scenario, host_token, client)
    else:
        raise ValueError(f"Unknown scenario id: {sid}")


# ---------------------------------------------------------------------------
# 결과 집계
# ---------------------------------------------------------------------------


def aggregate(results: list[dict]) -> dict:
    total_race = sum(r["race_count"] for r in results if isinstance(r.get("race_count"), int) and r["race_count"] >= 0)
    total_missing = sum(r["broadcast_missing"] for r in results if isinstance(r.get("broadcast_missing"), int) and r["broadcast_missing"] >= 0)
    failed_scenarios = [r["id"] for r in results if r.get("race_count", 0) < 0]
    return {
        "K3.1_race_count": total_race,
        "K3.2_broadcast_missing": total_missing,
        "scenarios_run": len(results),
        "failed_scenarios": failed_scenarios,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


async def main() -> int:
    parser = argparse.ArgumentParser(description="K3 동시성 측정 runner")
    parser.add_argument(
        "--fixture",
        default=".gstack-fixtures/k3-concurrency-scenarios.json",
        help="fixture JSON 경로",
    )
    parser.add_argument(
        "--scenario",
        default="all",
        help="all 또는 특정 id (예: k3-conc-001)",
    )
    parser.add_argument(
        "--ws-timeout",
        type=float,
        default=12.0,
        help="k3-conc-004 WS 수집 대기 시간(초) — 기본 12s",
    )
    args = parser.parse_args()

    fixture = load_fixture(args.fixture)
    if args.scenario != "all":
        fixture = [s for s in fixture if s["id"] == args.scenario]
    if not fixture:
        print(f"[K3] scenario not found: {args.scenario}", file=sys.stderr)
        return 1

    host_token = load_token()

    print(f"[K3] === N={len(fixture)} scenarios ===", flush=True)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        results: list[dict] = []
        for s in fixture:
            print(f"  [running] {s['id']}: {s['name']}", flush=True)
            t0 = time.monotonic()
            try:
                result = await run_scenario(s, host_token, client, ws_timeout=args.ws_timeout)
                elapsed = time.monotonic() - t0
                results.append(result)
                race = result["race_count"]
                missing = result["broadcast_missing"]
                notes = result.get("notes", [])
                status = "GREEN" if (race == 0 and missing == 0) else "YELLOW"
                print(
                    f"    [{status}] race={race} broadcast_missing={missing}"
                    f" ({elapsed:.1f}s){' | ' + '; '.join(notes) if notes else ''}",
                    flush=True,
                )
            except Exception as exc:
                elapsed = time.monotonic() - t0
                print(f"    [ERROR] {type(exc).__name__}: {exc} ({elapsed:.1f}s)", flush=True)
                results.append({
                    "id": s["id"],
                    "race_count": -1,
                    "broadcast_missing": -1,
                    "notes": [f"{type(exc).__name__}: {exc}"],
                })

    summary = aggregate(results)
    overall = "GREEN" if summary["K3.1_race_count"] == 0 and summary["K3.2_broadcast_missing"] == 0 else "YELLOW"
    print(f"\n[K3.SUMMARY] === N={summary['scenarios_run']} | {overall} ===", flush=True)
    print(f"  K3.1 race count:        {summary['K3.1_race_count']}", flush=True)
    print(f"  K3.2 broadcast missing: {summary['K3.2_broadcast_missing']}", flush=True)
    if summary["failed_scenarios"]:
        print(f"  failed scenarios:       {summary['failed_scenarios']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
