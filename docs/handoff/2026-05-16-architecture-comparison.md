# 매듭 아키텍처 비교: LangGraph deterministic vs LLM autonomous

작성: 2026-05-16 (시연 D-4)
목적: 졸업 발표 자료 — 두 아키텍처를 실측 비교하여 트레이드오프 정리

---

## 1. 두 아키텍처 개요

### LangGraph deterministic (현 시연 라인, `fix/quick-classify-regex`)
- **패턴**: 9-노드 state machine. `trigger_reason` 기반 라우팅으로 노드 우회 가능.
- **흐름**: `quick_classify` → `intent_detection`(또는 우회) → `entity_extraction` → `function_calling` → `supervisor_validation` → `vote_card_creation` / `place_recommendation` / `maedeup_card_creation`
- **의사결정**: 코드 if-else + `_route_*` 함수 (deterministic)
- **Gemini 호출**: 노드별로 필요할 때만 (intent classify, entity extract, place rerank 등)
- **코드량**: `pipeline/` 패키지 ~10 helper + 9 노드 + state + graph

### LLM autonomous tool-call loop (실험 트랙, 폐기)
- **패턴**: Gemini Function Calling agent loop. max 5 iter.
- **흐름**: system_prompt + tools 11개 → Gemini가 자율 tool 선택 → 결과 받고 다음 iter
- **의사결정**: LLM (top_p=0.1, top_k=1로 결정성 강화)
- **Gemini 호출**: 매 iter마다 1회 (5~6회 = 30~40s)
- **코드량**: `agent_v2/` 패키지 17 파일 ~2,100줄 (agent + 11 tools + hooks + registry)

---

## 2. 실측 결과 (2026-05-16, demo 3회씩)

| 비교 축 | LangGraph deterministic | LLM autonomous | 차이 |
|---|---|---|---|
| **ACT 2 (stalemate, 자동 개입)** | **~10s** (8~12s) | 30.28s (24~40s) | **3배 빠름** |
| **ACT 5 (direct_request, place)** | 9.15s (7.56~10.57s) | 8.31s (6.92~9.69s) | 비슷 (LangGraph 약간 느림) |
| **응답시간 변동 (3회 분산)** | ±2s | ±10s | LangGraph 우수 |
| **결정성 (tool 시퀀스 동일)** | 100% (코드 결정론적) | 100% (top_p/top_k 효과) | 동등 |
| **회귀 (LLM args 변조)** | 0건 | 측정 0건 + vote_card 중복 1건 발견 | LangGraph 우수 |
| **graph 자체 실행** | 0.47~0.50s | n/a | - |

### ACT 2 사용자 체감 latency 분해 (LangGraph)
- `AUTO_TRIGGER pipeline entry` → `vote_card_creation 완료`까지 ~10s
- 그 중 graph 실행: 0.47s (entity pre-extracted + function_call + validation + vote_card)
- 나머지 ~9.5s: trigger 받기 전 `_analyze_conversation` 호출 (entity pre-extract, Gemini 1회)

### ACT 5 latency 분해 (LangGraph)
- run_pipeline TOTAL 9.15s 중
  - place_recommendation: 7~10s (Kakao + Gemini rerank fallback + ✨ reasoning)
  - entity_extraction (fast-skip): 0.09s
  - function_calling: 0.10s
  - validation: 0.00s

---

## 3. 아키텍처 트레이드오프

### LangGraph deterministic의 장점
- **결정론적 흐름** — 같은 입력 → 같은 출력 보장
- **응답시간 floor 작음** — Gemini 호출 횟수 적음 (3~4회 vs 6+회)
- **테스트 가능** — 12개 테스트 파일 (unit + integration)
- **에러 격리** — 노드 단위로 fail 추적
- **시연 검증 완료** — 풀 시나리오 자동화 통과

### LangGraph deterministic의 단점
- **확장성 낮음** — 새 기능 추가 시 그래프 재배선 필요
- **monolithic 5,301줄**(분할 전) — 노드 함수 간 결합도 ↑

### LLM autonomous의 장점
- **자율성·매력** — "AI가 도구 알아서 선택" 컨셉 → agentic AI 트렌드 부합
- **확장성 높음** — tool 추가 = FunctionDeclaration + 함수 1개. 라우팅 자동
- **코드 슬림** — 5,301줄 → 2,100줄 + 11 tool 모듈
- **자율성**: "친구들의 거부 발언을 의미적으로 이해" 같은 컨셉 발표 매력

### LLM autonomous의 단점
- **응답시간 floor 큼** — Gemini 호출 6~8회가 본질적 limit (24~40s)
- **LLM args 변조 위험** — Gemini가 tool 인자 임의 조작 (회귀 3건 발견 + hotfix)
- **결정성 챙기는 비용** — temp=0 단독으론 부족, top_p/top_k 강제 + validation 가드 필요
- **테스트 어려움** — Gemini mocking 복잡, 우리 trial에선 테스트 0개
- **회귀 검증 비용 큼** — D-4 시점 manual run 6회로도 부족

---

## 4. 시연용 선택 근거

졸업 시연(2026-05-20) 요구사항:
- ✅ **응답시간 ≤ 5s 이상적, ≤ 15s 허용** — LangGraph 충족 (10s), LLM 미달 (30s)
- ✅ **결정성** — 발표 중 같은 입력 다른 결과 곤란
- ✅ **회귀 0건** — 시연 중 카드 깨짐 곤란
- ✅ **자동화 검증 통과** — D-day까지 안정성 보장

**결론: LangGraph deterministic으로 시연.**

LLM autonomous는 졸업 발표 슬라이드에서 비교 데이터로 활용 (학술적 가치 — "두 패러다임 측정 비교").

---

## 5. 졸업 발표 멘트 제안

> "매듭은 두 아키텍처를 실험했습니다.
>
> 첫 번째는 **LangGraph 기반 결정론적 9-노드 파이프라인**. 트리거 기반 라우팅, 노드별 책임 분리, 테스트 12개. 사용자 체감 10초.
>
> 두 번째는 **Gemini Function Calling 기반 LLM autonomous 11 tool agent**. 자율 도구 선택, 코드 슬림화. 사용자 체감 30초.
>
> 같은 시나리오에서 3배 latency 차이. 자율성을 살리되 응답시간 floor는 LLM 호출 횟수에 직결된다는 트레이드오프. 시연은 안정성 우선으로 LangGraph 라인을 사용하지만, **두 패러다임의 비교 자체가 매듭의 학술적 기여**입니다."

---

## 6. 데이터 출처

- spec-time 실측: docker logs maedeup-api (2026-05-16 11:21~11:27 KST, 3회)
- agent_v2 실측: docker logs maedeup-api (2026-05-16 10:40~11:06 KST, 6회)
- agent_v2 코드 분석: `git show experiment/llm-agent:backend/app/services/agent_v2/*` (브랜치 삭제 전 캡처)
- adversarial review: `general-purpose` subagent (Claude Opus 4.7)

## 7. 폐기된 자료

- 브랜치: `experiment/llm-agent` (로컬 + remote 둘 다, 2026-05-16 삭제)
- 워크트리: `.claude/worktrees/optimistic-agnesi-9aa632/` (2026-05-16 삭제)
- 패키지: `backend/app/services/agent_v2/` (main에 머지 안 됨, 워크트리와 함께 소멸)

학습된 인사이트만 본 문서에 보존.
