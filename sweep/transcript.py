"""방별 대화 전사 + JSON/Markdown 직렬화 (스펙 §9)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

from sweep.invariants import Violation


@dataclass
class Turn:
    speaker: str
    text: str
    trigger_reason: str | None
    cards: list[dict]
    latency_s: float | None


@dataclass
class RoomTranscript:
    room_id: int
    persona_keys: list[str]
    turns: list[Turn] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)

    def add_turn(self, turn: Turn) -> None:
        self.turns.append(turn)

    @property
    def passed(self) -> bool:
        return not self.violations

    @property
    def latencies(self) -> list[float]:
        return [t.latency_s for t in self.turns if t.latency_s is not None]

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "persona_keys": self.persona_keys,
            "passed": self.passed,
            "turns": [asdict(t) for t in self.turns],
            "violations": [asdict(v) for v in self.violations],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [f"## room {self.room_id} — {'PASS' if self.passed else 'FAIL'}",
                 f"personas: {', '.join(self.persona_keys)}", ""]
        for i, t in enumerate(self.turns):
            trig = f" [{t.trigger_reason}]" if t.trigger_reason else ""
            lat = f" ({t.latency_s:.2f}s)" if t.latency_s is not None else ""
            cards = f" → {[c.get('type') for c in t.cards]}" if t.cards else ""
            lines.append(f"{i}. **{t.speaker}**{trig}: {t.text}{cards}{lat}")
        if self.violations:
            lines += ["", "### 위반"]
            lines += [f"- `{v.code}`: {v.detail}" for v in self.violations]
        return "\n".join(lines)
