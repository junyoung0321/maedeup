# 전시 견고성 스윗 (Robustness Sweep) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 임의의 다자 대화를 LLM 시뮬레이터로 생성해 실 백엔드(/ws/social·/ws/agent·REST)에 흘려보내고, 하드 불변조건·동시성·핵심 시나리오 정확성을 자동 검증한 뒤 전사를 남겨 GO/NO-GO를 판정하는 단일 스윗 스크립트.

**Architecture:** 순수 로직(페르소나·불변조건·전사·리포트·시나리오)은 `sweep/` 패키지의 테스트 가능한 모듈로 분리하고, 라이브 오케스트레이션(REST/WS 클라이언트·대화 구동·asyncio 동시 구동)은 그 위에 얹는다. 엔트리포인트는 기존 `.gstack-*.py` 관례를 따르는 루트 스크립트 `.gstack-robustness-sweep.py`. LLM 심판관은 스크립트 밖 Claude가 전사를 읽어 수행.

**Tech Stack:** Python 3.11, asyncio, httpx, websockets, google-generativeai (GEMINI_API_KEY), pytest. 백엔드를 import하지 않고 HTTP/WS로만 통신 (기존 러너와 동일).

**Spec:** `docs/superpowers/specs/2026-06-03-robustness-sweep-design.md`

---

## File Structure

```
sweep/
  __init__.py
  personas.py      # 페르소나 7종 정의 + 템플릿 발화 뱅크 (순수)
  invariants.py    # 하드 불변조건 체커 (순수 함수, Violation 반환)
  transcript.py    # Turn/RoomTranscript 데이터클래스 + JSON/MD 직렬화 (순수)
  report.py        # 퍼센타일·집계·GO/NO-GO 합성 (순수)
  scenarios.py     # S1~S10 다자 결정적 시나리오 + 기대 카드 assert (순수)
  client.py        # SweepClient: REST + WS 래퍼 (라이브)
  simulator.py     # 발화 생성: gemini_call 주입 + 템플릿 fallback (혼합)
  driver.py        # run_room: 방 1개 대화 구동 루프 (라이브)
  config.py        # SweepConfig 데이터클래스 + argparse (순수)
  tests/
    __init__.py
    test_personas.py
    test_invariants.py
    test_transcript.py
    test_report.py
    test_scenarios.py
    test_simulator.py
.gstack-robustness-sweep.py   # 엔트리포인트: argparse → run_sweep → 출력 디렉터리
```

**테스트 실행 환경**: `.venv-test\Scripts\python.exe -m pytest sweep/tests/ -v` (memory: pytest는 `.venv-test`). `sweep/`은 백엔드 의존성이 없으므로 어떤 pytest 환경이든 가능. 테스트는 gitignore 가능성이 있어 커밋 시 `git add -f`.

**라이브 사전조건**: `docker compose up -d` 기동, `.gstack-demo-token`에 host JWT, `GEMINI_API_KEY` 환경변수.

---

## Task 0: 패키지 스캐폴드 + 의존성 확인

**Files:**
- Create: `sweep/__init__.py`
- Create: `sweep/tests/__init__.py`

- [ ] **Step 1: 패키지 디렉터리 생성**

`sweep/__init__.py` 내용:
```python
"""전시 견고성 스윗 — 임의 다자 대화 검증 하니스."""
```

`sweep/tests/__init__.py`: 빈 파일.

- [ ] **Step 2: 의존성 확인**

Run (PowerShell): `.venv-test\Scripts\python.exe -c "import httpx, websockets, google.generativeai; print('ok')"`
Expected: `ok` 출력. 누락 시 `pip install httpx websockets google-generativeai` (CLAUDE.md: 외부 패키지 임의 추가 금지 → 이미 backend/requirements.txt에 존재하므로 신규 아님).

- [ ] **Step 3: Commit**

```bash
git add -f sweep/__init__.py sweep/tests/__init__.py
git commit -m "chore(sweep): 견고성 스윗 패키지 스캐폴드"
```

---

## Task 1: 페르소나 + 템플릿 발화 뱅크

**Files:**
- Create: `sweep/personas.py`
- Test: `sweep/tests/test_personas.py`

- [ ] **Step 1: Write the failing test**

```python
# sweep/tests/test_personas.py
import random
from sweep.personas import PERSONAS, Persona, random_personas, fallback_utterance


def test_seven_personas_defined():
    keys = {p.key for p in PERSONAS}
    assert keys == {
        "host", "lurker", "rejector", "vague_time",
        "guest", "terse", "off_topic",
    }
    for p in PERSONAS:
        assert isinstance(p, Persona)
        assert p.system_prompt.strip()
        assert len(p.fallback_bank) >= 3


def test_random_personas_always_includes_host_and_count():
    rng = random.Random(42)
    chosen = random_personas(4, rng)
    assert len(chosen) == 4
    assert any(p.key == "host" for p in chosen), "방엔 항상 추진할 host가 1명 필요"
    # 결정적: 같은 시드면 같은 조합
    rng2 = random.Random(42)
    assert [p.key for p in random_personas(4, rng2)] == [p.key for p in chosen]


def test_fallback_utterance_is_deterministic_and_nonempty():
    p = next(p for p in PERSONAS if p.key == "rejector")
    u0 = fallback_utterance(p, 0)
    u1 = fallback_utterance(p, 1)
    assert u0 and u1
    assert u0 != u1  # 턴마다 다른 발화
    # 뱅크를 순환
    assert fallback_utterance(p, len(p.fallback_bank)) == p.fallback_bank[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_personas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sweep.personas'`

- [ ] **Step 3: Write minimal implementation**

