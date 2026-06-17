"""모바일 라이브 e2e 헬퍼 — 브라우저가 keepalive 구독자 역할을 하는 시나리오용.

서브커맨드:
  setup            방+게스트3+선호(강남) 생성 → ROOM_ID 출력
  send  <room_id>  게스트 3명이 ACT2 거절 메시지 전송 (agent WS 없음 — 브라우저가 구독자)
  check <room_id>  pending-vote 폴링 (vote_card 발현 확인)
"""
import asyncio
import json
import sys
import time
import urllib.request

import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000"
TOKEN = open(".gstack-demo-token").read().strip()

TRIGGER = "다들 시험 끝나고 한번 보자!"
ACT2 = {
    "수현": "내일은 동아리 MT라 안 되고, 이번주 수·목·금도 시험 기간이라 다 안 돼. 다음주 월·화도 발표 준비 때문에 일정 잡혀있어",
    "민수": "다음주 수요일은 본가 내려가야 해서 패스",
    "예린": "다음주 화요일은 좀 쉬고 싶다… 다음주 토요일 빼고 다 바빠",
}


def http(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def setup():
    room = http("POST", "/api/v1/rooms/", token=TOKEN,
                body={"name": "모바일라이브", "description": "e2e", "category": "모임"})
    rid = room["id"]
    guests = {}
    for name in ACT2:
        g = http("POST", f"/api/v1/rooms/{rid}/guest-join", body={"display_name": name})
        guests[name] = g["token"]
    http("POST", f"/api/v1/rooms/{rid}/preferences", token=TOKEN,
         body={"preferred_times": ["평일 저녁"], "preferred_location": "강남",
               "preferred_foods": [], "disliked_foods": [], "note": None})
    # 게스트 토큰을 파일에 저장 (send 단계에서 재사용)
    with open(f".mobile_live_{rid}.json", "w") as f:
        json.dump(guests, f)
    print(f"ROOM_ID={rid}")


async def _send_ws(rid, token, name, content):
    uri = f"{WS}/ws/social/{rid}?token={token}"
    async with websockets.connect(uri) as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({"role": "user", "content": content, "sender": name}))
        await asyncio.sleep(0.6)


async def send(rid):
    guests = json.load(open(f".mobile_live_{rid}.json"))
    await _send_ws(rid, TOKEN, "김창윤", TRIGGER)
    await asyncio.sleep(1.0)
    for name, msg in ACT2.items():
        await _send_ws(rid, guests[name], name, msg)
        print(f"[{name}] 전송")
        await asyncio.sleep(1.2)


def check(rid):
    for _ in range(30):
        time.sleep(2)
        try:
            body = http("GET", f"/api/v1/meetings/rooms/{rid}/pending-vote", token=TOKEN)
            if isinstance(body, dict) and body.get("meeting_id"):
                opts = body.get("time_options") or []
                labels = [o.get("label") for o in opts]
                print(f"VOTE_CARD meeting_id={body['meeting_id']} options={labels}")
                return
        except Exception:
            pass
    print("NO_VOTE_CARD")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "setup":
        setup()
    elif cmd == "send":
        asyncio.run(send(sys.argv[2]))
    elif cmd == "check":
        check(sys.argv[2])
