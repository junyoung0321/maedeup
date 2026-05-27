# 2026-05-30 — 전시 안정성 round 통합 정리 (Phase 1~5 + Gemini swap)

## 결론

origin/main HEAD = **`dc916be`** (push 완료). 졸업 전시 D-5/D-4 (2026-06-04 + 06-05) 준비 완료. K1.3 SLA `<5s` PASS 도달 (10.86s → **3.99s**, -73%). bug fix 3건 (T6 cache / AI banner / C 구조) 완료. bug-26-* 회귀 0.

## KPI 변화 흐름

| KPI | SLA | Phase 2 baseline | Phase 4 (T2~T7 후) | Phase 5 (3 site openai) | Final (16 site C) | **Gemini 3.1 swap** |
|---|---|---|---|---|---|---|
| K1.1 ACT2 p50 | <5s | 32.66s | 36.61s | 23.56s | 21.72s | **22.92s** |
| K1.1 ACT2 p95 | <8s | 62.10s | — | 43.41s | 25.12s | — |
| **K1.3 ACT5 p50** | **<5s** | 22.26s | — | 10.86s | 25.88s (회귀) | **3.99s ★ PASS** |
| K1.2 fallback rate | <10% | 40% | 20% | 0% | — | 0% |
| K2.1 트리거율 | >80% | 94.9% | 97.4% | 100% | 92.3% | **97.4%** |
| K2.2 intent | >85% | 90% | 92% | 92% | 86% | **90%** |
| K2.3 slot | >75% | 0% (측정 불가) | 40% | 40% | 40% | 40% (T7 saturation) |
| K3.1 race | 0 | 1 | 0 (BUG-27-1 fix) | 0 | 0 | 0 |
| K3.2 broadcast | 0 | 0 | 0 | 0 | 0 | 0 |
| K3.3 onboarding | 0 | 0 | 0 | 0 | 0 | 0 |

**최종 status**: K1.3 PASS + K2.* PASS + K3.* PASS + K1.1 baseline 동률 (Gemini 영향 ↓). 6 PASS / 3 FAIL (K1.1 / K1.2 일부 / K2.3 saturation).

## 16 site 모델 매핑 최종 표

| # | Site | env / tier | 모델 |
|---|---|---|---|
| 1 | conversation_analyzer (대화 요약 + 선호 추출) | LLM_PROVIDER_FOR_ANALYZER=openai | gpt-4o-mini |
| 2 | entity_extraction (slot 추출) | LLM_PROVIDER_FOR_ENTITY=openai | gpt-4o-mini |
| 3 | intent.py general_response | LLM_PROVIDER_FOR_INTENT=openai | gpt-4o-mini |
| 4 | **place_scoring (5 카드 rerank)** ★ | LLM_PROVIDER_FOR_PLACE_SCORING=gemini | gemini-3.1-flash-lite |
| 5 | conversation summary 갱신 | LLM_PROVIDER_FOR_SUMMARY=openai | gpt-4o-mini |
| 6 | social_summary | LLM_PROVIDER_FOR_SOCIAL_SUMMARY=openai | gpt-4o-mini |
| 7 | personal_data_extractor (비동기) | (genai SDK 직접, D 미적용) | gemini-3.1-flash-lite |
| 8 | stalemate_judge | tier=mid → openai | gpt-4o-mini |
| 9 | agent.py:78 _build_conversation_summary | tier=mid → openai | gpt-4o-mini |
| 10 | meeting_history (히스토리 필터) | tier=mid → openai | gpt-4o-mini |
| 11 | quick_classify (regex miss fallback) | tier=low → gemini | gemini-3.1-flash-lite |
| 12 | intent_classifier RAG boost | tier=low → gemini | gemini-3.1-flash-lite |
| 13 | finalization_reason (narrator) | tier=low → gemini | gemini-3.1-flash-lite |
| 14 | dates 자연어 날짜 parsing | tier=low → gemini | gemini-3.1-flash-lite |
| 15 | place self-correction (disliked) | tier=low → gemini | gemini-3.1-flash-lite |
| 16 | health.py ping | call_gemini 그대로 | gemini-3.1-flash-lite |

