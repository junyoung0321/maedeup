"""
매듭 졸업 시연 자동화 스크립트 (시연 1회분 풀-루프).

선행 셋업 (1회):
  1. docker compose up -d
  2. 평소 Chrome으로 http://localhost:3000 로그인
  3. F12 → 콘솔: localStorage.getItem('auth_token')
  4. 출력된 JWT를 프로젝트 루트 `.gstack-demo-token` 파일에 저장
     (gitignore 됨 — 토큰 노출 위험 없음)

매 시연 (반복):
  터미널 1:
      python .gstack-browser-launch.py     # chromium 띄움 + 토큰 자동 주입
  터미널 2:
      python .gstack-demo.py               # 시연 페이스 (3초 view_pause)
      python .gstack-demo.py --fast        # 빠른 검증 페이스

흐름:
    ACT 1 — 방 생성 + 선호도 + 게스트 2명 가입
    ACT 2 — 채팅 4메시지 (지민 1, 수현/민수 시뮬) → 자동 트리거 + 캘린더 sync (해결점 P)
    ACT 4 — vote_card 확정
    ACT 5 — 장소 추천 → 장소명 클릭 → 장소 확정 → 모임 완료 페이지

ACT 3(TimeBar) / ACT 6(partial) 은 옵션이라 본 스크립트에서 스킵.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import urllib.request
from dataclasses import dataclass

import websockets
from playwright.async_api import Page, async_playwright

API = "http://localhost:8000"
WS = "ws://localhost:8000"
CDP = "http://localhost:9222"
ROOM_NAME = "이번 주 저녁 약속"

PACE_FAST = {
    "between_steps": 0.3,
    "after_create": 2.5,
    "after_pref": 2.5,
    "after_msg": 1.0,
    "after_trigger": 12.0,
    "after_confirm": 4.0,
    "after_place_query": 14.0,
    "after_place_click": 1.5,
    "after_place_confirm": 6.0,
    "view_pause": 3.0,  # 카드 발견 후 클릭 전 사용자가 볼 시간
}
PACE_DEMO = {
    "between_steps": 1.2,
    "after_create": 4.0,
    "after_pref": 3.5,
    "after_msg": 2.0,
    "after_trigger": 14.0,
    "after_confirm": 5.0,
    "after_place_query": 16.0,
    "after_place_click": 2.5,
    "after_place_confirm": 8.0,
    "view_pause": 3.0,
}


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def hr(label: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}\n  {label}\n{bar}", flush=True)


# ---------------------------------------------------------------------------
# Guest helpers (multi-sim 합본)
# ---------------------------------------------------------------------------

@dataclass
class Guest:
    user_id: int
    name: str
    token: str


def join_guest(room_id: str, name: str) -> Guest:
    req = urllib.request.Request(
        f"{API}/api/v1/rooms/{room_id}/guest-join",
        data=json.dumps({"display_name": name}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        body = json.loads(r.read())
    return Guest(user_id=body["user_id"], name=body["name"], token=body["token"])


async def send_chat(room_id: str, guest: Guest, content: str) -> None:
    uri = f"{WS}/ws/social/{room_id}?token={guest.token}"
    async with websockets.connect(uri) as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({
            "role": "user",
            "content": content,
            "sender": guest.name,
        }))
        await asyncio.sleep(0.6)


# ---------------------------------------------------------------------------
# Browser helpers (CDP via Playwright)
# ---------------------------------------------------------------------------

async def js_eval(page: Page, expr: str):
    return await page.evaluate(expr)


async def fill_input(page: Page, placeholder_substr: str, text: str) -> bool:
    js = f"""
    (() => {{
      const inp = Array.from(document.querySelectorAll('input,textarea')).find(
        i => i.placeholder && i.placeholder.includes({json.dumps(placeholder_substr)})
      );
      if (!inp) return false;
      const proto = inp.tagName === 'TEXTAREA'
        ? window.HTMLTextAreaElement.prototype
        : window.HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
      setter.call(inp, {json.dumps(text)});
      inp.dispatchEvent(new Event('input', {{bubbles: true}}));
      inp.focus();
      return true;
    }})()
    """
    return bool(await js_eval(page, js))


async def click_button_by_text(page: Page, text: str, contains: bool = False, nth: int = 0) -> bool:
    """Click first (or nth-by-position) button whose innerText matches.
    nth=0 means first match; if contains=True, partial match.
    """
    if contains:
        match_expr = f"b.innerText.trim().includes({json.dumps(text)})"
    else:
        match_expr = f"b.innerText.trim() === {json.dumps(text)}"
    js = f"""
    (() => {{
      const btns = Array.from(document.querySelectorAll('button')).filter(
        b => b.innerText && {match_expr} && b.offsetParent
      );
      if (!btns.length) return false;
      const i = Math.min({nth}, btns.length - 1);
      btns[i].click();
      return true;
    }})()
    """
    return bool(await js_eval(page, js))


async def click_text_node(page: Page, exact_text: str) -> bool:
    js = f"""
    (() => {{
      const t = Array.from(document.querySelectorAll('*')).find(
        e => e.innerText && e.innerText.trim() === {json.dumps(exact_text)}
          && e.children.length === 0 && e.offsetParent
      );
      if (!t) return false;
      t.click();
      return true;
    }})()
    """
    return bool(await js_eval(page, js))


async def wait_for_button(page: Page, contains: str, timeout_s: float = 30.0, poll: float = 0.5) -> bool:
    """주기적으로 폴링해서 contains 포함하는 버튼이 보이면 True."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        found = await js_eval(
            page,
            f"Array.from(document.querySelectorAll('button')).some(b => b.innerText && b.innerText.includes({json.dumps(contains)}) && b.offsetParent)",
        )
        if found:
            return True
        await asyncio.sleep(poll)
    return False


