# SESSION_STATE — 매듭(Maedeup) 프로젝트

**최종 갱신**: 2026-05-16
**세션 컨텍스트**: Option C (TimeBar in-card 호스트 확정) + CalendarPane 빨간 배지 제거 — 라운드 8~9 GREEN
**브랜치**: `docs/spec-time-coordination` (origin/main 대비 86 ahead, origin/docs/spec-time-coordination 동기됨)
**HEAD**: `e8a10c4`

---

## 1. 프로젝트 개요

- **이름**: 매듭(Maedeup)
- **종류**: 졸업 프로젝트 — AI 모임 조율 플랫폼
- **핵심 가치**: 채팅으로 흩어진 시간·장소 의사를 자동으로 모아 vote_card / place_recommendation / maedeup_card로 마무리
- **스택**: Next.js 14 + FastAPI + SQLModel + asyncpg + Redis + LangGraph + Gemini 2.5 Flash + Kakao Local API
- **현재 상태**: MVP — spec v1.0 완성, Option C TimeBar in-card 확정 완성, **시연 D-6 (2026-05-22 금)**

---

## 2. git 상태

| 항목 | 값 |
|---|---|
| 현재 브랜치 | `docs/spec-time-coordination` |
| HEAD | `e8a10c4` |
| origin 대비 | origin/main 대비 86 ahead (origin/docs/spec-time-coordination 동기) |
| 별도 로컬 브랜치 | `chore/claude-subagents` (main 기반, 2 commit — sub-agents 5개 + .gitattributes) |

### 어제 세션 10 commit (최신순, cfaaf68 기준)
| SHA | 메시지 |
|---|---|
| `558c57c` | fix(timebar+toggle): restore race + 시연 toggle dormant (run12 GREEN) |
| `39fd8f9` | fix(demo): act_3_host_click_gap 0.8→2.5s (run11 GREEN) |
| `7fd7daa` | feat(demo): TimeBar majority overlap + WS race fix (run10 GREEN) |
| `f56271b` | feat(demo): ACT 3 TimeBar 합의 + UI 완결 + AUTO_CALENDAR_PUSH gate (run7 GREEN) |
| `1705e69` | docs: round4 GREEN 반영 CLAUDE/TODOS |
| `a5a4ca5` | docs(handoff): round4 GREEN |
| `a2e9b16` | fix(demo): ACT 5.5 preference_toggle 시드 보강 (C) |
| `0f3802b` | fix(demo): ACT 3 confirm 자동 루프 (A1~A5) |
| `1de7794` | docs: refresh stale CLAUDE.md/HANDOVER.md/TODOS.md |
| `c8a4a7d` | chore: EOL + .gitignore PNG ignore |

### 오늘 세션 15 commit (최신순, e8a10c4 기준)
| SHA | 메시지 |
|---|---|
| `e8a10c4` | chore(gitignore): option-c-*.png 시각 증거 스크린샷 패턴 추가 |
| `aac6303` | feat(demo): ACT 3 step 4 호스트 버튼 노출 시점 5초 대기 (Option C 시각 인지) |
| `0df31ae` | chore(gitignore): qa-runtime 검증 스크린샷 패턴 추가 |
| `bc315f1` | fix(calendar): 빨간 배지 제거 — avail.count는 이미 채팅 blocked 반영 |
| `8ce6b46` | feat(calendar): 셀 배지 "안 되는 사람 수" → "가능한 사람/전체" 형식 (잘못된 중간 단계) |
| `cb0acee` | fix(frontend): TS union narrowing — card.type maedeup_card guard 추가 |
| `ad22516` | fix(frontend): TS build error — InfoPanePhase에 없는 "placeRecommendation" 비교 제거 |
| `1fe9b17` | fix(frontend): R6 — setVoteCard phaseAlreadyAdvanced에 dateConfirmed 포함 |
| `cdf727b` | fix(frontend): Option C 보존 — maedeup_card auto phase-advance 가드 |
| `8a7c7d5` | fix(frontend): ScheduleRecommendationCard isHost 낙관적 렌더 — hostLoading race 해소 |
| `3528f19` | chore(docker): .pytest_cache dockerignore 추가 |
| `ffd4e1f` | feat(demo): ACT 3 TimeBar in-card 확정 셀렉터 갱신 (Option C) |
| `ecee744` | feat(timebar): Option C — 호스트 in-card "이 시간으로 확정" 버튼 도입 |
| `fc348dd` | chore(gitignore): qa-runtime 스크린샷 + .codex 마커 ignore |
| `cfaaf68` | docs(recovery): compact 직전 복구 4 파일 갱신 (run12 GREEN 시점) |

