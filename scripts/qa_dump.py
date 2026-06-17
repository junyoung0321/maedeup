import asyncio, json, sys
from playwright.async_api import async_playwright
CDP='http://localhost:9222'
TOKEN=open('.gstack-demo-token').read().strip()
RID=int(sys.argv[1])
async def main():
    async with async_playwright() as p:
        b=await p.chromium.connect_over_cdp(CDP)
        page=await b.contexts[0].new_page()
        await page.set_viewport_size({'width':390,'height':844})
        await page.goto('http://localhost:3000/m/login')
        await page.evaluate('localStorage.setItem("auth_token", '+json.dumps(TOKEN)+')')
        await page.goto('http://localhost:3000/m/chat/ai?roomId='+str(RID)); await page.wait_for_timeout(6500)
        tcbtn=page.get_by_role('button', name='시간대 변경')
        for i in range(await tcbtn.count()):
            if await tcbtn.nth(i).is_visible() and not await tcbtn.nth(i).is_disabled():
                await tcbtn.nth(i).click(); break
        await page.wait_for_timeout(4000)
        # timebar element existence (any visibility)
        tb=await page.eval_on_selector_all('[id^=timebar-]', 'els=>els.map(e=>({id:e.id, vis:e.offsetParent!==null}))')
        print('timebar elements:', json.dumps(tb, ensure_ascii=False))
        # count TimeBarSelector text markers (any)
        for v in ['가용성 조회 중','멤버 일정을 확인','가용성 조회 실패','내 일정','끝 시간 선택','시작 시간 선택']:
            c=await page.get_by_text(v, exact=False).count()
            print('  text count', v, '=', c)
        # dump the InfoPane subtree: find element containing '캘린더' header then its parent's text
        # capture all calendar-tab pane text (visible)
        info=await page.eval_on_selector_all('div', 'els=>els.filter(e=>e.textContent.includes("AI 추천:") && e.children.length<15).slice(0,3).map(e=>e.textContent.slice(0,200))')
        print('AI추천 blocks:', json.dumps(info, ensure_ascii=False)[:500])
        # check free-slots network
        await page.close()
asyncio.run(main())