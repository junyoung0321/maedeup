# 전시 안정성 spec — K1/K2/K3 data-driven

작성: 2026-05-27 (PM Claude Opus 4.7) | 전시 D-8 (2026-06-04)

## GOAL

**전시일 (2026-06-04) 까지 매듭이 관람객의 자유 사용자 발화 + 다인 룸 동시 사용 환경에서 안정적으로 작동.**

GOAL = **이상치**: KPI 9개 모두 잠정 SLA 통과.
Exit (GO 조건) = **현실치**: 아래 "Exit Criteria" 섹션 — 6개+ 통과 + 잔존 도우미 운영 안내문/alarm rule 준비. 시연 시나리오 GREEN 만으로 충족 X (시나리오 ≠ 자유 사용).

## 배경

- 전시 사용 방식: QR/링크 진입 → 관람객 본인 계정 생성 → 친구 초대 → 실제 모임 조율 시도. 시나리오 가이드 없음.
- 시연 자동화 (`.gstack-demo.py --fast`) 는 정해진 발화·순서·룸 크기 (2~4명) 만 검증. 자유 입력·다인 룸·동시성·신규 가입 흐름 모두 미검증.
- 사용자 (PM 김창윤) 우선순위 명시 (2026-05-27): "AI 응답 속도 + 사용자 채팅에 따라 시스템이 잘 작동 + 여러 사용자 사용 흐름 대응".
- root cause 우선 룰 ([[feedback-root-cause-over-surface-fix]]) — 추측 fix 금지, data-driven baseline → 미달 영역 fix.

## KPI 정의

| ID | metric | 잠정 SLA | sampling | 측정 도구 |
|---|---|---|---|---|
| **K1.1** 트리거 → 첫 카드 latency | p50 / p95 wall-clock sec | p50 < 5s, p95 < 8s | 시연 fast 모드 N=20 | `.gstack-demo.py` timestamp wrapper |
| **K1.2** Gemini fallback 빈도 | failure rate (timeout/error) | < 10% | 정상 발화 N=20 | backend log grep + gemini 호출 카운터 |
| **K1.3** direct_request → 카드 (ACT 5) | wall-clock sec | < 5s (scenario-v3 A5-1) | ACT 5 만 N=10 | `.gstack-demo.py` ACT 5 isolate run |
| **K2.1** 자유입력 트리거 발화율 | trigger emission ratio | > 80% | 자유입력 50셋 (반말/줄임말/이모지/오타/은어) | 신규 `tools/k2_free_input_runner.py` |
| **K2.2** intent 분류 top-1 정확도 | top-1 match rate | > 85% | 자유입력 50셋 + 예상 intent 라벨 | 같은 runner + intent_classifier 응답 grep |
| **K2.3** slot extractor robustness | 슬롯 추출 성공률 | > 75% | 모호 표현 30셋 (예: "다다음주", "오후쯤") | 같은 runner + entity_extraction 응답 grep |
| **K3.1** 동시 vote/manual pick race | 깨짐 건수 | 0건 | 5명 룸 × 동시 3 vote 시나리오 N=5 | 신규 `tools/k3_concurrency_runner.py` |
| **K3.2** WS broadcast 누락 | event 미수신 비율 | 0건 | 10명 룸 × 1 trigger 시나리오 N=3 | 같은 runner + WS client 다중 connect |
| **K3.3** 신규 가입 onboarding | 막힘 지점 수 | 0건 | 시뮬 신규 사용자 가입 → 방 생성 → 친구 초대 → 첫 입력 흐름 N=5 | 신규 `tools/k3_onboarding_runner.py` |

### 잠정 SLA 근거
- K1.1 / K1.3: scenario-v3 A5-1 "시연 임팩트" 요구사항 5s 기준 + 사용자 일반 인내심 8s
- K1.2: Gemini paid key + retry 1 정책 (`b5275e5`) 기반 추정
- K2.1 / K2.2 / K2.3: 졸업 전시 기준 적정선 (production grade ≠ academic demo)
- K3.*: 시연 핵심 가치 = "race 0, 누락 0" — degradation 즉 결함

