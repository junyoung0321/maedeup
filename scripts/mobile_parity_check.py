"""모바일 parity 확인 — room+vote_card 생성 후 CDP로 /m/chat/ai 스크린샷.
데스크탑 AiAssistantPane이 390px 모바일에 어떻게 렌더되는지 시각 확인."""
import asyncio
import json
import urllib.request

import websockets
from playwright.async_api import async_playwright

API = "http://localhost:8000"
WS = "ws://localhost:8000"
CDP = "http://localhost:9222"
TOKEN = open(".gstack-demo-token").read().strip()
TRIGGER = "다들 시험 끝나고 한번 보자!"
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
    room = http("POST", "/api/v1/rooms/", TOKEN, {"name": "parity검증", "description": "x", "category": "모임"})
    rid = room["id"]
    guests = {n: http("POST", f"/api/v1/rooms/{rid}/guest-join", None, {"display_name": n})["token"] for n in ACT2}
    http("POST", f"/api/v1/rooms/{rid}/preferences", TOKEN,
         {"preferred_times": ["평일 저녁"], "preferred_location": "강남", "preferred_foods": [], "disliked_foods": [], "note": None})
    print(f"ROOM_ID={rid}")
    stop = asyncio.Event()
    ka = asyncio.create_task(keepalive(rid, stop))
    await asyncio.sleep(1.0)
    await send_social(rid, TOKEN, "김창윤", TRIGGER)
    await asyncio.sleep(1.0)
    for n, msg in ACT2.items():
        await send_social(rid, guests[n], n, msg)
        await asyncio.sleep(1.2)
    # vote_card 대기
    mid = None
    for _ in range(30):
        await asyncio.sleep(2)
        try:
            b = http("GET", f"/api/v1/meetings/rooms/{rid}/pending-vote", TOKEN)
            if isinstance(b, dict) and b.get("meeting_id"):
                mid = b["meeting_id"]
                break
        except Exception:
            pass
    print(f"vote_card meeting_id={mid}")
    stop.set()
    try:
        await asyncio.wait_for(ka, timeout=2)
    except Exception:
        pass

    # CDP 스크린샷
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto("http://localhost:3000/")
        await page.evaluate(f'localStorage.setItem("auth_token", {json.dumps(TOKEN)})')
        await page.goto(f"http://localhost:3000/m/chat/ai?roomId={rid}")
        await page.wait_for_timeout(5000)
        body = await page.inner_text("body")
        print("탭 채팅방/캘린더/AI 보임:", all(t in body for t in ["채팅방", "캘린더", "AI"]))
        print("추천 카드/일정 텍스트 보임:", ("추천" in body) or ("전원 가능" in body) or ("일정" in body))
        await page.screenshot(path="qa_artifacts/parity_ai_top.png")
        # 메시지 영역 끝으로 스크롤해서 카드 확인
        try:
            await page.evaluate("document.querySelectorAll('[class*=overflow]')[0]?.scrollTo(0, 99999)")
        except Exception:
            pass
        await page.wait_for_timeout(1000)
        await page.screenshot(path="qa_artifacts/parity_ai_full.png", full_page=True)
        print("스크린샷: qa_artifacts/parity_ai_top.png, parity_ai_full.png")
        print("창은 /m/chat/ai 유지")


asyncio.run(main())
