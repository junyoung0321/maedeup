# SESSION_STATE — 매듭(Maedeup) 프로젝트

**최종 갱신**: 2026-05-15
**세션 컨텍스트**: spec v1.0 작성 + 미구현 항목 코드화 + Codex 리뷰 + QA 런타임 검증
**브랜치**: `docs/spec-time-coordination` (origin = `e996bba`, 로컬 미푸시 38+ 커밋)

---

## 1. 프로젝트 개요

- **이름**: 매듭(Maedeup)
- **종류**: 졸업 프로젝트 — AI 모임 조율 플랫폼
- **핵심 가치**: 채팅으로 흩어진 시간·장소 의사를 자동으로 모아 vote_card / place_recommendation / maedeup_card로 마무리
- **스택**: Next.js 14 + FastAPI + SQLModel + asyncpg + Redis + LangGraph + Gemini 2.5 Flash + Kakao Local API
- **현재 상태**: MVP — spec v1.0 완성, 핵심 코드 구현, **시연 직전**

---

## 2. spec 문서 구조 (3 파일 분할, PR-V로 분리됨)

| 파일 | 분량 | 역할 |
|---|---|---|
| `docs/handoff/spec-common.md` | 839줄 | 공통 정책·권한·API·비기능·부록·**결정 안건 SoT** |
| `docs/handoff/spec-time-coordination.md` | 619줄 | 시간 조율 (§1·S1~S10·§3.1·§4 시간·§6.1~6.13·§10) |
| `docs/handoff/spec-place-recommendation.md` | 459줄 | 장소 추천 (§1·S11~S20·§3.2~3.4·§4 장소·§6.14~6.18·§10) |

**합계**: 1917줄. 단일 SoT 원칙 — 결정 안건·변경 이력은 `spec-common.md` 한 곳만.

---

## 3. 코드 변경 인벤토리 (PR별)

| PR | SHA | 메시지 | 변경량 |
|---|---|---|---|
| **PR-X** | `9609bee` | calendar_consent default True + Alembic 마이그 + 게스트 보호 | +372 / -1 |
| **PR-Y1** | `54e1532` | F1 fallback (다수결 vote_card) 백엔드 + 9 파일 + pytest 8 케이스 | +522 / -3 |
| **PR-Y2** | `adc444f` | F1 fallback 프론트 UI (배너·배지·슬롯별 더보기 토글) | +132 / -11 |
| **PR-Z1** | `66110e9` | Q5 hybrid refresh 라우트 + P0-2·3·4 plumbing + 메타 키 + Q7-c | +946 / -4 |
| **PR-Z2** | `ea759d1` | Q5 hybrid 토글 UI (Schedule·Place 카드) + refresh API 호출 | +255 / -1 |
| **PR-V** | `6769400` | spec 3 분할 (common·time·place) + 외부 문서 cross-ref | +1943 / -1646 |
| **PR-V1.5** | `90131f2` | spec v1.0 미구현 12건 + Codex P1·P2 통합 | +1342 / -54 |
| **PR-V1.5.1** | `1892b50` | QA P2 hotfix — alembic sqlite·JSON dialect·SENTINEL | +60 / -11 |
| **PR-V1.5.2** | `aaec29d` | P3 hotfix — alembic batch_alter_table 7파일 + JSON·test seed | +208 / -193 |

---

## 4. 핵심 파일 경로

