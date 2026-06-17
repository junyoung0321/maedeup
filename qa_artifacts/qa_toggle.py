# -*- coding: utf-8 -*-
import sys, time, json, subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ART = Path(r"C:\Users\cyun0\git\maedeup\qa_artifacts")
JWT = (ART / ".hostjwt").read_text(encoding="utf-8").strip()
ROOM_URL = "http://localhost:3000/meeting/358"
GUEST_TOKEN = None
gv = Path(r"C:\Users\cyun0\git\maedeup\qa_artifacts\qa_vals.txt")
if gv.exists():
    for line in gv.read_text(encoding="utf-8").splitlines():
        if line.startswith("GUEST_TOKEN="):
            GUEST_TOKEN = line.split("=", 1)[1].strip()

results = {}
console_errors = []

def log(m):
    print("[QA]", m, flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR")
    page = ctx.new_page()
    page.on("console", lambda msg: console_errors.append(msg.type + ": " + msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append("pageerror: " + str(e)))

    page.goto("http://localhost:3000/", wait_until="domcontentloaded")
    page.evaluate("(t)=>localStorage.setItem('auth_token', t)", JWT)
    log("jwt injected")

    page.goto(ROOM_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(4500)
    log("room loaded url=" + page.url)

    # Dismiss "이번 모임 선호 정보" preference modal (z-index 1000 overlay blocks AI panel)
    for label in ["나중에 입력할게요", "닫기"]:
        b = page.get_by_text(label, exact=False)
        if b.count() > 0:
            try:
                b.first.click(timeout=2000); page.wait_for_timeout(800); log("dismissed modal via " + label); break
            except Exception as e:
                log("modal dismiss fail " + label + " " + str(e)[:80])
    # fallback: click X close button (aria/title)
    if page.get_by_text("이번 모임 선호 정보", exact=False).count() > 0:
        try:
            close_x = page.locator('button:has(svg)').filter(has_text="").last
            # try a generic close in modal header
            page.locator('div:has-text("이번 모임 선호 정보") button').first.click(timeout=2000)
            page.wait_for_timeout(600); log("dismissed modal via X")
        except Exception as e:
            log("X dismiss fail " + str(e)[:80])
    modal_gone = page.get_by_text("이번 모임 선호 정보", exact=False).count() == 0
    log("preference modal gone=" + str(modal_gone))

    ai_input = page.locator('textarea[placeholder*="AI에게 질문"], input[placeholder*="AI에게 질문"]')
    if ai_input.count() == 0:
        log("AI input not visible; scanning buttons")
        btns = page.locator("button")
        cand = []
        for i in range(min(btns.count(), 50)):
            try:
                cand.append(btns.nth(i).inner_text(timeout=400).strip()[:24])
            except Exception:
                pass
        log("buttons: " + json.dumps(cand, ensure_ascii=False))
        for kw in ["AI", "어시스턴트", "질문", "매듭"]:
            tb = page.get_by_role("button", name=kw)
            if tb.count() > 0:
                try:
                    tb.first.click(); page.wait_for_timeout(1500); log("clicked kw=" + kw); break
                except Exception as e:
                    log("click fail " + str(e))
        ai_input = page.locator('textarea[placeholder*="AI에게 질문"], input[placeholder*="AI에게 질문"]')

    page.screenshot(path=str(ART / "01_room_loaded.png"))
    if ai_input.count() == 0:
        results["ai_panel_found"] = False
        print("RESULTS=" + json.dumps(results, ensure_ascii=False))
        print("CONSOLE_ERRORS=" + json.dumps(console_errors, ensure_ascii=False))
        browser.close(); sys.exit(2)
    results["ai_panel_found"] = True
    log("AI input found")

    toggle = page.locator('button[title*="나만 보기"], button[title*="방 전체 공유"]')
    log("toggle count=" + str(toggle.count()))
    def ttext():
        try:
            return toggle.first.inner_text(timeout=1000).strip()
        except Exception:
            return "<none>"
    init_txt = ttext()
    results["toggle_render_initial"] = init_txt
    log("toggle initial=" + repr(init_txt))
    page.screenshot(path=str(ART / "02_toggle_default.png"))

    def click_toggle():
        try:
            toggle.first.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass
        try:
            toggle.first.click(timeout=4000)
            return "ok"
        except Exception as e1:
            try:
                toggle.first.click(timeout=4000, force=True)
                return "force"
            except Exception as e2:
                try:
                    toggle.first.evaluate("el=>el.click()")
                    return "jsclick"
                except Exception as e3:
                    return "FAIL:" + str(e3)[:80]

    seq = [init_txt]
    if toggle.count() > 0:
        m1 = click_toggle(); page.wait_for_timeout(700); seq.append(ttext())
        log("click1 method=" + m1)
        page.screenshot(path=str(ART / "03_toggle_private.png"))
        m2 = click_toggle(); page.wait_for_timeout(700); seq.append(ttext())
        log("click2 method=" + m2)
        page.screenshot(path=str(ART / "04_toggle_back_shared.png"))
    results["toggle_sequence"] = seq
    log("toggle seq=" + json.dumps(seq, ensure_ascii=False))

    if "나만" in ttext():
        click_toggle(); page.wait_for_timeout(500)
    log("state before send=" + ttext())

    try:
        ai_input.first.click(timeout=4000)
    except Exception as e:
        log("input click intercepted, trying force: " + str(e)[:80])
        try:
            ai_input.first.click(timeout=4000, force=True)
        except Exception:
            pass
    ai_input.first.fill("호스트공유질문테스트")
    page.wait_for_timeout(300)
    ai_input.first.press("Enter")
    page.wait_for_timeout(2500)
    body = page.locator("body").inner_text()
    results["host_msg_present"] = "호스트공유질문테스트" in body
    log("host msg present=" + str(results["host_msg_present"]))
    page.screenshot(path=str(ART / "05_host_msg_sent.png"))

    try:
        el = page.locator("text=호스트공유질문테스트").first
        results["host_align_chain"] = page.evaluate("(node)=>{let n=node,res=[];for(let i=0;i<6&&n;i++){const s=getComputedStyle(n);res.push(s.flexDirection+'|'+s.justifyContent+'|'+s.alignSelf);n=n.parentElement;}return res.join('  ');}", el.element_handle())
    except Exception as e:
        results["host_align_chain"] = "err:" + str(e)
    log("host align=" + str(results["host_align_chain"]))

    if GUEST_TOKEN:
        log("sending guest msg...")
        cp = subprocess.run([r"C:\Users\cyun0\git\maedeup\.venv\Scripts\python.exe", r"C:\Users\cyun0\git\maedeup\scripts\guest_agent_send.py", "358", GUEST_TOKEN, "게스트공유질문ABC"], capture_output=True, text=True, timeout=30)
        log("guest stdout=" + cp.stdout.strip() + " stderr=" + cp.stderr.strip()[:300])
        results["guest_helper_rc"] = cp.returncode
    else:
        results["guest_helper_rc"] = None
        log("NO GUEST TOKEN")

    page.wait_for_timeout(4500)
    body2 = page.locator("body").inner_text()
    results["guest_msg_present"] = "게스트공유질문ABC" in body2
    results["guest_speaker_label_present"] = "게스트B" in body2
    log("guest msg present=" + str(results["guest_msg_present"]) + " speaker=" + str(results["guest_speaker_label_present"]))

    try:
        gel = page.locator("text=게스트공유질문ABC").first
        chain = page.evaluate("(node)=>{let n=node,res=[];for(let i=0;i<6&&n;i++){const s=getComputedStyle(n);res.push(s.flexDirection+'|'+s.justifyContent+'|'+s.alignSelf);n=n.parentElement;}return res.join('  ');}", gel.element_handle())
        results["guest_align_chain"] = chain
        results["guest_is_left"] = ("row-reverse" not in chain)
    except Exception as e:
        results["guest_align_chain"] = "err:" + str(e)
        results["guest_is_left"] = None
    log("guest align=" + str(results.get("guest_align_chain")) + " is_left=" + str(results.get("guest_is_left")))

    page.screenshot(path=str(ART / "06_cross_user_guest_msg.png"))
    try:
        pane = page.locator('textarea[placeholder*="AI에게 질문"]').first.locator("xpath=ancestor::*[4]")
        pane.screenshot(path=str(ART / "06b_ai_panel_region.png"))
    except Exception as e:
        log("pane shot fail " + str(e))

    print("RESULTS=" + json.dumps(results, ensure_ascii=False))
    print("CONSOLE_ERRORS=" + json.dumps(console_errors, ensure_ascii=False))
    browser.close()
