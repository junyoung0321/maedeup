import asyncio, json, urllib.request
from playwright.async_api import async_playwright
API="http://localhost:8000"; CDP="http://localhost:9222"
TOKEN=open(".gstack-demo-token").read().strip()
def http(m,p,t=None,b=None):
    d=json.dumps(b).encode() if b is not None else None
    h={"Content-Type":"application/json"}
    if t: h["Authorization"]=f"Bearer {t}"
    return json.loads(urllib.request.urlopen(urllib.request.Request(f"{API}{p}",data=d,headers=h,method=m),timeout=10).read())
async def main():
    rid=http("POST","/api/v1/rooms/",TOKEN,{"name":"nav검증","description":"x","category":"모임"})["id"]
    async with async_playwright() as p:
        b=await p.chromium.connect_over_cdp(CDP); ctx=b.contexts[0]; page=await ctx.new_page()
        await page.set_viewport_size({"width":390,"height":844})
        await page.goto("http://localhost:3000/")
        await page.evaluate(f'localStorage.setItem("auth_token", {json.dumps(TOKEN)})')
        # 1) 채팅방 진입
        await page.goto(f"http://localhost:3000/m/chat/schedule?roomId={rid}"); await page.wait_for_timeout(2500)
        body=await page.inner_text("body")
        print("채팅방: 3탭(채팅방/캘린더/AI) 보임 =", all(t in body for t in ["채팅방","캘린더","AI"]))
        # 2) 캘린더 탭 클릭 → 통합 캘린더
        await page.get_by_text("캘린더",exact=True).first.click(); await page.wait_for_timeout(2500)
        print("  캘린더 클릭 후 URL:", page.url.split("localhost:3000")[1][:50])
        body=await page.inner_text("body")
        print("  → InfoPane(캘린더 그리드) 보임 =", ("매듭" in body and "월" in body) or "불가능 날짜" in body)
        # 3) AI 탭
        await page.get_by_text("AI",exact=True).first.click(); await page.wait_for_timeout(2500)
        body=await page.inner_text("body")
        print("  AI 탭 → AiAssistantPane 보임 =", ("AI 어시스턴트" in body) or ("AI에게 질문" in body))
        # 4) /m/schedule 리다이렉트
        await page.goto(f"http://localhost:3000/m/schedule?roomId={rid}"); await page.wait_for_timeout(2500)
        print("/m/schedule 리다이렉트 후 URL:", page.url.split("localhost:3000")[1][:50])
        print("  → 통합 캘린더로 =", "chat/ai" in page.url and "calendar" in page.url)
asyncio.run(main())