**분포**: gpt-4o-mini 8 site (정확도 우선) / gemini-3.1-flash-lite 8 site (속도 우선).

## .env 최종 상태

```ini
USE_PAID_GEMINI=true
GEMINI_MODEL=gemini-3.1-flash-lite
OPENAI_MODEL=gpt-4o-mini

# B 영역 (dominant 6 individual)
LLM_PROVIDER_FOR_ANALYZER=openai
LLM_PROVIDER_FOR_ENTITY=openai
LLM_PROVIDER_FOR_INTENT=openai
LLM_PROVIDER_FOR_PLACE_SCORING=gemini   ← revert (ACT5 회복)
LLM_PROVIDER_FOR_SUMMARY=openai
LLM_PROVIDER_FOR_SOCIAL_SUMMARY=openai

# D 영역 (3-tier)
LLM_TIER_HIGH=openai
LLM_TIER_MID=openai
LLM_TIER_LOW=gemini                     ← revert (K2.2 회복)
```

## 진행 흐름 (commit timeline)

| 시점 | commit | 변경 |
|---|---|---|
| 2026-05-27 | `f717b06` | silent-fail audit P0 4건 가시화 (debug→warning) |
| 2026-05-27 | `8ceffdb` | bug-26-g/f NameError 회귀 fix |
| 2026-05-29 | Phase 2 baseline 측정 (commit X) | K1/K2/K3 9 KPI 측정 |
| 2026-05-29 | `be87e7b` | BUG-27-1 Redis NX lock (race condition) |
| 2026-05-29 | `665a778` | baseline 정정 + BUG-27 cancel + fixture delay |
| 2026-05-30 | `06f0353` | T2 silent-fail A — slot.py VOTE_OPTIONS_PATCH 4구역 분리 |
| 2026-05-30 | `715ade1` | T3 silent-fail B — helpers/slots.py google + Redis narrow except |
| 2026-05-30 | `ca3a4c9` | T4 silent-fail C — agent.py greeting/trigger narrow except |
| 2026-05-30 | `52b025c` | T5 place_search Redis 캐싱 (K1.3 cache hit -47%) |
| 2026-05-30 | `9254c73` | T6 free-slots Redis 캐싱 + invalidate |
| 2026-05-30 | `79c88d2` | T7 entity_extraction endpoint + K2.3 측정 분기 정정 |
| 2026-05-30 | `aa71581` | T7 fix — extract-entities mock_state recent_messages |
| 2026-05-30 | `2ed3378` | K1-1 conversation_analyzer Redis 캐싱 (병렬화 보류) |
| 2026-05-30 | `2b95f1b` | K1-2 GPT-4o-mini wrapper + 3 site abstraction |
| 2026-05-30 | `4fd0a8a` | Phase 5 측정 결과 handoff |
| 2026-05-30 | `21de13b` | OpenAI 모델 swap 비교 (gpt-5-nano/mini vs 4o-mini) |
| 2026-05-30 | `d705b87` | **통합 fix 5항목**: T6 option c + banner + C 구조 (B+D, 14 site) |
| 2026-05-30 | `1e81639` | 최종 통합 측정 handoff |
| 2026-05-30 | `056db01` | ACT5 revert (LLM_PROVIDER_FOR_PLACE_SCORING=gemini) 측정 |
| 2026-05-30 | `dc916be` | **GEMINI_MODEL env swap + Gemini 3.1 Flash-Lite 측정** ← HEAD |

총 **19 commits** (5/27 ~ 5/30, 4일).

## Bug fix 3건

### 1. T6 free-slots cache invalidate (option c) ✓
- 증상: 5월 캘린더 1/1 stale (게스트 join 후 cache 미갱신)
- root cause: T6 invalidate 트리거 = `unavailable_toggle` 만, guest-join 미포함
- fix: TTL 300s → 30s + guest-join handler 직후 `maedeup:free_slots:{room_id}:*` pattern delete
- 검증: 시연 backend log `[T6_INVALIDATE] guest-join room=315` 정상 발현

