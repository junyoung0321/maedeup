#!/usr/bin/env python3
"""코드베이스 로직 감사 워크플로 결과(JSON) → 영역별 markdown 문서 + INDEX 생성.

입력: wetkfntb4.output (JSON: {results:[{area,title,audit:{findings,files_reviewed,notes},verdicts}]})
출력: docs/handoff/code-audit-2026-06-03/<NN>-<area>.md + INDEX.md
부수: stdout에 digest 출력 (검토용)
"""
from __future__ import annotations
import json, html, os, sys

OUT = r"C:\Users\cyun0\AppData\Local\Temp\claude\C--Users-cyun0-git-maedeup\651ca9d9-f5f9-444b-8605-3d1e5a5535e0\tasks\wetkfntb4.output"
DOCDIR = r"C:\Users\cyun0\git\maedeup\docs\handoff\code-audit-2026-06-03"
REPO = r"C:\Users\cyun0\git\maedeup"

SEV_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "none": 4, "": 5}

def u(x):
    if x is None: return ""
    if not isinstance(x, str): x = str(x)
    return html.unescape(x)

def relpath(p):
    p = u(p).replace("/", "\\")
    if p.startswith(REPO):
        return p[len(REPO)+1:].replace("\\", "/")
    return p.replace("\\", "/")

def cell(x):
    # markdown 표 셀 안전화
    return u(x).replace("|", "/").replace("\n", " ").strip()

def load():
    with open(OUT, encoding="utf-8") as f:
        data = json.load(f)
    if "result" in data and isinstance(data["result"], dict) and "results" in data["result"]:
        return data["result"]["results"]
    return data["results"]

def eff_sev(finding, vmap):
    sid = finding.get("id")
    v = vmap.get(sid)
    base = finding.get("severity", "P3")
    if not v:
        return base, None
    verdict = v.get("verdict")
    cs = v.get("corrected_severity", "")
    if verdict == "false_positive":
        return "none", v
    if verdict == "downgraded" and cs in ("P0", "P1", "P2", "P3"):
        return cs, v
    return base, v