async def url_room_id(page: Page) -> str | None:
    url = page.url
    # http://localhost:3000/meeting/18/
    parts = [p for p in url.rstrip("/").split("/") if p]
    if len(parts) >= 2 and parts[-2] == "meeting":
        return parts[-1]
    return None


# ---------------------------------------------------------------------------
# Demo flow
# ---------------------------------------------------------------------------

async def run_demo(fast: bool) -> None:
    pace = PACE_FAST if fast else PACE_DEMO

    async with async_playwright() as p:
        log("CDP 9222 연결...")
        browser = await p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        log(f"기존 페이지: {page.url}")

        token = await page.evaluate("localStorage.getItem('auth_token')")
        if not token:
            print("\n[ERROR] localStorage에 auth_token 없음.", file=sys.stderr)
            print("Chrome 창에서 로그인하거나 토큰 주입 후 재시도하세요.", file=sys.stderr)
            return

        # 홈으로 이동
        await page.goto("http://localhost:3000/", wait_until="networkidle", timeout=15000)
        await asyncio.sleep(pace["between_steps"])

        # ─────────────────────────────────────────────────
        hr("ACT 1 — 방 생성 + 선호도 + 게스트 가입")
        # ─────────────────────────────────────────────────

        log("'모임 생성' 버튼 클릭")
        if not await click_button_by_text(page, "모임 생성"):
            raise RuntimeError("'모임 생성' 버튼 못 찾음")
        await asyncio.sleep(pace["after_create"])

        log(f"모임명 입력: {ROOM_NAME}")
        ok = await fill_input(page, "스터디 모임", ROOM_NAME)
        if not ok:
            raise RuntimeError("모임명 input 못 찾음")
        await asyncio.sleep(pace["between_steps"])

        log("카테고리 '식사' 선택")
        await click_button_by_text(page, "식사")
        await asyncio.sleep(pace["between_steps"])

        log("'모임 생성' 제출")
        await click_button_by_text(page, "모임 생성", contains=True)
        await asyncio.sleep(pace["after_create"])

        room_id = await url_room_id(page)
        if not room_id:
            raise RuntimeError(f"방 ID 추출 실패: {page.url}")
        log(f"방 ID = {room_id}")

        log("선호도 팝업: '평일 저녁' 클릭")
        await click_button_by_text(page, "평일 저녁")
        await asyncio.sleep(pace["between_steps"])

        log("선호 장소: '강남' 입력")
        await fill_input(page, "건대", "강남")
        await asyncio.sleep(pace["between_steps"])

        log("선호도 '제출하기'")
        await click_button_by_text(page, "제출하기")
        await asyncio.sleep(pace["after_pref"])

        log("게스트 '수현' 가입")
        suhyun = join_guest(room_id, "수현")
        log(f"  → user_id={suhyun.user_id}")

        log("게스트 '민수' 가입")
        minsu = join_guest(room_id, "민수")
        log(f"  → user_id={minsu.user_id}")

        await asyncio.sleep(pace["between_steps"])

        # ─────────────────────────────────────────────────
        hr("ACT 2 — 채팅 4메시지 → 자동 트리거")
        # ─────────────────────────────────────────────────

        log("[지민] '우리 이번 주에 밥 먹자! 언제가 좋아?'")
        await fill_input(page, "메세지", "우리 이번 주에 밥 먹자! 언제가 좋아?")
        await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")
        await asyncio.sleep(pace["after_msg"])

        log("[수현] '나는 금요일 저녁이 좋은데'")
        await send_chat(room_id, suhyun, "나는 금요일 저녁이 좋은데")
        await asyncio.sleep(pace["after_msg"])

        log("[민수] '금요일은 알바 있어서 안 돼 ㅠ 토요일은?'")
        await send_chat(room_id, minsu, "금요일은 알바 있어서 안 돼 ㅠ 토요일은?")
        await asyncio.sleep(pace["after_msg"])

        log("[수현] '토요일은 가족 모임이라 힘들어'")
        await send_chat(room_id, suhyun, "토요일은 가족 모임이라 힘들어")

        log("트리거 + LLM + sync — vote_card 버튼 폴링 (최대 60s)...")
        appeared = await wait_for_button(page, "로 확정", timeout_s=60.0)
        if not appeared:
            log("⚠️  vote_card 버튼 60s 이내 미발견 — ACT 4 스킵")
            confirm_btn = []
        else:
            confirm_btn = await js_eval(
                page,
                "Array.from(document.querySelectorAll('button')).filter(b => b.innerText && b.innerText.includes('로 확정') && b.offsetParent).map(b => b.innerText)",
            )
            log(f"vote_card 버튼 발견: {confirm_btn[0] if confirm_btn else '?'}")

        # ─────────────────────────────────────────────────
        hr("ACT 4 — vote_card 확정")
        # ─────────────────────────────────────────────────

        if confirm_btn:
            log(f"카드 확인 시간 ({pace['view_pause']}s) 후 클릭")
            await asyncio.sleep(pace["view_pause"])
            log(f"클릭: {confirm_btn[0]}")
            await click_button_by_text(page, "로 확정", contains=True)
            await asyncio.sleep(pace["after_confirm"])
        else:
            log("⚠️  vote_card 미발견 — ACT 4 스킵")

        # ─────────────────────────────────────────────────
        hr("ACT 5 — 장소 추천 → 확정")
        # ─────────────────────────────────────────────────

        log("AI 패널에 '강남역 근처 한식 맛집 추천해줘' 입력")
        await fill_input(page, "AI에게", "강남역 근처 한식 맛집 추천해줘")
        await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")

        log("장소 추천 대기 — 카드 폴링 (최대 60s)...")
        place_appeared = await wait_for_button(page, "이 장소로 확정", timeout_s=60.0)
        if not place_appeared:
            log("⚠️  장소 카드 미발견 (60s)")
        else:
            log(f"카드 확인 시간 ({pace['view_pause']}s) 후 첫 장소 클릭")
            await asyncio.sleep(pace["view_pause"])

        # 첫 장소 카드: '이 장소로 확정' 버튼의 가장 가까운 카드 컨테이너 → 가장 위에 있는 굵은 텍스트
        clicked_place = await js_eval(
            page,
            """
            (() => {
              const btn = Array.from(document.querySelectorAll('button')).find(
                b => b.innerText && b.innerText.trim() === '이 장소로 확정' && b.offsetParent
              );
              if (!btn) return null;
              // 카드 컨테이너 찾기 — 버튼의 조상 중 width 200~500px 정도의 div
              let card = btn.parentElement;
              while (card && card.offsetWidth < 200) card = card.parentElement;
              if (!card) return null;
              // 카드 내부에서 % 같은 매칭 점수 옆에 있는 굵은 텍스트 (이름)
              const candidates = Array.from(card.querySelectorAll('span, div')).filter(e => {
                const t = (e.innerText || '').trim();
                return t && t.length >= 2 && t.length <= 40
                  && !t.includes('이 장소로 확정')
                  && !t.includes('%')
                  && !t.includes('서울')
                  && !t.includes('km')
                  && !t.includes('m')
                  && !t.includes('>')
                  && e.children.length === 0
                  && e.offsetParent;
              });
              if (!candidates.length) return null;
              // 가장 위쪽(top이 작은) 노드를 장소 이름으로
              candidates.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
              const target = candidates[0];
              target.click();
              return target.innerText.trim();
            })()
            """
        )
        log(f"첫 장소 카드 클릭: {clicked_place}")

        if clicked_place:
            await asyncio.sleep(pace["after_place_click"])
            # PlaceDetailPane이 뜰 때까지 추가 폴링 (장소 상세 헤더)
            for _ in range(20):
                pane_open = await js_eval(
                    page,
                    "Array.from(document.querySelectorAll('*')).some(e => e.innerText && e.innerText.trim() === '장소 상세' && e.offsetParent)",
                )
                if pane_open:
                    break
                await asyncio.sleep(0.4)

            log(f"상세 확인 시간 ({pace['view_pause']}s) 후 확정")
            await asyncio.sleep(pace["view_pause"])

            # PlaceDetailPane의 confirm 버튼은 가장 넓은 (~300px) "이 장소로 확정"
            log("PlaceDetailPane '이 장소로 확정' 클릭")
            ok = await js_eval(
                page,
                """
                (() => {
                  const btns = Array.from(document.querySelectorAll('button')).filter(
                    b => b.innerText && b.innerText.trim() === '이 장소로 확정' && b.offsetParent
                  );
                  if (!btns.length) return false;
                  const wide = btns.reduce((a, b) => b.offsetWidth > a.offsetWidth ? b : a);
                  wide.click();
                  return true;
                })()
                """
            )
            if not ok:
                log("⚠️  '이 장소로 확정' 버튼 못 찾음")
            await asyncio.sleep(pace["after_place_confirm"])
        else:
            log("⚠️  장소 카드 미발견 — 장소 확정 스킵")

        # ─────────────────────────────────────────────────
        hr("결과")
        # ─────────────────────────────────────────────────
        final_url = page.url
        title_text = await js_eval(
            page,
            "Array.from(document.querySelectorAll('h1,h2,h3,div')).map(e => e.innerText).filter(t => t && t.includes('성공적으로')).slice(0,1)",
        )
        log(f"최종 URL: {final_url}")
        log(f"결과: {title_text}")

        log("\n시연 끝. 브라우저는 그대로 유지.")


def main() -> None:
    fast = "--fast" in sys.argv
    try:
        asyncio.run(run_demo(fast))
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
