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
        await page.goto('http://localhost:3000/meeting/'+str(RID)); await page.wait_for_timeout(7000)
        tcbtn=page.get_by_role('button', name='시간대 변경')
        for i in range(await tcbtn.count()):
            if await tcbtn.nth(i).is_visible() and not await tcbtn.nth(i).is_disabled():
                await tcbtn.nth(i).click(); print('clicked 시간대 변경'); break
        await page.wait_for_timeout(4500)
        tb=await page.eval_on_selector_all('[id^=timebar-]', 'els=>els.length')
        tb_vis=await page.eval_on_selector_all('[id^=timebar-]', 'els=>els.filter(e=>e.offsetParent!==null).length')
        print('DESKTOP timebar cells total='+str(tb)+' visible='+str(tb_vis))
        await page.screenshot(path=SHOT+'/desktop_timebar_confirm.png', full_page=False)
        await page.close()
asyncio.run(main())