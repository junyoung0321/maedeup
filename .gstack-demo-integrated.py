"""
매듭 졸업 시연 자동화 — 통합 시나리오 (9주차 노션 SoT).

배경: 4명(지민/수현/민수/예린)이 동아리 종강 회식 잡기.
ACT 0~6 풀-루프: 메인 투어 → 모임 생성 → 채팅 교착 (다음주 자동확장) →
TimeBar 시간 합의 → Partial 카드 → AI 패널 단축 + 장소 확정 → 학습 검증.

선행 셋업 (1회):
  1. docker compose up -d
  2. 평소 Chrome으로 http://localhost:3000 로그인 (지민 계정)
     - User.name == "지민" 이어야 PersonalData 시드 매칭됨
  3. F12 → 콘솔: localStorage.getItem('auth_token')
  4. 출력된 JWT를 프로젝트 루트 `.gstack-demo-token`에 저장

매 시연 (반복):
  터미널 1: python .gstack-browser-launch.py
  터미널 2: python .gstack-demo-integrated.py            # 시연 페이스
            python .gstack-demo-integrated.py --fast     # 빠른 검증
            python .gstack-demo-integrated.py --skip-act3  # TimeBar 스킵
            python .gstack-demo-integrated.py --skip-seed  # PersonalData 시드 스킵

기존 .gstack-demo.py (v2, 3명 시나리오)는 그대로 유지. 이 스크립트는 별개.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

import websockets
from playwright.async_api import Page, async_playwright

API = "http://localhost:8000"
WS = "ws://localhost:8000"
CDP = "http://localhost:9222"
ROOM_NAME = "동아리 종강 회식"

# 시나리오 박힌 거부 날짜 → 다음주 자동확장 후보.
# 시연일 2026-05-13 기준 미래 날짜로 갱신 (이전 5/8·5/9·5/10은 과거가 됨).
# - 거부 5/15(금)·5/16(토)·5/17(일) → 다음주 5/18(월) 18:00 (전원 가능)
# slot 단위는 hour (act3-verify.py 패턴, 30분 인덱스 아님)
TIMEBAR_DATE = "2026-05-18"
TIMEBAR_SLOT_START = 18
TIMEBAR_SLOT_END = 19

# ACT 2 거부 메시지 (시연일 기준 미래 거부 — 자연어 거부 → 다음주 자동확장)
ACT2_MESSAGES = [
    ("host", "다들 시험 끝나고 한번 보자!"),
    ("수현", "5월 15일 금요일은 동아리 MT라 안 돼"),
    ("민수", "16일은 본가 내려가야 해서 패스"),
    ("예린", "17일 일요일은 좀 쉬고 싶다… 다음주 어때?"),
]

PACE_FAST = {
    "between_steps": 0.3,
    "after_create": 2.5,
    "after_pref": 2.0,
    "after_seed": 1.5,
    "after_msg": 0.9,
    "after_trigger": 14.0,
    "after_act3": 12.0,
    "after_act4_partial": 4.0,
    "after_confirm": 4.0,
    "after_place_query": 16.0,
    "after_place_click": 1.5,
    "after_place_confirm": 6.0,
    "view_pause": 3.0,
    "main_tour": 4.0,
}
PACE_DEMO = {
    "between_steps": 1.2,
    "after_create": 4.0,
    "after_pref": 3.0,
    "after_seed": 2.5,
    "after_msg": 2.0,
    "after_trigger": 16.0,
    "after_act3": 16.0,
    "after_act4_partial": 6.0,
    "after_confirm": 5.0,
    "after_place_query": 18.0,
    "after_place_click": 2.5,
    "after_place_confirm": 8.0,
    "view_pause": 3.5,
    "main_tour": 7.0,
}


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def hr(label: str) -> None:
    bar = "=" * 64
    print(f"\n{bar}\n  {label}\n{bar}", flush=True)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def http(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} → {e.code}: {body_text[:300]}") from None


# ---------------------------------------------------------------------------
# Guest / WebSocket helpers
# ---------------------------------------------------------------------------

@dataclass
class Guest:
    user_id: int
    name: str
    token: str


def join_guest(room_id: int, name: str) -> Guest:
    body = http("POST", f"/api/v1/rooms/{room_id}/guest-join", {"display_name": name})
    return Guest(user_id=body["user_id"], name=body["name"], token=body["token"])


async def send_chat(room_id: int, guest: Guest, content: str) -> None:
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


async def send_time_selection(room_id: int, token: str, date: str, start: int, end: int) -> None:
    uri = f"{WS}/ws/social/{room_id}?token={token}"
    async with websockets.connect(uri) as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.4)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({
            "type": "time_selection",
            "date": date,
            "start": start,
            "end": end,
        }))
        await asyncio.sleep(0.5)


async def host_consensus_listener(
    room_id: int,
    token: str,
    date: str,
    start: int,
    end: int,
    ready_evt: asyncio.Event,
) -> dict | None:
    """호스트 토큰으로 WS 연결 후 time_selection 보내고 schedule_consensus_ready 수신."""
    uri = f"{WS}/ws/social/{room_id}?token={token}"
    async with websockets.connect(uri) as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.4)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({
            "type": "time_selection",
            "date": date,
            "start": start,
            "end": end,
        }))
        ready_evt.set()
        deadline = time.time() + 20.0
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                msg = json.loads(raw)
            except Exception:  # noqa: BLE001
                continue
            if msg.get("type") == "schedule_consensus_ready":
                return msg
        return None


# ---------------------------------------------------------------------------
# Browser (CDP via Playwright) helpers
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


async def wait_for_text(page: Page, contains: str, timeout_s: float = 30.0, poll: float = 0.5) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        found = await js_eval(
            page,
            f"Array.from(document.querySelectorAll('*')).some(e => e.children.length === 0 && e.innerText && e.innerText.includes({json.dumps(contains)}) && e.offsetParent)",
        )
        if found:
            return True
        await asyncio.sleep(poll)
    return False


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


async def url_room_id(page: Page) -> int | None:
    url = page.url
    parts = [p for p in url.rstrip("/").split("/") if p]
    if len(parts) >= 2 and parts[-2] == "meeting":
        try:
            return int(parts[-1])
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Seed Personal Data via docker exec
# ---------------------------------------------------------------------------

def seed_personal_data(room_id: int) -> bool:
    cmd = [
        "docker", "exec", "maedeup-api",
        "python", "-m", "scripts.seed_demo_personal_data",
        "--room", str(room_id),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        log("⚠️  docker CLI 없음 — 시드 스킵")
        return False
    except subprocess.TimeoutExpired:
        log("⚠️  시드 timeout 30s")
        return False
    if result.returncode != 0:
        log(f"⚠️  시드 실패 (rc={result.returncode}): {result.stderr[:300]}")
        return False
    for line in (result.stdout + result.stderr).splitlines():
        if line.strip():
            log(f"  seed | {line}")
    return True


# ---------------------------------------------------------------------------
# Demo flow
# ---------------------------------------------------------------------------

async def run_demo(args: argparse.Namespace) -> None:
    pace = PACE_FAST if args.fast else PACE_DEMO

    async with async_playwright() as p:
        log("CDP 9222 연결...")
        browser = await p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        log(f"기존 페이지: {page.url}")

        host_token = await page.evaluate("localStorage.getItem('auth_token')")
        if not host_token:
            print("\n[ERROR] localStorage에 auth_token 없음.", file=sys.stderr)
            print("Chrome 창에서 로그인하거나 토큰 주입 후 재시도하세요.", file=sys.stderr)
            return

        # 호스트 이름 확인 (시드 매칭용)
        me = http("GET", "/api/v1/users/me", token=host_token)
        host_name = me.get("name", "?")
        log(f"호스트: {host_name} (id={me.get('id')})")
        if host_name != "지민":
            log(f"⚠️  호스트 name이 '지민'이 아님 ('{host_name}'). 시드가 호스트에 매칭 안 됨.")
            log("    수현/민수 시드는 게스트 join 시 정상 매칭됨.")

        # ─────────────────────────────────────────────────
        hr("ACT 0 — 메인화면 투어 (PersonalData ✨)")
        # ─────────────────────────────────────────────────

        await page.goto("http://localhost:3000/", wait_until="networkidle", timeout=15000)
        log("홈 도착. PersonalData / MeetingList / MiniCalendar 노출")
        await asyncio.sleep(pace["main_tour"])

        # ─────────────────────────────────────────────────
        hr("ACT 1 — 모임 생성 + 게스트 3명 + PersonalData 시드")
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

        # 선호 장소는 비워둠 — Partial 카드 트리거 (ACT 4)
        log("선호 장소: (비워둠) — ACT 4 Partial 카드 트리거")
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

        log("게스트 '예린' 가입 (게스트 역할)")
        yerin = join_guest(room_id, "예린")
        log(f"  → user_id={yerin.user_id}")

        await asyncio.sleep(pace["between_steps"])

        if not args.skip_seed:
            log("PersonalData 시드 실행 (지민·수현·민수)")
            seed_personal_data(room_id)
            await asyncio.sleep(pace["after_seed"])
        else:
            log("시드 스킵 (--skip-seed)")

        # ─────────────────────────────────────────────────
        hr("ACT 2 — 채팅 교착 → 자연어 거부 → 다음주 자동확장")
        # ─────────────────────────────────────────────────

        # ACT2_MESSAGES SoT: 시연일 미래 거부 날짜
        guest_by_name = {"수현": suhyun, "민수": minsu, "예린": yerin}
        for i, (sender, content) in enumerate(ACT2_MESSAGES):
            log(f"[{sender if sender != 'host' else '지민'}] '{content}'")
            if sender == "host":
                await fill_input(page, "메세지", content)
                await asyncio.sleep(0.4)
                await page.keyboard.press("Enter")
            else:
                await send_chat(room_id, guest_by_name[sender], content)
            if i < len(ACT2_MESSAGES) - 1:
                await asyncio.sleep(pace["after_msg"])

        log(f"trigger + LLM — 추천 카드 폴링 (최대 {int(pace['after_trigger'] * 4)}s)...")
        appeared = await wait_for_button(page, "로 확정", timeout_s=pace["after_trigger"] * 4)
        if appeared:
            cards = await js_eval(
                page,
                "Array.from(document.querySelectorAll('button')).filter(b => b.innerText && b.innerText.includes('로 확정') && b.offsetParent).map(b => b.innerText.trim())",
            )
            log(f"  ✓ 추천 카드 등장: {cards[0] if cards else '?'}")
        else:
            log("  ⚠️  추천 카드 미발견 — ACT 2 시연 멘트는 불가, 다음 단계 시도")

        await asyncio.sleep(pace["view_pause"])

        if args.skip_act3:
            # ─────────────────────────────────────────────────
            hr("ACT 2b — 추천 카드 확정 (ACT 3 스킵 분기)")
            # ─────────────────────────────────────────────────
            if appeared:
                log("ACT 3 스킵 — ACT 2 카드 바로 확정")
                await click_button_by_text(page, "로 확정", contains=True)
                await asyncio.sleep(pace["after_confirm"])
            else:
                log("⚠️  카드 없어서 확정 불가, 다음 단계로")
        else:
            # ─────────────────────────────────────────────────
            hr(f"ACT 3 — TimeBar 4명 시간 합의 ({TIMEBAR_DATE} 18:00-19:00)")
            # ─────────────────────────────────────────────────
            log("4명 동시 time_selection → schedule_consensus_ready 대기")

            ready = asyncio.Event()
            host_task = asyncio.create_task(host_consensus_listener(
                room_id, host_token, TIMEBAR_DATE, TIMEBAR_SLOT_START, TIMEBAR_SLOT_END, ready,
            ))

            async def fire_guests() -> None:
                await ready.wait()
                await asyncio.sleep(0.3)
                await asyncio.gather(
                    send_time_selection(room_id, suhyun.token, TIMEBAR_DATE, TIMEBAR_SLOT_START, TIMEBAR_SLOT_END),
                    send_time_selection(room_id, minsu.token, TIMEBAR_DATE, TIMEBAR_SLOT_START, TIMEBAR_SLOT_END),
                    send_time_selection(room_id, yerin.token, TIMEBAR_DATE, TIMEBAR_SLOT_START, TIMEBAR_SLOT_END),
                )

            guests_task = asyncio.create_task(fire_guests())
            consensus = await host_task
            await guests_task

            if consensus and consensus.get("snapshot_hash"):
                log(f"  ✓ consensus_ready snapshot={(consensus['snapshot_hash'] or '')[:12]}…")
            else:
                log("  ⚠️  consensus_ready 없음 — UI 버튼 polling으로 진행")

            # 호스트 UI 버튼 클릭 (HTTP /schedule-confirm은 snapshot race로 outdated 위험).
            # 시연 흐름과 동일하게 chromium에서 [✅ 추천 시간 그대로 확정] 버튼 누름.
            log("호스트 UI [✅ 추천 시간 그대로 확정] 버튼 대기...")
            confirm_btn_seen = await wait_for_button(
                page, "추천 시간 그대로 확정", timeout_s=15.0, poll=0.5,
            )
            if confirm_btn_seen:
                await asyncio.sleep(pace["view_pause"])
                await click_button_by_text(page, "추천 시간 그대로 확정", contains=True)
                log("  ✓ 클릭 완료 → all_members_selected 트리거")
            else:
                log("  ⚠️  [✅ 추천 시간 그대로 확정] 버튼 미발견")

            log(f"all_members_selected 파이프라인 대기 ({int(pace['after_act3'])}s)")
            await asyncio.sleep(pace["after_act3"])

            # ─────────────────────────────────────────────────
            hr("ACT 4 — Partial maedeup_card 발행 (선호 장소 없음)")
            # ─────────────────────────────────────────────────
            partial_seen = await wait_for_text(page, "장소", timeout_s=pace["after_act4_partial"], poll=0.5)
            if partial_seen:
                log("  ✓ Partial 카드/장소 placeholder 노출")
            else:
                log("  ⚠️  Partial 카드 미감지 (ACT 5로 진행)")
            await asyncio.sleep(pace["view_pause"])

        # ─────────────────────────────────────────────────
        hr("ACT 5 — AI 패널 단축 + Personal Data 활용 + 장소 확정")
        # ─────────────────────────────────────────────────

        log("AI 패널에 '강남에서 다 같이 갈만한 한식집' 입력")
        if not await fill_input(page, "AI에게", "강남에서 다 같이 갈만한 한식집"):
            log("⚠️  AI 패널 입력란 못 찾음 — placeholder 'AI에게' fallback 실패")
        else:
            await asyncio.sleep(0.4)
            await page.keyboard.press("Enter")

        log("(병행) 채팅에 학습용 발언 — '나 비린 거 별로야. 회집은 빼자'")
        await asyncio.sleep(0.6)
        await fill_input(page, "메세지", "나 비린 거 별로야. 회집은 빼자")
        await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")

        log(f"장소 카드 폴링 (최대 {int(pace['after_place_query'] * 3)}s)...")
        place_appeared = await wait_for_button(page, "이 장소로 확정", timeout_s=pace["after_place_query"] * 3)
        if not place_appeared:
            log("  ⚠️  장소 카드 미발견")
        else:
            log(f"  ✓ 장소 카드 등장 — 카드 확인 시간 ({pace['view_pause']}s)")
            await asyncio.sleep(pace["view_pause"])

        clicked_place = None
        if place_appeared:
            clicked_place = await js_eval(
                page,
                """
                (() => {
                  const btn = Array.from(document.querySelectorAll('button')).find(
                    b => b.innerText && b.innerText.trim() === '이 장소로 확정' && b.offsetParent
                  );
                  if (!btn) return null;
                  let card = btn.parentElement;
                  while (card && card.offsetWidth < 200) card = card.parentElement;
                  if (!card) return null;
                  const cands = Array.from(card.querySelectorAll('span, div')).filter(e => {
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
                  if (!cands.length) return null;
                  cands.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
                  cands[0].click();
                  return cands[0].innerText.trim();
                })()
                """
            )
            log(f"첫 장소 클릭: {clicked_place}")

        if clicked_place:
            await asyncio.sleep(pace["after_place_click"])
            for _ in range(20):
                pane_open = await js_eval(
                    page,
                    "Array.from(document.querySelectorAll('*')).some(e => e.innerText && e.innerText.trim() === '장소 상세' && e.offsetParent)",
                )
                if pane_open:
                    break
                await asyncio.sleep(0.4)

            log(f"상세 확인 시간 ({pace['view_pause']}s) → 확정")
            await asyncio.sleep(pace["view_pause"])
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
                log("⚠️  PlaceDetailPane 확정 버튼 못 찾음")
            await asyncio.sleep(pace["after_place_confirm"])
        else:
            log("⚠️  장소 미클릭 — ACT 5 확정 스킵")

        # ─────────────────────────────────────────────────
        hr("ACT 6 — 메인 복귀 + PersonalData 학습 검증")
        # ─────────────────────────────────────────────────

        if args.skip_act6:
            log("ACT 6 스킵 (--skip-act6)")
        else:
            await page.goto("http://localhost:3000/", wait_until="networkidle", timeout=15000)
            await asyncio.sleep(pace["view_pause"])

            try:
                me_after = http("GET", "/api/v1/users/me", token=host_token)
                ai_filled = me_after.get("is_ai_filled") or {}
                log(f"  host food_restrictions = {me_after.get('food_restrictions')}")
                log(f"  host liked_areas       = {me_after.get('liked_areas')}")
                log(f"  host is_ai_filled keys = {list(ai_filled.keys())}")
            except RuntimeError as e:
                log(f"  ⚠️  /users/me 실패: {e}")

        # ─────────────────────────────────────────────────
        hr("결과")
        # ─────────────────────────────────────────────────
        log(f"최종 URL: {page.url}")
        log(f"방 ID: {room_id}")
        log("시연 끝. 브라우저는 그대로 유지.")


def main() -> None:
    parser = argparse.ArgumentParser(description="매듭 통합 시연 자동화 (ACT 0~6)")
    parser.add_argument("--fast", action="store_true", help="빠른 페이스 (검증용)")
    parser.add_argument("--skip-act3", action="store_true", help="ACT 3 (TimeBar) 스킵 → ACT 2 카드 직접 확정")
    parser.add_argument("--skip-seed", action="store_true", help="PersonalData 시드 스킵")
    parser.add_argument("--skip-act6", action="store_true", help="ACT 6 학습 검증 스킵")
    args = parser.parse_args()
    try:
        asyncio.run(run_demo(args))
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:  # noqa: BLE001
        print(f"\n[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
