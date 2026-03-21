# Maedeup API 명세서

> Base URL: `http://localhost:8000`
> Version: 0.1.0

---

## 목차

1. [인증 방식](#인증-방식)
2. [공통 응답 형식](#공통-응답-형식)
3. [REST API](#rest-api)
   - [헬스 체크](#헬스-체크)
   - [인증 (Auth)](#인증-auth)
   - [채팅 메시지 (Chat)](#채팅-메시지-chat)
   - [이벤트 (Events)](#이벤트-events)
4. [WebSocket API](#websocket-api)
   - [소셜 채팅](#소셜-채팅-wssocialroom_id)
   - [에이전트 채팅](#에이전트-채팅-wsagentroom_id)
5. [에러 코드](#에러-코드)

---

## 인증 방식

### JWT 토큰

Google OAuth 로그인 완료 후 발급되는 JWT 토큰을 사용합니다.

**토큰 발급 흐름**

```
클라이언트 → GET /auth/google
           ← 302 redirect → Google OAuth
Google     → GET /auth/google/callback?code=xxx
           ← 302 redirect → {FRONTEND_URL}/auth/callback?token={jwt}
```

**JWT Payload 구조**

```json
{
  "sub": "1",
  "email": "user@example.com",
  "name": "홍길동",
  "picture": "https://lh3.googleusercontent.com/...",
  "exp": 1234567890
}
```

- 알고리즘: `HS256`
- 만료: 발급 후 **7일**

### 엔드포인트별 인증 방식

| 엔드포인트 유형 | 전달 방법 | 예시 |
|---|---|---|
| HTTP API (보호된 라우트) | `Authorization: Bearer <token>` 헤더 | `Authorization: Bearer eyJ...` |
| WebSocket | URL 쿼리 파라미터 `?token=` | `ws://localhost:8000/ws/social/room-1?token=eyJ...` |

### 인증 불필요 엔드포인트

- `GET /health`
- `GET /auth/google`
- `GET /auth/google/callback`

---

## 공통 응답 형식

### 성공 응답

HTTP 상태 코드와 함께 JSON 본문을 반환합니다.

| 상태 코드 | 의미 |
|---|---|
| `200 OK` | 조회/처리 성공 |
| `201 Created` | 리소스 생성 성공 |
| `204 No Content` | 삭제 성공 (본문 없음) |
| `302 Found` | 리디렉트 |

### 에러 응답

```json
{
  "detail": "에러 메시지"
}
```

---

## REST API

---

### 헬스 체크

#### `GET /health`

서버, 데이터베이스, Redis 상태를 확인합니다.

**인증**: 불필요

**응답 예시** `200 OK`

```json
{
  "status": "ok",
  "services": {
    "database": "ok",
    "redis": "ok"
  }
}
```

**서비스 장애 시** `200 OK`

```json
{
  "status": "degraded",
  "services": {
    "database": "ok",
    "redis": "error: Connection refused"
  }
}
```

> `status` 필드 값: `"ok"` | `"degraded"`
> HTTP 상태 코드는 항상 200을 반환합니다.

---

### 인증 (Auth)

#### `GET /auth/google`

Google OAuth 인증 페이지로 리디렉트합니다.

**인증**: 불필요

**응답**: `302 Found` → Google 로그인 페이지

---

#### `GET /auth/google/callback`

Google OAuth 콜백. 인증 코드를 처리하고 JWT 토큰을 발급합니다.

**인증**: 불필요

**쿼리 파라미터**

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `code` | string | ✅ | Google에서 발급한 인가 코드 |

**처리 흐름**

1. Google에 인가 코드를 전송하여 액세스 토큰 교환
2. Google UserInfo API로 사용자 정보 조회
3. DB에 사용자가 없으면 신규 생성, 있으면 조회
4. JWT 발급 후 프론트엔드로 리디렉트

**응답**: `302 Found` → `http://localhost:3000/auth/callback?token={jwt}`

---

### 채팅 메시지 (Chat)

Base path: `/api/v1/chat`

#### 채팅 메시지 스키마

```json
{
  "id": 1,
  "pane_type": "social",
  "role": "user",
  "content": "안녕하세요",
  "sender": "홍길동",
  "session_id": null,
  "created_at": "2026-03-21T12:00:00"
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | integer | 메시지 고유 ID |
| `pane_type` | `"social"` \| `"agent"` | 채팅 패널 구분 |
| `role` | `"user"` \| `"assistant"` \| `"system"` | 발화자 역할 |
| `content` | string | 메시지 내용 |
| `sender` | string \| null | 발신자 이름 |
| `session_id` | string \| null | 세션 구분자 |
| `created_at` | datetime (ISO 8601) | 생성 시각 (UTC) |

---

#### `GET /api/v1/chat/messages`

메시지 목록을 조회합니다. 최신순으로 반환됩니다.

**쿼리 파라미터**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `pane_type` | `"social"` \| `"agent"` | ❌ | — | 패널 타입 필터 |
| `session_id` | string | ❌ | — | 세션 ID 필터 |
| `limit` | integer | ❌ | `50` | 최대 조회 수 (최대 200) |

**응답** `200 OK`

```json
[
  {
    "id": 42,
    "pane_type": "social",
    "role": "user",
    "content": "안녕하세요",
    "sender": "홍길동",
    "session_id": null,
    "created_at": "2026-03-21T12:00:00"
  }
]
```

**요청 예시**

```
GET /api/v1/chat/messages?pane_type=social&limit=20
```

---

#### `POST /api/v1/chat/messages`

메시지를 생성합니다.

**요청 본문** `application/json`

```json
{
  "pane_type": "social",
  "role": "user",
  "content": "안녕하세요",
  "sender": "홍길동",
  "session_id": null
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `pane_type` | `"social"` \| `"agent"` | ✅ | 채팅 패널 구분 |
| `role` | string | ✅ | `"user"` \| `"assistant"` \| `"system"` |
| `content` | string | ✅ | 메시지 내용 |
| `sender` | string | ❌ | 발신자 이름 |
| `session_id` | string | ❌ | 세션 구분자 |

**응답** `201 Created`

```json
{
  "id": 43,
  "pane_type": "social",
  "role": "user",
  "content": "안녕하세요",
  "sender": "홍길동",
  "session_id": null,
  "created_at": "2026-03-21T12:00:00"
}
```

---

### 이벤트 (Events)

Base path: `/api/v1/events`

#### 이벤트 스키마

```json
{
  "id": 1,
  "title": "매듭 정기모임",
  "description": "3월 정기모임입니다",
  "location_name": "서울시 마포구",
  "latitude": 37.5563,
  "longitude": 126.9236,
  "starts_at": "2026-03-21T14:00:00",
  "ends_at": "2026-03-21T17:00:00",
  "created_at": "2026-03-01T10:00:00",
  "updated_at": "2026-03-01T10:00:00"
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | integer | 이벤트 고유 ID |
| `title` | string | 제목 (최대 255자) |
| `description` | string \| null | 설명 |
| `location_name` | string \| null | 장소 이름 (최대 255자) |
| `latitude` | float \| null | 위도 |
| `longitude` | float \| null | 경도 |
| `starts_at` | datetime (ISO 8601) | 시작 일시 (UTC) |
| `ends_at` | datetime \| null | 종료 일시 (UTC) |
| `created_at` | datetime (ISO 8601) | 생성 시각 |
| `updated_at` | datetime (ISO 8601) | 수정 시각 |

---

#### `GET /api/v1/events/`

이벤트 목록을 시작 일시 오름차순으로 반환합니다.

**응답** `200 OK`

```json
[
  {
    "id": 1,
    "title": "매듭 정기모임",
    "description": "3월 정기모임입니다",
    "location_name": "서울시 마포구",
    "latitude": 37.5563,
    "longitude": 126.9236,
    "starts_at": "2026-03-21T14:00:00",
    "ends_at": "2026-03-21T17:00:00",
    "created_at": "2026-03-01T10:00:00",
    "updated_at": "2026-03-01T10:00:00"
  }
]
```

---

#### `GET /api/v1/events/{event_id}`

특정 이벤트를 조회합니다.

**경로 파라미터**

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `event_id` | integer | 이벤트 ID |

**응답** `200 OK` — 이벤트 객체

**에러**

| 상태 코드 | 조건 |
|---|---|
| `404 Not Found` | 해당 ID의 이벤트가 없음 |

```json
{ "detail": "Event not found" }
```

---

#### `POST /api/v1/events/`

이벤트를 생성합니다.

**요청 본문** `application/json`

```json
{
  "title": "매듭 정기모임",
  "description": "3월 정기모임입니다",
  "location_name": "서울시 마포구",
  "latitude": 37.5563,
  "longitude": 126.9236,
  "starts_at": "2026-03-21T14:00:00",
  "ends_at": "2026-03-21T17:00:00"
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `title` | string | ✅ | 제목 |
| `description` | string | ❌ | 설명 |
| `location_name` | string | ❌ | 장소 이름 |
| `latitude` | float | ❌ | 위도 |
| `longitude` | float | ❌ | 경도 |
| `starts_at` | datetime | ✅ | 시작 일시 |
| `ends_at` | datetime | ❌ | 종료 일시 |

**응답** `201 Created` — 생성된 이벤트 객체

---

#### `DELETE /api/v1/events/{event_id}`

이벤트를 삭제합니다.

**경로 파라미터**

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `event_id` | integer | 이벤트 ID |

**응답** `204 No Content`

**에러**

| 상태 코드 | 조건 |
|---|---|
| `404 Not Found` | 해당 ID의 이벤트가 없음 |

---

## WebSocket API

WebSocket 연결 시 반드시 `?token=` 쿼리 파라미터로 JWT 토큰을 전달해야 합니다.

**연결 흐름**

```
1. WebSocket 연결 요청 (Upgrade: websocket)
2. 서버가 연결 수락 (accept)
3. 서버가 토큰 검증
   - 토큰 없음 또는 유효하지 않음 → close(1008) 후 종료
   - 토큰 유효 → 메시지 송수신 시작
```

**내부 구조**: Redis Pub/Sub를 사용하여 같은 `room_id`의 모든 연결에 메시지를 브로드캐스트합니다.

---

### 소셜 채팅: `ws/social/{room_id}`

**연결 URL**

```
ws://localhost:8000/ws/social/{room_id}?token={jwt}
```

**경로 파라미터**

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `room_id` | string | 채팅방 식별자 (예: `"room-1"`) |

**쿼리 파라미터**

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `token` | string | ✅ | JWT 액세스 토큰 |

#### 클라이언트 → 서버 (송신)

```json
{
  "role": "user",
  "content": "안녕하세요",
  "sender": "홍길동"
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `role` | string | ❌ | 기본값 `"user"` |
| `content` | string | ✅ | 메시지 내용 |
| `sender` | string | ❌ | 발신자 이름 |

#### 서버 → 클라이언트 (수신)

같은 방의 모든 연결에 브로드캐스트됩니다. DB에 저장된 메시지를 그대로 반환합니다.

```json
{
  "id": 42,
  "pane_type": "social",
  "role": "user",
  "content": "안녕하세요",
  "sender": "홍길동",
  "created_at": "2026-03-21T12:00:00.000000"
}
```

**Redis 채널**: `social:{room_id}`

---

### 에이전트 채팅: `ws/agent/{room_id}`

**연결 URL**

```
ws://localhost:8000/ws/agent/{room_id}?token={jwt}
```

**경로 파라미터**

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `room_id` | string | 채팅방 식별자 (예: `"room-1"`) |

**쿼리 파라미터**

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `token` | string | ✅ | JWT 액세스 토큰 |

#### 클라이언트 → 서버 (송신)

소셜 채팅과 동일한 형식입니다.

```json
{
  "role": "user",
  "content": "일정 알려줘",
  "sender": "홍길동"
}
```

#### 서버 → 클라이언트 (수신)

```json
{
  "id": 43,
  "pane_type": "agent",
  "role": "user",
  "content": "일정 알려줘",
  "sender": "홍길동",
  "created_at": "2026-03-21T12:00:00.000000"
}
```

**소셜과의 차이점**: 메시지를 Redis 큐(`agent_queue:{room_id}`)에도 추가하여 별도 에이전트 워커가 처리할 수 있습니다.

- **Redis 채널**: `agent:{room_id}` (Pub/Sub 브로드캐스트)
- **Redis 큐**: `agent_queue:{room_id}` (RPUSH, 에이전트 처리용)

---

## 에러 코드

### HTTP 에러

| 상태 코드 | 발생 상황 | 응답 본문 예시 |
|---|---|---|
| `401 Unauthorized` | JWT 토큰 없음 또는 유효하지 않음 | `{"detail": "Invalid or expired token"}` |
| `403 Forbidden` | 접근 권한 없음 | `{"detail": "Not authenticated"}` |
| `404 Not Found` | 리소스 없음 | `{"detail": "Event not found"}` |
| `422 Unprocessable Entity` | 요청 파라미터/본문 형식 오류 | `{"detail": [{"loc": [...], "msg": "..."}]}` |

### WebSocket Close Code

| 코드 | 이름 | 발생 상황 |
|---|---|---|
| `1000` | Normal Closure | 정상 종료 |
| `1001` | Going Away | 클라이언트 또는 서버 종료 |
| `1008` | Policy Violation | 토큰 없음 또는 토큰 검증 실패 |

**클라이언트 처리 가이드**

```
onclose(event):
  if event.code === 1008:
    localStorage.removeItem("auth_token")
    redirect("/")  // 로그인 페이지로 이동
```

### 422 에러 상세 형식

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "title"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

---

## 부록: 엔드포인트 목록 요약

| 메서드 | URL | 인증 | 설명 |
|---|---|---|---|
| `GET` | `/health` | ❌ | 서버 상태 확인 |
| `GET` | `/auth/google` | ❌ | Google OAuth 시작 |
| `GET` | `/auth/google/callback` | ❌ | Google OAuth 콜백 |
| `GET` | `/api/v1/chat/messages` | ❌ | 채팅 메시지 목록 조회 |
| `POST` | `/api/v1/chat/messages` | ❌ | 채팅 메시지 생성 |
| `GET` | `/api/v1/events/` | ❌ | 이벤트 목록 조회 |
| `GET` | `/api/v1/events/{id}` | ❌ | 이벤트 단건 조회 |
| `POST` | `/api/v1/events/` | ❌ | 이벤트 생성 |
| `DELETE` | `/api/v1/events/{id}` | ❌ | 이벤트 삭제 |
| `WS` | `/ws/social/{room_id}` | ✅ `?token=` | 소셜 채팅 WebSocket |
| `WS` | `/ws/agent/{room_id}` | ✅ `?token=` | 에이전트 채팅 WebSocket |

> 현재 REST API 엔드포인트에는 인증 미들웨어가 적용되어 있지 않습니다.
> 보호가 필요한 라우트에는 `get_current_user` 의존성을 추가하세요.