### 백엔드 (LangGraph 파이프라인)
- `backend/app/services/pipeline/state.py` — GraphState 정의 (preference_*·rejected_places·zero_slot_reason 등)
- `backend/app/services/pipeline/graph.py` — `_route_from_start` (trigger_reason 5분기: stalemate/conclusion/all_members/direct_request/**preference_toggle**)
- `backend/app/services/pipeline/nodes/entity.py` — date_hint·place_hint·cuisine·rejected_dates·**rejected_places** 추출
- `backend/app/services/pipeline/nodes/slot.py` — slot_filling 분기 (4 trigger × partial_mode)
- `backend/app/services/pipeline/nodes/function_call.py` — `_safe_search_place` + 0슬롯 reason 분기
- `backend/app/services/pipeline/nodes/vote_card.py` — payload + zero_slot_reason narrator + Q7 메타
- `backend/app/services/pipeline/nodes/place.py` — `_compute_final_score` (Q4=A) + `_sort_by_final_score` + F7·F9
- `backend/app/services/pipeline/nodes/maedeup.py` — 확정/partial 카드 발행
- `backend/app/services/pipeline/helpers/places.py` — `_detect_cuisine_type` (list 반환) + `_resolve_place_hint` (F5 4-step) + `_filter_out_rejected_places`
- `backend/app/services/pipeline/helpers/preference_toggle.py` — Q7-c lightweight 비교 + meta 계산
- `backend/app/services/pipeline/helpers/preferences.py` — `load_requester_context` (P0-2·3·4)
- `backend/app/services/kakao_maps.py` — `KakaoApiError` + 5xx/timeout/network 분리
- `backend/app/api/routes/meetings.py` — refresh 라우트 (`POST /{id}/recommendations/refresh`, Q13·Q14·Q7-c·Q15)
- `backend/app/api/routes/assistant.py:99` — 토큰 체크 보강 (Q-X3)
- `backend/app/models/user.py` — `calendar_consent default=True` + `is_ai_filled` dialect-agnostic
- `backend/app/models/meeting.py` — `google_event_ids` dialect-agnostic
- `backend/alembic/env.py` — sqlite 분기 (`_is_sqlite_url` + 동기 run_sync_migrations)
- `backend/alembic/versions/e2a3b4c5d6f7_set_calendar_consent_default_true.py` — PR-X 신규
- `backend/alembic/versions/*` — 7 파일에 `batch_alter_table` 패턴 적용 (PR-V1.5.2)

### 프론트엔드
- `frontend/src/hooks/useAgentWebSocket.ts` — VoteCardPayload·PlaceRecommendationPayload 타입 (preference_source·toggle_enabled·available_count·unavailable_users 등)
- `frontend/src/components/meeting/ScheduleRecommendationCard.tsx` — F1 fallback UI + Q5 hybrid 토글
- `frontend/src/components/meeting/PlaceRecommendationCard.tsx` — Q5 hybrid 토글

### 테스트 (신규 12 파일, 91/91 PASS)
- `backend/tests/integration/test_user_consent_default.py` (6 케이스, PR-X)
- `backend/tests/unit/test_majority_fallback.py` (4, PR-Y1)
- `backend/tests/integration/test_f1_fallback_pipeline.py` (3, PR-Y1)
- `backend/tests/unit/test_preference_toggle.py` (18, PR-Z1+V1.5)
- `backend/tests/integration/test_refresh_route.py` (10, PR-Z1+V1.5)
- `backend/tests/unit/test_rejected_places.py` (8, PR-V1.5)
- `backend/tests/unit/test_cuisine_ambiguity.py` (6, PR-V1.5)
- `backend/tests/unit/test_score_integration.py` (12, PR-V1.5)
- `backend/tests/unit/test_kakao_error_handling.py` (8, PR-V1.5)
- `backend/tests/unit/test_resolve_place_hint.py` (9, PR-V1.5)
- `backend/tests/unit/test_assistant_consent_message.py` (5, PR-V1.5)
- `backend/tests/unit/test_zero_slot_reason.py` (3, PR-V1.5)

### 핸드오프·메타 문서
- `docs/handoff/2026-05-14-spec-progress.md` — 진행 핸드오프 (v17까지 갱신)
- `docs/handoff/2026-05-14-spec-review-guide.md` — 외부 리뷰 가이드 (심사위원·협업자용)
- `docs/handoff/2026-05-14-spec-v2-plan.md` — v2 spec 계획 (38 항목)
- `docs/handoff/audit-findings.md` — 해결점 A~P (N PR-0에서 추가)
- `docs/handoff/demo-scenario.md` — 시연 시나리오 SoT (ACT 0~6, 3분30초)
- `docs/handoff/2026-05-13-recommend-input-catalog.md` — 입력 카탈로그 6 카테고리·P0/P1/P2

### 메모리 (영구 저장, `/home/cyun0407/.claude/projects/-mnt-c-Users-cyun0-git-maedeup/memory/`)
- `feedback_pm_operating_mode.md` — PM 4담당 운영 모드
- `feedback_handoff_auto_update.md` — PR 완료 시 handoff 자동 갱신
- `feedback_qa_runtime_role.md` — QA 4번째 담당 + Playwright MCP·CLI + 시연 환경 운영 규칙

### 시연 스크립트
- `.gstack-browser-launch.py` — Chromium CDP 띄우기 + JWT 주입
- `.gstack-demo.py` — ACT 1·2·4·5 자동화 (ACT 3·6 스킵)
- `.gstack-demo-integrated.py` — 통합 버전
- `.gstack-demo-token` — JWT 저장 (gitignore)

**🔴 중요**: 시연 스크립트는 **WSL이 아니라 Windows PowerShell + `.venv\Scripts\python.exe`**로 실행 (BUG-1 해결 방향, 사용자 결정)

---

## 5. 실행 명령

### Docker (WSL에서 `sg docker -c` 우회 필요)
```bash
sg docker -c "docker compose up -d"
sg docker -c "docker compose ps"
sg docker -c "docker exec maedeup-api alembic upgrade head"
sg docker -c "docker exec maedeup-api alembic current"
```

### Pytest (전체 신규 12 파일, 91/91 PASS 확인됨)
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

### 시연 (Windows PowerShell에서, **WSL X**)
```powershell
# 터미널 1
python .gstack-browser-launch.py

# 터미널 2 (별도 셸)
python .gstack-demo.py
# 또는 빠른 검증: python .gstack-demo.py --fast
```

### Codex 리뷰
```bash
# staged 변경 검토
codex review --uncommitted --title "..."
# 또는 특정 커밋
codex review --commit <SHA> --title "..." "<prompt>"
```

### QA Playwright MCP (작동 확인됨)
- `mcp__playwright__browser_navigate` (URL = localhost:3000)
- `mcp__playwright__browser_snapshot` / `browser_take_screenshot`
- `mcp__playwright__browser_console_messages` (level: error/warning/info/debug)
- `mcp__playwright__browser_network_requests`
- `mcp__playwright__browser_click` / `browser_type` / `browser_fill_form`
- `mcp__playwright__browser_evaluate` (JS 직접 실행, localStorage 주입 등)

---

## 6. 운영 모드 (PM 4 담당 + QA)

리더(Claude)는 **PM 역할만**:
- 작업 분배·진행 점검·결과 통합·최종 의사결정 제안
- 깊은 분석은 **항상 4 담당 에이전트에 위임**

**4 담당**:
1. **코드 분석 담당** — 정적, Read·grep
2. **문서/기획 담당** — 정적, Read
3. **리뷰/리스크 담당** — 정적, Read
4. **QA (서비스 런타임 검증)** — Bash·Playwright MCP·실서버 실행

**자동 워크플로**:
- PR 완료마다 `2026-05-14-spec-progress.md` 자동 갱신 (메모리에 영구 저장)
- Codex 리뷰는 user가 명시 시 codex CLI `review --uncommitted`
- 원격 푸시 금지 (사용자 직접 승인 시에만)

---

## 7. 환경 상태

| 항목 | 상태 |
|---|---|
| Docker WSL 통합 | ✅ 활성 (`sg docker -c` 우회 필요 — 사용자 docker 그룹 미가입) |
| 4 컨테이너 | ✅ healthy (api·frontend·postgres·redis) |
| Alembic head | ✅ `e2a3b4c5d6f7` (PR-X 마이그 적용) |
| pytest 신규 12 파일 | ✅ 91/91 PASS |
| Playwright MCP | ✅ 작동 (browser_navigate 성공, Page Title "매듭 (Maedeup)") |
| Codex CLI | ✅ 0.118.0 (ChatGPT 로그인 cyun0407@gmail.com) |

---

## 8. compact 후 첫 읽기 순서

복구할 다른 Claude(또는 자신)는 다음 순서로 읽기:

1. **본 파일 (`docs/SESSION_STATE.md`)** — 전체 컨텍스트
2. **`docs/DECISIONS.md`** — 30+ 결정 사항·근거
3. **`docs/TODO.md`** — 진행 중·남은 작업
4. **`docs/BUGS.md`** — 발견 버그·우선순위·해소 상태
5. **`docs/handoff/2026-05-14-spec-progress.md`** — 진행 핸드오프 (커밋 표·상세)
6. **`docs/handoff/spec-common.md`** — 공통 정책·권한·API (필요 시)
7. **`docs/handoff/spec-time-coordination.md` / `spec-place-recommendation.md`** — 도메인별 (필요 시)
8. **메모리** (`feedback_pm_operating_mode.md` / `feedback_qa_runtime_role.md` / `feedback_handoff_auto_update.md`) — 운영 규칙

`git log --oneline -40`로 최근 커밋 확인하면 빠르게 컨텍스트 잡힘.
