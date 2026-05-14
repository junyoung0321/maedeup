"""
매듭 졸업 시연 자동화 스크립트 — v3 시나리오 풀 자동화 (8 ACT 구조).

선행 셋업 (1회):
  1. docker compose up -d
  2. 평소 Chrome으로 http://localhost:3000 로그인
  3. F12 → 콘솔: localStorage.getItem('auth_token')
  4. 출력된 JWT를 프로젝트 루트 `.gstack-demo-token` 파일에 저장
     (gitignore 됨 — 토큰 노출 위험 없음)
  5. (선택) D-1 시드: `docker exec maedeup-api python -m scripts.seed_demo_personal_data --room <id>`
     → ACT 0.5 ✨ 노출 + ACT 5 reasoning 이름 인용 + ACT 5.5 hybrid 토글 활성 조건 충족용.

매 시연 (반복) — Windows PowerShell + `.venv\\Scripts\\python.exe` 사용 (WSL 금지, BUG-1):
  터미널 1:
      .venv\\Scripts\\python.exe .gstack-browser-launch.py
  터미널 2:
      .venv\\Scripts\\python.exe .gstack-demo.py               # 시연 페이스
      .venv\\Scripts\\python.exe .gstack-demo.py --fast        # 빠른 검증 페이스

v3 시나리오 흐름 (총 ~5:25):
    ACT 0.5 — Personal Data 모달 사전 투어 (40s, ✨ 6 카테고리)
    ACT 1   — 방 생성 + 선호도 + 게스트 3명(수현·민수·예린) 가입 (25s)
    ACT 2   — 채팅 4메시지 (강한 자연어 거부 + 다음주 확장) (40s)
    ACT 2.5 — F1 다수결 fallback vote_card 자동 발행 (30s, 자동 흐름)
    ACT 3   — ★시간대 변경 → 게스트 3명 vote → 방장 확정 팝업 (35s)
    ACT 4   — Partial maedeup_card 자동 발행 (10s, 자동 흐름)
    ACT 5   — AI 패널 "강남 한식 추천해줘" → 장소 확정 (30s)
    ACT 5.5 — Q5 hybrid 토글 ("내 선호") + F4 narrator (25s)

CLI 인자:
    --fast              빠른 검증 페이스 (latency 단축)
    --v2-mode           v2 흐름만 (ACT 0.5·3·5.5 모두 스킵)
    --skip-act-0-5      Personal Data 모달 자동 클릭 스킵
    --skip-act-3        시간 투표 스킵 (B-8 fallback: vote_card 바로 확정)
    --skip-act-5-5      Q5 hybrid 토글 스킵
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
    # v3 신규
    "act_0_5_modal_pause": 5.0,    # PersonalData 모달 펼친 후 시연자 narration
    "act_3_vote_gap": 0.6,          # 게스트 3명 vote API 호출 사이 간격
    "act_3_after_change": 1.5,      # "시간대 변경" 클릭 후 VoteCardSection 렌더 대기
    "act_3_after_popup": 1.0,       # 확정 팝업 렌더 대기
    "act_5_5_after_toggle": 4.0,    # "내 선호" 토글 클릭 후 refresh API + carousel rerender
    "act_5_5_view_pause": 3.0,      # refreshed carousel narration
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
    # v3 신규 (시연 페이스)
    "act_0_5_modal_pause": 8.0,
    "act_3_vote_gap": 1.0,
    "act_3_after_change": 2.5,
    "act_3_after_popup": 1.5,
    "act_5_5_after_toggle": 7.0,
    "act_5_5_view_pause": 5.0,
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


def get_pending_meeting_id(room_id: str, host_token: str) -> int | None:
    """GET /api/v1/meetings/rooms/{room_id}/pending-vote → meeting_id 추출.

    ACT 3에서 vote API를 호출하려면 meeting_id가 필요한데, vote_card payload는
    WebSocket으로만 프론트에 전달되므로 REST 엔드포인트로 별도 조회.
    """
    try:
        req = urllib.request.Request(
            f"{API}/api/v1/meetings/rooms/{room_id}/pending-vote",
            headers={"Authorization": f"Bearer {host_token}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            body = json.loads(r.read())
        if isinstance(body, dict) and "meeting_id" in body:
            return int(body["meeting_id"])
    except Exception as e:  # noqa: BLE001
        log(f"[WARN] pending-vote 조회 실패: {type(e).__name__}: {e}")
    return None


def vote_as_user(meeting_id: int, token: str, option_index: int, name_hint: str = "") -> bool:
    """게스트 한 명으로 POST /api/v1/meetings/{meeting_id}/vote.

    토큰 노출 방지: 본 함수는 로그에 토큰을 출력하지 않음 (name_hint만 출력).
    """
    try:
        req = urllib.request.Request(
            f"{API}/api/v1/meetings/{meeting_id}/vote",
            data=json.dumps({"option_index": int(option_index)}).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            _ = r.read()
        log(f"  ✓ vote: {name_hint or '?'} → option_index={option_index}")
        return True
    except Exception as e:  # noqa: BLE001
        # B-8 대응: 4xx (만료 토큰·중복 vote 등) → log + skip
        log(f"  [BACKUP] vote 실패 ({name_hint}): {type(e).__name__}: {e}")
        return False


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


async def wait_for_text(page: Page, contains: str, timeout_s: float = 10.0, poll: float = 0.4) -> bool:
    """버튼/링크가 아닌 일반 텍스트 노드 폴링 (모달/배너 등)."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        found = await js_eval(
            page,
            f"Array.from(document.querySelectorAll('*')).some(e => e.innerText && e.innerText.includes({json.dumps(contains)}) && e.offsetParent)",
        )
        if found:
            return True
        await asyncio.sleep(poll)
    return False


