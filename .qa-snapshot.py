"""CDP 9222 attach → 현재 페이지 screenshot. usage: python .qa-snapshot.py <out.png>"""
import asyncio, sys
from playwright.async_api import async_playwright

async def main(out_path: str) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.screenshot(path=out_path, full_page=False)
        print(f"saved: {out_path} url={page.url}")

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "qa-snap.png"))
