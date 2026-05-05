# 매듭 파이프라인 아키텍처 감사 — 진행 현황

작성일: 2026-05-05
브랜치: main
상태: **트리거 레이어 (01) 검증 완료, LangGraph 노드 레이어 (02) 검증 진행 중**

전 세션 핸드오프: `docs/handoff/2026-05-04-pipeline-audit-prep.md`

---

## 1. 본 세션 누적 작업

### 다이어그램 워크플로 확립
- **Source of truth**: `docs/handoff/diagrams/*.mmd` (Mermaid 파일)
- **Diff-first**: .mmd 직접 편집 → diff 보여주기 → 사용자 승인 → `generate_diagram` 렌더
- **FigJam = build artifact**: 보드 직접 수정 금지
- 파일 분리 원칙: 큰 다이어그램 1장 누적 금지, 주제별 파일

규칙은 `CLAUDE.md`의 "다이어그램 작업 규칙" 섹션 + 메모리 `feedback_diagram_workflow.md`에 보관.

### 다이어그램 6장 생성 (`docs/handoff/diagrams/`)
| 파일 | 내용 | 최신 FigJam |
|------|------|-----------|
| `00-overview.mmd` | 채팅 1발 → 카드까지 시퀀스 (큰 그림) | (미렌더) |
| `01-trigger-rules.mmd` | 4게이트 + 4트리거 + 해결점 A·B·C 표시 | https://www.figma.com/board/iOvYbFqjS9mEJkpIYY0W1p |
| `02-langgraph-flow.mmd` | 9노드 체인 + 의심점 A~D | (미렌더, 02 검증 후 일괄) |
| `03-intent-classifier.mmd` | classify_intent RAG 내부 | (미렌더) |
| `04-option-c-routing.mmd` | 해결점 C 옵션 4 구조 | https://www.figma.com/board/ZxhOlw1ze0sYyQYg074J4i |
| `05-full-overview.mmd` | 전체 시스템 한 장 | https://www.figma.com/board/ZSyoSC4QVy1ZmXQQ0DPBUu |

### 확정 이슈 문서
`docs/handoff/audit-findings.md` 신설. 검증 끝난 이슈만 등록.

---

## 2. 확정 해결점 4건

### 해결점 A — judge_stalemate 임계값 over-correction
- **위치**: `social.py:593`
- **변경**: `if count < 3` → `if count < 4`
- **근거**: 커밋 `52c0559`(2026-04-20)에서 카운팅 범위 확대(intent-only → 전부) + 임계값 하향(5→3)을 동시에 함. 카운팅 확대만으로 옛 버그 해결됨, 임계값까지 낮춘 건 over-correction
- **시급도**: 중 (false positive로 의심점 E 빈도 증가)

### 해결점 B — 배너 시스템 재설계 (옵션 3 AI 패널 통합)
- **위치**: `social.py:549~561`, `useSocialWebSocket.ts:511~513`, `ChatPane.tsx:92~93`
- **변경**:
  1. `intent_detected` 이벤트 발행 제거
  2. agent.py가 `ai_auto_trigger` 수신 시 AI 패널에 `trigger_reason`별 "분석 중" 메시지 즉시 발행
  3. 프론트의 dead code (`detectedIntent`/`dismissIntent`) 제거
- **근거**: 백엔드는 발행하나 프론트는 받기만 하고 렌더 안 함. 5~15초 LLM 대기 동안 UX 피드백 0
- **시급도**: 높음 (시연 직격)

### 해결점 C — LangGraph 조건부 진입 (옵션 4)
- **위치**: GraphState + agent.py 사전처리 + LangGraph 그래프 정의 + supervisor_validation
- **변경**:
  1. `GraphState`에 `trigger_reason` 필드 추가
  2. agent.py가 trigger_reason별 사전 처리 (TimeBar 데이터 주입 등)
  3. LangGraph entry에 `add_conditional_edges`로 트리거별 시작 노드 분기
     - `conclusion_detected` → entity_extraction부터 (노드1 스킵, ~1초 절약)
     - `all_members_selected` → slot_filling부터 (노드1+3 스킵, ~3초 절약)
     - `stalemate_judged` / `direct_request` → intent_detection부터 (현재)
  4. supervisor_validation 4-way 분기 확장
     - `conclusion_detected` → maedeup_card 직행 (vote+place 스킵)
     - `all_members_selected` → place_recommendation (vote 스킵)
     - 기존 vote/place 분기 유지
- **근거**: trigger_reason이 인사말 차별화에만 쓰이고 LangGraph는 무시. conclusion에도 불필요한 vote_card 생성 가능
- **작업 분량**: 150~200줄
- **시급도**: 중-높음 (시간 절약 + 시나리오 정합성)

### 해결점 D — extract_meeting_summary 제거 (책임 중복 정리)
- **위치**: `langgraph_pipeline.py:4080~4155` 삭제, `agent.py:22, 140` 정리
- **변경**:
  1. agent.py:140의 호출 제거 → 실패 시 빈 summary 발행
  2. `extract_meeting_summary` 함수 정의 80줄 삭제
  3. import 정리
- **근거**: legacy wrapper. `_analyze_conversation`이 통합 버전이라 wrapper의 의미 사라짐. 실패 시에만 중복 호출 발생
- **시급도**: 낮음 (정상 케이스 영향 0, 코드 정리 차원)

---

## 3. 미검증 의심점 3건

