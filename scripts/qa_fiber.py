import asyncio, json, sys
from playwright.async_api import async_playwright
CDP='http://localhost:9222'
TOKEN=open('.gstack-demo-token').read().strip()
RID=int(sys.argv[1])
SHOT='C:/Users/cyun0/git/maedeup/.qa-mobile/natural'
FIBER_JS=r'''
() => {
  function findFiber(dom){ for(const k in dom){ if(k.startsWith('__reactFiber$')) return dom[k]; } return null; }
  // find any element, walk up fiber tree, collect memoizedState/Props that look like meeting state
  const root = document.querySelector('main') || document.body;
  let fiber = findFiber(root);
  let found = null;
  let guard = 0;
  // climb to top
  while(fiber && fiber.return){ fiber = fiber.return; guard++; if(guard>200) break; }
  // BFS down collecting context values with infoPanePhase
  const stack=[fiber]; let seen=0;
  while(stack.length && seen<5000){
    const f=stack.pop(); seen++;
    if(!f) continue;
    let ms=f.memoizedState;
    let hops=0;
    while(ms && hops<40){
      const v=ms.memoizedState;
      if(v && typeof v==='object' && ('infoPanePhase' in v || 'confirmedDate' in v || 'contextMode' in v)){
        found={infoPanePhase:v.infoPanePhase, confirmedDate:v.confirmedDate, contextMode:v.contextMode, voteAwaitingTimeMeetingId:v.voteAwaitingTimeMeetingId, myDateSelection:v.myDateSelection};
      }
      ms=ms.next; hops++;
    }
    if(f.child) stack.push(f.child);
    if(f.sibling) stack.push(f.sibling);
  }
  return found;
}
'''
async def main():
    async with async_playwright() as p:
        b=await p.chromium.connect_over_cdp(CDP)
        page=await b.contexts[0].new_page()
        await page.set_viewport_size({'width':390,'height':844})
        await page.goto('http://localhost:3000/m/login')
        await page.evaluate('localStorage.setItem("auth_token", '+json.dumps(TOKEN)+')')
        await page.goto('http://localhost:3000/m/chat/ai?roomId='+str(RID)); await page.wait_for_timeout(6500)
        before=await page.evaluate(FIBER_JS)
        print('BEFORE click:', json.dumps(before, ensure_ascii=False))
        tcbtn=page.get_by_role('button', name='시간대 변경')
        for i in range(await tcbtn.count()):
            if await tcbtn.nth(i).is_visible() and not await tcbtn.nth(i).is_disabled():
                await tcbtn.nth(i).click(); print('clicked 시간대 변경'); break
        await page.wait_for_timeout(2500)
        after=await page.evaluate(FIBER_JS)
        print('AFTER click:', json.dumps(after, ensure_ascii=False))
        await page.wait_for_timeout(2000)
        after2=await page.evaluate(FIBER_JS)
        print('AFTER 4.5s:', json.dumps(after2, ensure_ascii=False))
        await page.close()
asyncio.run(main())