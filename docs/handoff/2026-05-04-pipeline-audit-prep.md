# 파이프라인 아키텍처 감사 — 다음 세션 핸드오프

작성일: 2026-05-04
브랜치: main
상태: 시연 시나리오 라이브 검증 중 다수 패치 누적, 본격 아키텍처 감사 필요

---

## 1. 다음 세션의 task

**파이프라인 아키텍처 전수 감사.** 표면 패치 멈추고 트리거/데이터흐름/책임 정리.

### 목표 산출물

1. **트리거 진입점 맵** — WebSocket 메시지 종류별로 어디서 파이프라인이 시작되는지
2. **노드별 입출력 계약 표** — 각 노드가 읽는 state 필드 / 쓰는 state 필드 / 호출하는 외부 API
3. **데이터 흐름 다이어그램** — 채팅 메시지 1개 → 화면 카드 노출까지 전체 경로
4. **중복/모순 식별** — 같은 정보를 두 군데서 만들거나 다른 형식으로 보유하는 부분
5. **이슈 우선순위 표** — 본질적 결함 vs 표면 결함 vs 시연 위험도

### 진행 방식

**옵션 1 (추천)**: Explore 에이전트 병렬 투입 → 산출물 보고 → 함께 수정 방향 설계
**옵션 2**: 본 세션에서 사용자와 직접 추적

---

## 2. 이번 세션에서 확인된 본질적 패턴

> 패치 한 번에 인접 모순이 또 드러남. 단일 책임/단일 진실 원천 부재.

| 발견된 이슈 | 본질 |
|----------|------|
| Fast-skip이 `rejected_dates` 누락 | 정규식 추출 vs LLM 추출이 다른 출력 형식 |
| `conflict_options` + `rejected_dates` 중복 | 두 LLM 응답이 같은 정보를 다르게 분류 |
| Range 문자열 ISO 파싱 실패 | `date_hints` 형식 계약이 노드마다 다름 |
| 1차 카드 잔류 + 2차 안 만들어짐 | 트리거 정책이 4가지인데 우선순위 없음 |
| "현재 대화 정리" + 추천 카드 모순 | 두 AI 컴포넌트가 같은 채팅을 따로 분석 |

---

## 3. 이번 세션에서 적용한 패치 (모두 main에 반영, 미커밋)

| # | 변경 | 파일 | 핵심 라인 |
|---|------|------|----------|
| 1 | AI 패널 빈 상태 카피 ("필요할 때 도와드릴게요") | `frontend/src/components/meeting/AiAssistantPane.tsx` | ~840-854 |
| 2 | `_analyze_conversation` 통합 호출 (카드+신호 동시 추출) | `backend/app/services/langgraph_pipeline.py` | ~3879 |
| 2b | `extract_meeting_summary` wrapper로 변경 (legacy fallback 보존) | 동 | ~3984 |
| 2c | `agent.py:_run_auto_trigger_pipeline`에서 `_analyze_conversation` 직접 호출 | `backend/app/api/ws/agent.py` | ~127-140 |
| 2d | `GraphState` `pre_extracted_signals` 필드 추가 | `langgraph_pipeline.py` | 142, 218 |
| 2e | `entity_extraction`에 pre-extracted 분기 추가 (Gemini 스킵) | 동 | ~2255-2370 |
| 2-A | 통합 프롬프트에 `rejected_dates` vs `conflict_options` 의미 룰 + 4가지 분류 예시 | 동 | ~3967-3986 |
| 2-A 코드 | `entity_extraction`에 conflict_options 안전망 (rejected_dates와 중복 제거) | 동 | ~2311-2329 |
| 안전망 | `vote_card_creation`에 `_filter_out_rejected` 한 번 더 적용 | 동 | ~3146-3149 |
| 옵션 C | 추천 카드 multi-date 섹션은 `calendar_strategy === "multi_date_vote"`일 때만 | `frontend/src/components/meeting/ScheduleRecommendationCard.tsx` | 122-124 |
| 옵션 C 페이로드 | `vote_card_payload`에 `calendar_strategy` 필드 emit | `langgraph_pipeline.py` | ~3204 |
| 옵션 C 인터페이스 | `VoteCardPayload`에 `calendar_strategy?: string` 추가 | `frontend/src/hooks/useAgentWebSocket.ts` | 18-26 |
| Range 처리 | `_expand_date_hint` 헬퍼 (range 문자열 → 단일 ISO 배열) | `langgraph_pipeline.py` | ~1473-1504 |
| Range 적용 | `entity_extraction` pre-extracted 분기에서 date_hints 정규화 + 거부 날짜 제거 | 동 | ~2295-2368 |