## Phase 구조

### Phase 1: 측정 인프라 구축 (D-8 ~ D-7, 2026-05-27 ~ 2026-05-28)

**산출물**:
1. `.gstack-demo.py` 확장 — K1 timestamp 자동 기록 (`time.monotonic()` wrapper, 각 ACT 시작/종료 marker, stdout `[K1.1] ACT 2 trigger→card: 4.32s` 출력)
2. `qa-runtime` 자동 검증 18 → 25항목 (K1.1/K1.2/K1.3 + K3.2 추가)
3. `tools/k2_free_input_runner.py` 신규 — 자유입력 50셋 fixtures + 발화 → 응답 grep → 결과 표 출력
4. `tools/k3_concurrency_runner.py` 신규 — 다인 룸 동시 시나리오 (asyncio gather, 동시 vote/manual pick)
5. `tools/k3_onboarding_runner.py` 신규 — 신규 사용자 가입 흐름 시뮬레이션 (HTTP 클라이언트 + Google OAuth mock)
6. fixture 데이터: `tests/fixtures/k2_free_inputs.json` (50개) + `tests/fixtures/k3_concurrency_scenarios.json` (5개)

### Phase 2: baseline 측정 (D-6, 2026-05-29)

**절차**:
1. K1 측정: `.gstack-demo.py --fast` N=20 회 → K1.1/K1.2 분포 자동 집계
2. K1.3 측정: `.gstack-demo.py --act5-only` N=10 회 → wall-clock 분포
3. K2 측정: `python tools/k2_free_input_runner.py --fixture k2_free_inputs.json` → 트리거율/intent/slot 표
4. K3 측정: `python tools/k3_concurrency_runner.py --scenario all` N=5 + `tools/k3_onboarding_runner.py` N=5
5. 결과 통합 보고 (`docs/handoff/2026-05-29-baseline-result.md`)
6. **사용자 review gate** — baseline 결과 보고 → fix scope 합의

### Phase 3: root cause fix — 미달 영역만 (D-5 ~ D-3, 2026-05-30 ~ 2026-06-01)

**원칙**: baseline 결과로 미달 KPI 만 fix. 추측 fix 금지.

**미달 가능 영역 (추정 — 실제 fix 는 baseline 후 결정)**:
- K1.1/K1.2 미달 → free-slots 캐싱 (LIMIT-7), intent_classifier 모델 적재 (qa-runtime 보고 model_v2 missing), Gemini paid key + retry 정책 재검토
- K2.1/K2.2/K2.3 미달 → 정규식 보강 (해결점 O), Gemini fallback 정책 (timeout 단축 + 안내 UI), slot extractor 모호 표현 룰 추가
- K3.1/K3.2 미달 → DB row lock / Redis lease, broadcast retry, WS reconnect catch-up
- K3.3 미달 → onboarding 흐름 막힘 지점 fix (Google OAuth 테스트 사용자 안내, 첫 방 생성 가이드 등)

각 fix 마다:
- 별 commit (root cause 명시)
- 변경 영역만 qa-runtime 회귀 검증
- fix 진행 사용자에게 1줄 알림

### Phase 4: 재측정 + GO/NO-GO (D-2 ~ D-1, 2026-06-02 ~ 2026-06-03)

**절차**:
1. Phase 2 동일 측정 절차 재실행
2. 개선 표 (before/after)
3. 잔존 미달 영역:
   - 도우미 운영 안내문 작성 (전시 부스에 비치)
   - alarm rule 설정 (Gemini quota soft limit, 에러 burst rate)
4. **사용자 GO/NO-GO 결정 gate**

## Exit Criteria (GO 조건)

