# 매듭 (Maedeup) 인수인계 문서

> 최종 갱신: 2026-05-15
> 브랜치: `docs/spec-time-coordination` (main 기반 53+ 커밋 ahead, origin 동기 `c8a4a7d` 까지 push 완료)
> 이전 버전(2026-04-14 작성, `feature/code-review-improvements` 기준)은 완전 폐기.

---

## 1. 개요

졸업 프로젝트. 채팅방에서 시간·장소 교착을 자동 감지해 투표카드·장소추천·매듭카드를 생성하는 AI 모임 조율 플랫폼. **현재 상태**: spec v1.0 완성(1917줄, 3파일 분할), 미구현 12건 코드화(PR-V1.5) 완료, pytest 91/91 PASS, QA dry-run v2 PASS — **시연 직전(5/19·5/20 발표 예정)**. 시연 자동화 스크립트 v3(`.gstack-demo.py` 812줄)까지 완성.

---

## 2. 현재 상태 (2026-05-15)

### spec 진행도
- **v1.0 완성** (2026-05-14, SHA `1a9f1e2`): §1~§13 전체 완료, 3-파일 분할(PR-V)
  - `docs/handoff/spec-common.md` (839줄) — 공통 정책·권한·API·비기능·결정 안건 SoT
  - `docs/handoff/spec-time-coordination.md` (619줄) — 시간 조율 본문
  - `docs/handoff/spec-place-recommendation.md` (459줄) — 장소 추천 본문
- **v2 계획서 완성** (SHA `b3d1509`): 38 항목, P0 8건·P1 18건·P2 12건, 10 카테고리, 신규 Q18~Q25, PR-v2.0~v2.5 분할안 — `docs/handoff/2026-05-14-spec-v2-plan.md`
- v2 본문 작성은 **시연 통과 + retrospective 후** 시작 권고

### 코드 PR 흐름 (이번 브랜치 내 주요 PR)

| PR | SHA | 내용 | 상태 |
|---|---|---|---|
| PR-X | `9609bee` | calendar_consent default True + Alembic 마이그 | ✅ push 완료 |
| PR-Y1 | `54e1532` | F1 fallback (다수결 vote_card) 백엔드 9파일 | ✅ push 완료 |
| PR-Y2 | `adc444f` | F1 fallback 프론트 UI (배너·배지·토글) | ✅ push 완료 |
| PR-Z1 | `66110e9` | Q5 hybrid refresh 라우트 + P0 plumbing + Q7-c | ✅ push 완료 |
| PR-Z2 | `ea759d1` | Q5 hybrid 토글 UI + refresh API | ✅ push 완료 |
| PR-V | `6769400` | spec 3분할 (common·time·place) | ✅ push 완료 |
| PR-V1.5 | `90131f2` | spec v1.0 미구현 12건 + Codex P1·P2 통합 | ✅ push 완료 |
| PR-V1.5.1 | `1892b50` | alembic sqlite·JSON dialect·SENTINEL hotfix | ✅ push 완료 |
| PR-V1.5.2 | `aaec29d` | alembic batch_alter_table 7파일 + test seed | ✅ push 완료 |

**푸시 상태**: origin 동기 완료, `c8a4a7d`(EOL+gitignore hygiene)까지 모두 push (2026-05-15). 이후 작업은 사용자 명시 승인 후 push.

### QA dry-run v2 결과 (2026-05-15)
- **PASS** (taskId `a9dbbaccb1eb8c374`, 8m38s, Playwright MCP)
- ACT 1→2→4→5 풀 자동 재현, room 72 / meeting 88 / 수담한정식 강남점 확정
- 백엔드 ERROR/EXCEPTION 0건, 스크린샷 6장 저장
- P0 버그: 0건. 잔존: LIMIT-7(free-slots 1095ms, P2), LIMIT-8(favicon 404, P3)

### 시연 자동화 v3 상태 (2026-05-15)
- `.gstack-demo.py` 812줄 (v3 완성, SHA `9c8c076` 포함 origin 푸시 완료)
- ACT 0.5(Personal Data 모달)·ACT 1·ACT 2·ACT 3·ACT 4·ACT 5·ACT 5.5(Q5 hybrid 토글) 모두 자동화
- CLI 인자: `--v2-mode` / `--skip-act-0-5` / `--skip-act-3` / `--skip-act-5-5`
- `backend/scripts/seed_demo_calendar_busy.py` 신설 (272줄): synthetic busy 시드, ACT 2.5 majority_fallback 안정 발동

---

## 3. 아키텍처 핵심