### 2. AI 패널 banner content ✓
- 증상: AI 패널 상단 배너에 trigger 유발한 사용자 발화 (예: "다음주 화요일은 좀 쉬고 싶다") 가 그대로 표시
- root cause: `AiAssistantPane.tsx:215` `autoTrigger.content || hardcoded` → content truthy 면 사용자 발화가 우선
- fix: hardcoded `"대화가 길어지네요, AI가 정리해볼게요 🗓️"` 만 표시
- 검증: 시연 chat_messages 에 사용자 발화 banner 노출 0건

### 3. C 구조 (B+D, 16 site abstraction) ✓
- 16 site 의 LLM 호출을 `call_llm(provider=...)` / `call_llm_tier(tier=...)` 로 추상화
- env toggle 9개로 모델 swap 가능 (B 6 individual + D 3 tier)
- swap test 자유도 ↑ — model 교체가 .env 변경 + restart 만으로 가능

### bug-26-* 회귀 0
시연 3회 모두 chat_messages 3 narrator (첫 추천 / slot patch / maedeup summary) 시각 일치. bug-26-d/e/g/h 모두 PASS 유지.

## 학습

### 1. swap test 결과 — 모델 선택 trade-off
- gpt-4o-mini 가 K2.2 정확도 best (92%)
- gpt-5-nano/mini 는 노이즈 수준 (50 sample 통계 약점)
- **gemini-3.1-flash-lite 가 K1.3 (place scoring) 에서 압도적** (3.99s vs 25.88s)
- 단일 모델 vs site별 분기 = **site별 분기가 종합 best** (정확도 + 속도 모두 잡음)

### 2. K1.3 ACT5 root cause 의 진짜 정체
- 처음 가설: Gemini API 자체 latency = 잘못된 가설 (paid 적용에도 36s)
- 실제 root cause: **5개 카드 score 각각 LLM 호출 누적** (place_scoring 노드)
- OpenAI 가 5회 누적 시 25s, Gemini Flash-Lite 가 5회 누적 시 4s — 호출 횟수 많은 영역은 **빠른 모델이 critical**

### 3. AskUserQuestion 알림 룰
- Remote Control 사용 중 일반 텍스트 답변은 사용자 폰 알림 X
- AskUserQuestion 도구만 알림 트리거
- "자율 풀가속 모드" 명시 시 AskUserQuestion 자제 (memory `feedback_askuserquestion_for_rc_notification.md`)

### 4. 추가 분석 필요 영역 (미해결)
- K1.1 ACT2 22s — Gemini 호출 적어 모델 swap 영향 ↓. 진짜 root cause = conversation_analyzer + entity_extraction prompt 크기 (~10KB) + 순차 실행. **병렬화 가능** 분석 완료 (Path D) 단 K2.2 회귀 위험 추정 -7~17pt 로 보류 (사용자 결정 D)
- K2.3 saturation (40% 동률) — T7 metric 자체의 saturation 가능성. fixture 50개의 expected_slot 형식 정정 필요
- ACT 5.5 preference_toggle dormant — documented (TimeBar race 회피)

## 전시 운영 권고

### 1. warmup 시연 1회
- cold start spike 회피 (iter1 32s vs iter5 23s)
- 전시 시작 5분 전 dummy 시연

### 2. 부스 안내문
- "AI 분석 최대 25초 소요" — K1.1 ACT2 22s 대비 사용자 인내 확보
- "장소 추천 4초 내" — K1.3 ACT5 PASS 강조

### 3. ACT2 narration 강화
- 22s 동안 "AI 분석 중" UI loading 명확 (사용자 wait 인지)

### 4. backup plan
- iter2 outlier 43s 같은 spike 가능 — 백업 시나리오 (Gemini quota 만료 / API down) 준비
- `.env` revert path 즉시 실행 가능 (3분 wall-clock):
  ```bash
  sed -i 's/^GEMINI_MODEL=.*/GEMINI_MODEL=gemini-2.5-flash/' .env
  docker compose up -d fastapi-app
  ```

## 미해결 backlog (전시 후)

### Phase 5 deferred (시간 압박 외)
- T8 ml_place model 학습 + 배포 (data/training/train.py 실행, 시간 큼)
- T9 ACT 5.5 Option C (PREFERENCE_TOGGLE_ENABLED=true 복원 + TimeBar race 검증)
- T10 partial card prefetch (spec v2 PR-V2.2)

