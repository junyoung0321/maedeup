"""다운스트림 진단 — ACT2 재현 후 멤버별 unavailability(Redis)에 06-10이 반영됐는지."""
import asyncio
import json
import urllib.request

import websockets

API = "http://localhost:8000"; WS = "ws://localhost:8000"
TOKEN = open(".gstack-demo-token").read().strip()
ACT2 = {
    "수현": "내일은 동아리 MT라 안 되고, 이번주 수·목·금도 시험 기간이라 다 안 돼. 다음주 월·화도 발표 준비 때문에 일정 잡혀있어",
    "민수": "다음주 수요일은 본가 내려가야 해서 패스",
    "예린": "다음주 화요일은 좀 쉬고 싶다… 다음주 토요일 빼고 다 바빠",
}


def http(m, p, t=None, b=None):
    d = json.dumps(b).encode() if b is not None else None
    h = {"Content-Type": "application/json"}
    if t:
        h["Authorization"] = f"Bearer {t}"
    return json.loads(urllib.request.urlopen(urllib.request.Request(f"{API}{p}", data=d, headers=h, method=m), timeout=10).read())


async def keepalive(rid, stop):
    async with websockets.connect(f"{WS}/ws/agent/{rid}?token={TOKEN}") as ws:
        while not stop.is_set():
            try:
                await asyncio.wait_for(ws.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            except Exception:
                break


async def send_social(rid, token, name, content):
    async with websockets.connect(f"{WS}/ws/social/{rid}?token={token}") as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({"role": "user", "content": content, "sender": name}))
        await asyncio.sleep(0.6)


async def main():
    room = http("POST", "/api/v1/rooms/", TOKEN, {"name": "unavail진단", "description": "x", "category": "모임"})
    rid = room["id"]
    id2name = {1: "김창윤(호스트)"}
    guests = {}
    for n in ACT2:
        g = http("POST", f"/api/v1/rooms/{rid}/guest-join", None, {"display_name": n})
        guests[n] = g["token"]
        id2name[g["user_id"]] = n
    http("POST", f"/api/v1/rooms/{rid}/preferences", TOKEN,
         {"preferred_times": ["평일 저녁"], "preferred_location": "강남", "preferred_foods": [], "disliked_foods": [], "note": None})
    stop = asyncio.Event()
    ka = asyncio.create_task(keepalive(rid, stop))
    await asyncio.sleep(1.0)
    await send_social(rid, TOKEN, "김창윤", "다들 시험 끝나고 한번 보자!")
    await asyncio.sleep(1.0)
    for n, msg in ACT2.items():
        await send_social(rid, guests[n], n, msg)
        await asyncio.sleep(1.2)
    await asyncio.sleep(18)  # 파이프라인 + CHAT_UNAVAIL_SYNC 완료 대기
    stop.set()
    try:
        await asyncio.wait_for(ka, timeout=2)
    except Exception:
        pass
    print(f"ROOM_ID={rid}")
    print("ID2NAME=" + json.dumps(id2name, ensure_ascii=False))


asyncio.run(main())
