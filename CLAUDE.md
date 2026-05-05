# 매듭 (Maedeup)

## 진행 중인 작업
세션 시작 시 `docs/handoff/` 폴더의 가장 최근 문서를 먼저 확인하세요.
**현재 task**: 시연 루프 검증 — 감사 해결점 A~M 코드 적용 완료, 브라우저 시연 ACT 1~5 검증 진행 중.
다음 세션 시작 지점:
1. ACT 3 재확인 (vote_card → confirm_time → Option A 흐름)
2. 채팅방 "안되는 날짜" 미적용 버그 디버깅
참고:
- `docs/handoff/2026-05-06-demo-loop-progress.md` (최신 — 미커밋 변경 + 다음 스텝)
- `docs/handoff/2026-05-05-architecture-audit-progress.md`
- `docs/handoff/audit-findings.md`
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
  app/services/langgraph_pipeline.py  # 핵심 AI 파이프라인 (8노드)
  app/routers/                        # API 엔드포인트
  app/models/                         # SQLModel 모델
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