```python
# sweep/personas.py
"""멤버 페르소나 정의 + Gemini 미가용 시 템플릿 발화 뱅크."""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    system_prompt: str
    fallback_bank: tuple[str, ...]
    hidden_goal: str


PERSONAS: list[Persona] = [
    Persona(
        key="host", label="주도형 호스트",
        system_prompt=(
            "너는 모임을 적극적으로 추진하는 호스트다. 날짜/장소를 직접 제안하고 "
            "결정을 재촉한다. '다음주에 모이자', '강남에서 보자' 같이 구체적으로 말한다."
        ),
        fallback_bank=(
            "다음주에 다 같이 모이자!", "강남에서 저녁 어때?",
            "날짜 정하자, 다들 언제 돼?", "내가 장소 추천받아볼게.",
        ),
        hidden_goal="모임을 확정까지 끌고 간다",
    ),
    Persona(
        key="lurker", label="잠수형",
        system_prompt="너는 대화에 거의 참여하지 않는다. 가끔 한 마디만 한다.",
        fallback_bank=("음..", "글쎄", "난 아무거나", "ㅇㅇ"),
        hidden_goal="최소한만 반응",
    ),
    Persona(
        key="rejector", label="까다로운 거절러",
        system_prompt=(
            "너는 제안되는 날짜를 자꾸 거절한다. 여러 요일을 연달아 안 된다고 한다."
        ),
        fallback_bank=(
            "월요일은 안돼", "화요일도 좀..", "주말은 가족 일정 있어",
            "그 시간엔 회사야", "다음주는 다 바빠",
        ),
        hidden_goal="대부분의 슬롯을 거절해 교착을 유발",
    ),
    Persona(
        key="vague_time", label="모호한 시간러",
        system_prompt="너는 시간을 항상 모호하게 말한다. 확정 표현을 피한다.",
        fallback_bank=("다다음주 언제쯤?", "조만간 보자", "나중에 적당히", "언젠가 한번"),
        hidden_goal="비확정 시간 표현으로 슬롯 추출을 어렵게 함",
    ),
    Persona(
        key="guest", label="게스트",
        system_prompt="너는 외부 게스트다. 캘린더 연동이 없고 일정 정보를 모른다.",
        fallback_bank=("저는 맞춰갈게요", "아무때나 괜찮아요", "정해지면 알려주세요"),
        hidden_goal="가용성 데이터 없이 흐름에 합류",
    ),
    Persona(
        key="terse", label="단답·이모지형",
        system_prompt="너는 아주 짧게, 이모지나 한두 글자로만 답한다.",
        fallback_bank=("ㅇㅋ", "👍", "ㄱㄱ", "아무때나", "🙆"),
        hidden_goal="초단답으로 의도 분류를 시험",
    ),
    Persona(
        key="off_topic", label="주제 이탈러",
        system_prompt="너는 모임 얘기 중간에 딴소리(잡담, 농담)를 섞는다.",
        fallback_bank=(
            "아 근데 어제 그 드라마 봤어?", "배고프다 ㅋㅋ",
            "참 그 얘기 들었어?", "날씨 미쳤다",
        ),
        hidden_goal="주제 이탈로 트리거 오판을 시험",
    ),
]

_BY_KEY = {p.key: p for p in PERSONAS}


def random_personas(n: int, rng: random.Random) -> list[Persona]:
    """host 1명을 반드시 포함해 n명 페르소나를 결정적으로 뽑는다."""
    host = _BY_KEY["host"]
    others = [p for p in PERSONAS if p.key != "host"]
    picked = rng.sample(others, k=min(n - 1, len(others)))
    return [host, *picked]


def fallback_utterance(persona: Persona, turn_index: int) -> str:
    """Gemini 미가용 시 뱅크에서 턴 인덱스로 순환 선택."""
    bank = persona.fallback_bank
    return bank[turn_index % len(bank)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_personas.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add -f sweep/personas.py sweep/tests/test_personas.py
git commit -m "feat(sweep): 페르소나 7종 + 템플릿 발화 뱅크"
```

---

## Task 2: 하드 불변조건 체커

**Files:**
- Create: `sweep/invariants.py`
- Test: `sweep/tests/test_invariants.py`

- [ ] **Step 1: Write the failing test**

```python
# sweep/tests/test_invariants.py
from sweep.invariants import (
    Violation, check_frame, check_card_payload, check_latency_budget,
    check_state_consistency,
)


def test_error_frame_flagged():
    v = check_frame({"type": "error", "detail": "boom"})
    assert any(x.code == "ws_error_frame" for x in v)


def test_clean_frame_ok():
    assert check_frame({"type": "vote_card", "meeting_id": 1}) == []


def test_vote_card_missing_options_flagged():
    v = check_card_payload({"type": "vote_card", "time_options": []})
    assert any(x.code == "vote_card_no_options" for x in v)


def test_maedeup_card_requires_date_and_place():
    v = check_card_payload({"type": "maedeup_card", "confirmed_date": None,
                            "confirmed_place": None})
    codes = {x.code for x in v}
    assert "maedeup_no_date" in codes and "maedeup_no_place" in codes


def test_place_reco_empty_results_flagged():
    v = check_card_payload({"type": "place_recommendation", "places": []})
    assert any(x.code == "place_reco_empty" for x in v)


def test_latency_budget_p95():
    # 모두 8s 이내 → 통과
    assert check_latency_budget([1.0, 2.0, 3.0, 4.0], p95_budget_s=8.0) == []
    # 하나가 9s → p95 위반
    v = check_latency_budget([1.0, 2.0, 3.0, 9.0], p95_budget_s=8.0)
    assert any(x.code == "latency_p95_exceeded" for x in v)


def test_state_consistency_recos_must_clear_after_finalize():
    # 확정됐는데 추천 카드가 화면에 남아있음 → 위반 (회귀 566b98e)
    v = check_state_consistency(finalized=True, active_reco_cards=2, active_vote_cards=1)
    codes = {x.code for x in v}
    assert "stale_cards_after_finalize" in codes


def test_state_consistency_vote_count_monotonic():
    v = check_state_consistency(finalized=False, active_reco_cards=0,
                                active_vote_cards=1, vote_count_drop=True)
    assert any(x.code == "vote_count_decreased" for x in v)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_invariants.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sweep.invariants'`

