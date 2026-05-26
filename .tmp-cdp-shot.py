import asyncio, sys
from playwright.async_api import async_playwright

OUT = sys.argv[1] if len(sys.argv) > 1 else "shot.png"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0]
        page = ctx.pages[0]
        for pg in ctx.pages:
            if "meeting" in pg.url or "localhost:3000" in pg.url:
                page = pg
                break
        print(f"URL: {page.url}")
        await page.screenshot(path=OUT, full_page=False)
        print(f"saved: {OUT}")

asyncio.run(main())