---

## 3. 자동 루프 흐름 요약

### run1~run12 (어제, TimeBar 합의 흐름 완성)

| 라운드 | 상태 | 핵심 내용 |
|---|---|---|
| run1 | RED | ACT 3 fallback 실패 |
| run2 | RED | 계속 실패 |
| run3 | GREEN | 라운드 4 PASS — ACT 3 첫 통과 |
| (사용자) | - | vote 카드 InfoPane 중복 발견 |
| 옵션 A | - | InfoPane VoteCardSection 롤백 + AI 패널 확정 버튼 복구 |
| 라운드 5 | GREEN | placeholder lock 해소 |
| (사용자) | - | UI 무한 루프 발견 |
| 라운드 5 fix | - | setInfoPanePhase("timeConfirmed") 적용 |
| (사용자) | - | TimeBar UI 실효 X 발견 |
| ACT 3 재작성 | - | TimeBar 합의 흐름 5단계 (게스트 WS + 호스트 Playwright + WS 송신 + A3-2 확정) |
| run7 | GREEN | 시각 체크리스트 15 항목 GREEN |
| (사용자) | - | 시간 결정 무시 발견 |
| 시나리오 분산 | - | backend majority overlap (compute_majority_slot) 추가 |
| run8/9 | RED | debounce + Playwright slot 24 selector 실패 |
| - | - | 호스트 WS 송신 + debounce NX lock 예외 적용 |
| run10 | GREEN | WS race 해소 |
| (사용자) | - | chromium stale cache 발견 |
| - | - | chromium 재시작 + host_click_gap 2.5s |
| run11 | GREEN | gap 조정 통과 |
| (사용자) | - | TimeBar 즉시 사라짐 회귀 발견 |
| qa agent | - | ACT 2.5 prefill 자동 echo back root cause 발견 |
| - | - | frontend restore guard + backend single-slot 제외 + PREFERENCE_TOGGLE_ENABLED=false |
| **run12** | **GREEN** | TimeBar 16초 mount 유지, 확정 2026-06-01 19:30 |

### Option C 라운드 1~9 (오늘 2026-05-16)

| 라운드 | 상태 | 핵심 내용 |
|---|---|---|
| R1~R7 | **fake RED** | TS build error 잠재 (`7fd7daa` 시점부터) — stale image(`7ffb7c4821a9`) 로 컨테이너 실행 → `docker compose build` 매번 실패 → 7 라운드 모두 stale bundle로 RED 보고 fix 시도 |
| fix1 | - | `ecee744` Option C frontend (TimeBar 유지 + "이 시간으로 확정" 버튼 + onHostFinalize) |
| fix2 | - | `8a7c7d5` ScheduleRecommendationCard isHost 낙관적 렌더 (hostLoading race) |
| fix3 | - | `cdf727b` AiAssistantPane maedeup_card auto phase-advance 가드 |
| fix4 | - | `1fe9b17` setVoteCard phaseAlreadyAdvanced에 dateConfirmed 추가 |
| fix5 | - | `ad22516` TS build error — "placeRecommendation" 비교 제거 |
| fix6 | - | `cb0acee` TS union narrowing — maedeup_card guard 추가 |
| **R8** | **GREEN** | TS fix 2건 후 build 통과 → 진짜 GREEN. ACT 3 "이 시간으로 확정" 즉시 클릭 성공 |
| R9 | GREEN | CalendarPane 빨간 배지 제거 검증 — 배지 0개, X/Y 카운트 31개 정상 |

---

## 4. GREEN 핵심 증거

### run12 GREEN (어제)
- TimeBar 16초간 mount 유지 (호스트 1st 클릭 후 사라짐 X)
- 2nd 클릭 (range 완성) 후만 unmount → consensus
- 확정 시간: **2026-06-01 (월) 19:30 (오후 7:30)**
- backend 로그: `[TIMEBAR] majority slot injected room=109 21..23`
- ERROR 0건, AUTO_CALENDAR_PUSH skip, PREFERENCE_TOGGLE_ENABLED dormant
- 시뮬 시나리오: 게스트 수현 오전(0-5), 민수 7-8:30(20-23), 예린 7:30-9:30(21-25), 호스트 7-9(20-24) → 4명 중 3명 겹침 slot 21-23 = 오후 7:30~8:30 → backend 19:30 확정