- [ ] **Step 3: Write minimal implementation**

```python
# sweep/invariants.py
"""스펙 §5 하드 불변조건 — 위반 시 Violation 리스트를 반환하는 순수 함수들."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str


def check_frame(frame: dict) -> list[Violation]:
    """WS 인바운드 프레임에 에러/예외 신호가 있는지."""
    out: list[Violation] = []
    ftype = frame.get("type")
    if ftype == "error" or "error" in frame:
        out.append(Violation("ws_error_frame", str(frame.get("detail") or frame.get("error"))))
    if frame.get("status_code", 200) >= 500:
        out.append(Violation("http_5xx", str(frame.get("status_code"))))
    return out


def check_card_payload(card: dict) -> list[Violation]:
    """카드 payload 정합성 (스펙 §5.4)."""
    out: list[Violation] = []
    t = card.get("type")
    if t == "vote_card":
        if not card.get("time_options"):
            out.append(Violation("vote_card_no_options", "time_options 비어있음"))
    elif t == "maedeup_card":
        if not card.get("confirmed_date"):
            out.append(Violation("maedeup_no_date", "confirmed_date 없음"))
        if not card.get("confirmed_place"):
            out.append(Violation("maedeup_no_place", "confirmed_place 없음"))
    elif t == "place_recommendation":
        if not card.get("places") and not card.get("results"):
            out.append(Violation("place_reco_empty", "검색 결과 없음"))
    return out


def _percentile(values: list[float], p: float) -> float:
    """nearest-rank 퍼센타일 (values 비어있으면 0)."""
    if not values:
        return 0.0
    s = sorted(values)
    k = max(1, math.ceil(p / 100.0 * len(s)))
    return s[k - 1]


def check_latency_budget(latencies_s: list[float], *, p95_budget_s: float = 8.0) -> list[Violation]:
    """트리거→카드 지연의 p95가 예산 내인지 (스펙 §5.2, K1 SLA)."""
    p95 = _percentile(latencies_s, 95)
    if p95 > p95_budget_s:
        return [Violation("latency_p95_exceeded", f"p95={p95:.2f}s > {p95_budget_s}s")]
    return []


def check_state_consistency(
    *,
    finalized: bool,
    active_reco_cards: int,
    active_vote_cards: int,
    vote_count_drop: bool = False,
    duplicate_card: bool = False,
) -> list[Violation]:
    """확정 후 카드 소거·중복·투표수 단조 (스펙 §5.5)."""
    out: list[Violation] = []
    if finalized and (active_reco_cards > 0 or active_vote_cards > 0):
        out.append(Violation(
            "stale_cards_after_finalize",
            f"확정 후 reco={active_reco_cards} vote={active_vote_cards} 잔존",
        ))
    if duplicate_card:
        out.append(Violation("duplicate_card", "동일 카드 중복 발급"))
    if vote_count_drop:
        out.append(Violation("vote_count_decreased", "투표수 감소 발생"))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_invariants.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add -f sweep/invariants.py sweep/tests/test_invariants.py
git commit -m "feat(sweep): 하드 불변조건 체커 (프레임·카드·지연·상태)"
```

---

## Task 3: 전사(Transcript) 데이터클래스 + 직렬화

**Files:**
- Create: `sweep/transcript.py`
- Test: `sweep/tests/test_transcript.py`

- [ ] **Step 1: Write the failing test**

```python
# sweep/tests/test_transcript.py
import json
from sweep.transcript import Turn, RoomTranscript
from sweep.invariants import Violation


def test_room_transcript_roundtrips_json():
    t = RoomTranscript(room_id=7, persona_keys=["host", "rejector"])
    t.add_turn(Turn(speaker="host", text="모이자", trigger_reason="direct_request",
                    cards=[{"type": "vote_card"}], latency_s=2.5))
    t.violations.append(Violation("ws_error_frame", "boom"))
    blob = t.to_json()
    parsed = json.loads(blob)
    assert parsed["room_id"] == 7
    assert parsed["turns"][0]["latency_s"] == 2.5
    assert parsed["violations"][0]["code"] == "ws_error_frame"


def test_passed_property_reflects_violations():
    t = RoomTranscript(room_id=1, persona_keys=["host"])
    assert t.passed is True
    t.violations.append(Violation("http_5xx", "500"))
    assert t.passed is False


def test_markdown_contains_room_and_violation():
    t = RoomTranscript(room_id=3, persona_keys=["host"])
    t.add_turn(Turn(speaker="host", text="안녕", trigger_reason=None,
                    cards=[], latency_s=None))
    t.violations.append(Violation("latency_p95_exceeded", "p95=9s"))
    md = t.to_markdown()
    assert "room 3" in md and "latency_p95_exceeded" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_transcript.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sweep.transcript'`

- [ ] **Step 3: Write minimal implementation**

```python
# sweep/transcript.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_transcript.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add -f sweep/transcript.py sweep/tests/test_transcript.py
git commit -m "feat(sweep): 전사 데이터클래스 + JSON/MD 직렬화"
```