### pipeline-split 구조

main HEAD(`dce4357`)에서 `langgraph_pipeline.py`는 **31줄 shim**으로 교체됨(Phase 5.2). 실제 코드는 `backend/app/services/pipeline/` 디렉토리로 분리:

```
backend/app/services/pipeline/
  state.py            # GraphState 정의 (preference_*·rejected_places·zero_slot_reason 등)
  graph.py            # _route_from_start (trigger_reason 5분기)
  nodes/
    entity.py         # date_hint·place_hint·cuisine·rejected_dates·rejected_places 추출
    slot.py           # slot_filling 4 trigger × partial_mode 분기
    function_call.py  # _safe_search_place + 0슬롯 reason 분기
    vote_card.py      # payload + zero_slot_reason narrator + Q7 메타
    place.py          # _compute_final_score (Q4=A) + F7·F9
    maedeup.py        # 확정/partial 카드 발행
  helpers/
    places.py         # _detect_cuisine_type + _resolve_place_hint (F5 4-step) + _filter_out_rejected_places
    preference_toggle.py  # Q7-c lightweight 비교 + meta 계산
    preferences.py    # load_requester_context (P0-2·3·4)
    slots.py          # _build_majority_fallback_slots (F1 fallback)
```

### LangGraph 파이프라인 (9노드 — trigger_reason 기반 조건부 진입)

```
[trigger_reason별 진입점]
  conclusion_detected   → entity_extraction → maedeup_card (vote+place 스킵)
  all_members_selected  → slot_filling → place_recommendation → maedeup_card
  stalemate_judged      → entity_extraction → slot_filling → vote_card_creation
  direct_request        → quick_classify → (entity_extraction →) vote|place|maedeup
  preference_toggle     → (graph.py route) → place_recommendation
```

노드 순서 (풀체인): `entity_extraction → slot_filling → function_calling → supervisor_validation → vote_card_creation → place_recommendation → maedeup_card_creation`

### WebSocket 구조

| 엔드포인트 | 용도 | Redis 채널 |
|---|---|---|
| `/ws/social/{room_id}` | 유저 채팅방 + 교착 감지 | `social:{room_id}` |
| `/ws/agent/{room_id}` | AI 어시스턴트 패널 | `agent:{room_id}` |

트리거 조건: 채팅 메시지 ≥4건 누적 → `judge_stalemate` LLM 호출 → `stalemate_judged` (해결점 A에서 임계값 5→4 수정됨)

### 백엔드 주요 라우터

| 파일 | 역할 |
|---|---|
| `backend/app/api/routes/meetings.py` | 미팅 CRUD + 투표 API + Q5 hybrid refresh 라우트 |
| `backend/app/api/routes/assistant.py` | AI 패널 직접 입력 + Q-X3 토큰 체크 |
| `backend/app/api/ws/social.py` | 채팅방 WS + 교착 감지(judge_stalemate) |
| `backend/app/api/ws/agent.py` | AI WS + trigger_reason 분기 + pipeline 실행 |

### 프론트엔드 핵심 컴포넌트

| 파일 | 역할 |
|---|---|
| `frontend/src/components/meeting/ScheduleRecommendationCard.tsx` | F1 fallback UI + Q5 hybrid 토글 |
| `frontend/src/components/meeting/PlaceRecommendationCard.tsx` | Q5 hybrid 토글 |
| `frontend/src/hooks/useAgentWebSocket.ts` | VoteCardPayload·PlaceRecommendationPayload 타입 확장 |
| `frontend/src/hooks/useSocialWebSocket.ts` | 채팅 WS 훅 (배너 데드코드 미정리 — 해결점 B 예정) |

### DB / Alembic

- DB: PostgreSQL 16 (운영) + SQLite (pytest)
- Alembic head: `e2a3b4c5d6f7` (PR-X calendar_consent 마이그 적용)
- 마이그 패턴: idempotent (`inspector.has_table/has_column`) + `batch_alter_table` (sqlite 호환, PR-V1.5.2에서 7파일 적용)

### 외부 API

| API | 용도 | 환경변수 |
|---|---|---|
| Gemini 2.5 Flash | 의도 분류·엔티티·장소 점수·검증 | `GEMINI_API_KEY` |
| gemini-embedding-001 | Intent RAG 임베딩 (55개 seed) | `GEMINI_API_KEY` |
| Google OAuth 2.0 | 로그인 + Calendar 연동 | `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI` |
| Google Calendar API | 멤버 free-slot 조회 | OAuth token |
| Kakao Local API | 장소 검색 | `KAKAO_REST_API_KEY` |
| Kakao Map JS SDK | 프론트 지도 | `NEXT_PUBLIC_KAKAO_MAP_KEY` |

