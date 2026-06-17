# 코드 감사: 모델·core: SQLModel 모델·security·config·rate_limit·log_filters

> 영역키 `models-core` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/core/security.py`
- `backend/app/core/config.py`
- `backend/app/core/rate_limit.py`
- `backend/app/core/log_filters.py`
- `backend/app/models/__init__.py`
- `backend/app/models/user.py`
- `backend/app/models/meeting.py`
- `backend/app/models/vote.py`
- `backend/app/models/room.py`
- `backend/app/models/chat.py`
- `backend/app/models/ai_memory.py`
- `backend/app/models/event.py`
- `backend/app/models/friendship.py`
- `backend/app/models/intent.py`
- `backend/app/models/meeting_preference.py`
- `backend/app/models/notification.py`
- `backend/app/main.py (startup wiring 확인용)`
- `backend/alembic/versions/d2e3f4a5b6c7_add_notifications_table.py`
- `backend/app/api/ws/agent.py (rate_limit/verify_token 호출부 확인용)`

## 감사 노트
검토 범위: 지정된 core 4파일 전체 + models 12파일 전체. main.py 시작부와 agent.py 호출부는 wiring 확인용으로만 참조.

확인한 핵심 불변식(결함 아님):
- verify_token(security.py:48)은 jose 기본 동작으로 exp/서명 검증 수행(options 우회 없음) → 만료 토큰 401 정상. WS(agent.py:765-786)와 HTTP 양쪽 모두 verify 후 RoomMember 멤버십 확인으로 IDOR 게이트가 일관됨.
- sub는 JWT에서 str로 들어오나 모든 라우트가 int(current_user.sub)로 변환 후 DB 비교(grep로 30+건 일관 확인) → str-vs-int 불일치 없음.
- 모든 datetime default가 datetime.now(timezone.utc).replace(tzinfo=None)로 naive UTC 통일(user/meeting/vote/room/chat/event/friendship/notification/ai_memory/intent/meeting_preference 전부) → naive vs aware 혼선 모델 레벨에선 없음. issue_jwt의 exp는 aware지만 jose가 처리하므로 무관.
- Enum 컬럼은 모두 sa.String(32) + server_default 문자열 패턴(CLAUDE.md 규약 준수), str-Enum 멤버가 값과 ==/바인딩 동치라 status 비교/대입 정상(meetings.py:254,537 등 확인). MeetingStatus/ParticipantStatus/VoteStatus/RoomStatus/FriendshipStatus/MemoryType/PaneType/Visibility 모두 (str, Enum).
- UniqueConstraint 적절: room_members(room,user), meeting_participants(meeting,user), friendships(requester,addressee), meeting_preferences(room,user). User.email unique. 게스트 synthetic email은 uuid4 hex[:12](48bit)로 충돌 위험 낮음(게스트 생성 race는 routes/rooms.py 영역 — PM이 routes 담당에 위임 권장).
- log_filters TokenMaskingFilter는 getMessage 후 record.msg 치환 + args=() 클리어로 안전, 정규식 [^\s&\"'\])]+ 는 JWT 문자(.-_ 영숫자) 모두 포함하고 구분자에서 정확히 멈춤. install_token_masking·validate_startup_settings 모두 main.py:43/48/50에서 실제 호출됨(초기 의심 철회).
- ai_memory.source_message_id는 ondelete=SET NULL로 orphan 방지 의도 명시(설계대로).

Codex 5버그와 겹침 없음(모두 false). 본 영역은 파이프라인/카드/슬롯 로직과 무관.

PM 후속 제안:
1) core-1/core-2/core-3은 전시 외부노출 리스크 영역 — 리스크/보안 담당에 severity 판정 위임 권장. 특히 core-3은 배포 직전 APP_ENV 점검 체크리스트 항목화 가치.
2) 게스트 생성 동시성(rooms.py:245-262 SELECT-then-INSERT, synthetic email unique)과 check_ws_llm_budget NX 소비락 관계는 routes/ws 담당 영역 — 별도 위임 권장.
3) Notification.payload 일관성(core-6)은 사소하나 모델 정합성 sweep 시 함께 정리.

## 발견 (활성)

### [P2] core-1 — HTTP rate limiter(check_rate_limit) 전혀 미사용 — 모든 REST 엔드포인트 무제한
`security/dos` · conf 9/10 · 미검증(P2/P3)

- **위치**: `backend/app/core/rate_limit.py:18-65`
- **메커니즘**: 1) rate_limit.py에 sliding-window HTTP 리미터 check_rate_limit가 구현돼 있음. 2) 그러나 전체 backend에서 이 함수를 import/Depends/middleware로 등록한 곳이 한 군데도 없음(grep 결과 정의부 외 참조 0). 3) main.py에 등록된 미들웨어는 CORS와 log_requests(SLOW 로깅)뿐. 4) 따라서 /api/v1/* REST 엔드포인트(auth, chat, meetings, places 등)는 IP/유저 단위 호출 제한이 전혀 없음. WS LLM 진입부만 check_ws_llm_budget로 보호됨.
- **근거**: grep 'check_rate_limit(' 전체 결과 = 정의(rate_limit.py:18) + docstring(78) 뿐, 호출 0건. main.py:75 add_middleware는 CORSMiddleware 하나, :84 log_requests는 로깅만. 반면 check_ws_llm_budget는 agent.py:1168에서 실제 호출됨.
- **영향**: 자유체험존 전시 환경에서 익명/게스트가 REST 엔드포인트(특히 Gemini/Kakao 호출을 트리거하는 places/recommendations, 게스트 생성 rooms)를 무제한 호출 가능 → 비용 폭증·DoS. 시연 happy-path는 영향 없으나 외부 노출 시 abuse 면.
- **제안 수정**: 비용/abuse 민감 라우터(places, recommendations, rooms 게스트 생성, auth)에 Depends(check_rate_limit) 부착하거나 ASGI 미들웨어로 글로벌 적용. 최소한 게스트 생성·LLM 트리거 경로만이라도 적용.

### [P2] core-3 — JWT_SECRET 기본값 검증이 dev 환경에서 우회됨 — 운영자 실수 시 공개 시크릿로 서명
`security` · conf 8/10 · 미검증(P2/P3)

- **위치**: `backend/app/core/config.py:14, 66-67, 83-84; docker-compose.yml:12`
- **메커니즘**: 1) JWT_SECRET 기본값 'change-me-in-production'(config.py:14). 2) validate_startup_settings는 APP_ENV가 {development,dev}가 아닐 때만 기본 시크릿을 거부(config.py:83-84). 3) docker-compose.yml:12는 APP_ENV 기본값을 development로 고정. 4) 즉 APP_ENV를 명시적으로 production으로 바꾸지 않으면(전시/배포에서 흔히 누락) 기본 공개 시크릿으로 HS256 서명해도 startup이 통과.
- **근거**: config.py:83-84 조건 `APP_ENV.lower() not in {development,dev} and JWT_SECRET == 'change-me-in-production'`. docker-compose.yml:12 `APP_ENV: ${APP_ENV:-development}`. 로컬 .env 확인 결과 APP_ENV=development 이면서 JWT_SECRET=maed***(커스텀)로 설정돼 현재 노출은 완화됨 — 단 가드가 아닌 운영자 수동 설정에만 의존.
- **영향**: 운영자가 .env에 커스텀 JWT_SECRET을 깜빡하고 APP_ENV=development로 외부 배포하면, 누구나 알려진 기본 시크릿으로 임의 유저(임의 sub)의 JWT를 위조 → 전 계정 인증 우회/세션 위조(IDOR 전면화). 현재 로컬 .env는 커스텀 시크릿이라 즉시 노출은 아님.
- **제안 수정**: JWT_SECRET=='change-me-in-production'이면 APP_ENV 무관하게 항상 startup 실패시키거나, 최소한 외부 바인딩(0.0.0.0) 시 강제. dev여도 기본 시크릿은 거부 권장.

### [P3] core-2 — check_rate_limit이 request.state.user_sub에 의존하나 어디서도 세팅 안 함 → 항상 IP 폴백
`correctness` · conf 8/10 · 미검증(P2/P3)

- **위치**: `backend/app/core/rate_limit.py:29-31`
- **메커니즘**: 1) check_rate_limit은 유저 식별을 getattr(request.state, 'user_sub', None)로 시도. 2) 그러나 전체 코드에서 request.state.user_sub를 set하는 곳이 전무(grep 'user_sub' = rate_limit.py:29 단 1건). 3) 인증은 get_current_user Depends로 처리돼 request.state에 sub를 안 넣음. 4) 결과적으로 user_id는 항상 IP(request.client.host)로 폴백.
- **근거**: grep 'user_sub|request.state' 결과 rate_limit.py:29 1건뿐. 인증 의존성 get_current_user(security.py:57)는 AuthUser 반환만, request.state 미수정.
- **영향**: (core-1로 인해 현재는 호출조차 안 되므로 잠재). 만약 리미터를 활성화해도 유저 단위가 아닌 IP 단위로만 동작 → NAT/공유 IP(전시장 와이파이) 뒤 다수 유저가 한 버킷을 공유해 정상 유저가 차단되거나, 동일 유저가 IP 바꾸면 우회. 키 prefix 'ratelimit:{path}:{ip}'로 의도(유저별)와 다른 단위.
- **제안 수정**: 인증 미들웨어/의존성에서 request.state.user_sub = payload['sub'] 세팅하거나, 리미터를 Depends로 쓸 때 current_user를 받아 키를 유저 기준으로 구성.

### [P3] core-4 — check_ws_llm_budget: INCR 직후 EXPIRE 미설정 시 키 영구 잔존 → 해당 room+user 영구 차단 가능
`data-integrity/resource` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/core/rate_limit.py:90-92`
- **메커니즘**: 1) count = INCR(key). 2) count==1일 때만 EXPIRE(window) 설정. 3) INCR과 EXPIRE 사이에 프로세스/연결 장애가 발생하면 키는 TTL 없이 영구 잔존. 4) 이후 같은 room+user의 INCR이 누적돼 limit(30) 초과 시 만료 없이 영구히 False 반환 → 해당 유저가 그 방에서 LLM 트리거 영구 차단.
- **근거**: rate_limit.py:90-92 `count = await redis_client.incr(key); if count == 1: await redis_client.expire(key, window)`. 두 명령이 원자적이지 않음(파이프라인/Lua 아님).
- **영향**: 정상 운영에선 거의 안 나지만, INCR 후 EXPIRE 전 예외 시(Redis 일시 단절·취소) 해당 (room,user) 버킷이 TTL 없이 남아 카운터가 영구 누적 → 드물게 특정 유저 LLM 응답 영구 무응답. fail-open 의도와 반대로 fail-closed로 굳을 수 있음.
- **제안 수정**: INCR+EXPIRE를 단일 파이프라인 또는 Lua로 원자화하고, count>1이어도 TTL이 없으면(-1) EXPIRE 재설정. 또는 SET key with EX + 별도 INCR.

