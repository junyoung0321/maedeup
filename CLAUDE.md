# 매듭 (Maedeup) - AI 모임 조율 플랫폼

## 프로젝트 개요
졸업 프로젝트. AI를 활용해 모임 일정/장소를 조율하는 웹앱.

## 기술 스택
- **Backend**: FastAPI + SQLModel + asyncpg + Redis + LangGraph + Gemini 2.5 Flash
- **Frontend**: Next.js 14 + TypeScript + Tailwind
- **DB**: PostgreSQL 16 + Alembic migrations
- **Infra**: Docker Compose (fastapi-app, frontend, postgres-db, redis-broker)

## 로컬 실행
```bash
docker compose up -d                              # 전체 실행
docker compose up -d --build frontend             # 프론트 변경 시 리빌드 필요
docker restart maedeup-api                        # 백엔드 변경은 자동 반영 (볼륨 마운트)
curl -X POST http://localhost:8000/api/v1/intents/seed  # 새 DB 후 intent seed 필수
```

## 핵심 아키텍처

### LangGraph 파이프라인 (8 노드)
`backend/app/services/langgraph_pipeline.py`
```
intent_detection → entity_extraction → slot_filling → function_calling
→ supervisor_validation → vote_card_creation → place_recommendation → maedeup_card_creation
```

### WebSocket 구조
- `/ws/social/{room_id}` — 유저 채팅방 (교착 5메시지 감지 → agent auto-trigger)
- `/ws/agent/{room_id}` — AI 어시스턴트 (직접 메시지: 항상 응답, auto-trigger: 교착/결론 시만)
- Redis pub/sub: `social:{room_id}`, `agent:{room_id}`

### AI 개입 조건
- **채팅방**: 5개+ 모임 관련 메시지 교착 시에만 AI 개입 (잡담/의견 교환 중 안 끼어듬)
- **결론 감지**: "확정", "콜", "그걸로 하자" → 정리 카드 자동 생성
- **AI 패널 직접**: 항상 즉시 응답 (debounce 없음)
- **멀티 날짜**: "목요일에 볼까 금요일에 볼까" → 투표 카드 자동 생성

### DB 주의사항
- Enum → `sa.Column(sa.String(32))`, `.value` 호출 금지
- alembic 마이그레이션은 idempotent (`inspector.has_table/has_column` 체크)
- `init_db()` = `SELECT 1`만 (create_all 금지)
- datetime은 naive UTC (timezone-aware → `.replace(tzinfo=None)`)

### Intent Classifier 3단계
1. RAG: gemini-embedding-001 + cosine similarity (55개 seed examples)
2. Gemini fallback: 중간 유사도 구간에서 Gemini 판단
3. 패턴 매칭: 한국 지명(XX동/역/구), 날짜 키워드, 멀티 날짜 감지

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

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

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
