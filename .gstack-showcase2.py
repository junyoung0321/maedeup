"""
시연 showcase 2: ✨ AI 학습 데이터 시연 (브라우저 자동화)

선행 셋업 (1회):
  1. docker compose up -d
  2. 평소 Chrome으로 http://localhost:3000 로그인
  3. F12 → 콘솔: localStorage.getItem('auth_token')
  4. 출력된 JWT를 프로젝트 루트 `.gstack-demo-token` 파일에 저장
  5. (선택) 깨끗한 시연을 위해 ai_memories 사전 정리:
     docker exec maedeup-postgres psql -U maedeup -d maedeup -c \
       "DELETE FROM ai_memories WHERE user_id = (SELECT id FROM users WHERE email = 'YOUR@email');"

매 시연 (반복):
  터미널 1: python .gstack-browser-launch.py
  터미널 2: python .gstack-showcase2.py

목적:
  AI가 채팅에서 호스트의 개인 정보(식단, 선호 지역, 일정 패턴)를 학습하고
  PersonalData 패널에 ✨ 마커로 표시. ✨ 클릭하면 출처 발화까지 확인 가능.

흐름 (약 90초):
  ACT 1 — 짧은 모임 생성 + 게스트 가입 (~15s)
  ACT 2 — 호스트 발화에 개인 정보 시그널 풍부한 4메시지 → 트리거 (~25s)
  ACT 4 — vote_card 확정 (~7s)
  ACT 5 — 장소 추천 + 확정 (~20s) — 파이프라인이 memory_extraction 노드 실행
  ACT 6 — 홈으로 이동 → PersonalData 패널 → ✨ 클릭 → 출처 모달 (~25s)
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
ROOM_NAME = "AI 학습 데이터 시연"

PACE = {
    "between_steps": 1.0,
    "after_create": 3.5,
    "after_pref": 3.0,
    "after_msg": 1.8,
    "after_trigger_wait": 60.0,
    "after_confirm": 5.0,
    "after_place_query": 14.0,
    "after_place_click": 1.5,
    "after_place_confirm": 6.0,
    "view_pause": 3.0,
    "memory_settle": 4.0,         # 완료 페이지 → memory_extraction 완료 대기
    "personal_data_observe": 8.0, # ✨ 마커가 추가된 상태 관찰 시간
    "modal_observe": 10.0,        # 출처 모달 관찰 시간
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

        # Gemini 헬스체크 — quota/키 이상 시 즉시 abort
        try:
            with urllib.request.urlopen(f"{API}/api/v1/health/gemini", timeout=8) as r:
                h = json.loads(r.read())
            if not h.get("ok"):
                raise RuntimeError(f"Gemini 헬스체크 실패: {h}. quota/키 확인 필요.")
            log(f"Gemini 헬스체크 OK (응답 len={h.get('len')})")
        except Exception as e:
            raise RuntimeError(f"Gemini unavailable: {e}") from e

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
        hr("ACT 2 — 호스트 개인 정보 시그널 포함 메시지 4개")
        # ─────────────────────────────────────────────────

        # 호스트 메시지 1번은 canned data의 source_quote와 verbatim 일치 → 모달 자연스러움
        log("[호스트] '우리 이번 주에 밥 먹자! 나 매운 거 못 먹어ㅠ 안 매운 한식 어때?'")
        await fill_input(page, "메세지", "우리 이번 주에 밥 먹자! 나 매운 거 못 먹어ㅠ 안 매운 한식 어때?")
        await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")
        await asyncio.sleep(pace["after_msg"])

        log("[수현] '오 좋아 금요일 저녁 어때?'")
        await send_chat(room_id, suhyun, "오 좋아 금요일 저녁 어때?")
        await asyncio.sleep(pace["after_msg"])

        log("[민수] '금요일은 알바라 안 돼 ㅠ 토요일은?'")
        await send_chat(room_id, minsu, "금요일은 알바라 안 돼 ㅠ 토요일은?")
        await asyncio.sleep(pace["after_msg"])

        log("[호스트] '토요일은 가족 모임. 평일 저녁이 편해, 강남 자주 가니까 강남 좋아'")
        await fill_input(page, "메세지", "토요일은 가족 모임. 평일 저녁이 편해, 강남 자주 가니까 강남 좋아")
        await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")

        log("\n>>> 트리거 + LLM + sync — vote_card 폴링 (최대 60s)...")
        appeared = await wait_for_button(page, "로 확정", timeout_s=pace["after_trigger_wait"])
        if not appeared:
            log("⚠️  vote_card 미발견 — ACT 4 스킵")
            confirm_btn = []
        else:
            confirm_btn = await js_eval(
                page,
                "Array.from(document.querySelectorAll('button')).filter(b => b.innerText && b.innerText.includes('로 확정') && b.offsetParent).map(b => b.innerText)",
            )
            log(f"vote_card 발견: {confirm_btn[0] if confirm_btn else '?'}")

        # ─────────────────────────────────────────────────
        hr("ACT 4 — vote_card 확정")
        # ─────────────────────────────────────────────────
        if confirm_btn:
            await asyncio.sleep(pace["view_pause"])
            log(f"클릭: {confirm_btn[0]}")
            await click_button_by_text(page, "로 확정", contains=True)
            await asyncio.sleep(pace["after_confirm"])

        # ─────────────────────────────────────────────────
        hr("ACT 5 — 장소 추천 + 확정 (파이프라인이 memory_extraction 노드 실행)")
        # ─────────────────────────────────────────────────
        log("AI 패널에 '강남역 근처 한식 맛집 추천해줘' 입력")
        await fill_input(page, "AI에게", "강남역 근처 한식 맛집 추천해줘")
        await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")

        log("장소 카드 폴링 (최대 60s)...")
        place_appeared = await wait_for_button(page, "이 장소로 확정", timeout_s=60.0)
        if place_appeared:
            await asyncio.sleep(pace["view_pause"])
            await js_eval(page, """
                (() => {
                  const btn = Array.from(document.querySelectorAll('button')).find(
                    b => b.innerText && b.innerText.trim() === '이 장소로 확정' && b.offsetParent
                  );
                  if (!btn) return null;
                  let card = btn.parentElement;
                  while (card && card.offsetWidth < 200) card = card.parentElement;
                  const candidates = Array.from(card.querySelectorAll('span, div')).filter(e => {
                    const t = (e.innerText || '').trim();
                    return t && t.length >= 2 && t.length <= 40
                      && !t.includes('이 장소로 확정')
                      && !t.includes('%') && !t.includes('km') && !t.includes('>')
                      && e.children.length === 0 && e.offsetParent;
                  });
                  if (!candidates.length) return null;
                  candidates.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
                  candidates[0].click();
                  return candidates[0].innerText.trim();
                })()
            """)
            await asyncio.sleep(pace["after_place_click"])
            for _ in range(20):
                pane_open = await js_eval(
                    page,
                    "Array.from(document.querySelectorAll('*')).some(e => e.innerText && e.innerText.trim() === '장소 상세' && e.offsetParent)",
                )
                if pane_open:
                    break
                await asyncio.sleep(0.4)
            await asyncio.sleep(pace["view_pause"])

            log("PlaceDetailPane '이 장소로 확정' 클릭")
            await js_eval(page, """
                (() => {
                  const btns = Array.from(document.querySelectorAll('button')).filter(
                    b => b.innerText && b.innerText.trim() === '이 장소로 확정' && b.offsetParent
                  );
                  if (!btns.length) return false;
                  const wide = btns.reduce((a, b) => b.offsetWidth > a.offsetWidth ? b : a);
                  wide.click();
                  return true;
                })()
            """)
            await asyncio.sleep(pace["after_place_confirm"])
        else:
            log("⚠️  장소 카드 미발견 (60s) — 완료 페이지 건너뜀")

        log(f"완료 페이지 진입. memory_extraction 노드 안정화 대기 ({pace['memory_settle']}s)")
        await asyncio.sleep(pace["memory_settle"])

        # ─────────────────────────────────────────────────
        hr("ACT 6 — 홈 이동 + PersonalData ✨ 시연")
        # ─────────────────────────────────────────────────

        log("홈으로 이동")
        await page.goto("http://localhost:3000/", wait_until="networkidle", timeout=15000)
        await asyncio.sleep(2.0)

        log("'내 개인 데이터' 패널 영역 스크롤 + 강조")
        # 패널이 화면에 보이도록 스크롤
        scrolled = await js_eval(page, """
            (() => {
              const headers = Array.from(document.querySelectorAll('span, div')).filter(
                e => e.innerText && e.innerText.trim() === '내 개인 데이터' && e.offsetParent
              );
              if (!headers.length) return false;
              headers[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
              return true;
            })()
        """)
        if not scrolled:
            log("⚠️  '내 개인 데이터' 패널 못 찾음 — 자동 토스트만 확인")
        await asyncio.sleep(pace["personal_data_observe"])

        log("✨ 마커 검색 (AI가 학습한 항목)")
        sparkle_buttons = await js_eval(page, """
            (() => {
              const btns = Array.from(document.querySelectorAll('button')).filter(
                b => b.getAttribute('aria-label') && b.getAttribute('aria-label').includes('AI가 학습한 항목')
              );
              return btns.length;
            })()
        """)
        log(f"✨ 마커 개수: {sparkle_buttons}")

        if sparkle_buttons:
            log("첫 ✨ 마커 클릭 → 출처 모달 열기")
            await js_eval(page, """
                (() => {
                  const btns = Array.from(document.querySelectorAll('button')).filter(
                    b => b.getAttribute('aria-label') && b.getAttribute('aria-label').includes('AI가 학습한 항목')
                  );
                  if (btns.length) btns[0].click();
                })()
            """)
            # 모달 로드 대기 (receipts API 호출 시간)
            await asyncio.sleep(2.5)

            # 모달 내용 캡처 — "AI 학습 출처" SPAN → closest 모달 root → innerText
            modal_text = await js_eval(page, """
                (() => {
                  // 1. visible "AI 학습 출처" SPAN 찾기
                  const span = Array.from(document.querySelectorAll('span')).find(
                    e => e.offsetParent && (e.innerText || '').trim() === 'AI 학습 출처'
                  );
                  if (!span) return null;
                  // 2. 조상 중 모달 root (max-w-[420px] 또는 shadow-2xl 클래스 포함) 찾기
                  let el = span.parentElement;
                  while (el) {
                    const cls = el.className || '';
                    if (cls.includes('max-w-[420px]') || cls.includes('shadow-2xl')) break;
                    el = el.parentElement;
                  }
                  if (!el) return null;
                  // 3. innerText 전체 리턴 (600자 제한)
                  return el.innerText.slice(0, 600);
                })()
            """)
            if modal_text is None:
                log("출처 모달 미발견")
            elif "출처 기록이 없습니다" in modal_text:
                log(f"출처 모달 — 출처 없음 상태:\n{modal_text}")
            elif "위 발화에서" in modal_text:
                log(f"출처 모달 — quote 노출됨:\n{modal_text}")
            else:
                log(f"출처 모달 — 알 수 없는 상태:\n{modal_text}")

            log(f"모달 관찰 시간 ({pace['modal_observe']}s)")
            await asyncio.sleep(pace["modal_observe"])
        else:
            log("⚠️  ✨ 마커 미발견 — memory_extraction이 새 정보를 추출 못 했을 수 있음")
            log("    (사전 ai_memories 정리 안 했거나, 메시지에서 추출 가능한 신호 부족)")

        log("\n=== showcase 2 끝 ===")
        log("브라우저는 그대로 유지.")


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