### [P3] core-5 — get_current_user가 sub/email/name을 KeyError 없이 보장 못 함 → 비정상 토큰에 401 대신 500
`edge-case` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/core/security.py:63-65`
- **메커니즘**: 1) verify_token이 서명·만료만 검증하고 payload claim 존재는 보장 안 함. 2) get_current_user가 payload['sub'], payload['email'], payload['name']을 .get 없이 직접 인덱싱(63-65). 3) 유효 서명이지만 해당 claim이 없는 토큰(예: 토큰 스키마 변경/외부 발급)이 오면 KeyError → FastAPI가 500 반환(401 아님).
- **근거**: security.py:63-65 직접 인덱싱 vs 66-68 picture/calendar_consent/is_guest는 .get 사용. 우리가 발급하는 issue_jwt(24-42)는 항상 채우므로 정상 경로엔 영향 없음.
- **영향**: 낮음. 정상 발급 토큰은 모든 claim 포함. 토큰 포맷 변경/구버전 토큰/수작업 토큰 시 401이어야 할 것이 500으로 새어 디버깅·클라이언트 처리 혼란. 보안 노출은 없음.
- **제안 수정**: payload.get(...) + 누락 시 명시적 401 raise, 또는 verify_token에서 필수 claim 검증.

### [P3] core-6 — Notification.payload server_default가 sa.text 없이 bare '{}' — create_all 시 잘못된 DEFAULT (현재 무해)
`data-integrity` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/models/notification.py:18-21`
- **메커니즘**: 1) user.is_ai_filled·meeting.google_event_ids는 server_default=text("'{}'")로 작성(따옴표 포함 SQL 리터럴), 마이그레이션도 sa.text("'{}'")로 일치. 2) notification.py만 server_default="{}"(bare 문자열)로 작성 — SQLAlchemy는 이를 따옴표 없는 리터럴 DEFAULT {} 로 방출. 3) 다만 실제 DDL은 마이그레이션(d2e3f4a5b6c7:39, sa.text("'{}'") 정상)에서 나오고 init_db는 SELECT 1만(create_all 금지)이라 런타임 스키마는 정상.
- **근거**: notification.py:20 `server_default="{}"` vs user.py:33 `server_default=text("'{}'")` vs meeting.py:44 동일 text() 패턴. 마이그레이션 d2e3f4a5b6c7_...py:39는 sa.text("'{}'")로 올바름.
- **영향**: 현재 무해(런타임 스키마는 마이그레이션 기준). 그러나 누군가 create_all/메타데이터 기반 DDL을 쓰거나 모델 일관성 검사 시 notification만 DEFAULT 절이 달라져 postgres에서 구문 오류 위험. 코드 일관성/미래 리스크.
- **제안 수정**: notification.py:20을 server_default=sa.text("'{}'")로 통일(나머지 JSON 컬럼과 동일 패턴).
