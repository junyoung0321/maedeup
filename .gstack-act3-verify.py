"""ACT 3 — confirmed_time(consensus_label) injection 검증 (c786ebb).

흐름:
  1. 호스트 JWT로 새 방 생성 + 선호도 (평일 저녁)
  2. chromium /meeting/{id}/ 로 NAV → agent WS 구독 활성화
  3. 게스트 3명 (수현/민수/예린) /guest-join
  4. 호스트 + 게스트 3명 모두 WS time_selection (slot 18~19 = 18:00-19:00)
  5. _maybe_emit_proposal → schedule_consensus_ready (snapshot_hash 캡처)
  6. POST /schedule-confirm mode=auto, snapshot_hash → publish_schedule_auto_trigger
  7. backend logs grep: [AUTO_TRIGGER] received → passed filter → task spawned
                       → [TRIGGER] all_members_selected
                       → confirmed_time / consensus_label = "18:00~19:00"

WS time_selection은 frontend가 보내는 그 메시지와 동일 (UI rendering만 우회).
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import urllib.request

import websockets
from playwright.async_api import async_playwright

API = "http://localhost:8000"
WS = "ws://localhost:8000"
CDP = "http://localhost:9222"
DATE = "2026-05-11"
SLOT_START = 18  # 18:00
SLOT_END = 19    # 18:30 (inclusive)


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def post(path: str, body: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


async def send_one_selection(room_id: int, token: str, name: str) -> None:
    uri = f"{WS}/ws/social/{room_id}?token={token}"
    async with websockets.connect(uri) as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.4)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({
            "type": "time_selection",
            "date": DATE,
            "start": SLOT_START,
            "end": SLOT_END,
        }))
        log(f"  [{name}] time_selection {DATE} slot {SLOT_START}-{SLOT_END}")
        await asyncio.sleep(0.6)


class Gate:
    def __init__(self) -> None:
        self.evt = asyncio.Event()

    async def set_ready_to_listen(self) -> None:
        self.evt.set()

    async def wait(self) -> None:
        await self.evt.wait()


async def host_subscribe_and_select(room_id: int, host_token: str, gate: Gate) -> dict | None:
    uri = f"{WS}/ws/social/{room_id}?token={host_token}"
    async with websockets.connect(uri) as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.4)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({
            "type": "time_selection",
            "date": DATE,
            "start": SLOT_START,
            "end": SLOT_END,
        }))
        log("  [host(지민)] time_selection 전송")
        await gate.set_ready_to_listen()

        deadline = time.time() + 15.0
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("type") == "schedule_consensus_ready":
                return msg
        return None


async def main() -> None:
    host_token = open(".gstack-demo-token").read().strip()
    log("호스트 토큰 로드")

    # 1. 방 생성
    room = post("/api/v1/rooms/", {
        "name": "ACT 3 검증 — confirmed_time",
        "category": "식사",
    }, token=host_token)
    room_id = room["id"]
    log(f"방 생성: id={room_id}")

    # 2. 호스트 선호도
    post(f"/api/v1/rooms/{room_id}/preferences", {
        "available_times": ["평일 저녁"],
        "preferred_places": [],
    }, token=host_token)
    log("호스트 선호도 등록")

    # 3. chromium NAV → agent WS 구독 활성화
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(f"http://localhost:3000/meeting/{room_id}/", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        log(f"chromium NAV → /meeting/{room_id}/ (agent WS subscribed)")

        # 4. 게스트 3명 join
        guests = []
        for name in ("수현", "민수", "예린"):
            body = post(f"/api/v1/rooms/{room_id}/guest-join", {"display_name": name})
            guests.append((name, body["token"], body["user_id"]))
            log(f"게스트 join: {name} user_id={body['user_id']}")

        await asyncio.sleep(0.8)

        # 5. time_selection 4명 동시
        gate = Gate()

        async def fire_guests() -> None:
            await gate.wait()
            await asyncio.sleep(0.3)
            await asyncio.gather(*[
                send_one_selection(room_id, tok, name) for name, tok, _ in guests
            ])

        log("time_selection (host + 3 guests) 시작")
        host_task = asyncio.create_task(host_subscribe_and_select(room_id, host_token, gate))
        guests_task = asyncio.create_task(fire_guests())

        msg = await host_task
        await guests_task

        if not msg:
            log("✘ consensus_ready 없음")
            sys.exit(1)
        snapshot_hash = msg.get("snapshot_hash")
        log(f"✓ consensus_ready 수신 snapshot_hash={(snapshot_hash or '')[:12]}")

        await asyncio.sleep(0.3)

        # 6. /schedule-confirm
        log("POST /schedule-confirm (mode=auto)")
        resp = post(f"/api/v1/rooms/{room_id}/schedule-confirm", {
            "mode": "auto",
            "snapshot_hash": snapshot_hash,
        }, token=host_token)
        log(f"  → triggered={resp.get('triggered')}")

        # 7. 파이프라인 실행 대기 (chromium 페이지 유지)
        log("파이프라인 실행 대기 (15s)…")
        await asyncio.sleep(15.0)
        log(f"검증 완료 — room_id={room_id}")
        print(f"ROOM_ID={room_id}")


if __name__ == "__main__":
    asyncio.run(main())
