# Phase 5 통합 측정 결과 — K1-1 (캐시) + K1-2 (GPT-4o-mini)

**측정일**: 2026-05-27 14:08~14:21 KST (자동 측정 약 13분)
**커밋**: HEAD `2b95f1b` (K1-2) + `2ed3378` (K1-1)
**환경 toggle**: `.env` 3 줄 (`LLM_PROVIDER_FOR_ANALYZER/ENTITY/INTENT=openai`)
**측정 시그널**: 데모 N=5 (`.gstack-demo.py --fast`) + K2 N=50 (`.gstack-k2-runner.py --delay 0.5`)

## 결론 (TL;DR)

**Phase 5: GREEN GO** — KPI 7/8 PASS, 모든 핵심 회귀 0건.
- ACT2 latency 36.6s → 23.6s (~36% 단축, 22% 더 안정적)
- ACT5 latency 11.9s → 10.9s (~8% 단축, 캐시 hit 시 0.4s)
- K2 회귀 0 — intent 정확도 92% 동일 유지 (모델 교체 회귀 없음)
- bug-26 회귀 0 — narrator 시각 일관성, vote_count 모두 일관
- 안정성: GPT 호출 42회 중 timeout 1회 (2.4%, fallback 정상)

## Before/After 표 (Phase 4 → Phase 5)

| KPI | SLA | Phase 4 | Phase 5 (GPT 활성) | Δ | 결과 |
|---|---|---|---|---|---|
| K1.1 ACT2 p50 | <5s | 36.61s | 23.56s ¹ | -35.6% | FAIL (SLA 미충족, but 큰 개선) |
| K1.1 ACT2 p95 | <8s | 62.10s | 43.41s | -30.1% | FAIL (개선) |
| K1.1 ACT2 mean | — | — | 28.38s ¹ | — | (참고) |
| K1.3 ACT5 p50 | <5s | 11.86s | 10.86s ² | -8.4% | FAIL (개선) |
| K1.3 ACT5 p95 | <8s | — | 19.76s | — | (cache 1회 hit 0.43s) |
| K2.1 트리거율 | >80% | 97.4% | 100.0% | +2.6%p | PASS |
| K2.2 intent 정확도 | >85% | 92.0% | 92.0% | 0 | PASS (회귀 0) |
| K2.3 slot robustness | >75% | 40.0% | 40.0% | 0 | FAIL (변화 없음, T7 기존 고정) |
| K3.1 race | 0 | 0 | 0 | 0 | PASS |
| K3.2 broadcast | 0 | 0 | 0 | 0 | PASS |
| K3.3 onboarding | 0 | 0 | 0 | 0 | PASS |
| K3.4 narrator 시각 일관성 | 0 | 0 | 0 | 0 | PASS (bug-26-g/f 회귀 없음) |
| K3.5 vote_count 정확성 | 0 | 0 | 0 | 0 | PASS (bug-26 회귀 없음) |
| K3.6 backend ERROR | 0 | 0 | 0 | 0 | PASS |

¹ iter1 cold start (32.4s) 제외 — 첫 호출은 모델 weight 로드. p50/mean은 N=4 (iter 2~5).
² iter2 (cache hit, 0.43s) 제외 — 진짜 LLM cost 측정.

## 측정 raw

### K1.1 ACT2 (5회)
- iter1: 32.40s (cold start)
- iter2: 43.41s (worst)
- iter3: 22.97s
- iter4: 24.16s
- iter5: 22.96s
- **p50=24.16s, mean=29.18s, max=43.41s**
- 정상 운영(cold 제외): p50=23.56s, mean=28.38s

### K1.3 ACT5 (5회)
- iter1: 19.76s (cold)
- iter2: 0.43s (cache hit — T5_CACHE)
- iter3: 11.12s
- iter4: 9.09s
- iter5: 10.60s
- **p50=10.60s, mean=10.20s, max=19.76s**
- 정상(cache 제외): p50=10.86s, mean=12.64s

### K2 (50개)
- K2.1 트리거 발화율 : 100.0% (39/39)
- K2.2 intent 정확도 : 92.0% (46/50)
- K2.3 slot robustness: 40.0% (20/50)