---

## Task 4: 리포트 집계 + GO/NO-GO

**Files:**
- Create: `sweep/report.py`
- Test: `sweep/tests/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# sweep/tests/test_report.py
from sweep.report import percentile, aggregate, go_no_go
from sweep.transcript import RoomTranscript, Turn
from sweep.invariants import Violation


def test_percentile_nearest_rank():
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([1, 2, 3, 4], 95) == 4
    assert percentile([], 95) == 0.0


def _passing_room(rid, lat):
    t = RoomTranscript(room_id=rid, persona_keys=["host"])
    t.add_turn(Turn("host", "x", "direct_request", [{"type": "vote_card"}], lat))
    return t


def test_aggregate_counts_and_latency():
    rooms = [_passing_room(1, 2.0), _passing_room(2, 4.0)]
    rooms[1].violations.append(Violation("http_5xx", "500"))
    rep = aggregate(rooms)
    assert rep.total == 2
    assert rep.passed == 1
    assert rep.failed == 1
    assert rep.p95_latency_s == 4.0
    assert "http_5xx" in rep.violation_counts


def test_go_no_go_blocks_on_failure():
    rooms = [_passing_room(1, 2.0)]
    rooms[0].violations.append(Violation("stale_cards_after_finalize", "x"))
    rep = aggregate(rooms)
    summary = go_no_go(rep)
    assert "NO-GO" in summary


def test_go_no_go_passes_when_clean():
    rep = aggregate([_passing_room(1, 2.0), _passing_room(2, 3.0)])
    assert "GO" in go_no_go(rep) and "NO-GO" not in go_no_go(rep)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sweep.report'`

- [ ] **Step 3: Write minimal implementation**

```python
# sweep/report.py
"""스윕 결과 집계 + GO/NO-GO 합성 (스펙 §9)."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from sweep.transcript import RoomTranscript


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(1, math.ceil(p / 100.0 * len(s)))
    return s[k - 1]


@dataclass
class SweepReport:
    total: int
    passed: int
    failed: int
    p50_latency_s: float
    p95_latency_s: float
    violation_counts: dict[str, int] = field(default_factory=dict)


def aggregate(rooms: list[RoomTranscript]) -> SweepReport:
    all_lat: list[float] = []
    vc: Counter[str] = Counter()
    passed = 0
    for r in rooms:
        all_lat.extend(r.latencies)
        if r.passed:
            passed += 1
        for v in r.violations:
            vc[v.code] += 1
    return SweepReport(
        total=len(rooms),
        passed=passed,
        failed=len(rooms) - passed,
        p50_latency_s=percentile(all_lat, 50),
        p95_latency_s=percentile(all_lat, 95),
        violation_counts=dict(vc),
    )


def go_no_go(report: SweepReport) -> str:
    """실패 0 + p95<8s 이면 GO, 아니면 NO-GO."""
    blockers: list[str] = []
    if report.failed > 0:
        blockers.append(f"{report.failed}/{report.total} 대화 불변조건 위반")
    if report.p95_latency_s > 8.0:
        blockers.append(f"p95 지연 {report.p95_latency_s:.2f}s > 8s")
    verdict = "NO-GO" if blockers else "GO"
    lines = [
        f"# 견고성 스윗 결과: {verdict}",
        f"- 대화: {report.passed}/{report.total} PASS",
        f"- 지연: p50={report.p50_latency_s:.2f}s p95={report.p95_latency_s:.2f}s",
    ]
    if report.violation_counts:
        lines.append(f"- 위반: {report.violation_counts}")
    if blockers:
        lines.append("## 차단 사유")
        lines += [f"- {b}" for b in blockers]
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_report.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add -f sweep/report.py sweep/tests/test_report.py
git commit -m "feat(sweep): 리포트 집계 + GO/NO-GO 합성"
```

---

## Task 5: 정확성 시나리오 (S1~S10 다자 결정적)

**Files:**
- Create: `sweep/scenarios.py`
- Test: `sweep/tests/test_scenarios.py`

- [ ] **Step 1: Write the failing test**

```python
# sweep/tests/test_scenarios.py
from sweep.scenarios import CORE_SCENARIOS, Scenario, assert_expected


def test_core_scenarios_cover_minimum_seven():
    keys = {s.key for s in CORE_SCENARIOS}
    assert {"S1", "S2", "S4", "S6", "S8", "S9", "S10"} <= keys


def test_each_scenario_has_utterances_and_expected():
    for s in CORE_SCENARIOS:
        assert s.utterances, f"{s.key} 발화 없음"
        assert s.expected_card_type in {"vote_card", "maedeup_card", "place_recommendation"}


def test_assert_expected_detects_wrong_card():
    s = next(s for s in CORE_SCENARIOS if s.key == "S1")  # vote_card 기대
    fails = assert_expected(s, observed_cards=[{"type": "maedeup_card"}])
    assert fails  # 기대와 다른 카드 → 실패 메시지

    ok = assert_expected(s, observed_cards=[{"type": "vote_card",
                                             "time_options": [{"label": "x"}]}])
    assert ok == []


def test_s2_checks_excluded_day():
    s = next(s for s in CORE_SCENARIOS if s.key == "S2")
    # 월요일이 옵션에 남아있으면 실패
    bad = assert_expected(s, observed_cards=[{
        "type": "vote_card",
        "time_options": [{"label": "월요일 저녁", "start_at": "2026-06-08T18:00:00"}],
    }])
    assert any("월" in f for f in bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_scenarios.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sweep.scenarios'`

- [ ] **Step 3: Write minimal implementation**

