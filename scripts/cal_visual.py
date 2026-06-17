import asyncio, json, urllib.request, websockets
from playwright.async_api import async_playwright
API="http://localhost:8000"; WS="ws://localhost:8000"; CDP="http://localhost:9222"
TOKEN=open(".gstack-demo-token").read().strip()
ACT2={"수현":"내일은 동아리 MT라 안 되고, 이번주 수·목·금도 시험 기간이라 다 안 돼. 다음주 월·화도 발표 준비 때문에 일정 잡혀있어","민수":"다음주 수요일은 본가 내려가야 해서 패스","예린":"다음주 화요일은 좀 쉬고 싶다… 다음주 토요일 빼고 다 바빠"}
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
    rid=http("POST","/api/v1/rooms/",TOKEN,{"name":"캘린더확인","description":"x","category":"모임"})["id"]
    g={n:http("POST",f"/api/v1/rooms/{rid}/guest-join",None,{"display_name":n})["token"] for n in ACT2}
    http("POST",f"/api/v1/rooms/{rid}/preferences",TOKEN,{"preferred_times":["평일 저녁"],"preferred_location":"강남","preferred_foods":[],"disliked_foods":[],"note":None})
    stop=asyncio.Event(); t=asyncio.create_task(ka(rid,stop)); await asyncio.sleep(1)
    await sn(rid,TOKEN,"김창윤","다들 시험 끝나고 한번 보자!"); await asyncio.sleep(1)
    for n,m in ACT2.items(): await sn(rid,g[n],n,m); await asyncio.sleep(1.2)
    await asyncio.sleep(16); stop.set()
    try: await asyncio.wait_for(t,timeout=2)
    except: pass
    async with async_playwright() as p:
        b=await p.chromium.connect_over_cdp(CDP); page=await b.contexts[0].new_page()
        await page.set_viewport_size({"width":390,"height":844})
        await page.goto("http://localhost:3000/"); await page.evaluate(f'localStorage.setItem("auth_token", {json.dumps(TOKEN)})')
        await page.goto(f"http://localhost:3000/m/chat/ai?tab=calendar&roomId={rid}"); await page.wait_for_timeout(5000)
        await page.screenshot(path="qa_artifacts/calendar_fixed.png", full_page=True)
        print(f"ROOM={rid} 스크린샷: qa_artifacts/calendar_fixed.png")
asyncio.run(main())
