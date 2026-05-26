# Phase 1 — K1/K2/K3 측정 인프라 구축 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 전시 안정성 spec (`docs/superpowers/specs/2026-05-27-exhibition-stability-k1-k2-k3-design.md`) 의 Phase 1 — K1/K2/K3 자동 측정 인프라 (`.gstack-*` runner 3개 + fixture 3개 + qa-runtime 25항목 확장) 구축. Phase 2 baseline 측정 실행 준비 완료까지.

**Architecture:** 매듭 기존 `.gstack-*` 패턴 (`.gstack-demo.py`, `.gstack-browser-launch.py`) 따라 root level 에 K1/K2/K3 runner 추가. fixture 는 `.gstack-fixtures/` 디렉토리. httpx + websockets (이미 사용 중) + asyncio 기반. backend FastAPI 의 기존 API endpoint (rooms / chat / vote / auth) 재사용. 별도 backend 변경 X.

**Tech Stack:** Python 3.11+, asyncio, httpx (신규 add), websockets (기존), Playwright (기존, K3 onboarding 만 사용 가능), backend FastAPI endpoint 호출.

**Spec link:** `docs/superpowers/specs/2026-05-27-exhibition-stability-k1-k2-k3-design.md`

---

## File Structure

| 신규 파일 | 책임 |
|---|---|
| `.gstack-fixtures/k2-free-inputs.json` | 자유 입력 50개 fixture (반말/줄임말/이모지/오타/은어 카테고리 + 예상 intent/slot 라벨) |
| `.gstack-fixtures/k3-concurrency-scenarios.json` | 다인 룸 동시성 시나리오 5개 (5명 동시 vote, 2명 동시 manual pick, busy_period 동시 발산 등) |
| `.gstack-fixtures/k3-onboarding-users.json` | 신규 사용자 가입 흐름 시뮬레이션 fixture 5개 (이메일·이름·OAuth mock token) |
| `.gstack-k2-runner.py` | K2.1/K2.2/K2.3 측정 — fixture 로드 → 자유 입력 발화 → 응답 grep → 결과 표 출력 |
| `.gstack-k3-concurrency-runner.py` | K3.1/K3.2 측정 — 다인 룸 시나리오 → asyncio.gather 동시 API call → race/누락 자동 감지 |
| `.gstack-k3-onboarding-runner.py` | K3.3 측정 — 신규 가입 → 방 생성 → 친구 초대 → 첫 입력 흐름 시뮬 + 막힘 지점 감지 |
| `.gstack-fixtures/README.md` | fixture 형식 문서 (스키마 + 카테고리 정의) |

| 변경 파일 | 변경 내용 |
|---|---|
| `.gstack-demo.py` | K1.1/K1.2/K1.3 timing wrapper — 각 ACT 시작/종료 marker (time.monotonic()) + stdout `[K1.x] ...` 출력 + 시연 종료 시 분포 summary |
| `~/.claude/projects/-mnt-c-Users-cyun0-git-maedeup/memory/feedback_qa_auto_panel_audit.md` | 18 → 25 항목 확장 (K1.1/K1.2/K1.3/K3.2 + silent fail 함정 자동 감지 등) |

| 신규 handoff | 책임 |
|---|---|
| `docs/handoff/2026-05-28-phase1-runners-ready.md` | Phase 1 완료 보고 + Phase 2 baseline 측정 진입 안내 |

---

## Task 1: `.gstack-demo.py` K1 timing wrapper

**Files:**
- Modify: `.gstack-demo.py` (ACT 진입/종료 marker + summary 함수)

- [ ] **Step 1.1: helper 함수 추가 — `_k1_mark()` + `_k1_summary()`**

`.gstack-demo.py` 의 import 블록 아래 (line ~85 부근, `API` 정의 직전) 에 helper 추가:

```python
# ─── K1 timing wrapper (Phase 1, spec 2026-05-27) ───────────────────────────
_k1_marks: dict[str, float] = {}
_k1_durations: list[tuple[str, float]] = []  # [(act_label, sec), ...]

def _k1_mark(label: str) -> None:
    """ACT 시작/종료 marker. label 형식: 'ACT2.start', 'ACT2.first_card'."""
    _k1_marks[label] = time.monotonic()

def _k1_record(act: str, start_label: str, end_label: str) -> None:
    """start~end 사이 duration 기록 + stdout 출력."""
    if start_label in _k1_marks and end_label in _k1_marks:
        dur = _k1_marks[end_label] - _k1_marks[start_label]
        _k1_durations.append((act, dur))
        _ts = time.strftime("%H:%M:%S")
        print(f"[{_ts}] [K1.1] {act}: {dur:.2f}s", flush=True)

def _k1_summary() -> None:
    """시연 종료 시 분포 summary 출력."""
    if not _k1_durations:
        return
    print("\n[K1.SUMMARY] === 측정 결과 ===", flush=True)
    for act, dur in _k1_durations:
        print(f"  {act}: {dur:.2f}s", flush=True)
    print("[K1.SUMMARY] === end ===\n", flush=True)
```

- [ ] **Step 1.2: ACT 진입/종료 지점에 marker 추가**

ACT 2 / ACT 2.5 / ACT 5 진입/종료 지점 (script 내 `=== ACT N ===` 출력 부근) 에 `_k1_mark()` 호출 삽입.

핵심 marker 5개:
- `ACT2.start` (ACT 2 트리거 발화 직전)
- `ACT2.first_card` (vote_card 또는 첫 카드 WS 수신 직후)
- `ACT5.start` (direct_request 발화 직전)
- `ACT5.first_card` (place_recommendation 카드 WS 수신 직후)
- 각 ACT 종료 시 `_k1_record("ACT2.trigger→card", "ACT2.start", "ACT2.first_card")` 호출

- [ ] **Step 1.3: `main()` 끝부분 `_k1_summary()` 호출 추가**

기존 `main()` 의 finally 또는 마지막 cleanup 직전:

```python
finally:
    _k1_summary()
    # 기존 cleanup ...
```

- [ ] **Step 1.4: Gemini fallback 카운터 (K1.2)**

backend 호출 후 응답 분석. 시연 자동화 stdout 에 backend log 가 직접 안 보이므로 `docker logs maedeup-api` 별도 grep 으로 측정 (Task 6 의 qa-runtime 25항목 확장에 포함). 본 Task 에서는 K1.1 만 처리, K1.2 는 qa-runtime 트랙으로 위임.

- [ ] **Step 1.5: 시연 1회 검증**

```bash
~/.venv-maedeup-demo/bin/python3 .gstack-demo.py --fast 2>&1 | grep -E "\[K1"
```

Expected output (예시):
```
[18:03:24] [K1.1] ACT2.trigger→card: 4.32s
[18:03:54] [K1.1] ACT5.trigger→card: 3.81s

[K1.SUMMARY] === 측정 결과 ===
  ACT2.trigger→card: 4.32s
  ACT5.trigger→card: 3.81s
[K1.SUMMARY] === end ===
```

- [ ] **Step 1.6: Commit**

```bash
git add .gstack-demo.py
git commit -m "feat(k1): .gstack-demo.py K1.1/K1.3 latency 자동 측정 wrapper

Phase 1 spec 의 K1 측정 인프라.
ACT 진입/종료 marker + 시연 종료 시 분포 summary.
K1.2 (Gemini fallback rate) 는 별 트랙 (qa-runtime 25항목 확장).
"
```

---

## Task 2: K2 fixture — 자유 입력 50개

**Files:**
- Create: `.gstack-fixtures/k2-free-inputs.json`
- Create: `.gstack-fixtures/README.md`

- [ ] **Step 2.1: fixture 스키마 정의 (README.md)**

```markdown
# .gstack-fixtures — 매듭 측정 인프라 fixture

## k2-free-inputs.json

자유 입력 50개. 5 카테고리 × 10개.

### 카테고리
- 반말 (banmal)
- 줄임말 (jurimmal)
- 이모지 (emoji)
- 오타 (otta)
- 은어 (eono)

### 스키마
```json
[
  {
    "id": "k2-001",
    "category": "banmal",
    "input": "야 다음주 점심 ㄱㄱ",
    "expected_intent": "MEETING_SUGGESTION",
    "expected_slot": {"date_hint": "next week"},
    "should_trigger": true
  }
]
```
```