def main():
    os.makedirs(DOCDIR, exist_ok=True)
    results = load()
    # 영역 순서 고정용 인덱스
    area_docs = []
    master_rows = []     # active findings
    codex_rows = []      # overlaps_codex
    rejected_rows = []   # false_positive
    sev_count = {"P0":0,"P1":0,"P2":0,"P3":0}
    verdict_count = {"confirmed":0,"false_positive":0,"downgraded":0,"needs_more_context":0,"unverified":0}

    digest = []

    for idx, r in enumerate(results, 1):
        akey = r.get("area","?")
        atitle = u(r.get("title",""))
        audit = r.get("audit") or {}
        findings = audit.get("findings") or []
        files = audit.get("files_reviewed") or []
        notes = u(audit.get("notes",""))
        verdicts = r.get("verdicts") or []
        vmap = {v.get("id"): v for v in verdicts if isinstance(v, dict) and v.get("id")}

        # 정렬: effective severity, then confidence desc
        enriched = []
        for f in findings:
            es, v = eff_sev(f, vmap)
            enriched.append((es, f, v))
        enriched.sort(key=lambda t: (SEV_ORDER.get(t[0],5), -float(t[1].get("confidence",0) or 0)))

        digest.append(f"\n### [{idx:02d}] {akey} — {atitle}  ({len(findings)} findings, {len(files)} files)")

        lines = []
        lines.append(f"# 코드 감사: {atitle}\n")
        lines.append(f"> 영역키 `{akey}` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.\n")
        lines.append("## 검토 파일")
        for fp in files:
            lines.append(f"- `{relpath(fp)}`")
        lines.append("")
        if notes:
            lines.append("## 감사 노트")
            lines.append(notes + "\n")

        active = [(es,f,v) for es,f,v in enriched if es != "none"]
        rejected = [(es,f,v) for es,f,v in enriched if es == "none"]

        if active:
            lines.append("## 발견 (활성)\n")
        for es, f, v in active:
            fid = u(f.get("id"))
            codex = f.get("overlaps_codex")
            sev_count[es] = sev_count.get(es,0)+1
            vtag = ""
            if v:
                verdict = v.get("verdict")
                verdict_count[verdict] = verdict_count.get(verdict,0)+1
                if verdict == "confirmed": vtag = "✅ 검증됨"
                elif verdict == "downgraded": vtag = f"⤵ 강등됨(원래 {f.get('severity')})"
                elif verdict == "needs_more_context": vtag = "❓ 추가확인 필요"
                else: vtag = verdict
            else:
                verdict_count["unverified"] += 1
                vtag = "미검증(P2/P3)"
            codex_tag = " · ⚠겹침:Codex" if codex else ""
            lines.append(f"### [{es}] {fid} — {u(f.get('title'))}")
            lines.append(f"`{u(f.get('category'))}` · conf {f.get('confidence')}/10 · {vtag}{codex_tag}")
            lines.append("")
            lines.append(f"- **위치**: `{u(f.get('location'))}`")
            lines.append(f"- **메커니즘**: {u(f.get('mechanism'))}")
            lines.append(f"- **근거**: {u(f.get('evidence'))}")
            if f.get("repro"): lines.append(f"- **재현**: {u(f.get('repro'))}")
            lines.append(f"- **영향**: {u(f.get('impact'))}")
            lines.append(f"- **제안 수정**: {u(f.get('proposed_fix'))}")
            if v and v.get("reasoning"):
                lines.append(f"- **검증 판단**: {u(v.get('reasoning'))}")
            lines.append("")
            # index rows
            row = (es, atitle, fid, cell(f.get("title")), cell(f.get("location")), f.get("confidence"), vtag)
            if codex:
                codex_rows.append(row)
            else:
                master_rows.append(row)

        if rejected:
            lines.append("## 검증에서 기각된 항목 (false positive)\n")
            for es, f, v in rejected:
                fid = u(f.get("id"))
                lines.append(f"### ~~{fid} — {u(f.get('title'))}~~ (원래 {f.get('severity')})")
                lines.append(f"- 주장: {u(f.get('mechanism'))}")
                lines.append(f"- 기각 사유: {u(v.get('reasoning')) if v else ''}")
                lines.append("")
                rejected_rows.append((atitle, fid, cell(f.get("title")), u(v.get("reasoning")) if v else ""))

        fname = f"{idx:02d}-{akey}.md"
        with open(os.path.join(DOCDIR, fname), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        area_docs.append((idx, akey, atitle, fname, len(active), len(rejected)))

        # digest 라인
        for es, f, v in enriched:
            vd = (v.get("verdict") if v else "—")
            cflag = "C" if f.get("overlaps_codex") else " "
            digest.append(f"   [{es:>4}] {cflag} c{f.get('confidence')} {u(f.get('id')):<26} {u(f.get('title'))[:90]}  <{vd}>")

    # ---- INDEX.md ----
    idx_lines = []
    idx_lines.append("# 코드베이스 로직 감사 — INDEX (2026-06-03)\n")
    idx_lines.append("매듭 코드베이스 14영역 read-only 로직 감사. Codex가 수정 중인 멀티유저 5버그는 제외(겹치는 항목은 별도 표).")
    idx_lines.append("P0/P1은 적대적 검증자가 재확인(✅확정 / ⤵강등 / 기각). P2/P3는 미검증(1차 감사 의견).\n")
    idx_lines.append(f"- 활성 P0: **{sev_count['P0']}** · P1: **{sev_count['P1']}** · P2: **{sev_count['P2']}** · P3: **{sev_count['P3']}**")
    idx_lines.append(f"- 검증: 확정 {verdict_count['confirmed']} · 강등 {verdict_count['downgraded']} · 기각 {verdict_count['false_positive']} · 추가확인 {verdict_count['needs_more_context']} · 미검증(P2/P3) {verdict_count['unverified']}")
    idx_lines.append(f"- Codex 5버그 겹침 {len(codex_rows)} · 기각 {len(rejected_rows)}\n")

    idx_lines.append("## 영역별 문서")
    idx_lines.append("| # | 영역 | 활성 | 기각 | 문서 |")
    idx_lines.append("|---|---|---|---|---|")
    for i, akey, atitle, fname, na, nr in area_docs:
        idx_lines.append(f"| {i:02d} | {cell(atitle)} | {na} | {nr} | [`{fname}`]({fname}) |")
    idx_lines.append("")

    master_rows.sort(key=lambda x: (SEV_ORDER.get(x[0],5), -float(x[5] or 0)))
    idx_lines.append("## 활성 발견 마스터 (severity 정렬)")
    idx_lines.append("| sev | 영역 | id | 제목 | 위치 | conf | 검증 |")
    idx_lines.append("|---|---|---|---|---|---|---|")
    for es, atitle, fid, title, loc, conf, vtag in master_rows:
        idx_lines.append(f"| {es} | {cell(atitle)[:24]} | {fid} | {title} | `{loc}` | {conf} | {cell(vtag)} |")
    idx_lines.append("")

    if codex_rows:
        codex_rows.sort(key=lambda x: SEV_ORDER.get(x[0],5))
        idx_lines.append("## Codex 5버그와 겹치는 항목 (참고 — 별도 수정 중)")
        idx_lines.append("| sev | 영역 | id | 제목 | 위치 |")
        idx_lines.append("|---|---|---|---|---|")
        for es, atitle, fid, title, loc, conf, vtag in codex_rows:
            idx_lines.append(f"| {es} | {cell(atitle)[:24]} | {fid} | {title} | `{loc}` |")
        idx_lines.append("")

    if rejected_rows:
        idx_lines.append("## 검증에서 기각된 항목 (false positive)")
        idx_lines.append("| 영역 | id | 제목 | 기각 사유(요약) |")
        idx_lines.append("|---|---|---|---|")
        for atitle, fid, title, reason in rejected_rows:
            idx_lines.append(f"| {cell(atitle)[:20]} | {fid} | {title} | {cell(reason)[:120]} |")
        idx_lines.append("")

    idx_lines.append("---")
    idx_lines.append("생성: `scripts/audit_report_gen.py` (워크플로 `codebase-logic-audit` 결과 파싱). 발견 텍스트는 감사 에이전트 원문(검증 판단만 별도 표기).")

    with open(os.path.join(DOCDIR, "INDEX.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(idx_lines))

    # ---- stdout digest ----
    print("="*80)
    print("DIGEST")
    print("="*80)
    print("\n".join(digest))
    print("\n" + "="*80)
    print(f"활성 P0={sev_count['P0']} P1={sev_count['P1']} P2={sev_count['P2']} P3={sev_count['P3']}")
    print(f"검증 {verdict_count} | codex겹침={len(codex_rows)} 기각={len(rejected_rows)}")
    print(f"문서 {len(area_docs)}개 + INDEX → {DOCDIR}")

if __name__ == "__main__":
    main()
