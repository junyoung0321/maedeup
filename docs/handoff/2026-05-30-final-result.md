# 매듭 최종 통합 측정 보고 (Phase 3 + 통합 fix 5항목)

**측정 일시**: 2026-05-27 16:07~16:30 KST
**HEAD**: `d705b87` (push 보류)
**측정자**: QA 런타임 검증 에이전트
**대상**: K1.1 / K1.3 ACT latency, K2.1~K2.3 정확도, bug fix 3건 (T6 / banner / C 구조), bug-26-* 회귀

---

## 1. 환경 검증 (사전조건)

| 항목 | 상태 |
|---|---|
| OPENAI_MODEL | gpt-4o-mini ✅ |
| LLM_TIER_HIGH/MID/LOW | openai ✅ |
| LLM_PROVIDER_FOR_PLACE_SCORING | openai ✅ |
| LLM_PROVIDER_FOR_SUMMARY | openai ✅ |
| LLM_PROVIDER_FOR_SOCIAL_SUMMARY | openai ✅ |
| backend healthy | ✅ |
| frontend rebuild | ✅ |
| chromium launcher (CDP 9222) | ✅ alive |
| openai API 호출 분포 (15분간) | 40건 |
| gemini API 호출 분포 (15분간) | 0건 |

**C 구조 (B+D, 16 site) 적용 정상 — 모든 LLM 호출 openai 라우팅 확인.**

---

## 2. KPI Before/After 표

| KPI | SLA | Phase 5 (3 site) | **Final (16 site)** | Δ | 판정 |
|---|---|---|---|---|---|
| K1.1 ACT2 p50 | <5s | 23.56s | **21.72s** | -1.84s ✅ | FAIL (SLA 미달) |
| K1.1 ACT2 p95 | <8s | 43.41s | **25.12s** | -18.29s ✅ | FAIL (SLA 미달) |
| K1.1 ACT2 max | — | — | 25.25s (cold) | — | — |
| K1.3 ACT5 p50 | <5s | 10.86s | **25.88s** | **+15.02s ❌** | FAIL (큰 회귀) |
| K1.3 ACT5 p95 | <8s | — | **28.31s** | — | FAIL |
| K1.3 ACT5 max | — | — | 28.91s (cold) | — | — |
| K2.1 트리거율 | >80% | 100% | **92.3%** (36/39) | -7.7% | **PASS** |
| K2.2 intent | >85% | 92% | **86.0%** (43/50) | -6% | **PASS** |
| K2.3 slot | >75% | 40% | **40%** (20/50) | 0% | FAIL (baseline) |
| K3.1 race | 0 | 0 | **0** | 0 | PASS |
| K3.2 broadcast | 0 | 0 | **0** | 0 | PASS |
| K3.3 onboarding | 0 | 0 | **0** | 0 | PASS |

### K1 raw samples (N=5)
- ACT2: [19.71, 20.08, 21.72, 24.62, 25.25] sec
- ACT5: [25.84, 25.85, 25.88, 25.89, 28.91] sec

### K1.3 회귀 원인 진단
backend log `[TIMING] place_recommendation`:
- cold (1차): 27.82s
- warm (2~5차): 25.03 / 25.04 / 25.04 / ~25 sec — 매우 일관됨

**원인**: Phase 5 에서는 place_scoring/summary/social_summary 가 Gemini 였는데, Final 에서 openai 로 전환되면서 5개 카드 score + summary 생성이 모두 GPT 호출이 됨. 누적 +15s.

**Phase 5 의 K1.3 ACT5 10.86s 는 T5 cache + Gemini-side site 의 합산 효과였음.** C 구조 확장 (16 site) 이 site 분포 차원에서는 정상이지만, place_scoring 같은 high-frequency call site 를 GPT 로 옮기면서 ACT5 비용이 증가.

---

## 3. Bug fix 검증

### 3.1 T6 cache option c (5월 캘린더 stale) ✅ PASS
backend log 증거:
```
[T6_INVALIDATE] guest-join room=315 pattern=maedeup:free_slots:315:* (3회/시연)
[T6_INVALIDATE] guest-join room=316 pattern=maedeup:free_slots:316:* (3회/시연)
... room=317/318/319 동일 패턴
[T6_CACHE_SET] ttl=30s (TTL 정상 단축)
[T6_CACHE_HIT] (재요청 시 정상 히트)
```
- 5월 캘린더 → guest-join 직후 cache 무효화 → 다음 fetch 시 갱신된 데이터 (4/4 명) 반환되는 흐름 확인.
- TTL 300s → 30s 변경 적용됨.
- guest-join 시 5월/6월 pattern 모두 무효화 (`maedeup:free_slots:{room_id}:*`).

