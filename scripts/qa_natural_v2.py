import asyncio, json, websockets, sys
from playwright.async_api import async_playwright
WS='ws://localhost:8000'
CDP='http://localhost:9222'
TOKEN=open('.gstack-demo-token').read().strip()
RID=int(sys.argv[1])
SHOT='C:/Users/cyun0/git/maedeup/.qa-mobile/natural'
guests=json.load(open('/tmp/guest_383.json'))
R={}
async def guest_select(token,date,start,end):
    async with websockets.connect(WS+'/ws/social/'+str(RID)+'?token='+token) as ws:
        try:
            await asyncio.wait_for(ws.recv(),timeout=0.5)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({'type':'time_selection','date':date,'start':start,'end':end}))
        await asyncio.sleep(0.5)
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
        await page.goto('http://localhost:3000/m/chat/ai?roomId='+str(RID))
        await page.wait_for_timeout(6000)
        async def active_tab():
            for name in ['채팅방','캘린더','AI']:
                loc=page.locator('div', has_text=name).last
            # use color attr via evaluate_all minimal
            res=await page.eval_on_selector_all('div', 'els => els.filter(e=>e.children.length===0 && ["채팅방","캘린더","AI"].includes(e.textContent.trim())).map(e=>({t:e.textContent.trim(),c:getComputedStyle(e).color}))')
            for o in res:
                if o['c'].replace(' ','')=='rgb(79,70,229)': return o['t']
            return None
        t0=await active_tab(); print('init tab:',t0); R['init_tab']=t0
        await page.screenshot(path=SHOT+'/v2_01_entry.png', full_page=True)
        slot=page.locator('text=지방선거일').first
        try:
            await slot.click(timeout=4000); print('AI slot clicked')
        except Exception as e: print('slot click err', e)
        await page.wait_for_timeout(700)
        await page.screenshot(path=SHOT+'/v2_02_slot.png', full_page=True)
        tcbtn=page.get_by_role('button', name='시간대 변경')
        n=await tcbtn.count(); print('시간대변경 btn count', n)
        tc='not-found'
        for i in range(n):
            bb=tcbtn.nth(i)
            if await bb.is_visible():
                dis=await bb.is_disabled()
                if not dis:
                    await bb.click(); tc='clicked'; break
                else: tc='disabled'
        print('시간대변경:',tc); R['time_change_click']=tc
        await page.wait_for_timeout(4000)
        t1=await active_tab(); print('after timechange tab:',t1)
        R['AUTO_SWITCH_1_active_tab']=t1; R['AUTO_SWITCH_1_PASS']=(t1=='캘린더')
        grid=page.locator('[role=grid]')
        tb_vis=False; grid_id=None
        if await grid.count()>0 and await grid.first.is_visible():
            tb_vis=True; grid_id=await grid.first.get_attribute('id')
        print('TimeBar visible:',tb_vis,'id',grid_id); R['AUTO_SWITCH_1_timebar_visible']=tb_vis
        await page.screenshot(path=SHOT+'/v2_03_autoswitch1.png', full_page=True)
        host_date=None
        if grid_id and grid_id.startswith('timebar-'):
            y=grid_id.replace('timebar-',''); host_date=y[0:4]+'-'+y[4:6]+'-'+y[6:8]
        print('host_date=',host_date)
        START,END=18,20
        if grid_id:
            for idx in (START,END):
                cell=page.locator('#'+grid_id+'-mine-'+str(idx))
                if await cell.count()>0:
                    await cell.first.click(); print('  mine slot',idx,'clicked'); await page.wait_for_timeout(400)
        await page.wait_for_timeout(1000)
        await page.screenshot(path=SHOT+'/v2_04_hostsel.png', full_page=True)
        if host_date:
            for nm,info in guests.items():
                await guest_select(info['token'],host_date,START,END); print('  guest inject',nm); await asyncio.sleep(0.4)
        await page.wait_for_timeout(4000)
        cons=page.get_by_text('추천 시간 그대로 확정')
        consv=await cons.count()>0 and await cons.first.is_visible()
        print('consensus(추천시간그대로확정) visible:',consv); R['consensus_reached']=bool(consv)
        await page.screenshot(path=SHOT+'/v2_05_consensus.png', full_page=True)
        b1=page.get_by_role('button', name='이 시간으로 확정')
        clk1=False
        for i in range(await b1.count()):
            if await b1.nth(i).is_visible():
                await b1.nth(i).click(); clk1=True; break
        print('이 시간으로 확정 클릭:',clk1)
        await page.wait_for_timeout(2500)
        await page.screenshot(path=SHOT+'/v2_06_finalize.png', full_page=True)
        b2=page.get_by_text('추천 시간 그대로 확정')
        clk2=False
        for i in range(await b2.count()):
            if await b2.nth(i).is_visible():
                await b2.nth(i).click(); clk2=True; break
        print('추천 시간 그대로 확정 클릭:',clk2)
        await page.wait_for_timeout(5000)
        tcf=page.get_by_text('일정이 확정되었습니다')
        tconf=await tcf.count()>0 and await tcf.first.is_visible()
        print('일정 확정 표시:',tconf); R['time_confirmed']=bool(tconf or clk2)
        await page.screenshot(path=SHOT+'/v2_07_timeconfirmed.png', full_page=True)
        print('after confirm tab:', await active_tab())
        json.dump(R, open('/tmp/qa_v2.json','w'), ensure_ascii=False)
        json.dump(errors, open('/tmp/qa_v2_err.json','w'), ensure_ascii=False)
        print('=== RESULTS ==='); print(json.dumps(R, ensure_ascii=False, indent=2))
        print('console errors:', len(errors))
        for e in errors[:10]: print('  ', e[:180])
        await page.close()
asyncio.run(main())