**커밋 안 한 상태**. 다음 세션 시작 시 `git status`로 확인.

---

## 4. 남은 핵심 이슈 (감사에서 풀어야 할 것)

### A. 첫 메시지에 즉시 추천 카드 생성
- "우리 이번 주에 밥 먹자" 한 줄에 `preference-based` 분기 발동 → 거부 발언 전 카드 생성
- 사용자가 처음 지적한 *"오자마자 바로 뜨네"* 패턴이 카피 변경으로 가려졌을 뿐 실제 동작은 그대로
- 트리거 정책 재설계 필요 (옵션 Y로 정리됨, 미적용)

### B. Stalemate trigger 후 새 카드 안 만들어짐
- 1차 호출에서 카드 생성됨 → 2차 호출은 `status=no_slots_yet`으로 종료
- 1차 카드(거부 정보 미반영)가 화면에 잔류
- slot_filling이 *"이미 슬롯 채워졌으니 끝"*으로 판단하는 분기 추적 필요

### C. "잠깐, 뭔가 잘못됐어요 😢" 에러 메시지 잔존
- 일부 케이스에서 추천 카드와 함께 표시됨
- function_calling 에러 시 발행되는 듯, 하지만 정상 카드와 공존하는 모순 상황

---

## 5. 시연 시나리오 (사용자 작성, 보존)

### 배경
대학 동기 3명(지민/수현/민수). 카톡에선 "언제 돼?" 핑퐁하다 흐지부지 → 매듭이 해결.

### 페르소나
- **지민** (방장, 캘린더 연동 O)
- **수현** (멤버, 캘린더 연동 O)
- **민수** (게스트, 캘린더 연동 X — 링크 입장)

### 5막 흐름 (3~4분)

1. **ACT 1 — 방 생성 & 입장 (30s)**: 모임 생성 → 선호도 팝업 (평일 저녁 + 강남) → 게스트 링크 입장
2. **ACT 2 — 채팅 교착 → AI 자동 개입 (1m)**: 5메시지 후 stalemate 감지 → "대화에서 일정 조율이 필요해 보여요!" → 추천 카드
3. **ACT 3 — 캘린더 & TimeBar 시간 선택 (1m, 선택 시연)**: When2Meet 스타일 + 전원 완료 → 자동 트리거
4. **ACT 4 — 일정 확정 (15s)**: "5월 8일 (금) 오후 6:00 (전원 가능)로 확정" 클릭
5. **ACT 5 — 장소 추천 → 확정 (1m)**: AI 패널에 "강남역 근처 한식 맛집" 입력 → 5개 카드 → 선택 → 확정

### 시연 자동화 도구
`.gstack-multi-sim.py` (gitignore, 임시)
```bash
python .gstack-multi-sim.py join <room_id> <name>
python .gstack-multi-sim.py send <room_id> <token> <message> <sender>
python .gstack-multi-sim.py scenario <room_id>
```

게스트 가입 + WS 채팅 발화로 다중 사용자 시뮬레이션.

---

## 6. 알아야 할 핵심 코드 위치

