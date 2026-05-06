"""
CDP controller — connects to existing Chromium at localhost:9222
and runs a single command. Each invocation is independent.

Usage:
    python .gstack-browser-cmd.py screenshot <out_path>
    python .gstack-browser-cmd.py goto <url>
    python .gstack-browser-cmd.py click <selector>
    python .gstack-browser-cmd.py type <selector> <text>
    python .gstack-browser-cmd.py press <key>
    python .gstack-browser-cmd.py text <selector>          # innerText of first match
    python .gstack-browser-cmd.py html <selector>          # outerHTML of first match
    python .gstack-browser-cmd.py eval <js_expression>     # returns JSON of result
    python .gstack-browser-cmd.py title
    python .gstack-browser-cmd.py url
    python .gstack-browser-cmd.py wait <selector> [<timeout_ms>]
"""
import asyncio
import json
import sys

from playwright.async_api import async_playwright


async def get_page(p):
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    if ctx.pages:
        return browser, ctx.pages[0]
    page = await ctx.new_page()
    return browser, page


async def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    args = sys.argv[2:]

    async with async_playwright() as p:
        browser, page = await get_page(p)

        try:
            if cmd == "screenshot":
                out = args[0] if args else "screenshot.png"
                await page.screenshot(path=out, full_page=False)
                print(f"saved: {out}")
            elif cmd == "goto":
                await page.goto(args[0], wait_until="networkidle", timeout=15000)
                print(f"url: {page.url}")
            elif cmd == "click":
                await page.click(args[0], timeout=5000)
                print(f"clicked: {args[0]}")
            elif cmd == "type":
                sel, txt = args[0], args[1]
                await page.fill(sel, txt)
                print(f"typed into {sel}")
            elif cmd == "press":
                await page.keyboard.press(args[0])
                print(f"pressed: {args[0]}")
            elif cmd == "text":
                t = await page.inner_text(args[0], timeout=3000)
                print(t)
            elif cmd == "html":
                el = await page.query_selector(args[0])
                if el is None:
                    print("(none)")
                else:
                    print(await el.evaluate("e => e.outerHTML"))
            elif cmd == "eval":
                expr = " ".join(args)
                # Wrap to JSON-stringify result
                result = await page.evaluate(expr)
                print(json.dumps(result, ensure_ascii=False, default=str))
            elif cmd == "title":
                print(await page.title())
            elif cmd == "url":
                print(page.url)
            elif cmd == "wait":
                sel = args[0]
                timeout = int(args[1]) if len(args) > 1 else 8000
                await page.wait_for_selector(sel, timeout=timeout)
                print(f"visible: {sel}")
            else:
                print(f"unknown cmd: {cmd}")
                return 1
        finally:
            # IMPORTANT: don't close — would clear page state. Just let process exit.
            pass
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
