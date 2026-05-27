# Phase 2 — K1/K2/K3 baseline 측정 결과 (2026-05-29)

## 결론
9개 KPI 중 **4개 PASS / 5개 FAIL**. 미달 5개 (K1.1 / K1.2 / K1.3 / K2.3 / K3.1)
가 Phase 3 fix scope.

핵심 발견:
- **K1 latency (Q파이프라인) 가 SLA 큰 폭 초과** — p50 32.66s (SLA 5s 의 6.5배), p95 62.10s
  (SLA 8s 의 7.7배). place_recommend (intent place_suggestion) Gemini 호출 본문에
  ~20s 이상 누적. ACT 2 (vote_card 생성) 도 동일 30s 대.
- **K2 intent 분류 정확도/트리거율은 이미 PASS** — 정규식 + classify endpoint
  의 자유 입력 robust 함. K2.3 만 API 미반환으로 측정 불가 (별 트랙).
- **K3 동시성은 K3.1 (진짜 race) 만 FAIL** — 2명 동시 manual pick 시 2건 confirm
  모두 성공 (race-free 면 ≤1). 다른 broadcast/onboarding 시나리오는 0건 missing.
- **K1.2 (Gemini fallback) 측정 시 ml_place_search model 파일 부재로 100% Gemini
  fallback 으로 동작 중** — `/data/output/training/models/model_v2_no_sentiment.pkl`
  미존재. Gemini 자체 fallback rate 는 timeout retry 40% / 최종 fail 10%.

## 측정 결과 표

| KPI | metric | SLA | 측정값 | 결과 |
|---|---|---|---|---|
| K1.1 | trigger→card p50 (ACT2) | <5s | 32.66s | FAIL |
| K1.1 | trigger→card p95 (ACT2) | <8s | 62.10s | FAIL |
| K1.1 | trigger→card p50 (ACT5) | <5s | 22.26s | FAIL |
| K1.2 | Gemini timeout retry rate | <10% | 40% (4/10) | FAIL |
| K1.2 | Gemini 최종 실패 rate | <10% | 10% (1/10) | FAIL (경계) |
| K1.3 | direct_request → card p50 | <5s | 22.26s | FAIL |
| K2.1 | 자유입력 트리거율 | >80% | 94.9% (37/39) | PASS |
| K2.2 | intent 정확도 | >85% | 90.0% (45/50) | PASS |
| K2.3 | slot robustness | >75% | 40% (20/50, classify API slot 미반환) | FAIL (별 트랙) |
| K3.1 | race count | 0 | 1 | FAIL |
| K3.2 | broadcast missing | 0 | 0 | PASS |
| K3.3 | onboarding block | 0 | 0 (5/5 clean) | PASS |
| QA-23 | ACT 5.5 토글 silent fail | 0/10 | 10/10 BACKUP 발동 | FAIL (신규 발견) |
| QA-25 | quota / 429 신호 | 0 | 0 | PASS |

## 측정 raw 데이터

### K1.1 / K1.3 시연 자동화 N=10
ACT2 (시간 교착 → vote_card) sorted samples (단위 s):
`[30.26, 31.52, 31.88, 32.29, 32.66, 32.74, 33.50, 36.83, 58.08, 62.10]`
- min 30.26 / p50 32.66 / mean 38.19 / p95 62.10 / max 62.10

ACT5 (장소 직접 요청 → place_card, = K1.3) sorted samples:
`[20.26, 20.73, 21.75, 21.75, 22.26, 22.28, 22.29, 22.77, 23.29, 23.79]`
- min 20.26 / p50 22.26 / mean 22.12 / p95 23.79 / max 23.79

특기: ACT2 에 큰 outlier 2건 (58.08 / 62.10) — Gemini timeout retry 와 일치 시간.
ACT5 는 분산 작음 (3.5s 범위) → 측정 안정.

raw logs: `/tmp/maedeup-baseline-k1-{1..10}.log` (각 ~50KB)

### K1.2 Gemini fallback (30분 docker logs)
- `ml_place_search 실패, Gemini fallback`: **10건 / 10 시연 = 100%** (model 파일 부재)
- `gemini_timeout attempt=1 retrying`: **4건** (timestamps 00:07:10 / 00:16:49 / 00:20:10 / 00:22:44)
- `gemini_call_failed type=TimeoutError`: **1건** (00:23:08, retry 후 최종 실패)
- Gemini 호출 본수 (place_suggestion intent run): **10건**
- → retry 발생률 40%, 최종 실패율 10%
- 429 / quota 신호: **0건** (timestamp false positive 만 검출됨)

### K2 자유 입력 N=50
- 총 50 발화, classify timeout 1건 (k2-013 'ㅇㅋ 그럼 거기서 봐' — ReadTimeout)
- K2.1 trigger expected = 39건, 분류 일치 37건 = **94.9%**
- K2.2 intent top-1 일치 = 45/50 = **90.0%**
- K2.3 slot robust = 20/50 = **40.0%** (expected_slot={} 항목만 카운트 — classify
  endpoint 가 slot 미반환이므로 측정 불가, 별 트랙)
