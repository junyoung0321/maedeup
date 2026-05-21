"""
Launch a persistent Chromium with CDP enabled.

선행 조건:
  docker compose up -d  (frontend:3000, api:8000)

토큰 자동 주입 (선택):
  프로젝트 루트에 `.gstack-demo-token` 파일을 만들고 JWT를 한 줄로 저장.
  (평소 Chrome에서 로그인 → F12 콘솔 → localStorage.getItem('auth_token') 결과)

  파일이 있으면 자동으로 localStorage에 주입 + 홈으로 이동.
  파일이 없으면 빈 chromium만 띄움 (로그인 차단됨, 직접 주입 필요).

스크립트 종료(Ctrl+C) 전까지 chromium은 유지됨.
다른 터미널에서 `python .gstack-demo.py` 실행 가능.
"""
import asyncio
import os
import pathlib

from playwright.async_api import async_playwright

USER_DATA = pathlib.Path(os.path.expanduser("~/.gstack-maedeup-profile"))
USER_DATA.mkdir(exist_ok=True)
TOKEN_FILE = pathlib.Path(__file__).parent / ".gstack-demo-token"


async def main() -> None:
    token = None
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            print(f"토큰 로드 ({TOKEN_FILE.name})")

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA),
            headless=False,
            args=[
                "--remote-debugging-port=9222",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            no_viewport=True,
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()

        if token:
            # localStorage 주입은 페이지가 그 origin에 있어야 동작 → 먼저 navigate
            await page.goto("http://localhost:3000", wait_until="domcontentloaded", timeout=15000)
            await page.evaluate(f"localStorage.setItem('auth_token', {token!r})")
            await page.goto("http://localhost:3000", wait_until="networkidle", timeout=15000)
            print("토큰 주입 완료 + 홈 이동")
        else:
            await page.goto("http://localhost:3000")
            print(f"토큰 파일 없음 ({TOKEN_FILE.name})")
            print("→ chromium에서 직접 로그인하거나 토큰 주입 필요")

        print(f"\n  CDP: http://localhost:9222")
        print(f"  Profile: {USER_DATA}")
        print(f"\n  다른 터미널에서: python .gstack-demo.py")
        print(f"  종료: Ctrl+C\n")

        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, asyncio.CancelledError):
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
