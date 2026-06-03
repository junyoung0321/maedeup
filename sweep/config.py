"""스윗 실행 파라미터 (스펙 §10)."""
from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass
class SweepConfig:
    rooms: int = 10
    concurrency: int = 4
    members_per_room: int = 4
    max_turns: int = 12
    seed: int = 0
    out_dir: str = "docs/handoff/robustness-sweep-2026-06-03"


def parse_args(argv: list[str] | None = None) -> SweepConfig:
    p = argparse.ArgumentParser(description="전시 견고성 스윗")
    p.add_argument("--rooms", type=int, default=10)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--members-per-room", type=int, default=4)
    p.add_argument("--max-turns", type=int, default=12)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out-dir", default="docs/handoff/robustness-sweep-2026-06-03")
    a = p.parse_args(argv)
    return SweepConfig(rooms=a.rooms, concurrency=a.concurrency,
                       members_per_room=a.members_per_room, max_turns=a.max_turns,
                       seed=a.seed, out_dir=a.out_dir)
