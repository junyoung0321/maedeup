# 매듭 (Maedeup)

## 진행 중인 작업
세션 시작 시 `docs/handoff/` 폴더의 가장 최근 문서를 먼저 확인하세요.
**현재 task**: spec v1.0 + Option C (TimeBar in-card 호스트 확정) + CalendarPane 빨간 배지 제거 + ACT 2 자연 표현 + 시나리오 정합성 7건 fix + 시연 D-6 (2026-05-22 금 점심) 준비 완료 (HEAD `4a98d2f`). **다음**: 시연 영상 5/18 (월) 촬영 + v2 spec 본문 작성.
시연 자동화 (WSL venv v2, 2026-05-15):
- 터미널 1: `~/.venv-maedeup-demo/bin/python3 .gstack-browser-launch.py`
- 터미널 2: `~/.venv-maedeup-demo/bin/python3 .gstack-demo.py` (또는 `--fast`)
- 사전에 `.gstack-demo-token` 파일에 JWT 저장.
- Windows 발표자 환경 병행: `.venv\Scripts\python.exe .gstack-demo.py`
미해결 backlog:
1. 해결점 P 정교화 (번복 처리, 게스트 정책)
2. 해결점 O (정규식 단축 사각지대) — spec v2 옵션 B 권고
3. ACT 4 confirm 후속 메시지 / ACT 5 quick_classify 보강
4. LIMIT-7 (free-slots 캐싱), LIMIT-8
5. F4 narrator (Q17 후속)
6. 코덱스 P1 backlog (Option C 라운드 1~9 완료 후 추가 필요 검토, TODOS.md §10) — vote_update 좁히기·VoteCardSection 회귀 테스트·timeConfirmed mount·seed 주석·refresh state 통일
7. 장소 추천 vote 시스템 검토 (v2 spec PR-v2.1 후보)
참고:
- `docs/handoff/2026-05-16-option-c-natural.md` (오늘 진행 기록 — Option C 라운드 1~9 + 자연 표현 + 시나리오 정합성, 2026-05-16)
- `docs/handoff/2026-05-15-round4-green.md` (자동 루프 5라운드 + GREEN 도달, 2026-05-15)
- `docs/handoff/2026-05-14-spec-progress.md` (v20 — spec v1.0 + PR-V1.5 + QA v2 + v3 자동화 + Option C 통합 보고)
- `docs/handoff/2026-05-14-spec-v2-plan.md` (v2 spec 38 항목 계획서)
- `docs/handoff/demo-scenario-v3.md` (시연 시나리오 SoT, 2026-05-16 갱신)
- `docs/handoff/spec-time-coordination.md` (619줄, v1.0)
- `docs/handoff/spec-common.md`
- `docs/handoff/audit-findings.md` (해결점 A~P)
- `docs/SESSION_STATE.md`, `docs/TODO.md`, `docs/DECISIONS.md`, `docs/BUGS.md` (복구 SoT 4파일, 646d252 commit)
- `docs/handoff/diagrams/`

## Project
AI 모임 조율 플랫폼 (졸업 프로젝트). 채팅방에서 일정/장소 교착 감지 → AI 자동 개입 → 투표/장소추천 카드 생성.
현재 상태: MVP 개발 중 (LangGraph 8노드 파이프라인 완성)

## Stack
- Frontend: Next.js 14, TypeScript, Tailwind
- Backend: FastAPI, SQLModel, asyncpg, Redis, LangGraph, Gemini 2.5 Flash
- DB: PostgreSQL 16 + Alembic migrations
- Infra: Docker Compose (fastapi-app, frontend, postgres-db, redis-broker)

## Structure
backend/
  app/services/langgraph_pipeline.py  # 31줄 re-export shim (Phase 5.2, dce4357)
  app/services/pipeline/              # 실제 파이프라인 (graph + nodes + helpers + constants)
    nodes/                            # conversation_analyzer, slot, memory, validation, maedeup 등
    helpers/                          # dates, formatting, json_extract, messaging, slot_state
    graph.py                          # 라우터 6 + _build_graph + run_pipeline
  app/api/routes/                     # API 엔드포인트 (auth/calendar/chat/events/finalization/places/recommendations/rooms/users/notifications/intents)
  app/models/                         # SQLModel 모델
  alembic/versions/                   # DB 마이그레이션 (idempotent 패턴 필수)
frontend/
  src/components/meeting/             # 채팅방, AI 어시스턴트 패널

## Conventions
- Enum → sa.Column(sa.String(32)), .value 호출 금지
- Alembic 마이그레이션은 idempotent (inspector.has_table/has_column 체크)
- init_db() = SELECT 1만 (create_all 금지)
- datetime은 naive UTC (timezone-aware → .replace(tzinfo=None))
- 커밋: conventional commits (feat/fix/chore), 한국어 OK

## Never
- API 키/시크릿 전체 출력 금지 (앞 4~5자만 마스킹)
- 승인 없이 커밋/푸시 금지
- 외부 패키지 임의 추가 금지
- DB create_all 사용 금지

## Commands
- 전체 실행: `docker compose up -d`
- 프론트 리빌드: `docker compose up -d --build frontend`
- 백엔드 반영: `docker restart maedeup-api` (볼륨 마운트, 자동 반영)
- Intent seed: `curl -X POST http://localhost:8000/api/v1/intents/seed`
- 배포: `/ship` → `/land-and-deploy`

## 다이어그램 작업 규칙
- **Source of truth**: `docs/handoff/diagrams/*.mmd` (Mermaid 파일)
- **수정 흐름**: .mmd 직접 편집 → diff 보여주기 → 사용자 승인 → `generate_diagram` MCP로 FigJam 렌더
- **FigJam은 build artifact**: 보드에서 직접 수정 금지, 항상 .mmd 파일에서만 수정
- **파일 분리 원칙**: 큰 다이어그램 1장 누적 금지. 주제별 파일 분리:
  - `00-overview.mmd` — 전체 시퀀스 (큰 그림)
  - `01-trigger-rules.mmd` — 트리거 규칙 + 4게이트
  - `02-langgraph-flow.mmd` — 9노드 체인
  - `03-intent-classifier.mmd` — classify_intent 내부
- 새 다이어그램 추가 시 번호 이어서 (`04-...`, `05-...`)

## gstack
웹 브라우징은 /browse 사용. mcp__claude-in-chrome__* 도구 사용 금지.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

### 환경변수
`.env` 필수: GEMINI_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, JWT_SECRET, KAKAO_REST_API_KEY, NEXT_PUBLIC_KAKAO_MAP_KEY

### Embedding 모델
`models/gemini-embedding-001`. 변경 시:
```bash
# Docker 내부에서
DELETE FROM intent_examples;
# 후 POST /api/v1/intents/seed
```

## gstack
Use /browse from gstack for all web browsing. Never use mcp__claude-in-chrome__* tools.

## 코딩 규칙
- API 키/시크릿 전체 출력 절대 금지 (앞 4~5자만 마스킹)
- 프론트엔드 변경은 Docker 리빌드 필요
- docker-compose의 DATABASE_URL/REDIS_URL은 하드코딩
- Google OAuth 테스트 사용자 등록 필요
- 카카오 OPEN_MAP_AND_LOCAL 서비스 활성화 필요
- Gemini rate limit 시 패턴 fallback으로 기본 동작 보장
- 커밋/푸시는 유저 확인 후에만

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