### Option C R8 GREEN (오늘)
- ACT 3 step 4: "이 시간으로 확정" 버튼 즉시 클릭 (FALLBACK 없음, primary 경로)
- 확정 시간: 2026-05-27 (수) 19:30 또는 2026-06-01 (월) 19:30 (demo 실행 시점 기준)
- 확정 장소: 수담한정식 강남점 또는 진미평양냉면 별관 (시점 기준)
- 시각 증거: `option-c-timebar-visible.png` (TimeBar 유지 + "이 시간으로 확정" 버튼 노출)

### CalendarPane R9 검증 (오늘)
- 빨간 배지 0개 (DOM 조사 + 스크린샷 확인)
- X/Y 카운트 (`#22c55e`/`#eab308`/`#ef4444`) 31개 정상
- 시각 증거: `calendar-badge-verify-124.png`, `calendar-closeup-124.png`

---

## 5. 적용된 fix 누적 (25+ 변경)

### Backend
- `backend/app/api/routes/meetings.py:323-334,636` — pending-vote.current_user_vote + vote_update.user_votes
- `backend/app/api/routes/meetings.py:563+867` — AUTO_CALENDAR_PUSH gate (confirm + place-confirm)
- `backend/app/core/config.py` — AUTO_CALENDAR_PUSH field
- `backend/app/api/ws/agent.py:427-479` — TimeBar majority overlap (compute_majority_slot) → manual_chosen_time 주입
- `backend/app/api/ws/agent.py:758-790` — all_members_selected 트리거 debounce 예외
- `backend/app/api/ws/social.py:81-92` — _is_explicit() + start==end 단일 슬롯 제외
- `backend/app/services/pipeline/helpers/preference_toggle.py:72-99` — PREFERENCE_TOGGLE_ENABLED 환경변수 검사
- `backend/scripts/seed_demo_personal_data.py` — 방장 home_base "신촌" + food 차별화 (C1·C3·C4 회피)

### Frontend (run12 이전)
- `frontend/src/contexts/MeetingContext.tsx:333-369` — setVoteCard 무조건 awaiting 해제 + setVoteUpdate same meeting 시 해제
- `frontend/src/components/meeting/InfoPane.tsx:341` — TimeBar mount 조건 `!scheduleConsensus`
- `frontend/src/components/meeting/InfoPane.tsx:388-392` — A3-2 클릭 시 setInfoPanePhase("timeConfirmed")
- `frontend/src/components/meeting/AiAssistantPane.tsx:525` — vote_card 렌더 조건에 phase 검사 (timeConfirmed/placeRecommendation/placeConfirmed/done hide)
- `frontend/src/components/meeting/AiAssistantPane.tsx:531` — hideConfirmAction prop 제거 (옵션 A)
- `frontend/src/components/meeting/ScheduleRecommendationCard.tsx` — hideConfirmAction prop 정의·사용 제거 + voteUpdate 구독 + vote count 시각화
- `frontend/src/components/meeting/TimeBarSelector.tsx:105-213` — restoredFromServer ref guard + selectionEnd null 시 broadcast 보류
- `frontend/src/hooks/useAgentWebSocket.ts:57-67` — VoteCardPayload.current_user_vote + VoteUpdatePayload.user_votes 타입

### Frontend (Option C, 오늘 — `ecee744`~`cb0acee`)
- `frontend/src/components/meeting/TimeBarSelector.tsx` — 호스트 전용 "이 시간으로 확정" 버튼 + onHostFinalize 콜백
- `frontend/src/components/meeting/InfoPane.tsx` — 호스트 확정 전 TimeBar unmount 차단 (Option C mount 조건 갱신)
- `frontend/src/components/meeting/ScheduleRecommendationCard.tsx` — isHost 낙관적 렌더 (hostLoading API race 해소)
- `frontend/src/components/meeting/AiAssistantPane.tsx` — maedeup_card auto phase-advance 가드 + TS union narrowing (maedeup_card guard)
- `frontend/src/contexts/MeetingContext.tsx` — setVoteCard phaseAlreadyAdvanced에 dateConfirmed 포함
- TS build error 2건 (`ad22516` + `cb0acee`): "placeRecommendation" 비교 제거 + maedeup_card guard

### Frontend (CalendarPane, 오늘 — `bc315f1`)
- `frontend/src/components/meeting/CalendarPane.tsx` — 빨간 배지 ("안 되는 사람 수") 통째 제거

