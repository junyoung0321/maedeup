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
        errors=[]
        page.on('console', lambda m: errors.append('['+m.type+'] '+m.text) if m.type=='error' else None)
        page.on('pageerror', lambda e: errors.append('[pageerror] '+str(e)))
        await page.set_viewport_size({'width':390,'height':844})
        await page.goto('http://localhost:3000/m/login')
        await page.evaluate('localStorage.setItem("auth_token", '+json.dumps(TOKEN)+')')
        await page.goto('http://localhost:3000/m/chat/ai?roomId='+str(RID)); await page.wait_for_timeout(6000)
        # 헤더 '완료' 버튼 클릭 (미완료 상태에서)
        btn=page.get_by_role('button', name='완료')
        n=await btn.count(); print('완료 버튼 count', n)
        clk=False
        for i in range(n):
            if await btn.nth(i).is_visible(): await btn.nth(i).click(); clk=True; break
        print('완료 버튼 클릭', clk)
        await page.wait_for_timeout(3000)
        # CompletionPage 텍스트 확인
        done=await page.eval_on_selector_all('*', 'els=>els.some(e=>e.children.length===0 && (e.textContent.includes("성공적으로 생성")||e.textContent.includes("모임 정보")||e.textContent.includes("모임 공유하기")||e.textContent.includes("모임 목록으로")))')
        print('CompletionPage 렌더', done)
        await page.screenshot(path=SHOT+'/DONE_button_test.png', full_page=True)
        print('console errors', len(errors))
        for e in errors[:8]: print('  ',e[:150])
        await page.close()
asyncio.run(main())