import asyncio, json, sys
from playwright.async_api import async_playwright
CDP='http://localhost:9222'
TOKEN=open('.gstack-demo-token').read().strip()
RID=int(sys.argv[1])
SHOT='C:/Users/cyun0/git/maedeup/.qa-mobile/natural'
R={}
def log(s): print(s)
async def active_tab(page):
    res=await page.eval_on_selector_all('div', 'els => els.filter(e=>e.children.length===0 && ["채팅방","캘린더","AI"].includes(e.textContent.trim())).map(e=>({t:e.textContent.trim(),c:getComputedStyle(e).color}))')
    for o in res:
        if o['c'].replace(' ','')=='rgb(79,70,229)': return o['t']
    return None
async def click_tab(page,name):
    await page.eval_on_selector_all('div', 'els => { const e=els.find(x=>x.children.length===0 && x.textContent.trim()==="'+name+'"); if(e) e.click(); }')
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
        await page.goto('http://localhost:3000/m/chat/ai?roomId='+str(RID)); await page.wait_for_timeout(7000)
        log('진입 tab='+str(await active_tab(page)))
        # AI 탭으로 이동 (사용자 수동 — 시나리오상 허용)
        await click_tab(page,'AI'); await page.wait_for_timeout(1500)
        log('AI 탭 이동 tab='+str(await active_tab(page)))
        await page.screenshot(path=SHOT+'/P01_ai_after_timeconfirm.png', full_page=True)
        # 입력창에 '강남 한식 추천해줘' 입력 후 전송
        box=page.get_by_placeholder('AI에게 질문하세요')
        if await box.count()==0:
            box=page.locator('input[type=text], textarea').last
        await box.first.click(); await box.first.fill('강남 한식 추천해줘')
        await page.keyboard.press('Enter')
        log('장소 추천 요청 전송')
        # carousel 대기 (Kakao+Gemini)
        place_found=False
        for _ in range(40):
            await page.wait_for_timeout(1500)
            cnt=await page.get_by_text('추천', exact=False).count()
            # PlaceRecommendationCard 특유 텍스트 / 장소명
            has=await page.eval_on_selector_all('*', 'els=>els.some(e=>e.children.length===0 && (e.textContent.includes("별점")||e.textContent.includes("리뷰")||e.textContent.includes("거리")||e.textContent.includes("카카오")))')
            cards=await page.eval_on_selector_all('[class*=place], [data-place], [aria-label*=장소]', 'els=>els.length')
            if has:
                place_found=True; break
        log('place carousel 등장='+str(place_found))
        await page.wait_for_timeout(1500)
        await page.screenshot(path=SHOT+'/P02_place_carousel.png', full_page=True)
        # 장소명 클릭 — PlaceRecommendationCard onPlaceClick. 첫 장소 카드 클릭
        before_tab=await active_tab(page)
        clicked=await page.eval_on_selector_all('*', 'els=>{ const c=els.find(e=>e.getAttribute && (e.getAttribute("role")==="button"||e.onclick) && /음식점|한식|식당|점|관|집/.test(e.textContent||"") && e.textContent.length<40 && e.offsetParent); if(c){c.click(); return c.textContent.slice(0,30);} return null; }')
        log('장소명 클릭 시도='+str(clicked))
        await page.wait_for_timeout(3500)
        after_tab=await active_tab(page)
        # PlaceDetailPane 노출?
        pdp=await page.get_by_text('이 장소로 확정', exact=False).count()
        pdp_vis=False
        loc=page.get_by_text('이 장소로 확정', exact=False)
        for i in range(pdp):
            if await loc.nth(i).is_visible(): pdp_vis=True; break
        R['AUTO_SWITCH_2_before_tab']=before_tab; R['AUTO_SWITCH_2_after_tab']=after_tab
        R['AUTO_SWITCH_2_placedetail_visible']=pdp_vis
        R['AUTO_SWITCH_2_PASS']=(after_tab=='캘린더' and pdp_vis)
        log('AUTO_SWITCH_2: '+str(before_tab)+' -> '+str(after_tab)+' PlaceDetail='+str(pdp_vis)+' PASS='+str(R['AUTO_SWITCH_2_PASS']))
        await page.screenshot(path=SHOT+'/P03_autoswitch2_placedetail.png', full_page=True)
        # '이 장소로 확정' 클릭
        clk=False
        for i in range(await loc.count()):
            if await loc.nth(i).is_visible(): 
                await loc.nth(i).scroll_into_view_if_needed(); await loc.nth(i).click(); clk=True; break
        log('이 장소로 확정 클릭='+str(clk))
        await page.wait_for_timeout(4000)
        await page.screenshot(path=SHOT+'/P04_place_confirmed.png', full_page=True)
        # done 화면 자동 렌더 대기 (2초 후 setContextMode done)
        done_auto=False
        for _ in range(8):
            await page.wait_for_timeout(1000)
            d=await page.get_by_text('생성', exact=False).count()
            dd=await page.eval_on_selector_all('*', 'els=>els.some(e=>e.children.length===0 && (e.textContent.includes("모임이 완성")||e.textContent.includes("생성 완료")||e.textContent.includes("확정된 모임")||e.textContent.includes("캘린더에 추가")))')
            if dd: done_auto=True; break
        R['done_auto_after_place']=done_auto
        log('장소 확정 후 done 화면 자동 렌더='+str(done_auto))
        await page.screenshot(path=SHOT+'/P05_done_auto.png', full_page=True)
        json.dump(R, open('/tmp/qa_full_p2.json','w'), ensure_ascii=False)
        json.dump(errors, open('/tmp/qa_full_p2_err.json','w'), ensure_ascii=False)
        print('=== PART2 RESULTS ==='); print(json.dumps(R, ensure_ascii=False, indent=2))
        print('console errors:', len(errors))
        for e in errors[:10]: print('  ',e[:160])
        await page.close()
asyncio.run(main())