```python
# sweep/scenarios.py
"""S1~S10 다자 결정적 시나리오 + 기대 카드 assert (스펙 §7)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScriptedUtterance:
    persona_key: str
    text: str


@dataclass(frozen=True)
class Scenario:
    key: str
    description: str
    utterances: tuple[ScriptedUtterance, ...]
    trigger_reason: str
    expected_card_type: str
    must_exclude_substr: tuple[str, ...] = ()   # 옵션 라벨에 있으면 안 되는 문자열
    must_include_substr: tuple[str, ...] = ()   # assistant 메시지에 있어야 하는 문자열


def _u(k: str, t: str) -> ScriptedUtterance:
    return ScriptedUtterance(k, t)


CORE_SCENARIOS: list[Scenario] = [
    Scenario("S1", "기본 시간 투표",
             (_u("host", "다음주에 다 같이 모이자"),),
             "direct_request", "vote_card"),
    Scenario("S2", "거절 누적 — 월요일 제외",
             (_u("host", "다음주에 모이자"), _u("rejector", "월요일은 안돼")),
             "direct_request", "vote_card", must_exclude_substr=("월",)),
    Scenario("S4", "다음주 확장",
             (_u("host", "이번주에 모이자"), _u("rejector", "이번주는 다 바빠")),
             "direct_request", "vote_card", must_include_substr=("확장",)),
    Scenario("S6", "TimeBar 합의",
             (_u("host", "다들 TimeBar에서 시간 골라줘"),),
             "all_members_selected", "vote_card"),
    Scenario("S8", "다수결 fallback",
             (_u("host", "다음주 모이자"), _u("rejector", "난 평일 다 안돼"),
              _u("guest", "저도 주말만 돼요")),
             "direct_request", "vote_card", must_include_substr=("전원",)),
    Scenario("S9", "시간 단독 partial",
             (_u("host", "다음주 화요일 6시에 보자"),),
             "direct_request", "maedeup_card"),
    Scenario("S10", "결론 자동감지",
             (_u("host", "그럼 토요일 7시 강남으로 확정하자"),
              _u("terse", "ㅇㅋ"), _u("guest", "좋아요")),
             "conclusion_detected", "maedeup_card"),
]


def assert_expected(scenario: Scenario, observed_cards: list[dict],
                    assistant_text: str = "") -> list[str]:
    """기대 위반 메시지 리스트(비어있으면 통과)."""
    fails: list[str] = []
    types = [c.get("type") for c in observed_cards]
    if scenario.expected_card_type not in types:
        fails.append(f"{scenario.key}: 기대 {scenario.expected_card_type}, 관측 {types}")
        return fails  # 카드 자체가 다르면 하위 검사 무의미

    card = next(c for c in observed_cards if c.get("type") == scenario.expected_card_type)
    labels = " ".join(o.get("label", "") for o in card.get("time_options", []))
    for bad in scenario.must_exclude_substr:
        if bad in labels:
            fails.append(f"{scenario.key}: 제외돼야 할 '{bad}'가 옵션에 존재")
    for need in scenario.must_include_substr:
        if need not in assistant_text:
            fails.append(f"{scenario.key}: assistant 메시지에 '{need}' 없음")
    return fails
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_scenarios.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add -f sweep/scenarios.py sweep/tests/test_scenarios.py
git commit -m "feat(sweep): S1~S10 다자 결정적 시나리오 + 기대 assert"
```

---

## Task 6: 시뮬레이터 (Gemini 주입 + fallback)

**Files:**
- Create: `sweep/simulator.py`
- Test: `sweep/tests/test_simulator.py`

- [ ] **Step 1: Write the failing test**

```python
# sweep/tests/test_simulator.py
import asyncio
from sweep.personas import PERSONAS
from sweep.simulator import generate_utterance


def _persona(key):
    return next(p for p in PERSONAS if p.key == key)


def test_uses_gemini_when_available():
    async def fake_gemini(prompt: str) -> str:
        return "  생성된 발화  "
    out = asyncio.run(generate_utterance(_persona("host"), ["이전 대화"], 0,
                                         gemini_call=fake_gemini))
    assert out == "생성된 발화"


def test_falls_back_on_gemini_error():
    async def boom(prompt: str) -> str:
        raise RuntimeError("rate limit")
    p = _persona("rejector")
    out = asyncio.run(generate_utterance(p, [], 1, gemini_call=boom))
    assert out == p.fallback_bank[1 % len(p.fallback_bank)]


def test_falls_back_on_empty_gemini():
    async def empty(prompt: str) -> str:
        return "   "
    p = _persona("host")
    out = asyncio.run(generate_utterance(p, [], 0, gemini_call=empty))
    assert out == p.fallback_bank[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_simulator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sweep.simulator'`

- [ ] **Step 3: Write minimal implementation**

