import asyncio, json, sys
from playwright.async_api import async_playwright
CDP = "http://localhost:9222"
TOKEN = open(".gstack-demo-token").read().strip()
RID = int(sys.argv[1])
SHOT = "C:/Users/cyun0/git/maedeup/.qa-mobile/natural"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        page = await b.contexts[0].new_page()
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto("http://localhost:3000/m/login")
        await page.evaluate('localStorage.setItem("auth_token", ' + json.dumps(TOKEN) + ')')
        await page.goto("http://localhost:3000/m/chat/ai?roomId=" + str(RID))
        await page.wait_for_timeout(6000)

        # AI 탭에서 추천 슬롯(첫 번째, 6/3) 클릭 — 카드의 슬롯 박스 클릭
        # '6월 3일' 슬롯 카드 클릭 (추천 배지 있는 박스)
        slot = page.get_by_text("6월 3일", exact=False).first
        if await slot.count() > 0:
            await slot.click()
            print("clicked 6월 3일 slot")
        await page.wait_for_timeout(600)
        # selectedSlotId 확인용: '시간대 변경' 버튼 enabled 인지
        tc = page.get_by_text("시간대 변경", exact=True).first
        cnt = await tc.count()
        print("시간대변경 버튼 count=", cnt)
        if cnt > 0:
            disabled = await tc.evaluate("el => { let b = el.closest('button'); return b ? b.disabled : 'no-button'; }")
            print("시간대변경 disabled=", disabled)
            await tc.click()
            print("clicked 시간대 변경")
        await page.wait_for_timeout(4000)

        # 현재 active 탭
        tabs = await page.evaluate("""() => {
            const els = [...document.querySelectorAll('div')].filter(d => ['채팅방','캘린더','AI'].includes(d.textContent.trim()) && d.textContent.trim().length<=3);
            return els.map(e => ({t: e.textContent.trim(), color: getComputedStyle(e).color, weight: getComputedStyle(e).fontWeight}));
        }""")
        print("TABS:", json.dumps(tabs, ensure_ascii=False))

        # TimeBar grid 존재?
        grid = await page.query_selector('[role="grid"]')
        print("grid present:", grid is not None, "id=", (await grid.get_attribute('id')) if grid else None)

        # CalendarPane '멤버 현황' present?
        body = await page.inner_text("body")
        for kw in ["멤버 현황", "멤버 일정", "가용성 조회", "내 일정", "다른 분들", "AI 추천 날짜", "끝 시간 선택", "전원", "이 시간으로 확정", "불가능 날짜"]:
            if kw in body:
                print("  body has:", kw)
        await page.screenshot(path=SHOT + "/diag_after_timechange.png", full_page=True)
        print("body snippet:", body[:600].replace(chr(10), " | "))
        await page.close()

asyncio.run(main())
