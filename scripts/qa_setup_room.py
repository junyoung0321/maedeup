"""QA용 fresh 방 셋업 — diag_unavail과 동일 ACT2 재현하되 게스트 토큰을 파일로 저장."""
import asyncio, json, urllib.request, sys
import websockets
API="http://localhost:8000"; WS="ws://localhost:8000"
TOKEN=open(".gstack-demo-token").read().strip()
ACT2={
 "수현":"내일은 동아리 MT라 안 되고, 이번주 수·목·금도 시험 기간이라 다 안 돼. 다음주 월·화도 발표 준비 때문에 일정 잡혀있어",
 "민수":"다음주 수요일은 본가 내려가야 해서 패스",
 "예린":"다음주 화요일은 좀 쉬고 싶다… 다음주 토요일 빼고 다 바빠",
}
def http(m,p,t=None,b=None):
    d=json.dumps(b).encode() if b is not None else None
    h={"Content-Type":"application/json"}
    if t: h["Authorization"]=f"Bearer {t}"
    return json.loads(urllib.request.urlopen(urllib.request.Request(f"{API}{p}",data=d,headers=h,method=m),timeout=10).read())
async def keepalive(rid,stop):
    async with websockets.connect(f"{WS}/ws/agent/{rid}?token={TOKEN}") as ws:
        while not stop.is_set():
            try: await asyncio.wait_for(ws.recv(),timeout=1.0)
            except asyncio.TimeoutError: pass
            except Exception: break
async def send_social(rid,token,name,content):
    async with websockets.connect(f"{WS}/ws/social/{rid}?token={token}") as ws:
        try: await asyncio.wait_for(ws.recv(),timeout=0.5)
        except asyncio.TimeoutError: pass
        await ws.send(json.dumps({"role":"user","content":content,"sender":name}))
        await asyncio.sleep(0.6)
async def main():
    room=http("POST","/api/v1/rooms/",TOKEN,{"name":"QA자연흐름","description":"x","category":"모임"})
    rid=room["id"]
    guests={}
    for n in ACT2:
        g=http("POST",f"/api/v1/rooms/{rid}/guest-join",None,{"display_name":n})
        guests[n]={"token":g["token"],"user_id":g["user_id"]}
    http("POST",f"/api/v1/rooms/{rid}/preferences",TOKEN,
         {"preferred_times":["평일 저녁"],"preferred_location":"강남","preferred_foods":[],"disliked_foods":[],"note":None})
    stop=asyncio.Event(); ka=asyncio.create_task(keepalive(rid,stop)); await asyncio.sleep(1.0)
    await send_social(rid,TOKEN,"김창윤","다들 시험 끝나고 한번 보자!"); await asyncio.sleep(1.0)
    for n,msg in ACT2.items():
        await send_social(rid,guests[n]["token"],n,msg); await asyncio.sleep(1.2)
    await asyncio.sleep(18); stop.set()
    try: await asyncio.wait_for(ka,timeout=2)
    except Exception: pass
    open(f"/tmp/qa_room_{rid}.json","w").write(json.dumps(guests,ensure_ascii=False))
    print(f"ROOM_ID={rid}")
    print("GUESTS="+json.dumps({k:v["user_id"] for k,v in guests.items()},ensure_ascii=False))
asyncio.run(main())