- [ ] **Step 2.2: 50개 fixture 작성 — 카테고리 5 × 10개**

`.gstack-fixtures/k2-free-inputs.json` 에 50개 entry. 각 카테고리 10개. 예상 intent 라벨은 backend 의 intent_classifier seed (`backend/app/api/routes/intents.py` 또는 seed 데이터) 와 동일 라벨 사용 — MEETING_SUGGESTION / FREE_CHAT / PLACE_QUESTION / SCHEDULE_REJECT / GENERAL_AGREEMENT 등.

핵심: `should_trigger=true/false` 로 트리거 발화 여부 명시. trigger 발화율 = sum(should_trigger AND emit_observed) / sum(should_trigger).

- [ ] **Step 2.3: JSON parse 검증**

```bash
python3 -c "import json; data = json.load(open('.gstack-fixtures/k2-free-inputs.json')); print(f'count={len(data)}'); assert len(data) == 50; cats = set(d['category'] for d in data); print(f'categories={cats}'); assert len(cats) == 5"
```

Expected: `count=50` + 5 카테고리 출력.

- [ ] **Step 2.4: Commit**

```bash
git add .gstack-fixtures/k2-free-inputs.json .gstack-fixtures/README.md
git commit -m "feat(k2): 자유 입력 50개 fixture + 스키마 문서

5 카테고리 × 10개 (반말/줄임말/이모지/오타/은어).
intent label seed (backend/.../intents) 와 일치."
```

---

## Task 3: `.gstack-k2-runner.py` — K2 자동 측정 runner

**Files:**
- Create: `.gstack-k2-runner.py`

- [ ] **Step 3.1: helper 함수 — fixture load + JWT 토큰 load**

`.gstack-k2-runner.py` 작성:

```python
"""K2 자동 측정 runner — 자유 입력 50개 → 트리거/intent/slot 결과 표.

사용:
  ~/.venv-maedeup-demo/bin/python3 .gstack-k2-runner.py
  ~/.venv-maedeup-demo/bin/python3 .gstack-k2-runner.py --fixture .gstack-fixtures/k2-free-inputs.json --room-id 100
"""
from __future__ import annotations
import argparse, asyncio, json, sys, time
from pathlib import Path
import httpx
import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000"

def load_fixture(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_token() -> str:
    return Path(".gstack-demo-token").read_text().strip()
```

- [ ] **Step 3.2: HTTP 발화 함수 + WS 응답 수신 함수**

```python
async def send_chat_and_capture(client: httpx.AsyncClient, room_id: int, content: str, token: str) -> dict:
    """채팅 1건 발화 → 트리거/intent/slot 응답 캡처. 5s timeout."""
    headers = {"Authorization": f"Bearer {token}"}
    # 1. 채팅 전송 (REST or WS — `.gstack-demo.py` send_chat 참고)
    resp = await client.post(
        f"{API}/api/v1/rooms/{room_id}/messages",
        headers=headers,
        json={"content": content, "pane_type": "social"},
        timeout=10.0,
    )
    # 2. 5초 동안 trigger event 대기 (WS 또는 polling)
    # 3. trigger 발생 여부 + intent + slot 추출
    return {"triggered": False, "intent": None, "slot": {}}  # placeholder
```

- [ ] **Step 3.3: 결과 집계 함수**

```python
def aggregate(results: list[dict]) -> dict:
    total = len(results)
    triggered = sum(1 for r in results if r["observed"]["triggered"])
    expected_trigger = sum(1 for r in results if r["expected"]["should_trigger"])
    correct_intent = sum(1 for r in results if r["observed"]["intent"] == r["expected"]["expected_intent"])
    correct_slot = sum(1 for r in results if r["observed"]["slot"] == r["expected"]["expected_slot"])
    return {
        "K2.1_trigger_rate": triggered / max(expected_trigger, 1),
        "K2.2_intent_accuracy": correct_intent / total,
        "K2.3_slot_robustness": correct_slot / total,
    }
```

- [ ] **Step 3.4: main 함수 통합**