```python
# sweep/simulator.py
"""페르소나 발화 생성 — gemini_call 주입, 실패/빈 응답 시 템플릿 fallback (스펙 §4)."""
from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from sweep.personas import Persona, fallback_utterance

GeminiCall = Callable[[str], Awaitable[str]]


def _build_prompt(persona: Persona, history: list[str]) -> str:
    convo = "\n".join(history[-8:]) if history else "(아직 대화 없음)"
    return (
        f"{persona.system_prompt}\n"
        f"너의 숨은 목표: {persona.hidden_goal}\n"
        f"지금까지의 대화:\n{convo}\n\n"
        f"위 페르소나로서 한국어 채팅 메시지 한 줄만 출력해. 따옴표/이름표 없이 내용만."
    )


async def generate_utterance(
    persona: Persona,
    history: list[str],
    turn_index: int,
    *,
    gemini_call: GeminiCall,
) -> str:
    """Gemini로 발화 생성. 예외/빈 응답이면 템플릿 뱅크로 fallback."""
    try:
        text = (await gemini_call(_build_prompt(persona, history))).strip()
    except Exception:
        text = ""
    if not text:
        return fallback_utterance(persona, turn_index)
    return text


def default_gemini_call() -> GeminiCall:
    """google-generativeai 직접 사용 (백엔드 import 없이). GEMINI_API_KEY 필요."""
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(os.environ.get("SWEEP_GEMINI_MODEL", "gemini-2.5-flash"))

    async def _call(prompt: str) -> str:
        resp = await model.generate_content_async(prompt)
        return resp.text or ""

    return _call
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_simulator.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add -f sweep/simulator.py sweep/tests/test_simulator.py
git commit -m "feat(sweep): 시뮬레이터 — Gemini 주입 + 템플릿 fallback"
```

---

## Task 7: REST/WS 클라이언트 (라이브)

**Files:**
- Create: `sweep/client.py`

> 라이브 통합 코드라 순수 단위테스트 대신 Task 9의 스모크 런으로 검증한다. 엔드포인트/페이로드는 기존 `.gstack-k3-concurrency-runner.py` / `.gstack-demo.py`에서 검증된 형태를 그대로 사용.

- [ ] **Step 1: 클라이언트 작성**

```python
# sweep/client.py
"""실 백엔드 REST + WS 래퍼. 백엔드 import 없이 HTTP/WS로만 통신."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

import httpx
import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000"


class SweepClient:
    def __init__(self, host_token: str):
        self.host_token = host_token
        self._http = httpx.AsyncClient(timeout=15.0)

    async def aclose(self) -> None:
        await self._http.aclose()

    def _auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    async def create_room(self, name: str) -> int:
        r = await self._http.post(f"{API}/api/v1/rooms",
                                  json={"name": name, "description": "robustness sweep"},
                                  headers=self._auth(self.host_token))
        r.raise_for_status()
        return int(r.json()["id"])

    async def guest_join(self, room_id: int, display_name: str) -> dict:
        r = await self._http.post(f"{API}/api/v1/rooms/{room_id}/guest-join",
                                  json={"display_name": display_name})
        r.raise_for_status()
        return r.json()  # {token, user_id, name}

    async def send_social(self, room_id: int, token: str, sender: str, content: str) -> None:
        uri = f"{WS}/ws/social/{room_id}?token={token}"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"role": "user", "content": content, "sender": sender}))

    @asynccontextmanager
    async def agent_listener(self, room_id: int, token: str):
        """/ws/agent 구독 — 카드/메시지 프레임을 yield하는 컨텍스트."""
        uri = f"{WS}/ws/agent/{room_id}?token={token}"
        async with websockets.connect(uri) as ws:
            yield ws

    async def direct_request(self, room_id: int, token: str, sender: str, content: str) -> None:
        """AI 패널 직접 요청 (trigger_reason=direct_request)."""
        uri = f"{WS}/ws/agent/{room_id}?token={token}"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"role": "user", "content": content, "sender": sender}))

    async def vote(self, meeting_id: int, token: str, option_index: int) -> dict:
        r = await self._http.post(f"{API}/api/v1/meetings/{meeting_id}/vote",
                                  json={"option_index": option_index},
                                  headers=self._auth(token))
        r.raise_for_status()
        return r.json()  # {votes, total_voters, selected_option_index}

    async def confirm(self, room_id: int, title: str, scheduled_at: str,
                      end_at: str, vote_options: list[dict]) -> dict:
        r = await self._http.post(f"{API}/api/v1/meetings/confirm",
                                  json={"room_id": room_id, "title": title,
                                        "scheduled_at": scheduled_at, "end_at": end_at,
                                        "vote_options": vote_options},
                                  headers=self._auth(self.host_token))
        r.raise_for_status()
        return r.json()
```

- [ ] **Step 2: import 스모크**

Run: `.venv-test\Scripts\python.exe -c "from sweep.client import SweepClient; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add -f sweep/client.py
git commit -m "feat(sweep): REST/WS 클라이언트 래퍼"
```

---

## Task 8: 대화 구동 루프 (방 1개, 라이브)

**Files:**
- Create: `sweep/driver.py`

> 라이브 코드. 검증은 Task 9 스모크 런(1방)에서 실제 카드가 잡히는지로 확인.

- [ ] **Step 1: driver 작성**