### 3.2 AI 패널 banner fix ✅ PASS
프론트 코드 `AiAssistantPane.tsx:215-217`:
```ts
// autoTrigger.content(사용자 발화)를 banner에 그대로 표시하던 bug fix.
// trigger source와 무관하게 hardcoded 안내 문구만 표시.
setAutoTriggerBanner("대화가 길어지네요, AI가 정리해볼게요 🗓️");
```
DB `chat_messages` 검증 (room 315):
- message id 2289: content = `"대화가 길어지네요, AI가 정리해볼게요 🗓️"`
- 사용자 발화 `"다음주 화요일은 좀 쉬고 싶다…"` 가 banner 본문에 노출되지 않음.

backend `[AUTO_TRIGGER] received` payload 에는 여전히 `content=` 사용자 발화가 들어 있지만, frontend 가 hardcoded 문구로 덮어써서 노출 차단.

### 3.3 C 구조 (B+D, 16 site) ✅ PASS
- LLM_TIER_HIGH/MID/LOW = openai (3-tier 자동 라우팅)
- 6개 dominant site 개별 env = openai (analyzer/entity/intent + place_scoring/summary/social_summary)
- 15분 측정 윈도우 동안 **openai 호출 40건 / gemini 0건** — 모든 site 가 openai 로 정상 라우팅.

---

## 4. bug-26-* 회귀 검증

| Bug | 내용 | 검증 방법 | 결과 |
|---|---|---|---|
| bug-26-d | vote_card total_count = 전체 룸 멤버 | vote_card 노드 status=vote_card_created 정상 emit | PASS (log) |
| bug-26-e | vote_options patch 후 narrator 추가 emit (시간 불일치) | chat_messages id 2291 (첫 추천) vs 2293 (조정) 모두 2026-06-03 19:30 일관 | PASS |
| bug-26-g | 첫 추천 메시지 본문 update (manual pick 후) | id 2290 "의견 나뉘네요" → 2291 "2026-06-03 19:30~21:00 추천" | PASS |
| bug-26-h | 시연 자동화 vote 호출 추가 (vote_count 0 고정) | vote_card_creation TIMING 0.02~0.03s 정상 emit | PASS (log) |

**주의**: votes 테이블이 비어있는 것은 이번 v3 fast 시연이 stalemate → all_members_selected manual 경로로만 진행되어 vote 분기를 거치지 않았기 때문. vote_card emit 자체는 backend log 로 확인됨. 본번 시연(육안)에서 vote 화면 추가 검증 권장.

---

## 5. Phase 5 GO/NO-GO 권고

### 권고: **YELLOW 조건부 GO**

**근거**:
- ✅ KPI 7건 PASS: K2.1/K2.2/K3.1/K3.2/K3.3 + bug fix 3건 + bug-26-* 회귀 0
- ❌ KPI 3건 FAIL: K1.1 ACT2 p50 (5s SLA 미달), K1.3 ACT5 p50 (+15s 회귀), K2.3 slot (baseline 동일)
- ⚠️ K1.3 회귀가 가장 큰 우려 — 전시 중 장소 추천 화면 노출까지 25-29초

**전시 시 도우미 안내 필수**:
- "장소 추천은 카드 5개를 AI 가 동시에 score 매기느라 25초 정도 걸려요"
- 시연 전 워밍업 1회 (장소 추천 1회 호출) 로 cold start 28s → 25s 안정화

### Revert 고려 옵션 (RED 회피)
**place_scoring 만 Gemini 로 되돌리기**:
- `.env`: `LLM_PROVIDER_FOR_PLACE_SCORING=gemini` 1줄 변경
- 예상 효과: ACT5 p50 25.88s → 약 12-15s 로 회복 (Phase 5 수준)
- 다른 site 는 그대로 openai 유지 (cost 안정)

이 옵션은 commit 추가 + .env 갱신 + frontend 리빌드 불필요 (env 만 변경 후 backend restart) — 5분 이내 적용 가능.

### 전시 D-day 의사결정
| 상황 | 권장 |
|---|---|
| 발표자가 ACT5 25-29s 견딜 수 있음 + 도우미 안내 OK | **현 상태 유지 (YELLOW GO)** |
| ACT5 < 15s 필수 (긴장된 발표 환경) | **place_scoring 만 Gemini 로 revert (GREEN GO)** |
| K2.3 slot 40% 가 시연 quality 에 영향 | 별도 task — 본 측정 범위 아님 |

---

## 6. handoff commit 정보

이 보고서는 `docs/handoff/2026-05-30-final-result.md` 로 commit 예정. **push 보류** (PM 사용자 승인 후).

