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
from sweep.driver import run_room
from sweep.personas import random_personas
from sweep.report import aggregate, go_no_go
from sweep.simulator import default_gemini_call
from sweep.transcript import RoomTranscript


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
    return await run_room(client, room_id, members,
                          gemini_call=gemini_call, max_turns=cfg.max_turns)


async def run_sweep(cfg: SweepConfig) -> None:
    client = SweepClient(load_host_token())
    gemini_call = default_gemini_call()
    sem = asyncio.Semaphore(cfg.concurrency)

    async def _guarded(i: int) -> RoomTranscript:
        async with sem:
            try:
                return await _one_room(client, i, cfg, gemini_call)
            except Exception as e:  # 방 자체가 터지면 FAIL 전사로 기록
                from sweep.invariants import Violation
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

    report = aggregate(rooms)
    summary = go_no_go(report)
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary, flush=True)
    print(f"\n전사 저장: {out.resolve()}", flush=True)


if __name__ == "__main__":
    asyncio.run(run_sweep(parse_args()))