- 5건 mismatch:
  - k2-013 (ReadTimeout)
  - k2-023 'ㅇㅋ 😊 거기서 보자' → meeting_schedule (expected general)
  - k2-029 '🍖 고기 먹으러 가자' → general (expected place_suggestion)
  - k2-045 '오조오억년만에…' → general (expected meeting_schedule)
  - k2-047 '그냥 아무데나 ㄱ' → place_suggestion (expected general)

raw log: `/tmp/maedeup-baseline-k2.log`

### K3.1 / K3.2 동시성 N=5
- k3-conc-001 (5명 동시 vote 동일): GREEN race=0 missing=0 (0.7s)
- k3-conc-002 (5명 동시 vote 다른): GREEN race=0 missing=0 (0.7s)
- k3-conc-003 (2명 동시 manual pick): **YELLOW race=1** — 2건 confirm 모두 201 OK
- k3-conc-004 (10명 broadcast): GREEN missing=0 (12.2s)
- k3-conc-005 (5명 동시 busy_period): GREEN race=0 missing=0 (0.5s)

K3.1 race=1 의 root cause: confirm endpoint 가 동시 호출에 대해 lock 없음. 동일
meeting 에 대해 두 사용자가 동시에 confirm → 둘 다 201 응답.

raw log: `/tmp/maedeup-baseline-k3-conc.log`

### K3.3 onboarding N=5
- k3-onb-001 ~ k3-onb-005: 모두 blocks=0 graceful=일관
- 5/5 clean
- trigger_observed=False (이미 알려진 fixture 약함 — fix backlog)

raw log: `/tmp/maedeup-baseline-k3-onboard.log`

## qa-runtime 25항목 검증
19~25 항목 중심 (Phase 2 baseline 새로 측정):
- [19] K1.1 latency 분포 — FAIL (위)
- [20] K1.2 Gemini fallback — FAIL (위)
- [21] K1.3 direct_request — FAIL (위)
- [22] K3.2 broadcast 정확성 — PASS
- [23] silent fail (ACT 5.5 토글) — **FAIL 신규 발견** — 시연 10회 모두 'preference_toggle
  미노출, ACT 5.5 스킵' BACKUP 발동. preference_toggle_enabled flag 가 항상 false
  추정. 신규 BUG-27-X 후보.
- [24] 시연 완료 메시지 ("초대 알림 전송" 텍스트) — PASS (10/10 노출)
- [25] quota / rate limit — PASS (0건)

1~18 항목 (시연 1회 통합 검증): 마지막 시연 (`/tmp/maedeup-baseline-k1-10.log`)
의 결과로 보면 시연이 ACT 3/4/5 모두 정상 완료, partial 카드 발행 + 최종 확정
모두 OK. ACT 5.5 만 BACKUP 발동.

## Phase 3 fix scope 제안

### P0 (E2E SLA 무력화)
1. **K1.1 / K1.3 latency 감축** — 현재 p50 22~32s, SLA 5s. 5~7배 단축 필요.
   - root cause 후보 (Gemini wait): `app/services/gemini.py` 의 timeout=25s 가
     너무 길다. 또한 single-shot Gemini 의존도 가 높음. 캐싱/병렬화/streaming/짧은
     prompt 가 모두 후보.
   - fix 옵션:
     - (a) **Gemini paid key 도입** (현재 free key 추정 → quota/지연 시 retry 큼)
     - (b) **place_search 결과 캐싱** (동일 query 재발화 시 즉시 응답)
     - (c) **intent_classifier 모델 로컬 적재** (정규식 embedding-only path)
     - (d) **free-slots 캐싱** (이미 LIMIT-7 backlog)
     - (e) **partial card prefetch** (사용자 발화 직후 background 호출 시작)
   - 권장: (b) + (e) 우선 도입. spec v2 PR-V2.2 후보.

2. **K1.2 ml_place_search model 배포** — `model_v2_no_sentiment.pkl` 파일 부재
   - 시연 10건 100% Gemini fallback → ACT 5 의 ~20s 대부분이 이 fallback 비용
   - fix: model 파일 docker 이미지/볼륨에 배포. 동시에 ML 모델 fallback 시점 단축
     (Gemini 호출 본수 절반 이상 감소 기대).

3. **K3.1 race condition** — confirm endpoint 동시성 lock
   - root cause: `POST /api/v1/meetings/{id}/confirm` 가 row lock 없이 status
     update. 동시 confirm 2건 모두 201 응답 + 두 번째 호출이 첫 번째 결과 덮어쓰기.
   - fix: SELECT … FOR UPDATE + status 사전 체크, 또는 unique constraint
     (room_id, status='confirmed') partial index.

### P1 (특정 기능 신뢰성)
4. **K2.3 slot robustness 측정 인프라** — classify endpoint slot 반환 또는
   별 entity_extraction endpoint 추가. 현재 측정 불가.

5. **ACT 5.5 preference_toggle silent fail (신규)** — 시연 10회 모두 BACKUP 발동.
   preference_toggle_enabled flag root cause 조사 필요. 시연 시연자 UX 영향 큼.

### P2 (개선 backlog)
6. K1.2 Gemini timeout 단축 (25s → 10s) + 더 적극적 retry 정책

## commit + push

본 handoff 작성 후 commit + push 예정 (자율 풀가속 모드).

다음 task: Phase 3 plan 작성 (위 P0 fix 순서 + spec v2 PR 후보 매핑).
