"""정정(correction) 시나리오 웹 시연: 거부 → reflect-back → 정정 → 업데이트된 reflect-back."""
import asyncio
import json
import pathlib
from playwright.async_api import async_playwright

CDP = "http://localhost:9222"
SHOT = pathlib.Path(__file__).parent / "_feature_shots"
SHOT.mkdir(exist_ok=True)
MSG1 = "얘들아 나 다음주 토요일 빼고 다 바빠 ㅠㅠ 언제 볼까?"
MSG2 = "아 근데 다시 보니까 수요일은 돼!"


def log(m): print(f"[corr] {m}", flush=True)


async def jeval(page, js):
    try:
        return await page.evaluate(js)
    except Exception as e:  # noqa: BLE001
        return None


async def fill_input(page, ph, text):
    js = f"""(() => {{
      const inp = Array.from(document.querySelectorAll('input,textarea')).find(i => i.placeholder && i.placeholder.includes({json.dumps(ph)}));
      if (!inp) return false;
      const proto = inp.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto,'value').set.call(inp,{json.dumps(text)});
      inp.dispatchEvent(new Event('input',{{bubbles:true}})); inp.focus(); return true; }})()"""
    return bool(await jeval(page, js))


async def click_btn(page, text, contains=False):
    expr = f"b.innerText.trim().includes({json.dumps(text)})" if contains else f"b.innerText.trim()==={json.dumps(text)}"
    return bool(await jeval(page, f"(()=>{{const b=Array.from(document.querySelectorAll('button')).filter(b=>b.innerText&&{expr}&&b.offsetParent);if(!b.length)return false;b[0].click();return true;}})()"))


async def reflect_lines(page):
    body = await jeval(page, "document.body.innerText") or ""
    return [ln.strip() for ln in body.splitlines() if "이해했어요" in ln or "어려운 날" in ln]


async def wait_reflect_change(page, prev, timeout_s=60):
    loop = asyncio.get_event_loop(); end = loop.time() + timeout_s
    while loop.time() < end:
        lines = await reflect_lines(page)
        if lines and lines[-1] != prev:
            return lines[-1]
        await asyncio.sleep(0.5)
    lines = await reflect_lines(page)
    return lines[-1] if lines else ""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]; page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.bring_to_front()
        await page.goto("http://localhost:3000/", wait_until="networkidle", timeout=20000)
        await asyncio.sleep(1)
        await click_btn(page, "모임 생성"); await asyncio.sleep(1.2)
        await fill_input(page, "스터디 모임", "정정 시연"); await asyncio.sleep(0.3)
        await click_btn(page, "식사", contains=True); await asyncio.sleep(0.3)
        await click_btn(page, "모임 생성", contains=True); await asyncio.sleep(2.5)
        log(f"방: {page.url}")
        if await jeval(page, "document.body.innerText.includes('평일 저녁')"):
            await click_btn(page, "평일 저녁", contains=True)
            await fill_input(page, "강남", "강남"); await asyncio.sleep(0.3)
            await click_btn(page, "제출", contains=True); await asyncio.sleep(1.5)

        # 1) 거부 발화
        log(f"입력1: {MSG1}")
        await fill_input(page, "AI에게", MSG1); await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")
        rb1 = await wait_reflect_change(page, "", 60)
        await asyncio.sleep(1.5)
        await page.screenshot(path=str(SHOT / "C1_rejected.png"), full_page=True)
        log(f"reflect-back #1: {rb1}")

        # 2) 정정 발화
        log(f"입력2(정정): {MSG2}")
        await fill_input(page, "AI에게", MSG2); await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")
        rb2 = await wait_reflect_change(page, rb1, 60)
        await asyncio.sleep(1.5)
        await page.screenshot(path=str(SHOT / "C2_corrected.png"), full_page=True)
        log(f"reflect-back #2: {rb2}")

        log("=" * 60)
        log(f"거부 후:  {rb1}")
        log(f"정정 후:  {rb2}")
        ok = ("6/10" in rb1 or "6/10(수)" in rb1) and ("6/10" not in rb2)
        log(f"수요일(6/10) 제거 확인: {'PASS ✅' if ok else 'CHECK — 화면 확인'}")
        log("=" * 60)
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