async def click_first_vote_slot(page: Page) -> bool:
    """ScheduleRecommendationCard의 첫 슬롯 카드 클릭 (selectedSlotId 세팅).

    ScheduleRecommendationCard.tsx:419~424 — Best 슬롯 div는 padding "12px 14px",
    borderRadius 12, cursor pointer 인 클릭 가능 div.
    ScheduleRecommendationCard.tsx:486~492 — 대안 슬롯도 동일 패턴 (padding "10px 12px").

    주의: React inline style은 DOM에서 hex → rgb()로 변환되므로
    hex 문자열 (#e2e8f0, #4f46e5)로 style 매칭 불가.
    대신 cursor:pointer + border-radius + 충분한 너비로 슬롯 카드 식별.

    전략 1 (primary): '추천' 배지 span을 포함한 조상 div 클릭 (Best 슬롯 확실히 선택)
    전략 2 (backup-A): cursor:pointer + borderRadius + 시간 텍스트(오전/오후) 포함 div
    전략 3 (backup-B): cursor:pointer + border 속성 있는 카드 div 중 최상단
    """
    # 전략 1: '추천' 배지 span → closest clickable parent div 클릭
    js1 = """
    (() => {
      // '추천' 텍스트를 담은 span 중 인디고 색(rgb(79, 70, 229)) 또는 fontSize 11 + fontWeight 600인 것
      const badges = Array.from(document.querySelectorAll('span')).filter(s => {
        return s.innerText && s.innerText.trim() === '추천' && s.offsetParent;
      });
      if (!badges.length) return false;
      // 각 badge의 조상 중 cursor:pointer이며 너비 100px 이상인 div
      for (const badge of badges) {
        let el = badge.parentElement;
        while (el && el.tagName !== 'BODY') {
          if (el.tagName === 'DIV') {
            const cs = window.getComputedStyle(el);
            if (cs.cursor === 'pointer' && el.offsetWidth > 100) {
              el.click();
              return true;
            }
          }
          el = el.parentElement;
        }
      }
      return false;
    })()
    """
    if bool(await js_eval(page, js1)):
        return True

    # 전략 2 (backup-A): 시간 텍스트(오전/오후) 포함 div 중 cursor:pointer
    js2 = """
    (() => {
      const cands = Array.from(document.querySelectorAll('div')).filter(d => {
        if (!d.offsetParent || d.offsetWidth < 100 || d.offsetWidth > 700) return false;
        const cs = window.getComputedStyle(d);
        if (cs.cursor !== 'pointer') return false;
        const br = parseFloat(cs.borderRadius || '0');
        if (br < 8) return false;
        const txt = d.innerText || '';
        return txt.includes('오전') || txt.includes('오후');
      });
      if (!cands.length) return false;
      cands.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
      cands[0].click();
      return true;
    })()
    """
    if bool(await js_eval(page, js2)):
        return True

    # 전략 3 (backup-B): cursor:pointer + border 있는 카드형 div 최상단
    js3 = """
    (() => {
      const cands = Array.from(document.querySelectorAll('div')).filter(d => {
        if (!d.offsetParent || d.offsetWidth < 100 || d.offsetWidth > 700) return false;
        const cs = window.getComputedStyle(d);
        if (cs.cursor !== 'pointer') return false;
        const br = parseFloat(cs.borderRadius || '0');
        if (br < 8) return false;
        // border가 실제 적용돼 있어야 함 (none/0px 제외)
        return cs.borderStyle !== 'none' && cs.borderWidth !== '0px';
      });
      if (!cands.length) return false;
      cands.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
      cands[0].click();
      return true;
    })()
    """
    return bool(await js_eval(page, js3))


