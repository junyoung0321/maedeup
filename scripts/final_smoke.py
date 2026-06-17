import asyncio, json
from playwright.async_api import async_playwright
CDP="http://localhost:9222"; TOKEN=open(".gstack-demo-token").read().strip()
import sys
RID=sys.argv[1] if len(sys.argv)>1 else None
async def main():
    if not RID:
        print("no room"); return
    async with async_playwright() as p:
        b=await p.chromium.connect_over_cdp(CDP); page=await b.contexts[0].new_page()
        await page.set_viewport_size({"width":390,"height":844})
        await page.goto("http://localhost:3000/"); await page.evaluate(f'localStorage.setItem("auth_token", {json.dumps(TOKEN)})')
        await page.goto(f"http://localhost:3000/m/chat/ai?roomId={RID}"); await page.wait_for_timeout(4000)
        body=await page.inner_text("body")
        print("3탭:", all(t in body for t in ["채팅방","캘린더","AI"]), "| 완료버튼:", "완료" in body, "| 추천카드:", ("추천" in body or "전원 가능" in body))
        await page.screenshot(path="qa_artifacts/final_ai.png")
        print("스크린샷: qa_artifacts/final_ai.png")
asyncio.run(main())