### Demo (오늘)
- `.gstack-demo.py` ACT 3: "이 시간으로 확정" 버튼 셀렉터 갱신 (`ffd4e1f`) + step 4 5초 대기 (`aac6303`)

### Demo (run12 이전)
- `.gstack-demo.py` ACT 3 통째 재작성 (5단계: 게스트 WS + 호스트 Playwright + WS 송신 best-effort + A3-2 확정)
- 페이스: act_3_vote_gap 2.5s, act_3_after_votes 4s, act_3_host_click_gap 2.5s, act_3_after_host_vote 5s, act_3_after_confirm_click 5s

### .env (gitignore, 시연 환경)
- `AUTO_CALENDAR_PUSH=false`
- `PREFERENCE_TOGGLE_ENABLED=false`
- `DEMO_FALLBACK_ENABLED=true`

---

## 6. 핵심 파일 경로

### Backend (LangGraph 파이프라인)
| 파일 | 역할 |
|---|---|
| `backend/app/services/pipeline/state.py` | GraphState 정의 |
| `backend/app/services/pipeline/graph.py` | _route_from_start (5분기) |
| `backend/app/services/pipeline/nodes/entity.py` | date_hint·place_hint·cuisine·rejected 추출 |
| `backend/app/services/pipeline/nodes/slot.py` | slot_filling 분기 |
| `backend/app/services/pipeline/nodes/function_call.py` | _safe_search_place + 0슬롯 분기 |
| `backend/app/services/pipeline/nodes/vote_card.py` | payload + zero_slot_reason narrator |
| `backend/app/services/pipeline/nodes/place.py` | _compute_final_score + F7·F9 |
| `backend/app/services/pipeline/nodes/maedeup.py` | 확정/partial 카드 발행 |
| `backend/app/services/pipeline/helpers/places.py` | _detect_cuisine_type + _resolve_place_hint + _filter_out_rejected |
| `backend/app/services/pipeline/helpers/preference_toggle.py` | Q7-c + PREFERENCE_TOGGLE_ENABLED |
| `backend/app/services/pipeline/helpers/preferences.py` | load_requester_context (P0-2·3·4) |
| `backend/app/api/ws/agent.py` | TimeBar majority overlap + debounce 예외 |
| `backend/app/api/ws/social.py` | _is_explicit() + single-slot 제외 |
| `backend/app/api/routes/meetings.py` | AUTO_CALENDAR_PUSH gate + refresh 라우트 |
| `backend/app/core/config.py` | AUTO_CALENDAR_PUSH / PREFERENCE_TOGGLE_ENABLED 필드 |
| `backend/scripts/seed_demo_personal_data.py` | 시연 personal data 시드 (방장 신촌 + food) |

### Frontend
| 파일 | 역할 |
|---|---|
| `frontend/src/contexts/MeetingContext.tsx` | setVoteCard awaiting 해제 + voteUpdate 구독 + phaseAlreadyAdvanced dateConfirmed |
| `frontend/src/components/meeting/InfoPane.tsx` | TimeBar mount 조건 + timeConfirmed phase + Option C 호스트 unmount 차단 |
| `frontend/src/components/meeting/AiAssistantPane.tsx` | vote_card phase 검사 렌더 조건 + maedeup_card guard + TS union narrowing |
| `frontend/src/components/meeting/ScheduleRecommendationCard.tsx` | vote count 시각화 + hideConfirmAction 제거 + isHost 낙관적 렌더 |
| `frontend/src/components/meeting/TimeBarSelector.tsx` | restore guard + selectionEnd null 보류 + 호스트 "이 시간으로 확정" 버튼 |
| `frontend/src/components/meeting/CalendarPane.tsx` | 빨간 배지 제거 (채팅 blocked 중복 표시 해소) |
| `frontend/src/hooks/useAgentWebSocket.ts` | VoteCardPayload / VoteUpdatePayload 타입 |

### Demo / 시연
| 파일 | 역할 |
|---|---|
| `.gstack-demo.py` | 풀 시나리오 자동화 (ACT 1~5.5) |
| `.gstack-browser-launch.py` | Chromium CDP 9222 기동 + JWT 주입 |
| `.gstack-demo-token` | JWT 저장 (gitignore) |
| `docs/handoff/demo-scenario-v3.md` | 시연 시나리오 SoT |
| `docs/handoff/2026-05-15-round4-green.md` | 자동 루프 진행 기록 |
| `docs/handoff/audit-findings.md` | 해결점 A~P |

