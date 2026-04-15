# 매듭 (Maedeup) 인수인계 문서

> 작성일: 2026-04-14
> 브랜치: `feature/code-review-improvements` (main 대비 2커밋 ahead + 미커밋 수정 3건)

---

## 1. 프로젝트 개요

졸업 프로젝트. AI를 활용해 모임 일정/장소를 자동 조율하는 웹앱.

- **Backend**: FastAPI + SQLModel + asyncpg + Redis + LangGraph + Gemini 2.5 Flash
- **Frontend**: Next.js 14 + TypeScript + Tailwind
- **DB**: PostgreSQL 16 + Alembic migrations
- **Infra**: Docker Compose (fastapi-app, frontend, postgres-db, redis-broker)

---

## 2. 핵심 아키텍처

### LangGraph 파이프라인 (8 노드)
```
intent_detection → entity_extraction → slot_filling → function_calling
→ supervisor_validation → vote_card_creation → place_recommendation → maedeup_card_creation
```

- `backend/app/services/langgraph_pipeline.py` (단일 파일, ~2400줄)
- 파이프라인 1회 실행 소요시간: 4~15초 (Gemini API + 카카오 API 호출 포함)

### WebSocket 구조
| 엔드포인트 | 용도 | Redis 채널 |
|-----------|------|-----------|
| `/ws/social/{room_id}` | 유저 채팅방 | `social:{room_id}` |
| `/ws/agent/{room_id}` | AI 어시스턴트 | `agent:{room_id}` |

- 채팅방에서 모임 관련 메시지 5개 연속 → AI 자동 개입 (auto-trigger)
- AI 패널 직접 메시지 → 항상 즉시 파이프라인 실행

### Intent Classifier 3단계
1. RAG: `gemini-embedding-001` + cosine similarity (55개 seed examples)
2. Gemini fallback: 중간 유사도 구간
3. 패턴 매칭: 한국 지명, 날짜 키워드, 멀티 날짜 감지

---

## 3. 로컬 실행 방법

```bash
# 전체 실행
docker compose up -d

# 새 DB 후 필수
curl -X POST http://localhost:8000/api/v1/intents/seed

# 프론트 변경 → 리빌드 필요
docker compose up -d --build frontend

# 백엔드 변경 → 볼륨 마운트라 재시작만
docker restart maedeup-api
```

### 필수 환경변수 (.env)
```
GEMINI_API_KEY
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI
JWT_SECRET
KAKAO_REST_API_KEY
NEXT_PUBLIC_KAKAO_MAP_KEY
```

### 접속 URL
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API 문서: http://localhost:8000/docs

---

## 4. 현재 브랜치 상태 (2026-04-14)

### PR #1: `feature/code-review-improvements` → `main`
- 코드 리뷰 5라운드 수행, 26개 파일 수정 (+282/-82)
- 주요 수정: datetime.utcnow() 제거, CORS 보안, 인가 추가, 리마인더 신뢰성, AI 고도화

### 미커밋 변경 (3개 파일, +114/-45)
아래 이슈 수정 작업이 아직 커밋되지 않은 상태:

| 파일 | 수정 내용 |
|------|----------|
| `backend/app/services/langgraph_pipeline.py` | 슬롯 완전 채움 시 확인 메시지 추가, 단일 슬롯 시 투표 건너뛰기, meeting_id 없을 때 DB 자동 생성 |
| `frontend/src/components/meeting/AiAssistantPane.tsx` | 투표 후 확정 버튼 분리, AI 타임아웃 90초로 연장, 카드 수신 시 로딩 해제 |
| `frontend/src/components/meeting/InfoPane.tsx` | 장소 상세 시 캘린더 숨김 + PlaceDetailPane 풀사이즈 |

---

## 5. 알려진 이슈 및 해결 상태

### 해결됨 (미커밋)
| 이슈 | 원인 | 수정 |
|------|------|------|
| AI 응답이 안 옴 | 슬롯 전부 채워지면 텍스트 응답 없이 카드만 발행 → 프론트 로딩 영구 유지 | `slot_filling`에 확인 메시지 추가 + 카드 수신 시 로딩 해제 |
| 투표+확정 버튼 동시 노출 | 투표 전에도 "일정 확정" 버튼 활성화 | 투표 완료 후에만 확정 버튼 표시 |
| 투표 버튼 안 눌림 | 더미 슬롯에 meeting_id 없음 → disabled | vote_card_creation에서 pending meeting 자동 생성 |
| 장소 상세 시 캘린더 잘림 + 장소 작게 나옴 | scale(0.71) 축소 + 200px 캘린더 잔존 | 장소 상세 시 캘린더 숨기고 풀사이즈 표시 |
| AI 타임아웃 30초 | 파이프라인이 30초 넘으면 프론트에서 자동 취소 | 경고 20초, 타임아웃 90초로 연장 |