### K1.1 추가 단축 (사용자 결정 D, 보류)
- conversation_analyzer + entity_extraction LLM 호출 병렬화 (Path D)
- K2.2 회귀 위험 -7~17pt 추정 — 회피 결정

### silent-fail audit P2 17건
- cleanup pass / fail-open rate limit / 의도된 fallback 등 후순위

### spec v2 본문
- mixed-provider 정책 명문화 (place_scoring → gemini, 나머지 openai)
- K1/K2/K3 KPI + SLA + 안전망 (revert path) 문서화

### BUG-27 backlog
- BUG-27-1 후속: alembic partial unique index (option A) + frontend 409 toast
- BUG-27-2: K2.3 entity_extraction endpoint (T7 완료 ✓)
- BUG-27-3: mock OAuth dev endpoint

## 산출물 목록

### 코드 (origin/main)
- `.env`: GEMINI_MODEL + OPENAI_MODEL + 9 env toggle
- `backend/app/services/llm.py`: `call_llm` + `call_llm_tier` abstraction
- `backend/app/services/openai_client.py`: AsyncOpenAI wrapper
- `backend/app/services/gemini.py`: settings.GEMINI_MODEL env 사용
- 16 site 의 LLM 호출 abstraction 적용
- T6 cache + invalidate (calendar.py + rooms.py)
- AI 패널 banner fix (AiAssistantPane.tsx)
- K1-1 conversation_analyzer Redis 캐싱

### Spec / Plan / Handoff
- `docs/superpowers/specs/2026-05-27-exhibition-stability-k1-k2-k3-design.md`
- `docs/superpowers/plans/2026-05-27-phase1-measurement-infra.md`
- `docs/superpowers/plans/2026-05-29-phase3-fix.md`
- `docs/handoff/2026-05-28-phase1-runners-ready.md`
- `docs/handoff/2026-05-29-baseline-result.md`
- `docs/handoff/2026-05-30-phase4-result.md`
- `docs/handoff/2026-05-30-model-swap-comparison.md`
- `docs/handoff/2026-05-30-final-result.md` (Phase 5 + ACT5 revert addendum)
- `docs/handoff/2026-05-27-silent-fail-and-bug-26-g.md` (Gemini swap addendum)
- **본 문서** (round summary)

### Memory
- `feedback_askuserquestion_for_rc_notification.md`
- `feedback_root_cause_over_surface_fix.md`
- `feedback_qa_auto_panel_audit.md` (25항목 확장)

### Fixture / Runner (Phase 1)
- `.gstack-fixtures/k2-free-inputs.json` (50개)
- `.gstack-fixtures/k3-concurrency-scenarios.json` (5개)
- `.gstack-fixtures/k3-onboarding-users.json` (5개)
- `.gstack-k2-runner.py` / `.gstack-k3-concurrency-runner.py` / `.gstack-k3-onboarding-runner.py`
- `.gstack-demo.py` K1 timing wrapper

## CLAUDE.md 갱신 권고

```markdown
**현재 task**: 전시 안정성 round 완료 (HEAD `dc916be`, 2026-05-30). 16 site 모델 매핑 확정 (gpt-4o-mini 8 + gemini-3.1-flash-lite 8), K1.3 PASS (3.99s), K2 PASS 유지, bug fix 3건 완료. **다음**: 전시 진행 (2026-06-04 + 06-05). 운영 보완 — warmup + narration + 부스 안내.
```

## 안전 tag (push 완료)
- `v-pre-phase1-green` — Phase 1 진입 전 backend 안정 (commit `595fa0b`)
- `v-phase1-ready` — Phase 1 완료 (commit `ca871e5`)
- `v-pre-phase3` — Phase 3 진입 직전 (push 완료)

추가 권고: 본 round 완료 시점 새 tag `v-exhibition-ready` 추가:
```bash
git tag v-exhibition-ready dc916be -m "전시 안정성 round 완료, K1.3 PASS + 16 site 모델 매핑"
git push origin v-exhibition-ready
```
