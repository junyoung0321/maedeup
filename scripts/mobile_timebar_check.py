"""통합 페이지 TimeBar 검증 — vote_card 생성 → AI 탭에서 '시간대 변경' 클릭 →
캘린더 탭에서 TimeBar(InfoPane) 노출 확인."""
import asyncio
import json
import urllib.request

import websockets
from playwright.async_api import async_playwright

API = "http://localhost:8000"; WS = "ws://localhost:8000"; CDP = "http://localhost:9222"
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
    room = http("POST", "/api/v1/rooms/", TOKEN, {"name": "TimeBar검증", "description": "x", "category": "모임"})
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
    mid = None
    for _ in range(30):
        await asyncio.sleep(2)
        try:
            b = http("GET", f"/api/v1/meetings/rooms/{rid}/pending-vote", TOKEN)
            if isinstance(b, dict) and b.get("meeting_id"):
                mid = b["meeting_id"]; break
        except Exception:
            pass
    print(f"vote_card meeting_id={mid}")
    stop.set()
    try:
        await asyncio.wait_for(ka, timeout=2)
    except Exception:
        pass

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto("http://localhost:3000/")
        await page.evaluate(f'localStorage.setItem("auth_token", {json.dumps(TOKEN)})')
        await page.goto(f"http://localhost:3000/m/chat/ai?roomId={rid}")
        await page.wait_for_timeout(5000)
        await page.screenshot(path="qa_artifacts/timebar_1_ai.png")

        # 카드 슬롯 클릭 후 '시간대 변경' 클릭
        clicked = False
        for label in ["시간대 변경", "시간 변경", "시간대"]:
            try:
                el = page.get_by_text(label, exact=False).first
                if await el.count() > 0:
                    # 슬롯 먼저 클릭(선택 활성화) 시도
                    try:
                        await page.get_by_text("전원 가능", exact=False).first.click(timeout=2000)
                        await page.wait_for_timeout(800)
                    except Exception:
                        pass
                    await el.click(timeout=3000)
                    clicked = True
                    print(f"'{label}' 클릭")
                    break
            except Exception:
                pass
        if not clicked:
            print("'시간대 변경' 버튼 못 찾음 (카드 상태 확인 필요)")
        await page.wait_for_timeout(2500)

        # 캘린더 탭으로 전환
        try:
            await page.get_by_text("캘린더", exact=True).first.click(timeout=3000)
            await page.wait_for_timeout(2500)
        except Exception as e:
            print(f"캘린더 탭 클릭 실패: {type(e).__name__}")
        body = await page.inner_text("body")
        has_timebar = ("시간" in body and ("오전" in body or "오후" in body or "전원" in body)) or ("이 시간으로 확정" in body)
        print(f"캘린더 탭 TimeBar/시간 UI 보임: {has_timebar}")
        await page.screenshot(path="qa_artifacts/timebar_2_calendar.png", full_page=True)
        print("스크린샷: timebar_1_ai.png, timebar_2_calendar.png")


asyncio.run(main())
