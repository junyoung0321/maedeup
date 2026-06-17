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
        await page.set_viewport_size({'width':390,'height':844})
        await page.goto('http://localhost:3000/m/login')
        await page.evaluate('localStorage.setItem("auth_token", '+json.dumps(TOKEN)+')')
        await page.goto('http://localhost:3000/m/chat/ai?roomId='+str(RID))
        await page.wait_for_timeout(6000)
        # click 시간대 변경 (slot auto-selected)
        tcbtn=page.get_by_role('button', name='시간대 변경')
        for i in range(await tcbtn.count()):
            if await tcbtn.nth(i).is_visible() and not await tcbtn.nth(i).is_disabled():
                await tcbtn.nth(i).click(); print('clicked 시간대 변경'); break
        await page.wait_for_timeout(4000)
        # phase 추론: idle 안내문 / dateConfirmed TimeBar 텍스트
        checks={
          'idle_안내(파란 테두리)': '파란 테두리 날짜를 클릭',
          'TimeBar_가용성조회중': '가용성 조회 중',
          'TimeBar_멤버일정': '멤버 일정을 확인',
          'TimeBar_내일정row': '내 일정',
          'TimeBar_다른분들': '다른 분들',
          'TimeBar_전원row끝시간': '끝 시간 선택',
          'CalendarPane_멤버현황': '멤버 현황',
          'TimeBar_이시간으로확정': '이 시간으로 확정',
        }
        for k,v in checks.items():
            loc=page.get_by_text(v, exact=False)
            cnt=await loc.count()
            vis=False
            for i in range(min(cnt,5)):
                if await loc.nth(i).is_visible(): vis=True; break
            print(f'  {k}: count={cnt} visible={vis}')
        # grid elements with ids
        ids=await page.eval_on_selector_all('[role=grid]', 'els => els.map(e=>({id:e.id, vis: e.offsetParent!==null}))')
        print('grids:', json.dumps(ids, ensure_ascii=False))
        # TimeBarSelector container? search for slotToTime markers like '끝 시간' or hour labels in visible calendar pane
        await page.screenshot(path=SHOT+'/diag2_phase.png', full_page=True)
        await page.close()
asyncio.run(main())