async def click_personal_data_widget(page: Page) -> bool:
    """홈 메인의 PersonalData 위젯 클릭 — '데이터 추가하기' 버튼 또는 Pencil 아이콘.

    PersonalData.tsx:396~402 — '데이터 추가하기' 버튼이 항상 노출되며 openModal() 호출.
    PersonalData.tsx:236~239 — Pencil 아이콘도 동일 openModal().
    """
    # 1순위: '데이터 추가하기' 버튼 (안정적 텍스트 매칭)
    if await click_button_by_text(page, "데이터 추가하기", contains=True):
        return True
    # 2순위: '내 개인 데이터' 헤더 옆 Pencil — text 매칭이 어렵므로 fallback
    js = """
    (() => {
      const headers = Array.from(document.querySelectorAll('span')).filter(
        s => s.innerText && s.innerText.trim() === '내 개인 데이터' && s.offsetParent
      );
      if (!headers.length) return false;
      const card = headers[0].closest('div[class*="rounded"]') || headers[0].parentElement;
      const pencil = card ? card.querySelector('svg.lucide-pencil') : null;
      if (pencil) { pencil.parentElement.click(); return true; }
      return false;
    })()
    """
    return bool(await js_eval(page, js))


async def close_personal_data_modal(page: Page) -> bool:
    """PersonalDataModal 닫기 — 모달의 X 또는 backdrop 클릭."""
    js = """
    (() => {
      // X 버튼 (close aria-label) 우선
      const xBtn = Array.from(document.querySelectorAll('button')).find(
        b => (b.getAttribute('aria-label') || '').includes('close') && b.offsetParent
      );
      if (xBtn) { xBtn.click(); return true; }
      // 취소 또는 닫기 텍스트 버튼
      const cancelBtn = Array.from(document.querySelectorAll('button')).find(
        b => b.innerText && (b.innerText.trim() === '취소' || b.innerText.trim() === '닫기') && b.offsetParent
      );
      if (cancelBtn) { cancelBtn.click(); return true; }
      return false;
    })()
    """
    return bool(await js_eval(page, js))


