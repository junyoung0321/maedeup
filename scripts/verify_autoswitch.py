import asyncio, json, urllib.request, websockets
from playwright.async_api import async_playwright
API="http://localhost:8000"; WS="ws://localhost:8000"; CDP="http://localhost:9222"
TOKEN=open(".gstack-demo-token").read().strip()
ACT2={"수현":"이번주 수목금 시험","민수":"다음주 수요일 본가","예린":"다음주 토요일 빼고 다 바빠"}
def http(m,p,t=None,b=None):
    d=json.dumps(b).encode() if b is not None else None
    h={"Content-Type":"application/json"}
    if t: h["Authorization"]=f"Bearer {t}"
    return json.loads(urllib.request.urlopen(urllib.request.Request(f"{API}{p}",data=d,headers=h,method=m),timeout=10).read())
async def ka(rid,stop):
    async with websockets.connect(f"{WS}/ws/agent/{rid}?token={TOKEN}") as ws:
        while not stop.is_set():
            try: await asyncio.wait_for(ws.recv(),timeout=1.0)
            except asyncio.TimeoutError: pass
            except: break
async def sn(rid,tok,nm,c):
    async with websockets.connect(f"{WS}/ws/social/{rid}?token={tok}") as ws:
        try: await asyncio.wait_for(ws.recv(),timeout=0.5)
        except asyncio.TimeoutError: pass
        await ws.send(json.dumps({"role":"user","content":c,"sender":nm})); await asyncio.sleep(0.6)
async def main():
    rid=http("POST","/api/v1/rooms/",TOKEN,{"name":"자동전환","description":"x","category":"모임"})["id"]
    g={n:http("POST",f"/api/v1/rooms/{rid}/guest-join",None,{"display_name":n})["token"] for n in ACT2}
    http("POST",f"/api/v1/rooms/{rid}/preferences",TOKEN,{"preferred_times":["평일 저녁"],"preferred_location":"강남","preferred_foods":[],"disliked_foods":[],"note":None})
    stop=asyncio.Event(); t=asyncio.create_task(ka(rid,stop)); await asyncio.sleep(1)
    await sn(rid,TOKEN,"김창윤","보자"); await asyncio.sleep(1)
    for n,m in ACT2.items(): await sn(rid,g[n],n,m); await asyncio.sleep(1.2)
    await asyncio.sleep(14); stop.set()
    try: await asyncio.wait_for(t,timeout=2)
    except: pass
    async with async_playwright() as p:
        b=await p.chromium.connect_over_cdp(CDP); page=await b.contexts[0].new_page()
        await page.set_viewport_size({"width":390,"height":844})
        await page.goto("http://localhost:3000/"); await page.evaluate(f'localStorage.setItem("auth_token", {json.dumps(TOKEN)})')
        await page.goto(f"http://localhost:3000/m/chat/ai?roomId={rid}"); await page.wait_for_timeout(5000)
        # 슬롯 클릭 후 '시간대 변경' (수동 탭전환 안 함)
        try:
            await page.get_by_text("전원 가능",exact=False).first.click(timeout=2000); await page.wait_for_timeout(600)
        except: pass
        clicked=False
        for lbl in ["시간대 변경","시간 변경"]:
            try:
                el=page.get_by_text(lbl,exact=False).first
                if await el.count()>0: await el.click(timeout=3000); clicked=True; print(f"'{lbl}' 클릭(수동 탭전환 안 함)"); break
            except: pass
        await page.wait_for_timeout(3000)
        body=await page.inner_text("body")
        # 자동 전환됐으면 캘린더/TimeBar 콘텐츠가 보여야 함
        auto=("불가능 날짜" in body) or ("멤버 현황" in body) or ("가능 인원" in body) or ("AI 추천 날짜" in body)
        print("시간대변경 후 자동으로 캘린더(TimeBar) 노출:", auto, "(기대 True)")
        await page.screenshot(path="qa_artifacts/autoswitch.png", full_page=True)
        print("스크린샷: qa_artifacts/autoswitch.png")
asyncio.run(main())
