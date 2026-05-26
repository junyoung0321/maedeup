"""ACT 6 모달 진단 — 현재 페이지에서 ✨ 클릭 후 DOM 상태 직접 점검"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = b.contexts[0]
        page = ctx.pages[0]
        print(f"URL: {page.url}")

        # 홈으로
        if "localhost:3000" not in page.url or "meeting" in page.url:
            await page.goto("http://localhost:3000/", wait_until="networkidle", timeout=15000)
            await asyncio.sleep(2.0)

        # ✨ 버튼 자세히
        sparkles = await page.evaluate("""
            (() => {
              const btns = Array.from(document.querySelectorAll('button')).filter(
                b => b.getAttribute('aria-label') && b.getAttribute('aria-label').includes('AI가 학습한 항목')
              );
              return btns.map(b => ({
                label: b.getAttribute('aria-label'),
                text: (b.innerText||'').slice(0,40),
                visible: !!b.offsetParent,
              }));
            })()
        """)
        print(f"✨ 버튼 개수: {len(sparkles)}")
        for i, s in enumerate(sparkles):
            print(f"  [{i}] {s}")

        if not sparkles:
            print("✨ 없음 — 진단 종료")
            return

        # 첫 ✨ 클릭 (스크롤 + 클릭)
        await page.evaluate("""
            (() => {
              const btn = Array.from(document.querySelectorAll('button')).find(
                b => b.getAttribute('aria-label') && b.getAttribute('aria-label').includes('AI가 학습한 항목')
              );
              if (btn) { btn.scrollIntoView({block:'center'}); btn.click(); }
            })()
        """)
        await asyncio.sleep(3.0)

        # 화면 캡처
        await page.screenshot(path=".diag-act6-after-click.png", full_page=False)
        print("스크린샷: .diag-act6-after-click.png")

        # DOM에서 "AI 학습 출처", "위 발화에서", "AI가 학습한 항목", role=dialog 등 검색
        diag = await page.evaluate("""
            (() => {
              const findText = (needle) => {
                const matches = [];
                document.querySelectorAll('*').forEach(e => {
                  if (!e.offsetParent) return;
                  const own = Array.from(e.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
                  if (own.includes(needle)) {
                    matches.push({
                      tag: e.tagName,
                      cls: (e.className && e.className.toString && e.className.toString().slice(0,80)) || '',
                      role: e.getAttribute('role') || '',
                      ownText: own.slice(0,120),
                    });
                  }
                });
                return matches.slice(0, 5);
              };
              return {
                hasLearningSourceHeader: findText('AI 학습 출처'),
                hasQuoteIntro: findText('위 발화에서'),
                hasToast: findText('AI가 대화에서 정보를 학습'),
                dialogs: Array.from(document.querySelectorAll('[role="dialog"]')).map(d => ({
                  visible: !!d.offsetParent,
                  text: (d.innerText||'').slice(0,300),
                })),
                modalishElements: Array.from(document.querySelectorAll('[class*="modal" i],[class*="dialog" i],[class*="popup" i]')).filter(e => e.offsetParent).map(e => ({
                  tag: e.tagName,
                  cls: e.className.toString().slice(0,80),
                  text: (e.innerText||'').slice(0,200),
                })),
              };
            })()
        """)
        print("\n=== DOM 진단 ===")
        print(json.dumps(diag, ensure_ascii=False, indent=2))

asyncio.run(main())