async def click_preference_toggle(page: Page, label: str = "내 선호") -> bool:
    """PlaceRecommendationCard.tsx:204~251 hybrid 토글 클릭.

    `[그룹 다수결] [내 선호]` 토글 중 label에 해당하는 button 클릭.
    aria-pressed=false 인 버튼만 활성 클릭 대상 (이미 active면 onClick early return).

    P2 fix: 검색 범위를 PlaceRecommendationCard 컨테이너 내부로 제한.
    PlaceRecommendationCard.tsx:198 — "장소 추천" span이 카드 헤더 내 유일 텍스트.
    PlaceRecommendationCard.tsx:183 — outer div background="#f1f5f9"(rgb(241,245,249)), borderRadius:18.
    해당 span을 앵커로 closest 조상 div(background rgb(241,245,249))를 카드 루트로 특정 →
    그 안에서만 토글 버튼 탐색.
    ScheduleRecommendationCard는 background="#f8fafc"(rgb(248,250,252)) → 색이 달라 교차 매칭 없음.
    """
    js = f"""
    (() => {{
      // 1단계: "장소 추천" 헤더 span → PlaceRecommendationCard 컨테이너 특정
      const header = Array.from(document.querySelectorAll('span')).find(
        s => s.innerText && s.innerText.trim() === '장소 추천' && s.offsetParent
      );
      // 컨테이너 후보: header 조상 중 background가 rgb(241, 245, 249) 인 div
      let container = null;
      if (header) {{
        let el = header.parentElement;
        while (el && el.tagName !== 'BODY') {{
          if (el.tagName === 'DIV') {{
            const bg = window.getComputedStyle(el).backgroundColor;
            if (bg === 'rgb(241, 245, 249)') {{
              container = el;
              break;
            }}
          }}
          el = el.parentElement;
        }}
      }}
      // 2단계: 컨테이너 내부에서만 토글 탐색 (fallback: 전체 DOM 중 가장 아래쪽 매칭 버튼)
      const scope = container || document;
      const btns = Array.from(scope.querySelectorAll('button')).filter(
        b => b.innerText && b.innerText.trim() === {json.dumps(label)} && b.offsetParent
      );
      if (!btns.length) {{
        // fallback: 컨테이너 미발견 시 DOM 위치 가장 아래쪽 버튼 (최근 렌더된 카드가 PlaceCard 가정)
        const allBtns = Array.from(document.querySelectorAll('button')).filter(
          b => b.innerText && b.innerText.trim() === {json.dumps(label)} && b.offsetParent
        );
        if (!allBtns.length) return 'not_found';
        allBtns.sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top);
        const last = allBtns[0];
        if (last.getAttribute('aria-pressed') !== 'false' || last.disabled) return 'already_active';
        last.click();
        return 'clicked_fallback';
      }}
      // aria-pressed=false 또는 disabled 아닌 첫 번째
      const target = btns.find(b => b.getAttribute('aria-pressed') === 'false' && !b.disabled);
      if (!target) return 'already_active';
      target.click();
      return 'clicked';
    }})()
    """
    result = await js_eval(page, js)
    if result in ("clicked", "clicked_fallback"):
        if result == "clicked_fallback":
            log(f"  [INFO] '{label}' 토글: PlaceCard 컨테이너 미발견, DOM 최하단 버튼 fallback 사용")
        return True
    log(f"  [BACKUP] '{label}' 토글: {result}")
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

@dataclass
class DemoFlags:
    fast: bool = False
    skip_act_0_5: bool = False
    skip_act_3: bool = False
    skip_act_5_5: bool = False

    @property
    def v2_mode(self) -> bool:
        return self.skip_act_0_5 and self.skip_act_3 and self.skip_act_5_5


