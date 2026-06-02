"""날짜추출 정확도 측정 하니스 (eval set vs 실제 entity.py 추출).

컨테이너에서 실행: docker exec maedeup-api python /app/_eval_date_extraction.py [extractor]
extractor: entity (기본) | analyzer
결과 JSON을 stdout 마지막 줄에 EVAL_RESULT= 로 출력.
"""
import asyncio
import json
import sys

from app.services.pipeline.nodes.entity import _extract_entities_from_context


def _rejected_iso(result: dict) -> set:
    rd = result.get("rejected_dates") or []
    out = set()
    for r in rd:
        if isinstance(r, dict):
            d = r.get("date")
        else:
            d = r
        if isinstance(d, str) and len(d) >= 10 and d[4] == "-":
            out.add(d[:10])
    return out


async def _run_one(u: dict, sem: asyncio.Semaphore) -> dict:
    async with sem:
        state = {"room_id": "999", "db": None, "social_recent": [f"{'예린'}: {u['utterance']}"]}
        try:
            res = await _extract_entities_from_context(state)
            pred = _rejected_iso(res)
        except Exception as e:  # noqa: BLE001
            return {"id": u["id"], "error": str(e), "pred": [], "tp": 0, "fp": 0, "fn": len(u["gold_unavailable"])}
    gold = {d for d in u.get("gold_unavailable", []) if isinstance(d, str)}
    tp = len(pred & gold)
    fp = len(pred - gold)
    fn = len(gold - pred)
    return {
        "id": u["id"], "category": u["category"], "difficulty": u["difficulty"],
        "utterance": u["utterance"], "gold": sorted(gold), "pred": sorted(pred),
        "tp": tp, "fp": fp, "fn": fn,
        "exact": pred == gold,
    }


async def main():
    evalset = json.load(open("/tmp/evalset.json", encoding="utf-8"))
    sem = asyncio.Semaphore(6)
    rows = await asyncio.gather(*[_run_one(u, sem) for u in evalset])

    # aggregate
    from collections import defaultdict
    agg = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "exact": 0, "n": 0})
    for r in rows:
        for key in (r.get("category", "?"), "ALL"):
            a = agg[key]
            a["tp"] += r["tp"]; a["fp"] += r["fp"]; a["fn"] += r["fn"]
            a["exact"] += 1 if r.get("exact") else 0
            a["n"] += 1

    def prf(a):
        tp, fp, fn = a["tp"], a["fp"], a["fn"]
        p = tp / (tp + fp) if (tp + fp) else 0.0
        rc = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * p * rc / (p + rc) if (p + rc) else 0.0
        return {"precision": round(p, 3), "recall": round(rc, 3), "f1": round(f1, 3),
                "exact_rate": round(a["exact"] / a["n"], 3) if a["n"] else 0.0,
                "n": a["n"], "tp": a["tp"], "fp": a["fp"], "fn": a["fn"]}

    summary = {k: prf(v) for k, v in agg.items()}
    out = {"summary": summary, "rows": rows}
    print("EVAL_RESULT=" + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