---

## 4. 실행 방법

### Docker (WSL에서 `sg docker -c` 우회 필요 — 사용자 docker 그룹 미가입)

```bash
sg docker -c "docker compose up -d"
sg docker -c "docker compose ps"
sg docker -c "docker exec maedeup-api alembic upgrade head"
# Intent seed (새 DB 또는 embedding 모델 변경 후)
curl -X POST http://localhost:8000/api/v1/intents/seed
# 프론트 변경 후 리빌드
sg docker -c "docker compose up -d --build frontend"
# 백엔드 변경 후 (볼륨 마운트, 코드만 변경 시)
docker restart maedeup-api
```

접속: Frontend `http://localhost:3000` / Backend API `http://localhost:8000` / Docs `http://localhost:8000/docs`

### pytest (신규 12 파일, 91/91 PASS 기준)

```bash
sg docker -c "docker exec maedeup-api pytest \
  tests/integration/test_user_consent_default.py \
  tests/unit/test_majority_fallback.py \
  tests/integration/test_f1_fallback_pipeline.py \
  tests/unit/test_preference_toggle.py \
  tests/integration/test_refresh_route.py \
  tests/unit/test_rejected_places.py \
  tests/unit/test_cuisine_ambiguity.py \
  tests/unit/test_score_integration.py \
  tests/unit/test_kakao_error_handling.py \
  tests/unit/test_resolve_place_hint.py \
  tests/unit/test_assistant_consent_message.py \
  tests/unit/test_zero_slot_reason.py -v --tb=short"
```

### 시연 자동화 v3 (2026-05-15 WSL venv v2 셋업 완료)

WSL venv 또는 Windows PowerShell 둘 다 가능. 발표자 환경은 Windows 권장, 개발·QA agent 검증은 WSL 권장.

사전 조건:
1. Docker 4 컨테이너 healthy 확인
2. `.gstack-demo-token` 파일에 JWT 저장
3. (D-1) Personal Data 시드: `python backend/scripts/seed_demo_personal_data.py --room <ID>`
4. (옵션) 캘린더 busy 시드: `python backend/scripts/seed_demo_calendar_busy.py`

#### WSL venv 실행 (개발·QA agent 기본)
```bash
# 터미널 1: chromium + CDP 9222 (WSLg → Windows 데스크탑 visible)
~/.venv-maedeup-demo/bin/python3 .gstack-browser-launch.py

# 터미널 2: 시연 자동화
~/.venv-maedeup-demo/bin/python3 .gstack-demo.py
# 빠른 검증 모드: --fast
# ACT 0.5 스킵: --skip-act-0-5
```

venv 사양: `~/.venv-maedeup-demo` (Python 3.12, `websockets==16.0`, `playwright==1.59.0`, chromium 1217 호환).

#### Windows PowerShell 실행 (발표자 환경 본번)
```powershell
# 터미널 1
.venv\Scripts\python.exe .gstack-browser-launch.py
# 터미널 2 (별도 셸)
.venv\Scripts\python.exe .gstack-demo.py
```

ACT 흐름: `0.5(Personal Data) → 1(방 생성) → 2(채팅 stalemate) → 3(TimeBar) → 4(partial) → 5(AI 패널·확정) → 5.5(Q5 hybrid 토글)`

---

## 5. 현재 브랜치 / 미해결 backlog

현재 브랜치: `docs/spec-time-coordination` (main 대비 53+ 커밋 ahead, origin 동기 완료)
별도 운영 브랜치: `chore/claude-subagents` (로컬, main 기반 — `.claude/agents/*.md` 5개 + .gitattributes + .gitignore PNG)

상세 TODO는 `TODOS.md` 및 `docs/TODO.md` 참조. 핵심 미결 항목:

| 우선순위 | 항목 | TODOS.md 참조 |
|---|---|---|
| P0 시급 | 해결점 O 구현 (정규식 단축 사각지대) | TODOS.md §2 |
| P0 시급 | 해결점 P 정교화 (번복·게스트 정책) | TODOS.md §3 |
| P0 시급 | v2 spec 본문 작성 시작 (38항목, 시연 후) | TODOS.md §1 |
| P1 다음 세션 | ACT 4 confirm 후속 메시지 / ACT 5 quick_classify 보강 | TODOS.md §4 |
| P1 다음 세션 | F4 narrator 백엔드 구현 (LIMIT-9, Q17=A) | TODOS.md §6 |
| P1 다음 세션 | LIMIT-7 free-slots Redis 캐싱 | TODOS.md §5 |
| P2 backlog | When2Meet 프라이버시 (InfoPane 대개편 후) | TODOS.md §8 |

