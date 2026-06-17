import asyncio, json, sys
from playwright.async_api import async_playwright
CDP='http://localhost:9222'
TOKEN=open('.gstack-demo-token').read().strip()
RID=int(sys.argv[1])
VIEW=sys.argv[2]
SHOT='C:/Users/cyun0/git/maedeup/.qa-mobile/natural'
async def main():
    async with async_playwright() as p:
        b=await p.chromium.connect_over_cdp(CDP)
        page=await b.contexts[0].new_page()
        if VIEW=='mobile':
            await page.set_viewport_size({'width':390,'height':844}); url='http://localhost:3000/m/chat/ai?roomId='+str(RID)
        else:
            await page.set_viewport_size({'width':1440,'height':900}); url='http://localhost:3000/meeting/'+str(RID)
        await page.goto('http://localhost:3000/m/login')
        await page.evaluate('localStorage.setItem("auth_token", '+json.dumps(TOKEN)+')')
        await page.goto(url); await page.wait_for_timeout(7000)
        # 다른 시간 펼치기
        alt=page.get_by_text('다른 시간', exact=False)
        for i in range(await alt.count()):
            if await alt.nth(i).is_visible(): await alt.nth(i).click(); print('expanded alternatives'); break
        await page.wait_for_timeout(800)
        # 6월 16일 슬롯 선택
        s16=page.get_by_text('6월 16일', exact=False)
        picked=False
        for i in range(await s16.count()):
            if await s16.nth(i).is_visible(): await s16.nth(i).click(); picked=True; print('picked 6월 16일'); break
        print('picked 16?', picked)
        await page.wait_for_timeout(600)
        # 시간대 변경
        tcbtn=page.get_by_role('button', name='시간대 변경')
        for i in range(await tcbtn.count()):
            if await tcbtn.nth(i).is_visible() and not await tcbtn.nth(i).is_disabled():
                await tcbtn.nth(i).click(); print('clicked 시간대 변경'); break
        await page.wait_for_timeout(4500)
        checks={'TimeBar가용성조회중':'가용성 조회 중','TimeBar멤버일정확인':'멤버 일정을 확인','TimeBar내일정':'내 일정','TimeBar끝시간':'끝 시간 선택','이시간으로확정':'이 시간으로 확정','멤버현황':'멤버 현황'}
        for k,v in checks.items():
            loc=page.get_by_text(v, exact=False); cnt=await loc.count(); vis=False
            for i in range(min(cnt,6)):
                if await loc.nth(i).is_visible(): vis=True; break
            print(f'  {k}: count={cnt} visible={vis}')
        ids=await page.eval_on_selector_all('[role=grid]', 'els => els.map(e=>({id:e.id, vis:e.offsetParent!==null}))')
        print('grids:', json.dumps(ids, ensure_ascii=False))
        await page.screenshot(path=SHOT+'/'+VIEW+'_16th_after_timechange.png', full_page=(VIEW=='mobile'))
        await page.close()
asyncio.run(main())