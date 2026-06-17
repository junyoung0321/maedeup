"""모바일 e2e 검증: 게스트 3명이 ACT2 메시지를 보내 추천 카드가 만들어지는지 확인.

데모(.gstack-demo.py)와 동일한 멀티유저 경로:
  - 호스트가 방 생성 + 트리거 발화
  - 게스트 3명(수현/민수/예린)이 거절 메시지 전송 (social WS)
  - 백엔드가 교착 감지 → 파이프라인 → vote_card 생성
검증: pending-vote 조회로 vote_card 발현 + 옵션(추천일) 확인.
"""
import asyncio
import json
import sys
import time
import urllib.request

import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000"

TRIGGER = "다들 시험 끝나고 한번 보자!"
ACT2 = {
    "수현": "내일은 동아리 MT라 안 되고, 이번주 수·목·금도 시험 기간이라 다 안 돼. 다음주 월·화도 발표 준비 때문에 일정 잡혀있어",
    "민수": "다음주 수요일은 본가 내려가야 해서 패스",
    "예린": "다음주 화요일은 좀 쉬고 싶다… 다음주 토요일 빼고 다 바빠",
}


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def http(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


async def send_ws(room_id, token, name, content):
    uri = f"{WS}/ws/social/{room_id}?token={token}"
    async with websockets.connect(uri) as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({"role": "user", "content": content, "sender": name}))
        await asyncio.sleep(0.6)


async def agent_keepalive(room_id, token, stop_evt):
    """데스크탑처럼 agent WS를 연결 유지 → 교착 트리거 구독자 역할."""
    uri = f"{WS}/ws/agent/{room_id}?token={token}"
    async with websockets.connect(uri) as ws:
        log("agent WS 연결 유지 시작 (구독자 역할)")
        while not stop_evt.is_set():
            try:
                m = await asyncio.wait_for(ws.recv(), timeout=1.0)
                t = json.loads(m).get("type", "?") if m.startswith("{") else "?"
                log(f"  [agent WS 수신] type={t}")
            except asyncio.TimeoutError:
                pass
            except Exception:
                break


async def main():
    host_token = open(".gstack-demo-token").read().strip()

    # 1. 방 생성
    room = http("POST", "/api/v1/rooms/", token=host_token,
                body={"name": "모바일검증", "description": "e2e", "category": "모임"})
    room_id = room["id"]
    log(f"방 생성: room={room_id}")

    # 2. 게스트 3명 조인
    guests = {}
    for name in ACT2:
        g = http("POST", f"/api/v1/rooms/{room_id}/guest-join", body={"display_name": name})
        guests[name] = g
        log(f"게스트 조인: {name} (user_id={g['user_id']})")

    # 2.3 호스트 선호 설정 (데모 ACT1 재현: 강남 + 평일 저녁) → has_place=true
    http("POST", f"/api/v1/rooms/{room_id}/preferences", token=host_token,
         body={"preferred_times": ["평일 저녁"], "preferred_location": "강남",
               "preferred_foods": [], "disliked_foods": [], "note": None})
    log("호스트 선호 설정: 강남 / 평일 저녁")

    # 2.5 agent WS 연결 유지 (데스크탑 패턴 재현)
    stop_evt = asyncio.Event()
    ka_task = asyncio.create_task(agent_keepalive(room_id, host_token, stop_evt))
    await asyncio.sleep(1.0)

    # 3. 호스트 트리거 발화
    log(f"[호스트] {TRIGGER}")
    await send_ws(room_id, host_token, "김창윤", TRIGGER)
    await asyncio.sleep(1.0)

    # 4. 게스트 거절 메시지
    for name, msg in ACT2.items():
        log(f"[{name}] {msg[:30]}…")
        await send_ws(room_id, guests[name]["token"], name, msg)
        await asyncio.sleep(1.2)

    # 5. vote_card 폴링 (최대 60s)
    log("vote_card 발현 대기…")
    meeting_id = None
    for _ in range(30):
        await asyncio.sleep(2)
        try:
            body = http("GET", f"/api/v1/meetings/rooms/{room_id}/pending-vote", token=host_token)
            if isinstance(body, dict) and body.get("meeting_id"):
                meeting_id = body["meeting_id"]
                log(f"✅ vote_card 발현! meeting_id={meeting_id}")
                opts = body.get("vote_options") or body.get("options") or []
                for o in opts:
                    label = o.get("label") if isinstance(o, dict) else o
                    log(f"   옵션: {label}")
                print("\nPENDING_VOTE_FULL:")
                print(json.dumps(body, ensure_ascii=False, indent=2)[:2000])
                break
        except Exception as e:
            pass
    if not meeting_id:
        log("❌ vote_card 미발현 (60s)")

    stop_evt.set()
    try:
        await asyncio.wait_for(ka_task, timeout=2)
    except Exception:
        pass
    print(f"\nROOM_ID={room_id}")
    print(f"MEETING_ID={meeting_id}")


asyncio.run(main())
