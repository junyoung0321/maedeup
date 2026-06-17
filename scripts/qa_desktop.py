import asyncio, json, sys
from playwright.async_api import async_playwright
CDP='http://localhost:9222'
TOKEN=open('.gstack-demo-token').read().strip()
RID=int(sys.argv[1])
SHOT='C:/Users/cyun0/git/maedeup/.qa-mobile/natural'
async def main():
    async with async_playwright() as p:
        b=await p.chromium.connect_over_cdp(CDP)
        page=await b.contexts[0].new_page()
        await page.set_viewport_size({'width':1440,'height':900})
        await page.goto('http://localhost:3000/m/login')
        await page.evaluate('localStorage.setItem("auth_token", '+json.dumps(TOKEN)+')')
        await page.goto('http://localhost:3000/meeting/'+str(RID))
        await page.wait_for_timeout(7000)
        await page.screenshot(path=SHOT+'/desktop_01_entry.png', full_page=False)
        # 시간대 변경 (slot auto-selected)
        tcbtn=page.get_by_role('button', name='시간대 변경')
        done=False
        for i in range(await tcbtn.count()):
            if await tcbtn.nth(i).is_visible() and not await tcbtn.nth(i).is_disabled():
                await tcbtn.nth(i).click(); done=True; print('clicked 시간대 변경'); break
        print('clicked?', done)
        await page.wait_for_timeout(4000)
        checks={
          'idle안내': '파란 테두리 날짜를 클릭',
          'TimeBar가용성조회중': '가용성 조회 중',
          'TimeBar멤버일정확인': '멤버 일정을 확인',
          'TimeBar내일정': '내 일정',
          'TimeBar끝시간선택': '끝 시간 선택',
          'CalendarPane멤버현황': '멤버 현황',
          'TimeBar이시간으로확정': '이 시간으로 확정',
        }
        for k,v in checks.items():
            loc=page.get_by_text(v, exact=False)
            cnt=await loc.count(); vis=False
            for i in range(min(cnt,6)):
                if await loc.nth(i).is_visible(): vis=True; break
            print(f'  {k}: count={cnt} visible={vis}')
        ids=await page.eval_on_selector_all('[role=grid]', 'els => els.map(e=>({id:e.id, vis: e.offsetParent!==null}))')
        print('grids:', json.dumps(ids, ensure_ascii=False))
        await page.screenshot(path=SHOT+'/desktop_02_after_timechange.png', full_page=False)
        await page.close()
asyncio.run(main())