---

## 6. 참고 문서 포인터

| 파일 | 역할 |
|---|---|
| `docs/handoff/2026-05-14-spec-progress.md` | 진행 핸드오프 v19 (이번 세션 커밋 표·결정 전체) |
| `docs/handoff/2026-05-14-spec-v2-plan.md` | v2 spec 38항목 계획서 (PR-v2.0~v2.5 분할안) |
| `docs/handoff/spec-common.md` | spec v1.0 공통 SoT (권한·데이터·API·비기능·결정 안건·변경 이력) |
| `docs/handoff/spec-time-coordination.md` | spec v1.0 시간 조율 본문 |
| `docs/handoff/spec-place-recommendation.md` | spec v1.0 장소 추천 본문 |
| `docs/handoff/audit-findings.md` | 해결점 A~P 누적 (16건, 코드/git 검증 완료) |
| `docs/handoff/demo-scenario-v3.md` | 시연 시나리오 SoT (2026-05-15, ACT 0.5~5.5) |
| `docs/handoff/2026-05-14-spec-review-guide.md` | 외부 리뷰 가이드 (심사위원·협업자용, 212줄) |
| `docs/SESSION_STATE.md` | 컨텍스트 복구 4-파일 중 메인 (핵심 파일 경로·환경 상태) |
| `docs/TODO.md` | 진행 중·남은 작업 (v1.6 backlog 15항목 포함) |
| `docs/DECISIONS.md` | 확정 결정 30건 (Q1~Q17 + Q-X~Y 시리즈) |
| `docs/BUGS.md` | 버그 인벤토리 (해소 5건, 잔존 BUG-1 + LIMIT-1~9) |

### 컨텍스트 복구 순서 (compact 후 새 세션 진입 시)

1. `docs/SESSION_STATE.md` (전체 컨텍스트)
2. `docs/DECISIONS.md` (30건 결정 사항)
3. `docs/TODO.md` (진행 중·남은 작업)
4. `docs/BUGS.md` (버그 인벤토리)
5. `docs/handoff/2026-05-14-spec-progress.md` (커밋 표·상세 진행)
6. `git log --oneline -40` (최근 커밋 스냅샷)

---

## 7. 코딩 규칙 / Never

- Enum → `sa.Column(sa.String(32))`, `.value` 호출 금지
- Alembic 마이그레이션은 idempotent (`inspector.has_table/has_column` 체크)
- `init_db()` = `SELECT 1`만 (`create_all` 금지)
- datetime은 naive UTC (`timezone-aware → .replace(tzinfo=None)`)
- API 키/시크릿 전체 출력 금지 (앞 4~5자만 마스킹)
- 프론트엔드 변경은 Docker 리빌드 필요
- 승인 없이 커밋/푸시 금지
- 외부 패키지 임의 추가 금지
- DB `create_all` 사용 금지
- 다이어그램 SoT: `docs/handoff/diagrams/*.mmd` (FigJam은 build artifact, .mmd만 수정)
- EOL: LF 강제 (`.gitattributes` 적용, 2026-05-15 `c8a4a7d`)

---

## 8. 운영 모드

- **리더(Claude)**: PM 역할만 — 작업 분배·진행 점검·결과 통합·결정 제안
- **4 담당 sub-agent** (`.claude/agents/*.md`, chore/claude-subagents 브랜치):
  - `code-writer` (Sonnet, Edit/Write) — 실제 코드 작성·수정
  - `code-analyst` (Opus, read-only) — deep 코드 분석·아키텍처 trade-off
  - `docs-planner` (Sonnet, read-only) — spec·문서 일관성
  - `risk-reviewer` (Opus, read-only) — 누락·리스크·과장 검토
  - `qa-runtime` (Opus, read-execute + Playwright MCP) — 실제 서버·브라우저 검증
- **모델 분배 규칙 (2026-05-15 v2, 메모리 `feedback-pm-operating-mode`)**: 작성·정적 검증 = Sonnet, deep reasoning·동적 검증 = Opus
- **Codex**: 외부 모델 (`gpt-5`/codex CLI), 별개 운영
- PR 완료마다 `docs/handoff/2026-05-14-spec-progress.md` 자동 갱신
- 원격 푸시는 사용자 명시 승인 후에만