```python
async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default=".gstack-fixtures/k2-free-inputs.json")
    parser.add_argument("--room-id", type=int, required=True, help="시드된 K2 측정 전용 룸 id")
    args = parser.parse_args()
    
    fixture = load_fixture(args.fixture)
    token = load_token()
    
    async with httpx.AsyncClient() as client:
        results = []
        for item in fixture:
            observed = await send_chat_and_capture(client, args.room_id, item["input"], token)
            results.append({"id": item["id"], "expected": item, "observed": observed})
            await asyncio.sleep(0.5)  # rate limit 회피
    
    summary = aggregate(results)
    print(f"\n[K2.SUMMARY] === N={len(results)} ===", flush=True)
    print(f"  K2.1 trigger 발화율: {summary['K2.1_trigger_rate']:.1%}", flush=True)
    print(f"  K2.2 intent 정확도: {summary['K2.2_intent_accuracy']:.1%}", flush=True)
    print(f"  K2.3 slot robustness: {summary['K2.3_slot_robustness']:.1%}", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 3.5: dry run 검증 (fixture 5개만)**

```bash
# K2 측정 전용 룸 생성 (호스트 = 토큰 사용자)
curl -X POST http://localhost:8000/api/v1/rooms -H "Authorization: Bearer $(cat .gstack-demo-token)" -H "Content-Type: application/json" -d '{"name": "K2 측정 dry run"}' | jq .id
# 출력된 room_id 사용
~/.venv-maedeup-demo/bin/python3 .gstack-k2-runner.py --fixture .gstack-fixtures/k2-free-inputs-dry.json --room-id <ROOM>
```

먼저 `.gstack-fixtures/k2-free-inputs-dry.json` (5개 sample) 만 작성 후 검증.

- [ ] **Step 3.6: 실제 50개 fixture 로 검증**

```bash
~/.venv-maedeup-demo/bin/python3 .gstack-k2-runner.py --room-id <ROOM>
```

Expected: `[K2.SUMMARY]` 출력 + K2.1/K2.2/K2.3 비율 (baseline 미확정, 단순 동작 검증).

- [ ] **Step 3.7: pyproject / requirements 에 httpx 추가 (필요 시)**

`backend/requirements.txt` 또는 `pyproject.toml` 확인 — httpx 이미 있으면 skip, 없으면 add. `~/.venv-maedeup-demo/` 의 pip 에 install.

- [ ] **Step 3.8: Commit**

```bash
git add .gstack-k2-runner.py
git commit -m "feat(k2): .gstack-k2-runner.py — 자유 입력 50개 자동 측정

K2.1 (트리거 발화율) / K2.2 (intent 정확도) / K2.3 (slot robustness)
fixture 로드 + HTTP 발화 + WS 수신 + 결과 표.
baseline 측정 진입 준비 완료."
```

---

## Task 4: K3 동시성 fixture + runner

**Files:**
- Create: `.gstack-fixtures/k3-concurrency-scenarios.json`
- Create: `.gstack-k3-concurrency-runner.py`

- [ ] **Step 4.1: 5 시나리오 fixture 작성**

```json
[
  {
    "id": "k3-conc-001",
    "name": "5명 룸 동시 vote 3건",
    "room_size": 5,
    "actions": [
      {"type": "vote", "user_idx": 1, "option_index": 0, "delay_ms": 0},
      {"type": "vote", "user_idx": 2, "option_index": 0, "delay_ms": 10},
      {"type": "vote", "user_idx": 3, "option_index": 1, "delay_ms": 20}
    ],
    "expected_total_votes": 3,
    "expected_race_count": 0
  },
  {
    "id": "k3-conc-002",
    "name": "2명 동시 manual pick",
    "room_size": 3,
    "actions": [
      {"type": "manual_pick", "user_idx": 0, "slot_id": 37, "delay_ms": 0},
      {"type": "manual_pick", "user_idx": 1, "slot_id": 38, "delay_ms": 50}
    ],
    "expected_winner": "user_idx_0",
    "expected_race_count": 0
  }
  // ... 3 more scenarios
]
```

- [ ] **Step 4.2: runner skeleton — fixture load + 시나리오 실행 framework**

```python
"""K3 동시성 측정 runner.

사용:
  ~/.venv-maedeup-demo/bin/python3 .gstack-k3-concurrency-runner.py --scenario all
"""
import argparse, asyncio, json, sys
from pathlib import Path
import httpx