```python
# sweep/driver.py
"""방 1개의 다자 대화를 끝까지 구동하며 카드 관찰·불변조건 체크·전사 기록."""
from __future__ import annotations

import asyncio
import json
import time

from sweep.client import SweepClient
from sweep.invariants import check_card_payload, check_frame, check_state_consistency
from sweep.personas import Persona
from sweep.simulator import GeminiCall, generate_utterance
from sweep.transcript import RoomTranscript, Turn

_CARD_TYPES = {"vote_card", "place_recommendation", "maedeup_card"}


async def _collect_frames(ws, *, window_s: float) -> list[dict]:
    """window_s 동안 들어오는 프레임 수집 (트리거 후 카드 대기)."""
    frames: list[dict] = []
    deadline = time.monotonic() + window_s
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic())
        except asyncio.TimeoutError:
            break
        try:
            frames.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return frames


async def run_room(
    client: SweepClient,
    room_id: int,
    members: list[tuple[Persona, dict]],   # (persona, guest_join_result)
    *,
    gemini_call: GeminiCall,
    max_turns: int = 12,
    card_window_s: float = 8.0,
) -> RoomTranscript:
    transcript = RoomTranscript(room_id=room_id,
                                persona_keys=[p.key for p, _ in members])
    host_persona, host_join = members[0]
    history: list[str] = []

    # host가 /ws/agent 리스너를 열어 트리거 후 카드를 수신
    async with client.agent_listener(room_id, host_join["token"]) as agent_ws:
        for turn_i in range(max_turns):
            persona, join = members[turn_i % len(members)]
            text = await generate_utterance(persona, history, turn_i, gemini_call=gemini_call)
            history.append(f"{persona.label}: {text}")

            t0 = time.monotonic()
            # host 차례엔 direct_request(트리거), 그 외엔 social 발화
            if persona.key == "host":
                await client.direct_request(room_id, join["token"], join["name"], text)
                trigger = "direct_request"
            else:
                await client.send_social(room_id, join["token"], join["name"], text)
                trigger = None

            frames = await _collect_frames(agent_ws, window_s=card_window_s)
            cards = [f for f in frames if f.get("type") in _CARD_TYPES]
            latency = (time.monotonic() - t0) if cards else None

            # 불변조건: 프레임 에러 + 카드 payload
            for f in frames:
                transcript.violations.extend(check_frame(f))
            for c in cards:
                transcript.violations.extend(check_card_payload(c))
            # 트리거를 쐈는데 어떤 응답도 없으면 침묵 드롭
            if trigger and not frames:
                from sweep.invariants import Violation
                transcript.violations.append(Violation("silent_drop", f"turn {turn_i} 트리거 무응답"))

            transcript.add_turn(Turn(speaker=persona.key, text=text,
                                     trigger_reason=trigger, cards=cards, latency_s=latency))

            # maedeup_card가 나오면 확정 → 종료
            if any(c.get("type") == "maedeup_card" for c in cards):
                break

    return transcript
```

- [ ] **Step 2: import 스모크**

Run: `.venv-test\Scripts\python.exe -c "from sweep.driver import run_room; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add -f sweep/driver.py
git commit -m "feat(sweep): 방 1개 대화 구동 루프 + 인라인 불변조건"
```

---

## Task 9: 동시 오케스트레이션 + 엔트리포인트

**Files:**
- Create: `sweep/config.py`
- Create: `.gstack-robustness-sweep.py`

- [ ] **Step 1: config 작성**

```python
# sweep/config.py
"""스윕 실행 파라미터 (스펙 §10)."""
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
```

- [ ] **Step 2: 엔트리포인트 작성**

```python
# .gstack-robustness-sweep.py
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
```

- [ ] **Step 3: config 단위 검증**

Run: `.venv-test\Scripts\python.exe -c "from sweep.config import parse_args; print(parse_args(['--rooms','5']).rooms)"`
Expected: `5`

- [ ] **Step 4: 라이브 스모크 런 (1방, 동시성 1)**

사전: `docker compose up -d` 확인, `.gstack-demo-token` 존재, `$env:GEMINI_API_KEY` 설정.

Run: `.venv\Scripts\python.exe .gstack-robustness-sweep.py --rooms 1 --concurrency 1 --max-turns 4`
Expected:
- 콘솔에 `# 견고성 스윗 결과: GO` 또는 `NO-GO` 요약 출력
- `docs/handoff/robustness-sweep-2026-06-03/room-*.json` / `room-*.md` / `SUMMARY.md` 생성
- room md에 최소 1개 `vote_card` 또는 assistant 응답이 잡혀야 함 (트리거→카드 경로 동작 확인)

만약 카드가 전혀 안 잡히면: `card_window_s`(driver, 기본 8s)를 늘리거나, host의 direct_request 발화가 trigger를 못 일으키는지 전사에서 확인 후 발화 텍스트를 더 명시적으로 조정.

- [ ] **Step 5: Commit**

```bash
git add -f sweep/config.py .gstack-robustness-sweep.py
git commit -m "feat(sweep): 동시 오케스트레이션 + 엔트리포인트"
```

---

## Task 10: 동시 액션(경합) 주입 + 심판관 핸드오프

**Files:**
- Modify: `sweep/driver.py` (동시 투표 헬퍼 추가)
- Create: `sweep/JUDGE_PROMPT.md` (Claude 심판관용 프롬프트 템플릿)

- [ ] **Step 1: 동시 투표 헬퍼 추가 (driver.py 끝에 추가)**

```python
# sweep/driver.py 에 추가
async def concurrent_vote_storm(
    client: SweepClient,
    meeting_id: int,
    voters: list[tuple[str, int]],   # (token, option_index)
) -> list[dict]:
    """전원이 동시에 투표 — race condition 검증 (스펙 §6, K3.1)."""
    results = await asyncio.gather(
        *[client.vote(meeting_id, tok, opt) for tok, opt in voters],
        return_exceptions=True,
    )
    return [r if not isinstance(r, Exception) else {"error": repr(r)} for r in results]


async def observe_broadcast(
    client: SweepClient,
    room_id: int,
    member_tokens: list[str],
    trigger: "asyncio.Future | None" = None,
    *,
    window_s: float = 8.0,
) -> list[int]:
    """전 멤버가 /ws/agent를 동시에 구독한 상태에서 카드 이벤트 수신 수를 반환.

    각 멤버 리스너가 window_s 동안 받은 카드 프레임 개수 리스트.
    스펙 §5.6: 전원이 동일 카드 이벤트를 받아야 함 → 수신 수가 멤버마다 같아야 함.
    """
    async def _listen(token: str) -> int:
        count = 0
        async with client.agent_listener(room_id, token) as ws:
            deadline = time.monotonic() + window_s
            while time.monotonic() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic())
                except asyncio.TimeoutError:
                    break
                try:
                    if json.loads(raw).get("type") in _CARD_TYPES:
                        count += 1
                except json.JSONDecodeError:
                    continue
        return count

    return await asyncio.gather(*[_listen(t) for t in member_tokens])
```