async def run_demo(flags: DemoFlags) -> None:
    pace = PACE_FAST if flags.fast else PACE_DEMO

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

        # 홈으로 이동
        await page.goto("http://localhost:3000/", wait_until="networkidle", timeout=15000)
        await asyncio.sleep(pace["between_steps"])

        # ─────────────────────────────────────────────────
        if not flags.skip_act_0_5:
            hr("ACT 0.5 — Personal Data 모달 사전 투어 (✨ 6 카테고리)")
            # ─────────────────────────────────────────────────
            log("Personal Data 위젯 노출 대기 (최대 5s)...")
            shown = await wait_for_text(page, "내 개인 데이터", timeout_s=5.0)
            if not shown:
                log("[BACKUP] PersonalData 위젯 미렌더 — ACT 0.5 스킵")
            else:
                log("PersonalData 위젯 클릭 → 모달 열기")
                if not await click_personal_data_widget(page):
                    log("[BACKUP] '데이터 추가하기' / Pencil 클릭 실패 — ACT 0.5 스킵")
                else:
                    # 모달 펼침 후 시연자 narration 시간 확보
                    log(f"모달 펼침 — {pace['act_0_5_modal_pause']}s 동안 6 카테고리 노출")
                    await asyncio.sleep(pace["act_0_5_modal_pause"])
                    log("모달 닫기")
                    if not await close_personal_data_modal(page):
                        log("[BACKUP] 모달 닫기 실패 — ESC 키 시도")
                        await page.keyboard.press("Escape")
                    await asyncio.sleep(pace["between_steps"])
        else:
            log("[FLAG] --skip-act-0-5 — Personal Data 모달 스킵")

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

        log("게스트 '예린' 가입 (카톡 링크 시뮬 — ACT 3 vote용)")
        yerin = join_guest(room_id, "예린")
        log(f"  → user_id={yerin.user_id}")

        await asyncio.sleep(pace["between_steps"])

        # ─────────────────────────────────────────────────
        hr("ACT 2 — 채팅 교착 → 강한 자연어 거부 → 다음주 확장")
        # ─────────────────────────────────────────────────

        log("[지민] '다들 시험 끝나고 한번 보자!'")
        await fill_input(page, "메세지", "다들 시험 끝나고 한번 보자!")
        await asyncio.sleep(0.4)
        await page.keyboard.press("Enter")
        await asyncio.sleep(pace["after_msg"])

        # D-1 #1: 수현 발화 강화 — 5/13~5/16 + 5/19·5/20 직접 열거 (28일 확장 후 busy_by_user non-empty 보장)
        suhyun_msg = (
            "5/8 금요일은 동아리 MT라 안 되고, 5/13·5/14·5/15·5/16도 시험 기간이라 다 안 돼. "
            "다음주 5/19·5/20도 발표 준비 때문에 일정 잡혀있어"
        )
        log(f"[수현] {suhyun_msg[:30]}... (강화된 거부)")
        await send_chat(room_id, suhyun, suhyun_msg)
        await asyncio.sleep(pace["after_msg"])

        log("[민수] '9일은 본가 내려가야 해서 패스'")
        await send_chat(room_id, minsu, "9일은 본가 내려가야 해서 패스")
        await asyncio.sleep(pace["after_msg"])

        log("[예린] '10일 토요일은 좀 쉬고 싶다… 다음주도 사실 5/11 빼고 다 바빠'")
        await send_chat(room_id, yerin, "10일 토요일은 좀 쉬고 싶다… 다음주도 사실 5/11 빼고 다 바빠")

        # ─────────────────────────────────────────────────
        hr("ACT 2.5 — F1 다수결 fallback vote_card 자동 발행")
        # ─────────────────────────────────────────────────
        # P1 fix: vote_card 발현 신호는 "추천" 배지(안정적 텍스트)로 먼저 감지.
        # ScheduleRecommendationCard:449~454 — 베스트 슬롯 div 내 "추천" 배지 span이
        # selectedSlotId 여부와 무관하게 카드 렌더 시점부터 항상 존재.
        # "로 확정" 텍스트는 selectedSlotId 세팅 후에야 나타나므로 여기서 폴링하면 안 됨.
        log("트리거 + LLM + sync — vote_card '추천' 배지 폴링 (최대 60s)...")
        vote_card_appeared = await wait_for_text(page, "AI 일정 추천", timeout_s=60.0)
        if not vote_card_appeared:
            log("⚠️  vote_card 60s 이내 미발견 — ACT 3/4 스킵")
            confirm_btn = []
        else:
            log("vote_card 발현 확인 (AI 일정 추천 헤더 노출)")
            # 슬롯 클릭 먼저 수행 → selectedSlotId 세팅 → 그 후 "로 확정" 버튼 텍스트 생성
            log("vote_card 슬롯 사전 클릭 (selectedSlotId 세팅 — '로 확정' 텍스트 생성용)")
            pre_slot_ok = await click_first_vote_slot(page)
            if not pre_slot_ok:
                await asyncio.sleep(0.8)
                pre_slot_ok = await click_first_vote_slot(page)
            if pre_slot_ok:
                await asyncio.sleep(0.5)
            # 이제 "로 확정" 버튼이 렌더됐는지 확인 (최대 5s)
            appeared = await wait_for_button(page, "로 확정", timeout_s=5.0)
            if not appeared:
                log("⚠️  슬롯 클릭 후에도 '로 확정' 버튼 미발견 — fallback: confirm_btn 비움")
                confirm_btn = []
            else:
                confirm_btn = await js_eval(
                    page,
                    "Array.from(document.querySelectorAll('button')).filter(b => b.innerText && b.innerText.includes('로 확정') && b.offsetParent).map(b => b.innerText)",
                )
                log(f"vote_card 버튼 발견: {confirm_btn[0] if confirm_btn else '?'}")

        # ─────────────────────────────────────────────────
        # ACT 3 — ★시간대 변경 → 게스트 vote → 방장 확정
        # ─────────────────────────────────────────────────
        act3_completed = False
        if confirm_btn and not flags.skip_act_3:
            hr("ACT 3 — ★시간대 변경 → 게스트 3명 vote → 방장 확정 팝업")

            # step 0: 슬롯 선택 확보 (ACT 2.5에서 이미 클릭했으나 re-click으로 선택 상태 보장).
            # ScheduleRecommendationCard:424 — 동일 슬롯 재클릭은 setSelectedSlotId(same) → 무해.
            log("step 0 — vote_card 슬롯 선택 확보 (ACT 2.5 선택 상태 재확인)")
            slot_ok = await click_first_vote_slot(page)
            if not slot_ok:
                log("[BACKUP] 슬롯 클릭 실패 — 1회 재시도")
                await asyncio.sleep(0.8)
                slot_ok = await click_first_vote_slot(page)
            if not slot_ok:
                log("[BACKUP] 슬롯 클릭 재시도 실패 — ACT 3 스킵, ACT 4로 fallback")
            else:
                await asyncio.sleep(0.8)

                # step 1: "시간대 변경" 버튼 클릭
                log("step 1 — '시간대 변경' 버튼 클릭")
                changed = await click_button_by_text(page, "시간대 변경")
                if not changed:
                    log("[BACKUP] '시간대 변경' 버튼 클릭 실패 — ACT 3 스킵")
                else:
                    await asyncio.sleep(pace["act_3_after_change"])

                    # step 2: meeting_id 조회 → 게스트 3명 vote API 호출
                    log("step 2 — meeting_id 조회 + 게스트 3명 vote API 호출")
                    meeting_id = get_pending_meeting_id(room_id, host_token)
                    if meeting_id is None:
                        log("[BACKUP] meeting_id 조회 실패 — ACT 3 vote 스킵")
                    else:
                        log(f"  meeting_id = {meeting_id}")
                        # 수현 → 0, 민수 → 0, 예린 → 1 (만장일치 아니어도 conflict 시연용)
                        vote_as_user(meeting_id, suhyun.token, 0, name_hint="수현")
                        await asyncio.sleep(pace["act_3_vote_gap"])
                        vote_as_user(meeting_id, minsu.token, 0, name_hint="민수")
                        await asyncio.sleep(pace["act_3_vote_gap"])
                        vote_as_user(meeting_id, yerin.token, 1, name_hint="예린")
                        await asyncio.sleep(pace["act_3_vote_gap"] + 1.0)

                        # step 3: 지민(방장)도 vote — VoteCardSection의 "투표하기" 버튼
                        log("step 3 — 방장(지민) '투표하기' 클릭")
                        # 첫 번째 "투표하기" 버튼 클릭 (슬롯 0 투표)
                        host_vote_clicked = await click_button_by_text(page, "투표하기")
                        if not host_vote_clicked:
                            log("[BACKUP] 방장 '투표하기' 미발견 — host_token 직접 vote")
                            vote_as_user(meeting_id, host_token, 0, name_hint="지민(방장)")
                        await asyncio.sleep(pace["act_3_after_change"])

                        # step 4: "일정 확정하기" 클릭 (방장만 활성) → 팝업 → "확정하기"
                        log("step 4 — '일정 확정하기' 클릭 → 팝업 대기")
                        finalize_ok = await wait_for_button(page, "일정 확정하기", timeout_s=10.0)
                        if not finalize_ok:
                            log("[BACKUP] '일정 확정하기' 버튼 미활성 — ACT 4로 fallback")
                        else:
                            await click_button_by_text(page, "일정 확정하기")
                            await asyncio.sleep(pace["act_3_after_popup"])

                            # 팝업의 "확정하기" 클릭 (취소 아님)
                            log("step 5 — 확정 팝업 '확정하기' 클릭")
                            popup_ok = await click_button_by_text(page, "확정하기")
                            if not popup_ok:
                                log("[BACKUP] '확정하기' 버튼 미발견")
                            else:
                                await asyncio.sleep(pace["after_confirm"])
                                act3_completed = True
                                log("ACT 3 완료 — 시간 확정 → Partial maedeup_card 자동 발행 예정")

        # ─────────────────────────────────────────────────
        hr("ACT 4 — Partial maedeup_card 자동 발행" + (" (ACT 3 skip → vote_card 직접 확정)" if not act3_completed else ""))
        # ─────────────────────────────────────────────────

        if not act3_completed and confirm_btn:
            # B-8 시나리오 4 fallback: ACT 3 우회 → vote_card "○월 ○일로 확정" 직접 클릭
            log(f"카드 확인 시간 ({pace['view_pause']}s) 후 vote_card 확정")
            await asyncio.sleep(pace["view_pause"])
            log(f"클릭: {confirm_btn[0]}")
            await click_button_by_text(page, "로 확정", contains=True)
            await asyncio.sleep(pace["after_confirm"])
        elif act3_completed:
            # ACT 3에서 이미 확정 → maedeup_card (partial) WebSocket 수신 대기만
            log(f"Partial 카드 발행 대기 ({pace['view_pause']}s)")
            await asyncio.sleep(pace["view_pause"])
        else:
            log("⚠️  vote_card 미발견 — ACT 4 스킵")

        # ─────────────────────────────────────────────────
        hr("ACT 5 — 장소 추천 → 확정")
        # ─────────────────────────────────────────────────

        # D-1 #5: 짧은 입력으로 변경 — direct_request 트리거 단축 경로
        log("AI 패널에 '강남 한식 추천해줘' 입력 (v3: 짧은 발화)")
        await fill_input(page, "AI에게", "강남 한식 추천해줘")
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
        # ACT 5.5 — Q5 hybrid 토글 ("내 선호") + F4 narrator
        # ─────────────────────────────────────────────────
        toggle_clicked = False
        if not flags.skip_act_5_5:
            hr("ACT 5.5 — Q5 hybrid 토글 ('내 선호') + F4 실명 narrator")

            # step 1: "내 선호" 토글 노출 대기 (preference_toggle_enabled=true 조건)
            log("'내 선호' 토글 노출 대기 (최대 10s)...")
            toggle_visible = await wait_for_button(page, "내 선호", timeout_s=10.0)
            if not toggle_visible:
                # B-5 대응: preference_toggle_enabled=false → 토글 미노출. ACT 5.5 스킵.
                log("[BACKUP] '내 선호' 토글 미노출 (preference_toggle_enabled=false 추정) — ACT 5.5 스킵")
            else:
                log("step 1 — '내 선호' 토글 클릭")
                toggle_clicked = await click_preference_toggle(page, "내 선호")
                if not toggle_clicked:
                    log("[BACKUP] 토글 클릭 실패 — ACT 5.5 스킵")
                else:
                    # step 2: refresh API 응답 + carousel rerender 대기
                    log(f"refresh API + carousel rerender 대기 ({pace['act_5_5_after_toggle']}s)")
                    await asyncio.sleep(pace["act_5_5_after_toggle"])

                    # step 3: narrator 노출 확인 ("님 선호 기준으로 다시 추천했어요")
                    narrator_shown = await wait_for_text(page, "선호 기준", timeout_s=5.0)
                    if narrator_shown:
                        log("  ✓ narrator: '○○님 선호 기준으로 다시 추천했어요' 노출 확인")
                    else:
                        log("  [INFO] narrator 미확인 — refresh는 실행됐을 수 있음 (Idempotency 캐시 가능)")

                    log(f"refreshed carousel narration ({pace['act_5_5_view_pause']}s)")
                    await asyncio.sleep(pace["act_5_5_view_pause"])
        else:
            log("[FLAG] --skip-act-5-5 — Q5 hybrid 토글 스킵")

        # ─────────────────────────────────────────────────
        hr("결과 검증 (verify_demo_completion)")
        # ─────────────────────────────────────────────────
        final_url = page.url
        # 1. 모임 완료/확정 텍스트
        title_text = await js_eval(
            page,
            "Array.from(document.querySelectorAll('h1,h2,h3,div')).map(e => e.innerText).filter(t => t && (t.includes('성공적으로') || t.includes('확정되었'))).slice(0,2)",
        )
        # 2. ACT 5.5 narrator 자취 (선택)
        narrator_trace = await js_eval(
            page,
            "Array.from(document.querySelectorAll('*')).map(e => (e.innerText || '').trim()).filter(t => t.includes('선호 기준으로') && t.length < 80).slice(0, 1)",
        )

        log(f"[VERIFY] 최종 URL: {final_url}")
        log(f"[VERIFY] 확정/완료 텍스트: {title_text}")
        log(f"[VERIFY] ACT 5.5 narrator 자취: {narrator_trace}")
        log(f"[VERIFY] ACT 3 완료={act3_completed}, ACT 5.5 토글 클릭={toggle_clicked}")
        if flags.v2_mode:
            log("[VERIFY] v2-mode 실행 — ACT 0.5·3·5.5 모두 스킵 흐름")

        log("\n시연 끝. 브라우저는 그대로 유지.")


def main() -> None:
    argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return

    # v2-mode = ACT 0.5·3·5.5 모두 스킵 (구 v2 흐름 재현)
    v2_mode = "--v2-mode" in argv
    flags = DemoFlags(
        fast="--fast" in argv,
        skip_act_0_5=v2_mode or "--skip-act-0-5" in argv,
        skip_act_3=v2_mode or "--skip-act-3" in argv,
        skip_act_5_5=v2_mode or "--skip-act-5-5" in argv,
    )

    log(
        f"[FLAGS] fast={flags.fast} v2_mode={flags.v2_mode} "
        f"skip_0.5={flags.skip_act_0_5} skip_3={flags.skip_act_3} skip_5.5={flags.skip_act_5_5}"
    )
    try:
        asyncio.run(run_demo(flags))
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