- KPI 9개 중 6개+ SLA 통과 + 잔존 미달 영역 도우미 운영 안내문 준비 완료
- silent-fail audit P1 backlog 처리 진행률 50%+ (별 트랙, 본 spec 외)
- 시연 시나리오 GREEN 유지 (회귀 0)

## Out of scope (별 backlog)

- 모바일 호환성 (사용자 우선순위 외 — 별 spec 후보)
- silent-fail audit P1 15건 (별 트랙, qa-runtime 자동 검증 18→25 항목에 일부 흡수)
- P2-1 `scheduled_at` 컨벤션 정합화 (시연 GREEN, 사용자 visible 정상)
- v2 spec 본문 (별 트랙)
- 시연 영상 촬영 (날짜 TBD — 본 spec exit 이후)

## 산출물 목록

### 코드
- `.gstack-demo.py` (확장)
- `tools/k2_free_input_runner.py` (신규)
- `tools/k3_concurrency_runner.py` (신규)
- `tools/k3_onboarding_runner.py` (신규)

### Fixtures
- `tests/fixtures/k2_free_inputs.json` (50개)
- `tests/fixtures/k3_concurrency_scenarios.json` (5개)
- `tests/fixtures/k3_onboarding_users.json` (5개)

### 문서
- 본 spec
- `docs/handoff/2026-05-29-baseline-result.md` (Phase 2 결과)
- `docs/handoff/2026-06-03-go-nogo-decision.md` (Phase 4 결정)

### Memory
- (필요 시 새 feedback memory — fix 진행 중 발견된 새 패턴)

## 위험 + 완화

| 위험 | 완화 |
|---|---|
| Phase 1 구축 시간 초과 (D-7 못 맞춤) | runner 분리 (K2 / K3 / K3-onboarding 병행 가능) — 한 개라도 GREEN 측정 가능 |
| Phase 2 baseline 결과 모두 미달 | Phase 3 우선순위 = K3 (race/누락 0건 = 시연 가치) > K1 (latency) > K2 (robustness, 부분 도우미 안내로 보완 가능) |
| Phase 3 fix 회귀 발생 | 각 fix 마다 qa-runtime 회귀 검증 강제, 회귀 시 즉시 revert |
| Gemini paid key quota 소진 | quota monitor + alarm rule (Phase 4 alarm 에 포함) |

## 의존성

- silent-fail audit P0 4건 가시화 완료 (`f717b06`) — Phase 1 측정 시 silent fail 무음 차단 효과
- bug-26-g/f fix 완료 (`8ceffdb`) — 첫 추천 메시지 시각 일관성 baseline 가능
- P1-2 TZ fix 완료 (`595fa0b`) — vote_options payload 형식 baseline 가능

## 진행 트래킹

- TaskCreate 로 Phase 단위 task 생성
- 각 Phase 완료 시 handoff 문서 갱신 ([[feedback-handoff-auto-update]])
- 사용자 review gate 2개 (Phase 2 baseline 보고, Phase 4 GO/NO-GO) — AskUserQuestion 으로 알림 트리거 ([[feedback-askuserquestion-for-rc-notification]])

## Implementation plan 분할 정책

본 spec 은 9 KPI × 4 Phase 로 단일 implementation plan 으로 묶으면 too large. 분할:

1. **Plan 1 (writing-plans 즉시 작성)**: Phase 1 만 — 측정 인프라 구축 (`.gstack-demo.py` 확장 + 3 runner + fixtures). 명확하고 self-contained.
2. **Plan 2 (Phase 2 baseline 결과 보고 후 작성)**: Phase 3 fix 항목 — 미달 KPI 만, baseline 결과 기반 root cause 명시. 추측 fix 회피.
3. **Plan 3 (Phase 4 직전 작성)**: 재측정 + 도우미 운영 안내문 + alarm rule.

이렇게 분할하면 각 plan 이 단일 implementation 단위 + 사용자 review gate 가 자연스럽게 spec 외부에 배치됨.
