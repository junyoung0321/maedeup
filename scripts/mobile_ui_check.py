"""앱뷰 UI 확인 — CDP 데모 브라우저(9222)로 /m/chat/ai 열어 MobileVoteCard +
isMe 수정(게스트 공유입력 화자명/좌측) 확인. 게스트 public agent 메시지 1개 주입."""
import asyncio
import json
import sys
import urllib.request

import websockets
from playwright.async_api import async_playwright

API = "http://localhost:8000"
WS = "ws://localhost:8000"
CDP = "http://localhost:9222"
RID = sys.argv[1]
TOKEN = open(".gstack-demo-token").read().strip()


def http(m, p, t=None, b=None):
    d = json.dumps(b).encode() if b is not None else None
    h = {"Content-Type": "application/json"}
    if t:
        h["Authorization"] = f"Bearer {t}"
    return json.loads(urllib.request.urlopen(urllib.request.Request(f"{API}{p}", data=d, headers=h, method=m), timeout=10).read())


async def guest_public_msg():
    g = http("POST", f"/api/v1/rooms/{RID}/guest-join", None, {"display_name": "게스트C"})
    async with websockets.connect(f"{WS}/ws/agent/{RID}?token={g['token']}") as ws:
        await asyncio.sleep(0.3)
        await ws.send(json.dumps({"role": "user", "content": "나는 매운거 좋아!", "sender": "게스트C", "visibility": "public"}))
        await asyncio.sleep(0.8)
    print("게스트C public agent 메시지 전송")


async def main():
    await guest_public_msg()
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto("http://localhost:3000/")
        await page.evaluate(f'localStorage.setItem("auth_token", {json.dumps(TOKEN)})')
        await page.goto(f"http://localhost:3000/m/chat/ai?roomId={RID}")
        await page.wait_for_timeout(4000)
        body = await page.inner_text("body")
        # 검증 신호
        has_card = ("전원 가능" in body) or ("모임 날짜" in body) or ("추천" in body)
        has_guest = "게스트C" in body
        has_guest_msg = "매운거 좋아" in body
        print(f"MobileVoteCard/추천 텍스트 보임: {has_card}")
        print(f"게스트C 화자명 보임(isMe 수정): {has_guest}")
        print(f"게스트C 입력 내용 보임: {has_guest_msg}")
        await page.screenshot(path="qa_artifacts/mobile_ai_branch.png", full_page=True)
        print("스크린샷: qa_artifacts/mobile_ai_branch.png")
        await page.close()


asyncio.run(main())
