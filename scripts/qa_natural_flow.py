import asyncio, json, urllib.request, websockets, sys
from playwright.async_api import async_playwright

API = "http://localhost:8000"
WS = "ws://localhost:8000"
CDP = "http://localhost:9222"
TOKEN = open(".gstack-demo-token").read().strip()
RID = int(sys.argv[1])
SHOT_DIR = "C:/Users/cyun0/git/maedeup/.qa-mobile/natural"
guests = json.load(open("/tmp/guest_383.json"))


def http(m, p, t=None, b=None):
    d = json.dumps(b).encode() if b is not None else None
    h = {"Content-Type": "application/json"}
    if t:
        h["Authorization"] = f"Bearer {t}"
    return json.loads(urllib.request.urlopen(urllib.request.Request(f"{API}{p}", data=d, headers=h, method=m), timeout=15).read())


async def guest_select(rid, token, date, start, end):
    async with websockets.connect(f"{WS}/ws/social/{rid}?token={token}") as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({"type": "time_selection", "date": date, "start": start, "end": end}))
        await asyncio.sleep(0.5)


RESULTS = {}


async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = await ctx.new_page()
        errors = []
        page.on("console", lambda m: errors.append("[" + m.type + "] " + m.text) if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: errors.append("[pageerror] " + str(e)))
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto("http://localhost:3000/m/login")
        await page.evaluate('localStorage.setItem("auth_token", ' + json.dumps(TOKEN) + ')')
        await page.goto("http://localhost:3000/m/chat/ai?roomId=" + str(RID))
        await page.wait_for_timeout(6000)

        body = await page.inner_text("body")
        await page.screenshot(path=SHOT_DIR + "/01_ai_tab_entry.png", full_page=True)
        print("STEP1 entry done. body len=", len(body))

        clicked_slot = False
        for label in ["6월 16일", "6월 17일", "6월 18일", "전원 가능"]:
            try:
                el = page.get_by_text(label, exact=False).first
                if await el.count() > 0:
                    await el.click(timeout=2500)
                    clicked_slot = True
                    print("STEP2 slot click:", label)
                    break
            except Exception:
                pass
        await page.wait_for_timeout(800)
        await page.screenshot(path=SHOT_DIR + "/02_slot_selected.png", full_page=True)

        changed = False
        for lbl in ["시간대 변경", "시간 변경"]:
            try:
                el = page.get_by_text(lbl, exact=True).first
                if await el.count() == 0:
                    el = page.get_by_text(lbl, exact=False).first
                if await el.count() > 0:
                    await el.click(timeout=3000)
                    changed = True
                    print("STEP2 click:", lbl)
                    break
            except Exception:
                pass
        RESULTS["step2_time_change_clicked"] = changed
        await page.wait_for_timeout(3500)
        body2 = await page.inner_text("body")
        auto1 = any(k in body2 for k in ["멤버 일정", "가용성", "끝 시간", "내 일정", "다른 분들", "이 시간으로 확정"])
        RESULTS["AUTO_SWITCH_1_timechange_to_calendar"] = bool(auto1)
        await page.screenshot(path=SHOT_DIR + "/03_after_timechange_AUTOSWITCH1.png", full_page=True)
        print("AUTO_SWITCH_1:", auto1)

        grid_id = None
        try:
            grid_el = await page.query_selector('[role="grid"]')
            if grid_el:
                grid_id = await grid_el.get_attribute("id")
        except Exception:
            pass
        print("grid id=", grid_id)
        host_date = None
        if grid_id and grid_id.startswith("timebar-"):
            ymd = grid_id.replace("timebar-", "")
            host_date = ymd[0:4] + "-" + ymd[4:6] + "-" + ymd[6:8]
        print("host_date=", host_date)

        START_SLOT, END_SLOT = 18, 20
        host_sel_ok = False
        if grid_id:
            for idx in (START_SLOT, END_SLOT):
                sel = "#" + grid_id + "-mine-" + str(idx)
                try:
                    cell = await page.query_selector(sel)
                    if cell:
                        await cell.click(timeout=2000)
                        host_sel_ok = True
                        await page.wait_for_timeout(400)
                except Exception as e:
                    print("mine cell click err", sel, e)
        print("STEP3 host select ok=", host_sel_ok)
        await page.wait_for_timeout(1200)
        await page.screenshot(path=SHOT_DIR + "/04_host_time_selected.png", full_page=True)

        if host_date:
            for name, info in guests.items():
                await guest_select(RID, info["token"], host_date, START_SLOT, END_SLOT)
                print("  guest inject", name, host_date, START_SLOT, END_SLOT)
                await asyncio.sleep(0.4)
        await page.wait_for_timeout(3500)
        body3 = await page.inner_text("body")
        consensus = any(k in body3 for k in ["전원 합의", "모두 시간대를 골랐", "추천 시간 그대로 확정", "이 시간으로 확정"])
        RESULTS["step3_consensus_reached"] = bool(consensus)
        await page.screenshot(path=SHOT_DIR + "/05_consensus.png", full_page=True)
        print("STEP3 consensus:", consensus)

        try:
            el = page.get_by_text("이 시간으로 확정", exact=False).first
            if await el.count() > 0:
                await el.click(timeout=3000)
                print("STEP3 click 이 시간으로 확정")
        except Exception as e:
            print("err1", e)
        await page.wait_for_timeout(2500)
        await page.screenshot(path=SHOT_DIR + "/06_host_finalize.png", full_page=True)

        try:
            el = page.get_by_text("추천 시간 그대로 확정", exact=False).first
            if await el.count() > 0:
                await el.click(timeout=3000)
                print("STEP3 click 추천 시간 그대로 확정")
        except Exception as e:
            print("err2", e)
        await page.wait_for_timeout(4000)
        body4 = await page.inner_text("body")
        time_confirmed = any(k in body4 for k in ["일정이 확정되었습니다", "모임이 확정", "장소를", "장소 추천", "한식"])
        RESULTS["step3_time_confirmed"] = bool(time_confirmed)
        await page.screenshot(path=SHOT_DIR + "/07_time_confirmed.png", full_page=True)
        print("STEP3 time confirmed:", time_confirmed)

        json.dump(RESULTS, open("/tmp/qa_results_part1.json", "w"), ensure_ascii=False)
        json.dump(errors, open("/tmp/qa_console_part1.json", "w"), ensure_ascii=False)
        print("=== PART1 RESULTS ===")
        print(json.dumps(RESULTS, ensure_ascii=False, indent=2))
        print("console err/warn:", len(errors))
        for e in errors[:15]:
            print("  ", e[:180])
        await page.close()


asyncio.run(main())