API = "http://localhost:8000"

async def run_scenario(scenario: dict, host_token: str) -> dict:
    """1 시나리오 실행 → race 감지 결과 반환."""
    # 1. 룸 생성 + N명 게스트 가입 (각 게스트는 별 token 필요 — fixture 에 미리 시드)
    # 2. actions 의 delay_ms 기준 asyncio.gather 로 동시 실행
    # 3. DB SELECT * FROM votes WHERE meeting_id=<N> 또는 vote_options 검증
    # 4. WS broadcast 누락 검증 (각 게스트 WS connect 후 event count)
    return {"race_count": 0, "broadcast_missing": 0}
```

- [ ] **Step 4.3: race 감지 로직 — DB 중복 row + WS event count diff**

```python
async def detect_race(client: httpx.AsyncClient, meeting_id: int, expected_votes: int) -> int:
    """DB 의 vote_options.option_index 별 vote_count 가 expected 와 일치하는지."""
    resp = await client.get(f"{API}/api/v1/meetings/{meeting_id}")
    data = resp.json()
    actual_total = sum(opt.get("vote_count", 0) for opt in data.get("vote_options", []))
    return abs(actual_total - expected_votes)
```

- [ ] **Step 4.4: 결과 집계**

```python
def aggregate(results: list[dict]) -> dict:
    total_race = sum(r["race_count"] for r in results)
    total_missing = sum(r["broadcast_missing"] for r in results)
    return {
        "K3.1_race_count": total_race,
        "K3.2_broadcast_missing": total_missing,
        "scenarios_run": len(results),
    }
```

- [ ] **Step 4.5: dry run (1 시나리오)**

```bash
~/.venv-maedeup-demo/bin/python3 .gstack-k3-concurrency-runner.py --scenario k3-conc-001
```

Expected: `[K3.SUMMARY] race=0 broadcast_missing=0 scenarios=1`

- [ ] **Step 4.6: 전 시나리오 실행 + 검증**

```bash
~/.venv-maedeup-demo/bin/python3 .gstack-k3-concurrency-runner.py --scenario all
```

- [ ] **Step 4.7: Commit**

```bash
git add .gstack-fixtures/k3-concurrency-scenarios.json .gstack-k3-concurrency-runner.py
git commit -m "feat(k3): K3.1/K3.2 동시성 측정 runner + 5 시나리오 fixture

asyncio.gather 동시 vote/manual pick → DB 중복 + WS event count diff
자동 감지. race/누락 0 = K3 GREEN 조건."
```

---

## Task 5: K3 onboarding fixture + runner

**Files:**
- Create: `.gstack-fixtures/k3-onboarding-users.json`
- Create: `.gstack-k3-onboarding-runner.py`

- [ ] **Step 5.1: 5 신규 사용자 fixture 작성**

```json
[
  {
    "id": "k3-onb-001",
    "email": "test-onb-001@maedeup.local",
    "name": "테스트유저1",
    "oauth_mock_token": "mock-token-001",
    "expected_room_create": true,
    "expected_friend_invite": true,
    "expected_first_input": "다음주 점심 어때?"
  }
  // ... 4 more
]
```

- [ ] **Step 5.2: backend 의 Google OAuth mock path 확인**

`backend/app/api/routes/auth.py` 검토 — test/dev mode 에서 mock OAuth 허용하는 path 있는지. 없으면 fixture 의 `oauth_mock_token` 을 어떻게 backend 가 해석할지 추가 fix 필요 (별 task 후보).

- [ ] **Step 5.3: runner — 가입 → 방 생성 → 친구 초대 → 첫 입력 흐름**

```python
"""K3 onboarding 측정 runner.

사용:
  ~/.venv-maedeup-demo/bin/python3 .gstack-k3-onboarding-runner.py
"""
import asyncio, json, sys
from pathlib import Path
import httpx

API = "http://localhost:8000"

