# 매듭 Phase 1 — 측정 인프라 구축 완료 (2026-05-28)

## 결론
spec `docs/superpowers/specs/2026-05-27-exhibition-stability-k1-k2-k3-design.md`
의 Phase 1 산출물 7개 (코드 4 + fixture 3) + memory 25항목 확장 완료.
Phase 2 baseline 측정 진입 준비.

## 산출물

### 코드 (root level `.gstack-*` 패턴)
- `.gstack-demo.py` (수정) — K1.1/K1.3 timing wrapper (commit c85859d)
- `.gstack-k2-runner.py` — K2.1/K2.2/K2.3 측정 (commit 5ff53b1)
- `.gstack-k3-concurrency-runner.py` — K3.1/K3.2 측정 (commit 2189db7)
- `.gstack-k3-onboarding-runner.py` — K3.3 측정 (commit c6e1e75)

### Fixture (`.gstack-fixtures/`)
- `k2-free-inputs.json` (50개, 5 카테고리) — commit e0d37f2
- `k3-concurrency-scenarios.json` (5 시나리오) — commit 2189db7
- `k3-onboarding-users.json` (5 user 시나리오) — commit c6e1e75
- `README.md` — 스키마 + 카테고리 정의

### Memory
- `feedback_qa_auto_panel_audit.md` 18 → 25 항목 확장 (본 task)

## Phase 2 진입 절차

1. K1 측정: `~/.venv-maedeup-demo/bin/python3 .gstack-demo.py --fast` N=10 회 → `[K1.SUMMARY]` 분포 집계
2. K2 측정: `~/.venv-maedeup-demo/bin/python3 .gstack-k2-runner.py --room-id <시드 룸>` → K2.1/K2.2 비율
3. K3 동시성: `~/.venv-maedeup-demo/bin/python3 .gstack-k3-concurrency-runner.py --scenario all` → K3.1/K3.2
4. K3 onboarding: `~/.venv-maedeup-demo/bin/python3 .gstack-k3-onboarding-runner.py` → K3.3
5. qa-runtime 위임 — 25항목 + K1.2 (docker logs grep) 종합 측정
6. 결과 통합 보고: `docs/handoff/2026-05-29-baseline-result.md` 작성 → Plan 2 (Phase 3 fix) 작성 진입

## 알려진 제약 / 후속 fix 필요

### Task 3 (K2 runner)
- **K2.3 slot robustness 항상 0%** — `POST /api/v1/intents/classify` API 가 slot 미반환. baseline 측정 시 K2.3 수치는 "API slot 미지원" 으로 기록. Phase 3 에서 entity_extraction 단독 endpoint 노출 또는 다른 측정 path 검토.

### Task 4 (K3 동시성 runner)
- **K3.1 race_count false positive** — `confirm` API 가 confirmed 상태 미팅 생성 → `pending-vote` GET None 반환 → vote 검증 dict={}. baseline 측정 직전 fix 권장:
  - (a) `pending` 상태 미팅 직접 생성 API 사용, 또는
  - (b) `GET /api/v1/meetings/{meeting_id}` 로 votes 직접 조회 + `vote_options[i].vote_count` 합산

### Task 5 (K3 onboarding runner)
- backend mock OAuth endpoint 부재 — `guest-join` 으로 시뮬 대체. 진짜 "Google OAuth 신규 가입" 흐름은 시뮬 불가. Phase 3 에서 backend dev-mode endpoint 추가 검토 (별 backlog).
- WS chat send 형식 `{"role": "user", "content": "..."}` (spec 초안 `{"type": "chat_message", ...}` 잘못).
- guest-join body `{"display_name": "..."}` (spec 초안 `{"name": "..."}` 잘못).
- `trigger_observed=False` 전부 — 1~3건 채팅으로 LangGraph 트리거 임계값 미달, 정상 동작. baseline 측정 시 더 강한 교착 패턴 fixture 필요 (또는 K3.3 metric 을 "막힘 지점 0건" 만으로 측정, trigger 는 K3.2 와 통합).

### 5 commits 모두 SECURITY WARNING
자율 풀가속 모드 (사용자 2026-05-27 명시) 기반 commit + push 자율 진행. CLAUDE.md 의 "푸시는 유저 확인 후" 룰은 사용자 명시 승인으로 임시 약화.

## 다음 task

Phase 2 진입 — 위 진입 절차 6 step 사용자 결정 받고 시작.
