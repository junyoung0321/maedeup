# 매듭 (Maedeup)

## 진행 중인 작업
세션 시작 시 `docs/handoff/` 폴더의 가장 최근 문서를 먼저 확인하세요.
**현재 task**: 시연 직전 (D-4, 2026-05-16) — 해결점 A~P + Fix 1~14 + demo-stab 백포팅 + call_gemini 결정성 강화 완료. 실측 검증 통과.

### 실측 latency (2026-05-16, 3회 평균)
- ACT 2 (자동 개입, stalemate): **8s** (분산 ±1s)
- ACT 5 (장소 추천, direct_request): **3.41s** (분산 ±0.05s) — 5s 목표 달성 ✅
- 결정성: tool 시퀀스 100% 동일 (top_p=0.1, top_k=1 효과)
- 회귀: 0건

### 시연 자동화 (순서 엄수)
**사전 절차 (시연 시작 전 1회):**
1. `.env`에 `DEMO_FALLBACK_ENABLED=true` 설정 (없으면 personal_data_extractor canned fallback 비활성 → ACT 6 학습 안 됨)
2. `docker exec maedeup-api python -m scripts.seed_demo` — 시연 멤버(지민·수현·민수) DB 시드 + personal data 사전 학습
3. JWT 발급: `docker exec maedeup-api python -c "from app.core.security import issue_jwt; print(issue_jwt(user_id=1, email='dnfltkagudwp123@gmail.com', name='정준영', picture=None, calendar_consent=True))"` → `.gstack-demo-token`에 저장

**실행:**
- 터미널 1: `python .gstack-browser-launch.py`
- 터미널 2: `python .gstack-demo.py` (`--fast` 옵션 가능)

**ACT 6 학습 모먼트 검증:** `docker logs maedeup-api | Select-String "users affected"` — `0 users affected` 보이면 seed_demo 실행 필요. 1+ 보이면 정상.

### 시연 후 보완 항목 (D+ 작업)
1. 해결점 P 정교화 (번복 처리, 게스트 정책) — 시연 시나리오에 등장 안 함, 우선순위 낮음
2. 해결점 O (정규식 단축 사각지대) — ✅ 2026-05-16 완료 (`_REJECT_SIGNAL_PATTERN` 보강)
3. ACT 4 confirm 후속 메시지 — 자동화 검증 통과, manual 발견 시 진행
4. ACT 5 quick_classify 보강 — ✅ 2026-05-16 완료 (한식집/술집/회식/모임/약속 키워드 + 어때/골라 동사)

참고:
- `docs/handoff/2026-05-06-demo-loop-progress.md`
- `docs/handoff/demo-scenario.md` (시연 시나리오 SoT)
- `docs/handoff/audit-findings.md` (해결점 A~P)
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