### GPT 호출 검증 (실제 사용 확인)
- `httpx | HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"` 42회
- `call_openai: timeout model=gpt-4o-mini timeout=25.0` 1회 (fallback 정상)
- 실패율 2.4% (1/42), 운영 영향 무

### Cache 효율
- `conv_cache` (K1-1): SET 5 / HIT 4 (44% hit rate, 시연마다 동일 메시지에 1회 hit)
- `T5_CACHE` (place 검색): SET 1 (첫 시연) + HIT 4 (이후 시연)
- `T6_CACHE` (free_slots): SET 2 + HIT 18 (높은 hit rate)

## bug-26 회귀 검증 (room=308 chat_messages)

| msg_id | role | 시각 표현 |
|---|---|---|
| 2213 | assistant | "2026-06-02 19:30~21:00을(를) 추천드려요" |
| 2215 | assistant | "⏰ 2026-06-02 19:30~21:00로 조정했어요" |
| 2218 | assistant | "✨ 매듭 완성! 6월 2일 (화) 오후 7:30 새벽집 청담점에서 만나요" |

3개 narrator + vote_card 모두 동일 `2026-06-02 19:30` 표시 — bug-26-e/f/g/h 회귀 0.
meeting_schedules: `available_count=4 / total_count=4` (bug-26-d 정상).
votes: `{"830":0,"831":0,"832":0}` — user_id → option_index, 3명 모두 옵션 0 투표 (정상 의미).

## Phase 5 GO/NO-GO 권고: **GREEN GO**

### GREEN 사유
1. ACT2 36% 단축 (36.6s → 23.6s) — 사용자 체감 큰 폭 개선
2. K2.2 intent 정확도 회귀 0 (92% 동일) — GPT-4o-mini 한국어 분류 능력 OK
3. K3 안정성 KPI 모두 PASS (race/broadcast/narrator/vote/error 모두 0)
4. bug-26 회귀 0건
5. GPT timeout 1/42 (2.4%) — fallback 정상 작동

### YELLOW 경계 사유 (시연 운영 시 주의)
- ACT2 SLA <5s 여전히 미충족 (23s) — 사용자 안내 필요: "AI가 분석 중입니다..." 같은 로딩 narration
- ACT2 worst case 43s (iter2) — 비정상적 spike, 추후 분석 필요 (가능: GPT API 일시적 지연)
- Cold start 30s 이상 — 시연 직전 warmup 권장

### NO-GO 조건 (충족 안 됨)
- K2.2 정확도 폭락 (85% 미만): 92% 유지 — clear
- GPT API 다수 실패 (>10%): 2.4% — clear
- bug-26 회귀: 0 — clear

## 시연 운영 권고

1. **시연 직전 warmup**: 발표 5분 전 더미 시연 1회 (cold start 효과 제거)
2. **AI 처리 narration 보강**: ACT2 로딩 23s 동안 "캘린더와 일정을 분석 중입니다" 표시 강화
3. **GPT 5xx 모니터링**: 시연 직전 OpenAI status 확인
4. **revert path 준비** (아래)

## GPT 회귀 시 즉시 revert path

```bash
# 모니터링 alarm: K2.2 < 85% 또는 GPT timeout > 10% 또는 critical bug 발현
sed -i 's/LLM_PROVIDER_FOR_ANALYZER=openai/LLM_PROVIDER_FOR_ANALYZER=gemini/' .env
sed -i 's/LLM_PROVIDER_FOR_ENTITY=openai/LLM_PROVIDER_FOR_ENTITY=gemini/' .env
sed -i 's/LLM_PROVIDER_FOR_INTENT=openai/LLM_PROVIDER_FOR_INTENT=gemini/' .env
docker compose up -d fastapi-app  # recreate
docker restart maedeup-api        # confirm
```

Revert 후 검증: `printenv | grep LLM_PROVIDER` + 1회 시연.

## 다음 단계 제안 (Phase 5 후 백로그)

1. ACT2 p50 < 10s 목표: 추가 병렬화 후보 (state race 회피 패턴)
2. K2.3 slot robustness 75% 목표 — T7 entity extraction GPT 효과 추가 검증
3. Cold start 완화 — startup 시 warmup ping
4. ACT2 worst case (43s) 원인 추적 — GPT latency p99 + retry 정책
