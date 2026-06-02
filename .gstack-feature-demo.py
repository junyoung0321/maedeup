"""날짜추출 견고성 기능 시연 (CDP 브라우저). 스크린샷으로 동작 증빙.

선행: .gstack-browser-launch.py 가 CDP 9222 + host 로그인 상태로 떠 있어야 함.
실행: .venv\\Scripts\\python.exe .gstack-feature-demo.py
"""
import asyncio
import json
import sys
import pathlib

from playwright.async_api import async_playwright, Page

CDP = "http://localhost:9222"
SHOT_DIR = pathlib.Path(__file__).parent / "_feature_shots"
SHOT_DIR.mkdir(exist_ok=True)
UTTERANCE = "얘들아 나 다음주 토요일 빼고 다 바빠 ㅠㅠ 우리 언제 보면 좋을까?"


def log(m): print(f"[feat] {m}", flush=True)


async def jeval(page, js):
    try:
        return await page.evaluate(js)
    except Exception as e:  # noqa: BLE001
        log(f"eval err: {e}")
        return None


async def fill_input(page, placeholder_substr, text):
    js = f"""
    (() => {{
      const inp = Array.from(document.querySelectorAll('input,textarea')).find(
        i => i.placeholder && i.placeholder.includes({json.dumps(placeholder_substr)}));
      if (!inp) return false;
      const proto = inp.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(inp, {json.dumps(text)});
      inp.dispatchEvent(new Event('input', {{bubbles: true}}));
      inp.focus(); return true;
    }})()"""
    return bool(await jeval(page, js))


async def click_btn(page, text, contains=False):
    expr = (f"b.innerText.trim().includes({json.dumps(text)})" if contains
            else f"b.innerText.trim() === {json.dumps(text)}")
    js = f"""
    (() => {{
      const b = Array.from(document.querySelectorAll('button')).filter(b => b.innerText && {expr} && b.offsetParent);
      if (!b.length) return false; b[0].click(); return true;
    }})()"""
    return bool(await jeval(page, js))


async def page_has_text(page, text):
    return bool(await jeval(page, f"document.body.innerText.includes({json.dumps(text)})"))


async def wait_text(page, text, timeout_s=60):
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout_s
    while loop.time() < end:
        if await page_has_text(page, text):
            return True
        await asyncio.sleep(0.5)
    return False


async def shot(page, name):
    p = SHOT_DIR / f"{name}.png"
    await page.screenshot(path=str(p), full_page=True)
    log(f"📸 {p.name}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.bring_to_front()

        log("홈 이동")
        await page.goto("http://localhost:3000/", wait_until="networkidle", timeout=20000)
        await asyncio.sleep(1)

        log("'모임 생성' 클릭")
        if not await click_btn(page, "모임 생성"):
            log("모임 생성 버튼 못 찾음 — 현재 화면 스크린샷")
            await shot(page, "00_no_create_btn")
            return
        await asyncio.sleep(1.2)
        await fill_input(page, "스터디 모임", "날짜추출 시연")
        await asyncio.sleep(0.4)
        # 카테고리 '식사'
        await click_btn(page, "식사", contains=True)
        await asyncio.sleep(0.4)
        await click_btn(page, "모임 생성", contains=True)
        await asyncio.sleep(2.5)
        room_url = page.url
        log(f"방 생성됨: {room_url}")

        # 선호도 팝업 (있으면 처리)
        if await page_has_text(page, "평일 저녁") or await page_has_text(page, "선호"):
            await click_btn(page, "평일 저녁", contains=True)
            await fill_input(page, "강남", "강남")
            await asyncio.sleep(0.3)
            await click_btn(page, "제출", contains=True)
            await asyncio.sleep(1.5)
        await shot(page, "01_room_created")

        # AI 패널에 자유 발화 (여집합 거부)
        log(f"AI 패널 입력: {UTTERANCE}")
        if not await fill_input(page, "AI에게", UTTERANCE):
            # 일반 메시지 입력으로 폴백
            await fill_input(page, "메세지", UTTERANCE) or await fill_input(page, "메시지", UTTERANCE)
        await asyncio.sleep(0.5)
        await shot(page, "02_typed")
        await page.keyboard.press("Enter")
        log("전송 — reflect-back/일정 응답 대기 (최대 60s)")

        got_rb = await wait_text(page, "이렇게 이해했어요", timeout_s=60)
        await asyncio.sleep(2)
        await shot(page, "03_after_send")

        if got_rb:
            log("✅ reflect-back 메시지 발현 확인")
        else:
            log("⚠️ reflect-back 텍스트 미발견 — 화면 확인 필요")

        # 일정 추천/투표 카드도 폴링
        if await wait_text(page, "투표", timeout_s=20) or await wait_text(page, "추천", timeout_s=1):
            await asyncio.sleep(2)
            await shot(page, "04_schedule_card")

        # 화면 텍스트 일부 덤프 (증빙)
        body = await jeval(page, "document.body.innerText")
        rb_line = ""
        for line in (body or "").splitlines():
            if "이해했어요" in line or "어려운 날" in line:
                rb_line = line.strip()
                break
        log("=" * 60)
        log(f"reflect-back on screen: {rb_line or '(없음)'}")
        log("=" * 60)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