async def simulate_onboarding(client: httpx.AsyncClient, user: dict) -> dict:
    """1 사용자 가입 흐름 시뮬 → 막힘 지점 dict 반환."""
    blocks = []
    # 1. 가입 (POST /api/v1/auth/google or mock endpoint)
    resp = await client.post(f"{API}/api/v1/auth/mock", json={"email": user["email"], "name": user["name"]})
    if resp.status_code != 200:
        blocks.append({"step": "auth", "code": resp.status_code, "body": resp.text[:200]})
        return {"user_id": user["id"], "blocks": blocks}
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # 2. 방 생성
    # 3. 친구 초대
    # 4. 첫 입력
    return {"user_id": user["id"], "blocks": blocks}
```

- [ ] **Step 5.4: 결과 집계**

```python
def aggregate(results: list[dict]) -> dict:
    total_blocks = sum(len(r["blocks"]) for r in results)
    return {
        "K3.3_block_count": total_blocks,
        "users_run": len(results),
    }
```

- [ ] **Step 5.5: dry run**

```bash
~/.venv-maedeup-demo/bin/python3 .gstack-k3-onboarding-runner.py
```

- [ ] **Step 5.6: Commit**

```bash
git add .gstack-fixtures/k3-onboarding-users.json .gstack-k3-onboarding-runner.py
git commit -m "feat(k3): K3.3 onboarding 측정 runner + 5 사용자 fixture

신규 가입 → 방 생성 → 친구 초대 → 첫 입력 흐름 시뮬.
막힘 지점 (HTTP error / timeout) 자동 감지."
```

---

## Task 6: qa-runtime memory 25항목 확장 + Phase 1 handoff

**Files:**
- Modify: `~/.claude/projects/-mnt-c-Users-cyun0-git-maedeup/memory/feedback_qa_auto_panel_audit.md`
- Create: `docs/handoff/2026-05-28-phase1-runners-ready.md`

- [ ] **Step 6.1: memory 18 → 25 항목 확장**

기존 18 항목 뒤에 19~25 추가:

```markdown
19. **K1.1 latency 분포** — `.gstack-demo.py` 시연 종료 시 `[K1.SUMMARY]` 출력 grep → 트리거 → 첫 카드 latency 추출. p50 < 5s, p95 < 8s SLA 미달 시 P1.
20. **K1.2 Gemini fallback 빈도** — `docker logs maedeup-api --tail 500 | grep -c "TIMEOUT\|fallback"` 으로 시연 동안 fallback count 측정. 시연 1회당 전체 호출 대비 비율 > 10% 미달 시 P1.
21. **K1.3 direct_request → 카드** — ACT 5 isolate 시 K1.1 와 별 metric 으로 추출. < 5s 미달 시 P0 (scenario-v3 A5-1).
22. **K3.2 WS broadcast 누락** — qa-runtime 의 WS event timeline 수집 + 다인 룸 시나리오 시 멤버 수 × event 수 expected 와 actual 차이 > 0 시 P1.
23. **silent fail 함정 자동 감지** — `docker logs maedeup-api | grep -E "WARNING|ERROR|Traceback"` 종료 후 grep. 신규 출현 (이전 시연 baseline 대비) 시 P1 — 숨겨진 코드 버그 가시화.
24. **요약 / 종합 메시지 길이** — chat_messages.content 의 maedeup summary 본문 길이 검증 (예: 50~200자). 너무 짧으면 정보 부족, 너무 길면 readability 저하.
25. **외부 API quota monitor** — Gemini API + Kakao API 호출 횟수 / quota 비율 (paid key 사용 시). 80% 초과 시 P1 alarm.
```

- [ ] **Step 6.2: Phase 1 handoff 문서 작성**

`docs/handoff/2026-05-28-phase1-runners-ready.md`:

```markdown
# Phase 1 — 측정 인프라 구축 완료 (2026-05-28)

## 결론
spec `2026-05-27-exhibition-stability-k1-k2-k3-design.md` 의 Phase 1
산출물 6개 + memory 25항목 확장 완료. Phase 2 baseline 측정 진입 준비.

## 산출물
- `.gstack-fixtures/k2-free-inputs.json` (50개)
- `.gstack-fixtures/k3-concurrency-scenarios.json` (5개)
- `.gstack-fixtures/k3-onboarding-users.json` (5개)
- `.gstack-k2-runner.py`
- `.gstack-k3-concurrency-runner.py`
- `.gstack-k3-onboarding-runner.py`
- `.gstack-demo.py` (K1 timing wrapper 추가)
- memory `feedback_qa_auto_panel_audit.md` (18 → 25 항목)

