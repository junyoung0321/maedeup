import asyncio, json, websockets, sys
from playwright.async_api import async_playwright
WS='ws://localhost:8000'; CDP='http://localhost:9222'
TOKEN=open('.gstack-demo-token').read().strip()
RID=int(sys.argv[1])
SHOT='C:/Users/cyun0/git/maedeup/.qa-mobile/natural'
guests=json.load(open('/tmp/guest_'+str(RID)+'.json'))
R={}; STEPS=[]
def log(s): STEPS.append(s); print(s)
async def guest_select(token,date,start,end):
    async with websockets.connect(WS+'/ws/social/'+str(RID)+'?token='+token) as ws:
        try: await asyncio.wait_for(ws.recv(),timeout=0.5)
        except asyncio.TimeoutError: pass
        await ws.send(json.dumps({'type':'time_selection','date':date,'start':start,'end':end}))
        await asyncio.sleep(0.5)
async def active_tab(page):
    res=await page.eval_on_selector_all('div', 'els => els.filter(e=>e.children.length===0 && ["채팅방","캘린더","AI"].includes(e.textContent.trim())).map(e=>({t:e.textContent.trim(),c:getComputedStyle(e).color}))')
    for o in res:
        if o['c'].replace(' ','')=='rgb(79,70,229)': return o['t']
    return None
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
        await page.goto('http://localhost:3000/m/chat/ai?roomId='+str(RID)); await page.wait_for_timeout(6500)
        log('STEP1 진입 tab='+str(await active_tab(page)))
        await page.screenshot(path=SHOT+'/F01_entry.png', full_page=True)
        # STEP2: 추천 슬롯 자동선택됨 → '시간대 변경' 클릭
        tcbtn=page.get_by_role('button', name='시간대 변경'); tcdone=False
        for i in range(await tcbtn.count()):
            if await tcbtn.nth(i).is_visible() and not await tcbtn.nth(i).is_disabled():
                await tcbtn.nth(i).click(); tcdone=True; break
        log('STEP2 시간대변경 클릭='+str(tcdone))
        await page.wait_for_timeout(4500)
        t1=await active_tab(page)
        tb=await page.eval_on_selector_all('[id^=timebar-]', 'els=>els.length')
        R['AUTO_SWITCH_1_active_tab']=t1; R['AUTO_SWITCH_1_timebar_elements']=tb
        R['AUTO_SWITCH_1_PASS']=(t1=='캘린더' and tb>0)
        log('AUTO_SWITCH_1: tab='+str(t1)+' timebar_cells='+str(tb)+' -> PASS='+str(R['AUTO_SWITCH_1_PASS']))
        # scroll to timebar and screenshot
        await page.evaluate('const e=document.querySelector("[id^=timebar-]"); if(e) e.scrollIntoView({block:"center"});')
        await page.wait_for_timeout(800)
        await page.screenshot(path=SHOT+'/F02_autoswitch1_timebar.png', full_page=True)
        # date from timebar id
        first_id=await page.eval_on_selector('[id^=timebar-]', 'e=>e.id')
        ymd=first_id.split('-')[1]
        host_date=ymd[0:4]+'-'+ymd[4:6]+'-'+ymd[6:8]
        log('host_date='+host_date)
        # STEP3: 호스트 시간선택 mine slot 18,20 (직접 클릭)
        START,END=18,20
        for idx in (START,END):
            sel='#timebar-'+ymd+'-mine-'+str(idx)
            el=page.locator(sel)
            if await el.count()>0:
                await el.first.scroll_into_view_if_needed()
                await el.first.click(); log('  host slot '+str(idx)+' clicked'); await page.wait_for_timeout(500)
        await page.wait_for_timeout(1000)
        await page.screenshot(path=SHOT+'/F03_host_selected.png', full_page=True)
        # 게스트3 동일 슬롯 주입
        for nm,info in guests.items():
            await guest_select(info['token'],host_date,START,END); log('  guest inject '+nm); await asyncio.sleep(0.4)
        await page.wait_for_timeout(4500)
        # 합의: '이 시간으로 확정' 버튼 visible?
        b1=page.get_by_role('button', name='이 시간으로 확정')
        consensus=False
        for i in range(await b1.count()):
            if await b1.nth(i).is_visible(): consensus=True; break
        R['consensus_reached']=consensus
        log('STEP3 합의(이 시간으로 확정 버튼 노출)='+str(consensus))
        await page.evaluate('const bs=[...document.querySelectorAll("button")].filter(b=>b.textContent.includes("이 시간으로 확정")); if(bs[0]) bs[0].scrollIntoView({block:"center"});')
        await page.wait_for_timeout(600)
        await page.screenshot(path=SHOT+'/F04_consensus.png', full_page=True)
        # 호스트 '이 시간으로 확정'
        clk1=False
        for i in range(await b1.count()):
            if await b1.nth(i).is_visible(): await b1.nth(i).click(); clk1=True; break
        log('STEP3 이 시간으로 확정 클릭='+str(clk1))
        await page.wait_for_timeout(2500)
        await page.screenshot(path=SHOT+'/F05_after_finalize.png', full_page=True)
        # '추천 시간 그대로 확정'
        b2=page.get_by_role('button', name='추천 시간 그대로 확정')
        clk2=False
        for i in range(await b2.count()):
            if await b2.nth(i).is_visible(): 
                await b2.nth(i).scroll_into_view_if_needed(); await b2.nth(i).click(); clk2=True; break
        log('STEP3 추천 시간 그대로 확정 클릭='+str(clk2))
        await page.wait_for_timeout(5000)
        # 시간 확정 확인
        tcf=page.get_by_text('일정이 확정되었습니다', exact=False)
        tconf=await tcf.count()>0 and await tcf.first.is_visible()
        R['time_confirmed']=bool(tconf or clk2)
        log('STEP3 시간확정 표시='+str(tconf)+' (확정클릭='+str(clk2)+')')
        await page.screenshot(path=SHOT+'/F06_time_confirmed.png', full_page=True)
        R['after_timeconfirm_tab']=await active_tab(page)
        json.dump(R, open('/tmp/qa_full_p1.json','w'), ensure_ascii=False)
        json.dump(errors, open('/tmp/qa_full_err.json','w'), ensure_ascii=False)
        log('=== PART1 RESULTS ==='); print(json.dumps(R, ensure_ascii=False, indent=2))
        log('console errors: '+str(len(errors)))
        for e in errors[:10]: print('  ',e[:160])
        await page.close()
asyncio.run(main())