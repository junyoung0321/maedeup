# -*- coding: utf-8 -*-
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ART = Path(r"C:\Users\cyun0\git\maedeup\qa_artifacts")
JWT = (ART / ".hostjwt").read_text(encoding="utf-8").strip()
ROOM_URL = "http://localhost:3000/meeting/358"

JS = r"""() => {
    function describe(el){
        if(!el) return null;
        return {tag: el.tagName, cls: (el.className && el.className.toString().slice(0,80)) || "", title: (el.getAttribute && el.getAttribute("title")) || "", txt: (el.innerText||"").slice(0,40)};
    }
    function chainOf(top){
        let n=top, chain=[];
        for(let i=0;i<8 && n;i++){ const s=getComputedStyle(n); chain.push(n.tagName+'.'+((n.className&&n.className.toString().slice(0,50))||'')+' z='+s.zIndex+' pos='+s.position+' pe='+s.pointerEvents); n=n.parentElement; }
        return chain;
    }
    const out = {};
    const btns = [...document.querySelectorAll('button[title]')].filter(b=>/(나만 보기|방 전체 공유)/.test(b.getAttribute('title')||''));
    const tog = btns[0];
    if(tog){
        const r = tog.getBoundingClientRect();
        const cx = r.left + r.width/2, cy = r.top + r.height/2;
        const top = document.elementFromPoint(cx, cy);
        out.toggle = {rect:{x:r.left,y:r.top,w:r.width,h:r.height}, center:[cx,cy], topEl: describe(top), isToggleItself: (top===tog) || tog.contains(top), topChain: chainOf(top)};
    } else out.toggle = "NOT FOUND";
    const inp = document.querySelector('input[placeholder*="AI에게 질문"], textarea[placeholder*="AI에게 질문"]');
    if(inp){
        const r = inp.getBoundingClientRect();
        const cx = r.left + r.width/2, cy = r.top + r.height/2;
        const top = document.elementFromPoint(cx, cy);
        out.input = {rect:{x:r.left,y:r.top,w:r.width,h:r.height}, center:[cx,cy], topEl: describe(top), isInputItself: (top===inp)||inp.contains(top), topChain: chainOf(top)};
    } else out.input = "NOT FOUND";
    return out;
}"""

def log(m): print("[DIAG]", m, flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR")
    page = ctx.new_page()
    page.goto("http://localhost:3000/", wait_until="domcontentloaded")
    page.evaluate("(t)=>localStorage.setItem('auth_token', t)", JWT)
    page.goto(ROOM_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    info = page.evaluate(JS)
    log(json.dumps(info, ensure_ascii=False, indent=2))
    page.screenshot(path=str(ART / "diag_full.png"))
    browser.close()