### 미해결 / 알려진 한계
| 이슈 | 설명 |
|------|------|
| 카카오 API 수용인원 미제공 | headcount 필터링 시 기본값 20 사용 |
| Google Calendar 미연동 시 | 더미 슬롯 3개 반환 (테스트 환경) |
| 장소 추천 거리 0m | 좌표 기반 검색 미사용 시 발생 |
| 컨테이너 재시작 후 WS 끊김 | 브라우저 새로고침 필요 (재연결 5회 시도 후 포기) |
| Gemini rate limit | 패턴 fallback으로 기본 동작은 보장되지만 정확도 하락 |

---

## 6. 시연 시나리오

### 핵심 한 문장 데모
```
"이번 주 금요일에 강남에서 4명이서 저녁 먹으려고 해"
```
→ 확인 메시지 → 장소 추천 5개 → 매듭카드 (전체 파이프라인 시연)

### 전체 플로우
1. AI 패널에서 위 문장 입력
2. 장소 추천에서 장소 선택 → 장소 확정
3. 매듭카드 자동 생성 (최종 요약)

### 멀티 날짜 시나리오
```
"토요일이나 일요일 중에 언제 볼까?"
```
→ 투표카드 2옵션 → 투표 → 일정 확정 → 장소 추천 → 매듭카드

### 채팅방 자동 개입
```
1: 이번 주에 한번 보자
2: 좋아 언제가 좋아?
3: 금요일 저녁 어때?
4: 나도 금요일 괜찮아
5: 어디서 볼까?
```
→ 5번째 메시지 후 AI 자동 트리거

---

## 7. DB 관련 주의사항

- Enum은 `sa.Column(sa.String(32))`, `.value` 호출 금지
- Alembic 마이그레이션은 idempotent (`inspector.has_table/has_column` 체크)
- `init_db()` = `SELECT 1`만 (create_all 금지)
- datetime은 naive UTC (`timezone-aware → .replace(tzinfo=None)`)
- Embedding 모델 변경 시: `DELETE FROM intent_examples;` 후 `/api/v1/intents/seed` 재호출

---

## 8. 주요 파일 위치

| 파일 | 역할 |
|------|------|
| `backend/app/services/langgraph_pipeline.py` | AI 파이프라인 전체 (~2400줄) |
| `backend/app/api/ws/agent.py` | AI WebSocket 핸들러 |
| `backend/app/api/ws/social.py` | 채팅방 WebSocket + 교착 감지 |
| `backend/app/services/intent_classifier.py` | 의도 분류 (RAG + Gemini + 패턴) |
| `backend/app/services/gemini.py` | Gemini API 래퍼 |
| `backend/app/api/routes/meetings.py` | 미팅 CRUD + 투표 API |
| `backend/app/api/routes/intents.py` | Intent seed/classify API |
| `frontend/src/components/meeting/AiAssistantPane.tsx` | AI 패널 UI (투표/추천/매듭카드) |
| `frontend/src/components/meeting/ChatPane.tsx` | 채팅방 UI |
| `frontend/src/components/meeting/InfoPane.tsx` | 캘린더 + 장소상세 패널 |
| `frontend/src/components/meeting/PlaceDetailPane.tsx` | 장소 상세 + 카카오맵 |
| `frontend/src/hooks/useAgentWebSocket.ts` | AI WebSocket 훅 |
| `frontend/src/hooks/useSocialWebSocket.ts` | 채팅 WebSocket 훅 |
| `docker-compose.yml` | 4개 서비스 (api, frontend, postgres, redis) |

---

## 9. 외부 API 의존성

| API | 용도 | 키 |
|-----|------|-----|
| Gemini 2.5 Flash | 의도 분류, 엔티티 추출, 장소 점수 매기기, 검증 | `GEMINI_API_KEY` |
| gemini-embedding-001 | Intent RAG 임베딩 | `GEMINI_API_KEY` |
| Google OAuth 2.0 | 로그인 + Calendar 연동 | `GOOGLE_CLIENT_ID/SECRET` |
| Google Calendar API | 멤버 일정 조회 → 빈 시간 계산 | OAuth token |
| Kakao Local API | 장소 검색 (키워드/카테고리) | `KAKAO_REST_API_KEY` |
| Kakao Map JS SDK | 프론트 지도 표시 | `NEXT_PUBLIC_KAKAO_MAP_KEY` |

---

## 10. 코딩 규칙

- API 키/시크릿 전체 출력 절대 금지 (앞 4~5자만 마스킹)
- 프론트엔드 변경은 Docker 리빌드 필요
- Google OAuth 테스트 사용자 등록 필요
- 카카오 OPEN_MAP_AND_LOCAL 서비스 활성화 필요
- 커밋/푸시는 유저 확인 후에만
