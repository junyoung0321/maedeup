"""K2 자동 측정 runner — 자유 입력 50개 → 트리거/intent/slot 결과 표.

K2.1 트리거 발화율: should_trigger=true 발화 중 intent가 NOTIFIABLE
  (meeting_schedule / place_suggestion) 로 분류된 비율.
  — 실제 WS 트리거 이벤트는 3+ 메시지 누적 후 발생하므로 단건 측정에 부적합.
    intent 분류 기반으로 "이 발화가 트리거할 의도를 가졌는가"를 측정.

K2.2 intent 정확도: POST /api/v1/intents/classify 결과 top-1 vs expected_intent.

K2.3 slot robustness: backend가 단건 classify API에서 slot을 반환하지 않으므로
  expected_slot == {} (빈 dict) 인 경우만 정확 match로 집계. 별 트랙 확인 필요.
  현재는 baseline 수치 기록 목적으로만 출력.

사용:
  ~/.venv-maedeup-demo/bin/python3 .gstack-k2-runner.py --room-id <ROOM>
  ~/.venv-maedeup-demo/bin/python3 .gstack-k2-runner.py \\
    --fixture .gstack-fixtures/k2-free-inputs.json --room-id 100 --limit 3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

API = "http://localhost:8000"

# K2.1: NOTIFIABLE intent = should_trigger 가능 intent 목록
_NOTIFIABLE_INTENTS = {"meeting_schedule", "place_suggestion"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def load_fixture(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_token() -> str:
    return Path(".gstack-demo-token").read_text().strip()


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# classify: POST /api/v1/intents/classify
# ---------------------------------------------------------------------------

async def classify_one(
    client: httpx.AsyncClient,
    token: str,
    text: str,
) -> dict:
    """단일 발화 intent 분류 → {intent, confidence} 반환."""
    resp = await client.post(
        f"{API}/api/v1/intents/classify",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": text},
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "intent": data.get("intent"),
        "confidence": data.get("confidence"),
        # slot: classify endpoint 는 slot 미반환 — empty dict 로 기록
        "slot": data.get("slot") or {},
    }


# ---------------------------------------------------------------------------
# 집계
# ---------------------------------------------------------------------------

def aggregate(results: list[dict]) -> dict:
    total = len(results)

    # K2.1: should_trigger=true 발화 중 NOTIFIABLE intent 분류된 비율
    expected_trigger_n = sum(1 for r in results if r["expected"]["should_trigger"])
    triggered_n = sum(
        1 for r in results
        if r["expected"]["should_trigger"]
        and r["observed"]["intent"] in _NOTIFIABLE_INTENTS
    )

    # K2.2: intent top-1 정확도
    correct_intent_n = sum(
        1 for r in results
        if r["observed"]["intent"] == r["expected"].get("expected_intent")
    )

    # K2.3: slot robustness — observed slot vs expected_slot dict equality
    # classify API 는 slot 미반환이므로 observed["slot"]={} 가 기본값.
    # expected_slot={} 인 entry 만 match 됨 — baseline 수치 기록용.
    correct_slot_n = sum(
        1 for r in results
        if r["observed"]["slot"] == r["expected"].get("expected_slot", {})
    )

    return {
        "K2.1_trigger_rate": triggered_n / max(expected_trigger_n, 1),
        "K2.2_intent_accuracy": correct_intent_n / total,
        "K2.3_slot_robustness": correct_slot_n / total,
        "total": total,
        "expected_trigger_n": expected_trigger_n,
        "triggered_n": triggered_n,
        "correct_intent_n": correct_intent_n,
        "correct_slot_n": correct_slot_n,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

async def main() -> int:
    parser = argparse.ArgumentParser(
        description="K2 자유 입력 자동 측정 — 트리거율/intent 정확도/slot robustness"
    )
    parser.add_argument(
        "--fixture",
        default=".gstack-fixtures/k2-free-inputs.json",
        help="fixture JSON 경로 (default: .gstack-fixtures/k2-free-inputs.json)",
    )
    parser.add_argument(
        "--room-id",
        type=int,
        required=False,
        default=None,
        help="측정 룸 ID (현재 미사용 — classify API 는 room-independent. 향후 WS 트리거 측정 확장용)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="dry run 용 fixture 개수 제한 (예: --limit 3)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="각 발화 사이 대기 시간(초) — Gemini rate limit 회피 (default: 0.3)",
    )
    args = parser.parse_args()

    fixture = load_fixture(args.fixture)
    if args.limit:
        fixture = fixture[: args.limit]

    token = load_token()

    print(
        f"[K2] === N={len(fixture)} "
        f"fixture={args.fixture} "
        f"delay={args.delay}s ===",
        flush=True,
    )

    results = []
    async with httpx.AsyncClient() as client:
        for i, item in enumerate(fixture):
            try:
                observed = await classify_one(client, token, item["input"])
            except Exception as exc:
                log(f"[WARN] classify 실패 id={item['id']}: {type(exc).__name__}: {exc}")
                observed = {"intent": None, "confidence": None, "slot": {}}

            results.append({"id": item["id"], "expected": item, "observed": observed})

            triggered_mark = (
                "✓" if (
                    item["should_trigger"]
                    and observed["intent"] in _NOTIFIABLE_INTENTS
                )
                else "✗"
            )
            intent_match = "=" if observed["intent"] == item.get("expected_intent") else "≠"
            print(
                f"  [{i + 1:02d}/{len(fixture)}] {item['id']} "
                f"K2.1={triggered_mark} "
                f"intent={observed['intent']!r}{intent_match}{item.get('expected_intent')!r} "
                f"conf={observed['confidence']!r} "
                f"input={item['input'][:28]!r}",
                flush=True,
            )

            if i < len(fixture) - 1:
                await asyncio.sleep(args.delay)

    summary = aggregate(results)
    print(f"\n[K2.SUMMARY] === N={summary['total']} ===", flush=True)
    print(
        f"  K2.1 트리거 발화율  : {summary['K2.1_trigger_rate']:.1%}"
        f" ({summary['triggered_n']}/{summary['expected_trigger_n']} expected-trigger)",
        flush=True,
    )
    print(
        f"  K2.2 intent 정확도  : {summary['K2.2_intent_accuracy']:.1%}"
        f" ({summary['correct_intent_n']}/{summary['total']})",
        flush=True,
    )
    print(
        f"  K2.3 slot robustness: {summary['K2.3_slot_robustness']:.1%}"
        f" ({summary['correct_slot_n']}/{summary['total']})"
        f"  [NOTE: classify API는 slot 미반환 — expected_slot={{}} 인 항목만 match]",
        flush=True,
    )
    print("[K2.SUMMARY] === end ===\n", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
