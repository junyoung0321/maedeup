"""
시연 showcase 1: 잡담→모임 전환 자동 캐치 (브라우저 자동화)

선행 셋업 (1회):
  1. docker compose up -d
  2. 평소 Chrome으로 http://localhost:3000 로그인
  3. F12 → 콘솔: localStorage.getItem('auth_token')
  4. 출력된 JWT를 프로젝트 루트 `.gstack-demo-token` 파일에 저장

매 시연 (반복):
  터미널 1: python .gstack-browser-launch.py
  터미널 2: python .gstack-showcase1.py

목적:
  AI가 잡담은 무시하고 진짜 모임 이야기 시작점만 정확히 캐치하는 모습을 시연.
  메인 데모와 달리 처음부터 모임 4턴이 아니라, 잡담 3턴 후 모임 이야기가 시작되는
  더 현실적인 시나리오.

흐름 (약 50초):
  ACT 1 — 방 생성 + 선호도 + 게스트 2명 가입 (~15s)
  ACT 2 — 잡담 3턴 (AI 무반응) → 모임 5턴 (어느 시점에 AI 자동 개입) (~35s)

PACE_DEMO로 메시지 사이 1.5~2초 간격 → 화면에서 잡담 부분 AI 무반응이 명확히 보임.
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
ROOM_NAME = "잡담하다 모임 잡기 시연"

PACE = {
    "between_steps": 1.2,
    "after_create": 4.0,
    "after_pref": 3.5,
    "after_msg_chitchat": 2.2,   # 잡담 사이 — 시청자가 AI 무반응 확인할 시간
    "after_msg_meeting": 1.8,    # 모임 메시지 사이 — 트리거 도달까지
    "after_trigger_wait": 60.0,
}


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def hr(label: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}\n  {label}\n{bar}", flush=True)


# ---------------------------------------------------------------------------
# Guest helpers
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


async def wait_for_button(page: Page, contains: str, timeout_s: float = 30.0, poll: float = 0.5) -> bool:
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
    parts = [p for p in url.rstrip("/").split("/") if p]
    if len(parts) >= 2 and parts[-2] == "meeting":
        return parts[-1]
    return None


# ---------------------------------------------------------------------------
# Showcase flow
# ---------------------------------------------------------------------------

async def run_showcase() -> None:
    pace = PACE

    async with async_playwright() as p:
        log("CDP 9222 연결...")
        browser = await p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        log(f"기존 페이지: {page.url}")

        token = await page.evaluate("localStorage.getItem('auth_token')")
        if not token:
            print("\n[ERROR] localStorage에 auth_token 없음.", file=sys.stderr)
            return

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
        if not await fill_input(page, "스터디 모임", ROOM_NAME):
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
        hr("ACT 2 — 잡담 3턴 (AI 무반응) → 모임 5턴 (AI 자동 개입)")
        # ─────────────────────────────────────────────────

        # 잡담 — AI는 절대 발동 안 함 (NOTIFIABLE intent 아님, counter=0 유지)
        log("[잡담 1] 지민: '오늘 점심 뭐 먹었어?'")
        await fill_input(page, "메세지", "오늘 점심 뭐 먹었어?")
        await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")
        await asyncio.sleep(pace["after_msg_chitchat"])

        log("[잡담 2] 수현: '치킨 시켜먹었어 ㅎㅎ'")
        await send_chat(room_id, suhyun, "치킨 시켜먹었어 ㅎㅎ")
        await asyncio.sleep(pace["after_msg_chitchat"])

        log("[잡담 3] 민수: 'ㅋㅋ 나는 김밥'")
        await send_chat(room_id, minsu, "ㅋㅋ 나는 김밥")
        await asyncio.sleep(pace["after_msg_chitchat"])

        log(">>> 여기까지는 AI 무반응 (잡담은 카운터 +0)")
        await asyncio.sleep(2.0)  # 시청자가 무반응 확인할 시간

        # 모임 이야기 시작 — AI가 NOTIFIABLE intent로 카운터 쌓기 시작
        log("[모임 1] 지민: '근데 우리 이번 주에 한번 모이자'")
        await fill_input(page, "메세지", "근데 우리 이번 주에 한번 모이자")
        await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")
        await asyncio.sleep(pace["after_msg_meeting"])

        log("[모임 2] 수현: '오 좋아 금요일 저녁 어때?'")
        await send_chat(room_id, suhyun, "오 좋아 금요일 저녁 어때?")
        await asyncio.sleep(pace["after_msg_meeting"])

        log("[모임 3] 민수: '금요일은 알바라 안 돼'")
        await send_chat(room_id, minsu, "금요일은 알바라 안 돼")
        await asyncio.sleep(pace["after_msg_meeting"])

        log("[모임 4] 수현: '그럼 토요일?'")
        await send_chat(room_id, suhyun, "그럼 토요일?")
        await asyncio.sleep(pace["after_msg_meeting"])

        log("[모임 5] 지민: '토요일은 가족 모임'")
        await fill_input(page, "메세지", "토요일은 가족 모임")
        await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")

        log("\n>>> AI 자동 개입 대기 (vote_card 폴링, 최대 60s)...")
        appeared = await wait_for_button(page, "로 확정", timeout_s=pace["after_trigger_wait"])
        if appeared:
            confirm_btn = await js_eval(
                page,
                "Array.from(document.querySelectorAll('button')).filter(b => b.innerText && b.innerText.includes('로 확정') && b.offsetParent).map(b => b.innerText)",
            )
            log(f"⚡ AI 개입 성공 — vote_card 등장: {confirm_btn[0] if confirm_btn else '?'}")
            log("(시청자가 vote_card 확인할 수 있도록 10초 대기)")
            await asyncio.sleep(10.0)
        else:
            log("⚠️  vote_card 미발견 (60s) — 트리거 확인 필요")

        log("\n=== showcase 1 끝 ===")
        log("브라우저는 그대로 유지. 영상 컷 다음 단계로 진행하세요.")


def main() -> None:
    try:
        asyncio.run(run_showcase())
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