`02-langgraph-flow.mmd` 노드 3·4 영역. **검증 순서 결정**: 흐름상 노드3 내부 → 노드3→4 데이터 흐름 순서로

| ID | 요약 | 위치 |
|---|---|---|
| **D** (의심) | fast-skip 짧은 명령 시 거부 정보 무시 | entity_extraction 진입 분기 (`:2403~2435`) |
| **C** (의심) | `_is_specific_iso_date` 자연어 거부 누락 | entity_extraction 필터 (`:2344~2358`) |
| **B** (의심) | `date_hints` 3중 쓰기 | entity → slot → slot conflict (`:2315, 2555, 2628`) |

### 의심점 C 사전 분석 (검증 진행 중)
- `_is_specific_iso_date` 함수가 정확히 `YYYY-MM-DD`만 통과
- LLM이 자연어로 응답("Friday", "다음 금요일") 시 모두 누락
- 같은 자연어가 `conflict_options`엔 살아남아서 모순 발생
- 시연 ACT 2 직격 위험 (사용자 거부 발언이 카드에 무시됨)

**해결 방향 후보** (다음 세션 결정):
- A. 자연어→ISO 변환 헬퍼 추가 (추천, 30~50줄)
- B. 프롬프트 strict (LLM 신뢰성 보장 안 됨)
- C. 재시도 (비용 증가)
- D. 이중 추출 (복잡)

---

## 4. 다음 세션 시작 지점

### Step 1. 의심점 D (fast-skip) 검증
- 코드: `langgraph_pipeline.py:2403~2435`
- 짧은 명령("일정 추천해줘") 시 entity_extraction 자체 스킵하는 분기
- 채팅의 거부 발언("토요일 안 돼") 무시 위험
- 해결점 C(라우터)와 충돌 가능성 — 라우터가 entity로 보낸 후 fast-skip 발동하면 거부 정보 누락 더 심해질 수 있음

### Step 2. 의심점 C 결정 (옵션 A로 추정)
- 자연어→ISO 변환 헬퍼 옵션 확정

### Step 3. 의심점 B (date_hints 3중 쓰기) 검증
- entity_extraction → slot_filling → slot conflict 분기 3군데에서 같은 필드 덮어쓰기
- 해결점 C에서 entity와 slot의 책임 재정의 필요 → 같이 풀어야

### Step 4. 02-langgraph-flow.mmd 일괄 업데이트 + 렌더
- 의심점 B/C/D 검증 결과를 다이어그램 라벨에 반영
- 해결점 D (extract_meeting_summary 제거) 반영
- 해결점 C 호환성 표시

### Step 5. 코드 수정 일괄 PR
- 모든 해결점 (A, B, C, D + B/C/D 의심점이 해결점으로 승격된 것) 한 번에
- 시급도 순서 또는 의존성 순서로 commit 분리:
  1. 해결점 D (cleanup, 영향 작음)
  2. 해결점 A (1줄 변경)
  3. 해결점 C (foundational, 다른 변경의 전제)
  4. 해결점 B (cross-cutting)
  5. 의심점 D/C/B에서 승격된 해결점들

---

## 5. 환경/상태

- 도커 스택 정상 (재시작 시 `docker compose up -d`)
- 코드 변경 미발생 (감사 단계, 수정 미시작)
- 미커밋 변경: 본 세션에서 추가된 문서 파일들
  - `docs/handoff/audit-findings.md` (신규)
  - `docs/handoff/diagrams/00~05-*.mmd` (신규 6개)
  - `docs/handoff/2026-05-05-architecture-audit-progress.md` (본 문서)
  - `CLAUDE.md` (다이어그램 작업 규칙 섹션 추가)
- 메모리 추가: `feedback_diagram_workflow.md`

---

## 6. 핵심 깨달음 (감사 중 발견)

1. **trigger_reason은 인사말 차별화에만 쓰임** — LangGraph는 4개 트리거를 똑같이 처리. conclusion에도 vote_card 만드는 모순.
2. **intent_detected 배너는 반쪽 구현** — 백엔드 발행, 프론트 수신·state 저장하나 렌더 0. 비용만 발생.
3. **judge_stalemate 임계값이 over-correction** — 옛 버그(intent-only 카운팅)는 카운팅 범위 확대로 풀렸는데 임계값까지 같이 낮춤.
4. **`extract_meeting_summary`는 legacy wrapper** — `_analyze_conversation` 통합 버전 도입 후 wrapper로 남아 책임 중복.
5. **TRIG4(direct_request)는 PUB을 우회** — 다이어그램이 실제 흐름과 달랐음 (정정 완료).
6. **노드별 입력 계약 재정의 필요** — 해결점 C 적용 시 entity_extraction이 intent 없이도, slot_filling이 extracted_entities 없이도 동작해야 함.

---

## 7. 시연 위험도 정리 (5/8 시나리오 기준)

| 위험 | 영향 ACT | 해결점 |
|------|---------|------|
| 사용자 거부 발언 누락 → 거부된 날짜가 카드에 표시 | ACT 2 | 의심점 C, D 해결 후 |
| 5~15초 LLM 대기 중 UX 피드백 없음 | ACT 2~3 전환 | 해결점 B |
| conclusion 시 불필요 vote_card | (시나리오에 없음) | 해결점 C |
| stalemate 과조기 발동 → 잘못된 카드 생성 | ACT 2 | 해결점 A |
