"""전시 견고성 스윗 엔트리포인트.

실행 (Windows):  .venv\\Scripts\\python.exe .gstack-robustness-sweep.py --rooms 30 --concurrency 8
사전조건: docker compose up -d / .gstack-demo-token / GEMINI_API_KEY
"""
from __future__ import annotations

import asyncio
import random
from pathlib import Path

from sweep.client import SweepClient
from sweep.config import SweepConfig, parse_args
from sweep.driver import run_room, run_scenario
from sweep.invariants import Violation
from sweep.personas import PERSONAS, random_personas
from sweep.report import aggregate, go_no_go
from sweep.scenarios import CORE_SCENARIOS
from sweep.simulator import default_gemini_call
from sweep.transcript import RoomTranscript

# persona_key → label 매핑 (run_scenario 에 전달)
_PERSONA_LABEL_BY_KEY: dict[str, str] = {p.key: p.label for p in PERSONAS}

# 동시 투표 경합 검사를 활성화할 방 인덱스 범위 (처음 2개)
_VOTE_STORM_ROOMS = 2


def _safe_print(msg: str) -> None:
    """Windows cp949 콘솔에서 한글/특수문자 인코딩 오류 없이 출력."""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", errors="replace").decode("ascii", errors="replace"), flush=True)


def load_host_token() -> str:
    return Path(".gstack-demo-token").read_text().strip()


async def _one_room(client: SweepClient, idx: int, cfg: SweepConfig,
                    gemini_call) -> RoomTranscript:
    rng = random.Random(cfg.seed + idx)
    personas = random_personas(cfg.members_per_room, rng)
    room_id = await client.create_room(f"sweep-{idx}")
    members = []
    for p in personas:
        join = await client.guest_join(room_id, f"{p.label}-{idx}")
        members.append((p, join))
    # GOAL 3: 처음 _VOTE_STORM_ROOMS 개 방에서 동시 투표 경합 검사 활성화
    enable_storm = idx < _VOTE_STORM_ROOMS
    return await run_room(client, room_id, members,
                          gemini_call=gemini_call, max_turns=cfg.max_turns,
                          enable_vote_storm=enable_storm)


async def run_sweep(cfg: SweepConfig) -> None:
    client = SweepClient(load_host_token())
    gemini_call = default_gemini_call()
    sem = asyncio.Semaphore(cfg.concurrency)

    async def _guarded(i: int) -> RoomTranscript:
        async with sem:
            try:
                return await _one_room(client, i, cfg, gemini_call)
            except Exception as e:  # 방 자체가 터지면 FAIL 전사로 기록
                t = RoomTranscript(room_id=-i, persona_keys=[])
                t.violations.append(Violation("room_crashed", repr(e)))
                return t

    try:
        rooms = await asyncio.gather(*[_guarded(i) for i in range(cfg.rooms)])
    finally:
        await client.aclose()

    out = Path(cfg.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for r in rooms:
        (out / f"room-{r.room_id}.json").write_text(r.to_json(), encoding="utf-8")
        (out / f"room-{r.room_id}.md").write_text(r.to_markdown(), encoding="utf-8")

    # GOAL 1: 정확성 시나리오 (CORE_SCENARIOS) — --scenarios 옵트인 시에만 실행
    scenario_results: dict[str, list[str]] = {}
    if cfg.scenarios != "off":
        _safe_print(f"\n[시나리오 정확성 검사] CORE_SCENARIOS 실행 중 (--scenarios={cfg.scenarios})...")
        scenario_client = SweepClient(load_host_token())
        try:
            for scenario in CORE_SCENARIOS:
                _safe_print(f"  {scenario.key}: {scenario.key} ...")
                key, failures = await run_scenario(
                    scenario_client, scenario,
                    host_token=load_host_token(),
                    persona_label_by_key=_PERSONA_LABEL_BY_KEY,
                )
                scenario_results[key] = failures
                status = "PASS" if not failures else f"FAIL ({len(failures)} failures)"
                _safe_print(f"  {scenario.key}: {status}")
        finally:
            await scenario_client.aclose()
    else:
        _safe_print("\n[시나리오 정확성 검사] 건너뜀 (--scenarios=off, 기본값). 활성화: --scenarios core")

    # GOAL 2: aggregate에 scenario_results 전달
    report = aggregate(rooms, scenario_results=scenario_results)
    summary = go_no_go(report)
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    _safe_print(summary)
    _safe_print(f"\n전사 저장: {out.resolve()}")


if __name__ == "__main__":
    asyncio.run(run_sweep(parse_args()))