### Sub-agents (로컬 브랜치 `chore/claude-subagents`)
| 파일 | 역할 |
|---|---|
| `.claude/agents/code-writer.md` | Sonnet — 코드 구현 |
| `.claude/agents/analyst.md` | Opus — 정적 분석 |
| `.claude/agents/qa-runtime.md` | Sonnet — 런타임 검증 |
| `.claude/agents/risk-reviewer.md` | Opus — 리스크 검토 |
| `.claude/agents/docs-planner.md` | Sonnet — 문서 작성 |

---

## 7. 실행 명령어

### Docker (WSL)
```bash
sg docker -c "docker compose up -d"
sg docker -c "docker compose ps"
sg docker -c "docker restart maedeup-api"
```

### 시연 자동화 (WSL venv, 터미널 2개)
```bash
# 터미널 1 — Chromium CDP 기동
~/.venv-maedeup-demo/bin/python3 .gstack-browser-launch.py

# 터미널 2 — 풀 시나리오 실행
~/.venv-maedeup-demo/bin/python3 .gstack-demo.py
```

### 시연 D-1 준비
```bash
# personal data 시드 (room ID는 시연 방 ID로 교체)
sg docker -c "docker exec maedeup-api python -m scripts.seed_demo_personal_data --room <ROOM_ID>"
# JWT 갱신 (만료 의심 시)
# 로그인 후 localStorage의 token 값을 .gstack-demo-token에 저장
```

### 기타
```bash
# Intent seed
curl -X POST http://localhost:8000/api/v1/intents/seed
# Alembic
sg docker -c "docker exec maedeup-api alembic upgrade head"
```

---

## 8. 환경 상태

| 항목 | 상태 |
|---|---|
| Docker 4 컨테이너 | healthy (api·frontend·postgres·redis) |
| chromium | pid 31337, CDP 9222 LISTEN (frontend rebuild 후 fresh) |
| WSL venv | `~/.venv-maedeup-demo/bin/python3` (Python 3.12, websockets 16, playwright 1.59, chromium 1217) |
| JWT | `.gstack-demo-token` (5/13 생성, 401 0건이라 유효) |
| AUTO_CALENDAR_PUSH | false (시연 환경) |
| PREFERENCE_TOGGLE_ENABLED | false (dormant) |
| DEMO_FALLBACK_ENABLED | true |

---

## 9. 시연 정보

- **시연 일정**: 2026-05-22 (금) 점심 (D-6, 오늘 = 2026-05-16)
- **D-1 준비일**: 2026-05-21 (목)
- **시나리오 SoT**: `docs/handoff/demo-scenario-v3.md`
- **ACT 구조**: ACT 0(소개) → 1(방 생성) → 2(채팅 stalemate + vote_card) → 3(TimeBar 합의 → "이 시간으로 확정" → 19:30 확정) → 4(partial confirm) → 5(장소 추천·확정) → 5.5(preference_toggle dormant) → 6(extractor)
- **확정 시간**: 2026-06-01 (월) 오후 7:30 (demo 실행 시점 동적 변동)
- **핵심 장면**: TimeBar 4인 겹침 시각화 → 호스트 "이 시간으로 확정" 클릭 (Option C) → 확정

---

## 10. 운영 모드

- **PM (리더)**: 분배·점검·통합·결정 제안만. 깊은 분석은 sub-agent 위임
- **코드 작성**: code-writer (Sonnet)
- **분석·검증**: analyst / risk-reviewer (Opus)
- **QA 런타임**: qa-runtime (Sonnet, Playwright MCP)
- **문서**: docs-planner (Sonnet)
- **커밋 정책**: 사용자 명시 승인 후만, 단일 commit per 라운드
- **푸시 정책**: 사용자 명시 승인 후만

---

## 11. compact 후 읽기 순서

1. `docs/SESSION_STATE.md` — 전체 컨텍스트 (본 파일)
2. `docs/DECISIONS.md` — 확정 결정 사항
3. `docs/TODO.md` — 남은 작업
4. `docs/BUGS.md` — 잔존 버그 + 우선순위
5. `docs/handoff/demo-scenario-v3.md` — 시연 SoT
6. `docs/handoff/2026-05-15-round4-green.md` — 자동 루프 진행 기록
7. `git log --oneline -15` — 최근 commit
