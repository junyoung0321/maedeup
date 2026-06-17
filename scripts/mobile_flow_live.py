"""앱뷰 라이브 — 보이는 CDP 브라우저로 모바일 풀 흐름.
호스트가 /m/chat/schedule에서 발화(실제 keepalive) → 게스트 ACT2 → AI 추천 카드.
창은 /m/chat/ai에 둔 채 종료(사용자가 직접 봄)."""
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


async def send_social(rid, token, name, content):
    async with websockets.connect(f"{WS}/ws/social/{rid}?token={token}") as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({"role": "user", "content": content, "sender": name}))
        await asyncio.sleep(0.6)


async def main():
    room = http("POST", "/api/v1/rooms/", TOKEN, {"name": "앱뷰라이브", "description": "x", "category": "모임"})
    rid = room["id"]
    guests = {n: http("POST", f"/api/v1/rooms/{rid}/guest-join", None, {"display_name": n})["token"] for n in ACT2}
    http("POST", f"/api/v1/rooms/{rid}/preferences", TOKEN,
         {"preferred_times": ["평일 저녁"], "preferred_location": "강남", "preferred_foods": [], "disliked_foods": [], "note": None})
    print(f"ROOM_ID={rid}")

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto("http://localhost:3000/")
        await page.evaluate(f'localStorage.setItem("auth_token", {json.dumps(TOKEN)})')
        await page.goto(f"http://localhost:3000/m/chat/schedule?roomId={rid}")
        await page.wait_for_timeout(3000)  # keepalive 연결
        print("호스트 /m/chat/schedule 진입 (keepalive 연결)")

        # 호스트가 입력창에 발화 (실제 UI 상호작용)
        try:
            inp = page.get_by_placeholder("메세지를 입력하세요")
            await inp.fill(TRIGGER)
            await inp.press("Enter")
            print(f"[호스트 UI 입력] {TRIGGER}")
        except Exception as e:
            print(f"입력창 못 찾음, WS로 대체: {type(e).__name__}")
            await send_social(rid, TOKEN, "김창윤", TRIGGER)
        await page.wait_for_timeout(1500)

        # 게스트 ACT2 (WS)
        for n, msg in ACT2.items():
            await send_social(rid, guests[n], n, msg)
            print(f"[{n}] {msg[:24]}…")
            await page.wait_for_timeout(1200)

        # AI 트리거 + 카드 대기, 채팅 화면 스냅
        await page.wait_for_timeout(20000)
        await page.screenshot(path="qa_artifacts/mobile_flow_chat.png", full_page=True)
        print("채팅 화면 스냅: qa_artifacts/mobile_flow_chat.png")

        # vote_card 확인
        try:
            body = http("GET", f"/api/v1/meetings/rooms/{rid}/pending-vote", TOKEN)
            mid = body.get("meeting_id") if isinstance(body, dict) else None
            print(f"vote_card meeting_id={mid}")
        except Exception:
            print("pending-vote 조회 실패")

        # AI 탭으로 이동 → 추천 카드
        await page.goto(f"http://localhost:3000/m/chat/ai?roomId={rid}")
        await page.wait_for_timeout(4000)
        b = await page.inner_text("body")
        print(f"AI 탭 추천카드 보임: {('전원 가능' in b) or ('모임 날짜' in b)}")
        print(f"AI reflect-back 보임: {('어려운 날' in b) or ('이해했어요' in b)}")
        await page.screenshot(path="qa_artifacts/mobile_flow_ai.png", full_page=True)
        print("AI 화면 스냅: qa_artifacts/mobile_flow_ai.png")
        print("창은 /m/chat/ai 에 둠 (직접 확인용)")


asyncio.run(main())