### 백엔드
- `backend/app/services/langgraph_pipeline.py`
  - `_analyze_conversation` (~3879) — 통합 LLM 호출
  - `extract_meeting_summary` (~3984) — wrapper, legacy fallback 포함
  - `_expand_date_hint` (~1477) — range → 단일 ISO 변환
  - `_filter_out_rejected` (~1471) — 거부 날짜 슬롯 필터
  - `_filter_out_blocked` (~1447) — "불가능 날짜" 토글 슬롯 필터
  - `entity_extraction` 노드 (2253+) — pre_extracted_signals 분기 포함
  - `slot_filling` 노드 (2465+) — conflict mediation 분기 (~2526)
  - `function_calling` 노드 (2768+) — slot 빌드 + 필터
  - `vote_card_creation` 노드 (3106+) — payload 빌드 + 안전망 필터
  - `run_pipeline` (3734+) — 파이프라인 진입점

- `backend/app/api/ws/agent.py`
  - `_build_conversation_summary` (48+) — 별도 요약 (10메시지마다)
  - `_run_auto_trigger_pipeline` (105+) — stalemate/all_members_selected/conclusion_detected 트리거
  - WebSocket 핸들러 (320+) — AI 패널 직접 요청 진입

- `backend/app/api/ws/social.py`
  - WebSocket 핸들러 (175+) — 채팅 메시지 처리
  - `_detect_and_notify_intent` — intent 감지 + auto_trigger emit
  - `stalemate_judge` 호출

- `backend/app/services/stalemate_judge.py` — 별도 LLM 판정기

### 프론트엔드
- `frontend/src/components/meeting/ScheduleRecommendationCard.tsx` — AI 추천 카드
- `frontend/src/components/meeting/AiAssistantPane.tsx` — AI 패널 컨테이너
- `frontend/src/hooks/useAgentWebSocket.ts` — WS 페이로드 인터페이스

---

## 7. 환경/상태

- 도커 스택 정상 가동 (재시작 시 `docker compose up -d`)
- API 변경 시 `docker restart maedeup-api` (볼륨 마운트, 자동 반영)
- 프론트 변경 시 `docker compose up -d --build frontend` (1~2분)
- DB는 새로 만든 상태 (이번 세션에서 wipe). 시드 완료 (`POST /api/v1/intents/seed`)
- 사용된 방: room 1~9 (대부분 dirty 상태, 새 방 만들면 됨)
- 호스트 계정: `cyun0407@gmail.com` (Google OAuth 로그인 됨)
- 게스트 계정: 시뮬레이션 도구로 매번 새로 만듦

---

## 8. 다음 세션 시작 가이드

1. `git status` — 미커밋 변경 확인
2. `docker ps` — 컨테이너 살아있는지 확인 (안 살아있으면 `docker compose up -d`)
3. 이 문서 다시 읽기
4. **Explore 에이전트 띄워서 산출물 1~5 생성 의뢰** — 본 세션 컨텍스트 대신 신선한 시각으로 코드 전수 조사
5. 결과 받으면 함께 검토 → 본질 결함 우선순위 결정 → 하나씩 정리

### Explore 에이전트 의뢰 시 핵심 질문

- "채팅 메시지 1개가 들어왔을 때 파이프라인이 시작되는 모든 진입점을 찾아라"
- "각 LangGraph 노드가 GraphState의 어떤 필드를 읽고 어떤 필드를 쓰는지 표로 정리"
- "같은 정보(예: 날짜 후보)를 만들거나 가지는 함수/필드를 모두 찾아라 (중복 식별)"
- "EARLY-EMIT으로 발행되는 메시지와 정상 emit의 차이를 추적"
- "preference-based fast-track의 진입 조건을 정확히 명시"

---

## 9. 메모

- 사용자 (한국 학생, 졸업 프로젝트). 한국어 대화 OK
- 작업 스타일: 자율적 진행 선호, 큰 결정만 확인
- 외부 패키지 임의 추가 금지 (CLAUDE.md 룰)
- API 키/시크릿 마스킹 필수
- 커밋/푸시는 사용자 확인 후만