- [ ] **Step 2: 동시 투표 결과 불변조건 검증 (단위 테스트)**

`sweep/tests/test_invariants.py`에 추가:
```python
def test_vote_storm_results_no_error_and_monotonic():
    # 동시 투표 결과에 error 프레임 없고 total_voters가 비감소인지 확인하는 헬퍼
    from sweep.invariants import check_vote_storm
    good = [{"votes": {"0": 1}, "total_voters": 1},
            {"votes": {"0": 2}, "total_voters": 2}]
    assert check_vote_storm(good) == []
    bad = [{"error": "boom"}]
    assert any(v.code == "vote_error" for v in check_vote_storm(bad))


def test_broadcast_all_members_must_match():
    from sweep.invariants import check_broadcast
    # 전원 1개씩 수신 → 통과
    assert check_broadcast([1, 1, 1]) == []
    # 한 명이 0개 수신 → 누락 위반
    v = check_broadcast([1, 1, 0])
    assert any(x.code == "broadcast_missed" for x in v)
```

`sweep/invariants.py`에 추가:
```python
def check_vote_storm(results: list[dict]) -> list[Violation]:
    """동시 투표 결과 — 에러 없음 + total_voters 비감소 (스펙 §5.5, §6)."""
    out: list[Violation] = []
    prev = -1
    for r in results:
        if "error" in r:
            out.append(Violation("vote_error", r["error"]))
            continue
        tv = r.get("total_voters", 0)
        if tv < prev:
            out.append(Violation("vote_count_decreased", f"{prev}→{tv}"))
        prev = max(prev, tv)
    return out


def check_broadcast(per_member_card_counts: list[int]) -> list[Violation]:
    """전 멤버가 동일 카드 이벤트를 받았는지 (스펙 §5.6, K3.2).

    수신 수가 멤버마다 다르면(특히 0인 멤버) 브로드캐스트 누락.
    """
    if not per_member_card_counts:
        return []
    mx = max(per_member_card_counts)
    if mx == 0:
        return []  # 애초에 카드가 없던 구간 — 누락 아님
    missed = [i for i, c in enumerate(per_member_card_counts) if c < mx]
    if missed:
        return [Violation("broadcast_missed",
                          f"멤버 {missed}가 카드 수신 부족 (수신={per_member_card_counts})")]
    return []
```

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/test_invariants.py -v`
Expected: PASS (10 passed)

- [ ] **Step 3: 심판관 프롬프트 템플릿 작성**

```markdown
# sweep/JUDGE_PROMPT.md
# 견고성 스윗 — Claude 심판관 프롬프트

스윕 종료 후, 다음 절차로 전사를 채점한다 (스펙 §8). 심판은 Claude(이 모델)가 직접 수행.

## 입력
- `docs/handoff/robustness-sweep-2026-06-03/room-*.md` 전사
- `SUMMARY.md` (하드 불변조건 GO/NO-GO)

## 표본
- 실패(FAIL) 전사: **전부**
- 통과(PASS) 전사: 무작위 표본 (기본 10개, 또는 전체가 10개 미만이면 전부)

## 채점 질문 (각 전사)
1. AI 응답(카드·메시지)이 그 대화 맥락에 **말이 되는가**? (동문서답·뜬금없음 없음)
2. 트리거 시점이 적절한가? (잡담에 과민 트리거 / 명백한 요청에 무반응 없음)
3. 페르소나의 의도(거절·모호·게스트)를 **무시하지 않았는가**?
4. 카드 내용이 직전 대화와 모순되지 않는가?

## 출력
- soft-fail 플래그 목록: `room-N — <질문#> — <근거(전사 인용)>`
- 최종 한 줄: 하드 GO/NO-GO + soft-fail 건수 → 전시 권고
```

- [ ] **Step 4: Commit**

```bash
git add -f sweep/driver.py sweep/invariants.py sweep/tests/test_invariants.py sweep/JUDGE_PROMPT.md
git commit -m "feat(sweep): 동시 투표 경합 + 브로드캐스트 누락 검증 + 심판관 핸드오프"
```

---

## 전체 검증 (모든 태스크 후)

- [ ] **단위테스트 전체 통과**

Run: `.venv-test\Scripts\python.exe -m pytest sweep/tests/ -v`
Expected: 전부 PASS (~24 tests)

- [ ] **라이브 스윗 소규모 실행**

Run: `.venv\Scripts\python.exe .gstack-robustness-sweep.py --rooms 5 --concurrency 3 --max-turns 8`
Expected: `SUMMARY.md` 생성 + 콘솔 GO/NO-GO. 전사 5개 방 기록.

- [ ] **심판관 단계 (Claude)**

`sweep/JUDGE_PROMPT.md` 절차로 전사 채점 → soft-fail 플래그 + 전시 권고 합성.

---

## 비고: TDD 적용 범위

- **순수 모듈 (Task 1~6, 10)**: 진짜 실패하는 테스트 우선 → 구현. 백엔드/네트워크 의존 없음.
- **라이브 모듈 (Task 7~9)**: 단위테스트 대신 import 스모크 + 실제 백엔드 1방 스모크 런으로 검증. 라이브 통합은 본질적으로 실 서버 필요.
- **심판관 (Task 10)**: 코드가 아니라 Claude 절차 → 프롬프트 템플릿으로 고정.