## Phase 2 진입 절차
1. `~/.venv-maedeup-demo/bin/python3 .gstack-demo.py --fast` N=10 회 → K1.1/K1.3 분포
2. `~/.venv-maedeup-demo/bin/python3 .gstack-k2-runner.py --room-id <시드 룸>` → K2.1/K2.2/K2.3 비율
3. `~/.venv-maedeup-demo/bin/python3 .gstack-k3-concurrency-runner.py --scenario all` → K3.1/K3.2
4. `~/.venv-maedeup-demo/bin/python3 .gstack-k3-onboarding-runner.py` → K3.3
5. qa-runtime 위임으로 25항목 + K1.2 (docker logs grep) 종합 측정
6. 결과 통합 보고: `docs/handoff/2026-05-29-baseline-result.md` (Plan 2 작성 진입)

## 알려진 제약
- Task 5 의 backend mock OAuth endpoint 없으면 Google OAuth 우회 fix 필요 (Phase 1 산출물에는 fixture 만, runner skeleton 만 포함)
- Task 6 의 25항목 중 일부는 baseline 수치 미확정 (Phase 2 결과로 SLA 정정)
```

- [ ] **Step 6.3: CLAUDE.md "진행 중인 작업" 갱신**

`CLAUDE.md` 의 `**현재 task**` 라인을 Phase 1 완료 + Phase 2 진입 안내로 갱신.

- [ ] **Step 6.4: Commit + Push (자율 풀가속 모드)**

```bash
git add docs/handoff/2026-05-28-phase1-runners-ready.md CLAUDE.md
git commit -m "docs(phase1): K1/K2/K3 측정 인프라 완료 + Phase 2 진입 안내

Phase 1 산출물 6개 + memory 25항목 확장 완료.
baseline 측정 절차 6 step 명시. Plan 2 (Phase 3 fix) 는 baseline 결과 후 작성."
git push origin main
```

(memory 파일은 git 추적 외부라 별도 commit 불필요. `~/.claude/projects/...` 디렉토리는 macOS/Linux 사용자 디렉토리.)

---

## Self-Review (writing-plans skill step)

### Spec coverage
- K1.1 → Task 1 ✅
- K1.2 → Task 6 step 6.1 (qa-runtime memory 25항목) ✅
- K1.3 → Task 1 + Task 6 step 6.1 ✅
- K2.1/K2.2/K2.3 → Task 2 + Task 3 ✅
- K3.1/K3.2 → Task 4 ✅
- K3.3 → Task 5 ✅
- Phase 1 산출물 (6 파일 + memory 확장) → Task 1~6 전부 ✅
- Phase 2 진입 절차 → Task 6 handoff ✅

### Placeholder scan
- Task 5 의 backend OAuth mock endpoint 존재 여부 불확실 — step 5.2 에 "확인 + 별 task 후보" 명시 (intentional, baseline 측정 진입에 blocking 아님)
- Task 3 의 step 3.2 `send_chat_and_capture` 의 실제 trigger event 수신 로직은 `.gstack-demo.py` 의 WS 수신 패턴 참고 — placeholder 명시 (intentional)
- 기타 TODO/TBD 없음

### Type consistency
- fixture 스키마 (Task 2 schema) ↔ runner 의 `item["input"]`, `item["expected_intent"]` 등 ↔ aggregate 함수의 `r["expected"]["expected_intent"]` — 모두 일관
- `_k1_marks` (Task 1 step 1.1) ↔ `_k1_record` 호출 (step 1.2) — 일관

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-27-phase1-measurement-infra.md`.**

자율 풀가속 모드 (사용자 2026-05-27 명시) — 사용자 추가 redirect 전까지 무질문 자율 진행.

**기본 진행 방식: Subagent-Driven** — Task 1 부터 순차, 각 task subagent 위임 + 회귀 검증 + commit + push. Task 간 PM 직접 결과 점검만 (사용자 confirm 없이 진행).

Phase 2 baseline 측정 진입 직전 (Task 6 commit + push 직후) handoff 보고로 turn 종료 — 사용자가 baseline 측정 시작 결정.
