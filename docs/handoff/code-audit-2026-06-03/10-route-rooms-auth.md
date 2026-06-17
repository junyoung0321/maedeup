# 코드 감사: API: rooms.py(멤버십·leave·host 이양·guest)·auth·chat share·intents 등

> 영역키 `route-rooms-auth` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/api/routes/rooms.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/chat.py`
- `backend/app/api/routes/intents.py`
- `backend/app/api/routes/users.py`
- `backend/app/api/routes/notifications.py`
- `backend/app/api/routes/assistant.py`
- `backend/app/api/routes/events.py`
- `backend/app/models/chat.py`
- `backend/app/models/event.py`
- `backend/app/core/security.py`
- `backend/app/services/scheduling_round.py`
- `backend/scripts/qa_privacy_boundary.py`

## 감사 노트
담당 영역(rooms/auth/chat/intents/users/notifications/assistant/events) 8파일 + 보조 모델/security/scheduling_round를 직접 정독했다.

가장 중대한 것은 chat.py의 IDOR/프라이버시 2건(chat-1, chat-2): GET /chat/messages가 room_id 없이 호출되면 멤버십·방 필터가 모두 빠져 (a) 전 방 social/shared 메시지, (b) 타 유저 personal_assistant(홈 비서) 사적 대화까지 한 인증 유저가 긁어올 수 있다. qa_privacy_boundary.py는 항상 room_id를 명시해 호출하므로 이 사각이 테스트에서 가려져 있다(scripts/qa_privacy_boundary.py:180,191,238 모두 room_id 지정). 프론트도 항상 room_id를 붙여(useAgentWebSocket.ts:388, useSocialWebSocket.ts:392) happy path는 영향 없지만 인증 토큰만 있으면 직접 공격 가능.

chat-3(create_message 위조)은 프론트가 WS 경로를 주로 쓰므로 실사용 노출은 낮으나, 인증된 임의 클라이언트가 user_id/sender/role을 임의 지정해 타인·AI 사칭 메시지를 영속화할 수 있는 신뢰 경계 결함.

확인한 핵심 불변식(정상):
- auth.py OAuth state는 secrets.compare_digest로 상수시간 비교(auth.py:63), refresh_token은 신규 발급 시에만 갱신(line 123). 결함 없음.
- share_message는 user_id를 서버 강제 + pg_advisory_xact_lock + shared_from_id 멱등 검사로 동시 공유를 직렬화(chat.py:155-172). 견고함.
- notifications.py mark_read/mark_all_read·list는 모두 user_id 스코프로 IDOR 없음(notifications.py:91 소유자 검사). datetime은 naive UTC 일관.
- users.py respond_to_friend_request는 addressee만 처리(users.py:431), 이미 처리된 요청은 409(line 433). pending 검사 일관.
- assistant.py는 프롬프트 인젝션 완화(<user_input> 델리미터 + 시스템 규칙7, assistant.py:268,303-307)와 user.id 스코프 컨텍스트로 사용자 경계 유지. _build_user_context의 calendar_active 토큰 동반 체크(line 101-105) 정확.
- schedule_confirm host 검사(rooms.py:542) + snapshot_hash stale 방어(line 549-551) + manual zero-slot 거부(line 586-594) 로직 정합. (schedule-confirm meeting_confirmed 미발행 이슈는 Codex 담당 #1 영역이라 제외.)

추정/미확인(추가 검토 제안):
- rooms-4: _publish_social_message(app/api/ws/social.py)가 redis=None을 안전 처리하는지 미확인 → ws-social 담당에게 위임 권장.
- chat-1/chat-2의 실제 악용 가능성 확정엔 personal_assistant visibility default가 'shared'로 저장되는지 DB 레벨 1건 확인이 더 깔끔(코드상 server_default='shared'로 강함, confidence 8).

PM 후속 제안: chat.py list_messages 프라이버시/멤버십 재설계는 리스크 담당+백엔드 수정 담당에 위임. ws/social.py None-redis 처리와 all_members_selected 소비락(Codex #2)은 동시성 담당으로 묶어 검토 권장.

## 발견 (활성)

### [P1] chat-1 — GET /chat/messages: room_id 미지정 시 멤버십 검사 우회 → 전 방 메시지 IDOR
`security/IDOR` · conf 8/10 · ✅ 검증됨

- **위치**: `backend/app/api/routes/chat.py:58-92`
- **메커니즘**: 1) list_messages는 room_id가 주어졌을 때만(line 60) RoomMember 멤버십을 검사한다. 2) 클라이언트가 room_id를 생략하고 GET /chat/messages?pane_type=social(또는 pane_type 생략) 호출. 3) line 74의 `if room_id is not None` 가드 때문에 room 필터 where절이 추가되지 않음 → 쿼리가 전체 rooms의 메시지를 대상으로 함. 4) 프라이버시 필터(line 80-90)는 pane_type==agent/None 일 때만 적용되고, 그것조차 'agent가 아니거나 / shared / 본인 private'을 통과시킴. 5) 결과: 인증된 아무 유저나 자신이 속하지 않은 방의 social 메시지 전체 + 모든 방의 shared agent 메시지를 limit(최대 200)까지 열람 가능.
- **근거**: chat.py:60 `if room_id is not None:` 멤버십 검사를 room_id 존재 조건부로 둠. chat.py:74 `if room_id is not None: stmt = stmt.where(ChatMessage.room_id == room_id)` — room_id 없으면 방 필터 자체가 없음. 프라이버시 where(line 80-90)는 agent-private만 차단하고 social/shared는 무제한 통과.
- **영향**: 타 방 대화 내용(social pane 전체, shared agent 카드/메시지) 유출. 졸업전시 자유체험존처럼 다수가 동시에 방을 만드는 환경에서 한 유저가 전체 방 대화를 긁어올 수 있는 개인정보/프라이버시 노출.
- **제안 수정**: room_id가 None이면 (a) 호출 거부(400)하거나 (b) 현재 유저가 속한 room_id 집합으로 ChatMessage.room_id.in_(...)을 강제. 또는 room_id를 필수 파라미터로 승격. personal_assistant 메시지(room_id NULL)도 session_id/user 경계로 따로 보호 필요.
- **검증 판단**: 적대적 재검증 결과 주장의 모든 메커니즘 단계가 코드와 정확히 일치하며, 이를 막는 가드를 찾지 못했다.

[확인된 사실]
1. backend/app/api/routes/chat.py:60 — `if room_id is not None:`로 RoomMember 멤버십 검사를 room_id 존재 시에만 수행. room_id 생략 시 검사 스킵.
2. chat.py:74 — `if room_id is not None: stmt = stmt.where(ChatMessage.room_id == room_id)`. room_id 없으면 방 필터 자체가 없어 전체 rooms 대상 쿼리.
3. chat.py:80-90 — 프라이버시 where절은 `pane_type == agent or None`일 때만 적용. `?pane_type=social` 명시 호출 시 이 필터가 통째로 빠짐.
4. social 메시지는 모두 `visibility='shared'`로 저장됨(ws/social.py:595, ws/agent.py:1395 + 모델 기본값 chat.py model:38-39 server_default="shared"). 따라서 시나리오 B(pane_type도 생략)의 프라이버시 필터(`pane_type != agent` 통과)도 모든 방 social을 통과시킴.
5. 라우트는 get_current_user(chat.py:55)만 의존. main.py:75-95 미들웨어는 CORS+요청로깅뿐 → 추가 멤버십 강제 없음. 인증된 아무 유저나 호출 가능.

[반증 시도 — 모두 실패]
- 상위 가드/미들웨어: 없음(main.py 확인).
- repositories/messages.py의 MessageReader는 room_id를 필수 인자로 받아 안전하나(line 49,60), 이는 pipeline 전용 경로이고 HTTP 엔드포인트 list_messages는 raw select(chat.py:71)를 직접 써서 우회함. 오히려 messages.py:8 docstring("Raw select(ChatMessage) outside this module is banned")을 위반.
- 프론트가 항상 room_id를 보내더라도 IDOR은 서버측 강제 부재가 본질이므로 무관.

[주장보다 넓은 영향 — 추가 확인]
시나리오 B(`GET /chat/messages` pane_type·room_id 모두 생략, session_id 생략) 시 personal_assistant(비서) 메시지도 노출됨. assistant.py:336-372에서 room_id=None·visibility 미지정(기본 shared)으로 저장되고 session_id=personal_assistant:{user_id}(assistant.py:225)로만 user를 구분하는데, list_messages는 session_id를 강제하지 않으므로 타 유저의 사적 비서 대화 전체가 limit(최대 200)까지 유출됨. proposed_fix가 이 부분도 지적함.

severity: 익명 불가(인증 필요)이나 인증된 임의 유저가 단일 요청으로 전 시스템의 모든 방 social 대화 + shared agent 카드 + 타 유저 비서 사적 대화를 열람 가능. 졸업전시 자유체험존 다중 동시 사용 환경에서 구체적 노출 위험. P1 유지 타당.

### [P1] chat-2 — GET /chat/messages: pane_type 미지정 시 타 유저 personal_assistant 대화 노출
`security/privacy` · conf 8/10 · ✅ 검증됨

- **위치**: `backend/app/api/routes/chat.py:71-90`
- **메커니즘**: 1) pane_type=None + room_id=None 호출. 2) line 72 `if pane_type:` 거짓 → pane_type 필터 없음. 3) personal_assistant 메시지(assistant.py:337, room_id=NULL, user별 1:1 비서 대화)는 pane_type='personal_assistant'이고 visibility 기본 'shared'(chat.py 모델 default). 4) line 80-90 프라이버시 필터의 첫 OR절 `ChatMessage.pane_type != PaneType.agent`가 참 → personal_assistant 메시지가 그대로 통과. 5) 결과: 아무 인증 유저나 모든 유저의 홈 비서 대화(개인 personal data·모임·친구 컨텍스트가 섞인 사적 대화)를 열람 가능.
- **근거**: assistant.py:336-343,365-372 personal_assistant 메시지는 visibility를 명시하지 않음 → ChatMessage.visibility server_default='shared'(chat.py:38-46). list_messages 프라이버시 필터(chat.py:83) `pane_type != PaneType.agent`가 personal_assistant를 무조건 통과시킴.
- **영향**: 타 유저의 사적 1:1 비서 대화(개인 식이제한·선호지역·일정 등 민감정보 포함 가능) 유출.
- **제안 수정**: list_messages에서 pane_type==personal_assistant 또는 room_id IS NULL 메시지는 ChatMessage.user_id==현재유저 또는 session_id==_personal_session_id(user) 로 강제 제한. 더 안전하게는 list_messages를 room 컨텍스트 전용으로 한정하고 personal_assistant는 /assistant/history로만 접근.
- **검증 판단**: 적대적으로 코드를 재독하고 가드를 찾았으나 막는 코드 없음. 주장 mechanism 전부 코드와 일치.

1) 엔드포인트: GET /api/v1/chat/messages, 인증(get_current_user)만 요구 (chat.py:49-57, main.py:99). pane_type/room_id 모두 Optional default=None (chat.py:51-52).
2) room_id=None이면 멤버십 체크 자체를 건너뜀 — line 60 `if room_id is not None:` 가드라 None이면 통과 (chat.py:60-69). 무방비 확인.
3) pane_type=None이면 line 72 `if pane_type:` 거짓 → pane_type 필터 미적용 (chat.py:72-73).
4) 프라이버시 필터 line 80 `pane_type is None` 참 → 진입하나, OR 첫 절 line 83 `ChatMessage.pane_type != PaneType.agent`가 personal_assistant 행에 대해 'personal_assistant'!='agent' → True → OR 전체 만족 → 통과 (chat.py:80-90). 주석 line 78-79가 "agent pane 요청은 shared+본인 private만"으로 명시 → 필터가 agent 전용 설계이고 personal_assistant는 설계상 누락 확인.
5) personal_assistant 메시지는 assistant.py:336-343(user_msg), 365-372(assistant_msg)에서 visibility/user_id 미지정 저장 → 모델 server_default visibility='shared'(chat.py:38-46), user_id=None(chat.py:32-37 default). 소유자 식별은 session_id='personal_assistant:{user_id}'로만(assistant.py:219-225,335). 따라서 (C)절 user_id 매칭으로도 안 걸러지고 (A)절로 무조건 통과.

PaneType(str,Enum)(chat.py:9)이라 line 83의 .value 미사용도 SQL 바인드 시 'agent' 문자열로 처리돼 동작에 영향 없음.

결과: 임의 인증 유저가 GET /api/v1/chat/messages (pane_type/room_id/session_id 모두 생략) 호출 시 모든 유저의 personal_assistant 1:1 비서 대화가 응답에 포함(limit 최대 200, line 54). 비서 대화 content에는 식이제한·선호지역·일정·친구·AI memory 컨텍스트 기반 답변이 섞임(assistant.py:86-216 context builders) → 타인 개인정보 수평적 노출(IDOR).

반증 실패 근거: 프론트는 항상 room_id+pane_type 명시(useAgentWebSocket.ts:388, useSocialWebSocket.ts:392)하나 이는 클라이언트 관례일 뿐 서버 가드 아님 — 직접 HTTP 호출로 우회 가능. P1 유지 적절(인증 필요하나 수평적 권한상승+사적대화 유출). 미확인: 운영 DB의 personal_assistant 실제 데이터량(전시 자유체험존 특성상 제한적일 수 있음)이나 심각도 본질 불변.

### [P2] chat-3 — POST /chat/messages: 클라이언트가 user_id·sender·visibility·role을 임의 지정(메시지 위조)
`data-integrity/security` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/chat.py:95-117`
- **메커니즘**: 1) create_message는 room 멤버십만 검사(line 102-111)하고 ChatMessage.model_validate(payload)로 페이로드를 그대로 저장(line 113). 2) ChatMessageCreate(chat.py:62-72)는 user_id/sender/role/visibility/pane_type을 모두 클라이언트 입력으로 받음. 3) 인증 유저(현재 방 멤버)가 payload.user_id를 타 유저 id로, sender를 타인 이름으로, visibility를 shared로, role을 'assistant'로 설정해 POST. 4) 서버가 인증 sub로 override하지 않으므로 타인/AI를 사칭한 메시지가 DB에 영속화됨. 화자 귀속(speaker attribution)·isMe 판정이 user_id 기반이면 위조 가능.
- **근거**: chat.py:113 `msg = ChatMessage.model_validate(payload)` — user_id/sender/role/visibility를 인증 정보로 덮어쓰지 않음. share_message(chat.py:175-186)는 명시적으로 user_id=user_id로 강제하는 것과 대조적. 멤버십 검사는 payload.room_id 한정(chat.py:102).
- **영향**: 방 멤버가 다른 멤버 또는 AI(assistant role)를 사칭한 채팅/카드 메시지를 영속화 가능. 화자 귀속·shared 노출 경계 신뢰성 훼손. (프론트는 WS 경로를 주로 쓰므로 happy path 영향은 적지만 인증된 임의 클라이언트로 직접 공격 가능.)
- **제안 수정**: create_message에서 user_id=int(current_user.sub), sender=current_user.name로 서버측 강제, role/visibility/pane_type을 허용 화이트리스트로 검증. 이 엔드포인트가 내부/테스트 전용이면 라우터에서 제거하거나 권한 강화.

### [P2] rooms-1 — leave_room 호스트 이양 분기에서 떠나는 호스트의 캘린더 이벤트 정리 누락 → 고아 google_event_ids + 미삭제 GCal 이벤트
`data-integrity` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/rooms.py:656-756`
- **메커니즘**: 1) 호스트가 다른 멤버가 있는 방을 leave (is_host and other_members_count>0). 2) line 656 분기로 진입 → 소유권 이양만 수행하고 line 702 else의 '본인 캘린더 이벤트 정리' 블록(line 703-733)은 건너뜀. 3) 이후 line 736-755에서 떠나는 호스트의 RoomMember/MeetingPreference/MeetingParticipant는 삭제됨. 4) 그러나 confirmed MeetingSchedule.google_event_ids[str(host_id)]는 그대로 남고, 호스트의 실제 Google Calendar 이벤트도 삭제되지 않음. 5) 결과: (a) 멤버 아님에도 호스트의 캘린더 event id가 meeting에 잔존(고아 참조), (b) 떠난 호스트 달력에 모임 일정이 계속 남음.
- **근거**: rooms.py:702-733 캘린더 self-delete 블록이 else(일반멤버/단독호스트)에만 존재. rooms.py:656-701 호스트 이양 분기에는 calendar 정리 코드 없음. 이후 공통 정리(rooms.py:736-755)는 RoomMember/Participant/Preference만 삭제하고 meeting.google_event_ids는 손대지 않음.
- **영향**: 호스트가 멤버 둔 채 떠날 때 본인 달력에 모임이 잔존하고 meeting 레코드에 죽은 event id가 남음. 데모 happy path에선 호스트가 leave하지 않으므로(주석 명시) 미발현이지만 자유체험존 실사용 시 발생 가능.
- **제안 수정**: 호스트 이양 분기에서도 떠나는 user_id에 대한 confirmed 모임 캘린더 이벤트 삭제 + google_event_ids에서 str(user_id) 제거를 공통 처리로 빼서 두 경로 모두 적용.

### [P3] rooms-3 — schedule_confirm manual 검증의 ChosenTime 주석/범위 불일치(0~47 vs TIME_SLOT_MAX=26)
`correctness` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/rooms.py:501-506,559-564`
- **메커니즘**: ChosenTime 주석(rooms.py:504-505)은 slot index를 '30분 단위, 0~47'로 기술하나 실제 검증(rooms.py:561 `ct.end_idx >= sr.TIME_SLOT_MAX`)은 TIME_SLOT_MAX=26(scheduling_round.py:38, 09:00~22:00 26셀)을 사용. availability entry도 `e=min(TIME_SLOT_MAX-1,e)`=25로 클램프(scheduling_round.py:663). 검증 자체는 0..25로 일관되어 동작상 결함은 아니나, 주석이 가리키는 0~47 인덱스를 프론트가 신뢰해 30분×48 그리드를 보내면 26~47 슬롯이 모두 'out_of_range'로 거부됨.
- **근거**: rooms.py:504 `start_idx: int  # TimeBar slot index (30분 단위, 0~47)` 주석 vs rooms.py:561 TIME_SLOT_MAX(26) 비교. scheduling_round.py:38 `TIME_SLOT_MAX = 26`.
- **영향**: 동작 결함 없음(현재 프론트는 26슬롯 가정). 단 주석이 잘못되어 향후 프론트/타 작업자가 0~47 인덱스로 구현하면 manual 확정이 광범위하게 400 거부됨. 회귀 위험 표시.
- **제안 수정**: ChosenTime 주석을 실제 슬롯 도메인(0~25, TIME_SLOT_MAX 기준)으로 수정. 또는 상수를 단일 소스로 공유.

### [P3] rooms-2 — guest_join_room: 게스트 생성과 RoomMember 추가 사이 동시성 — 게스트 캡/중복 검사 TOCTOU
`race condition` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/rooms.py:207-268`
- **메커니즘**: 1) 같은 방에 동일 display_name으로 두 guest-join 요청이 거의 동시에 도착. 2) 둘 다 line 207-214 중복 검사에서 기존 게스트 없음을 확인(아직 commit 전). 3) 둘 다 line 240-247 캡 검사 통과. 4) 둘 다 새 User+RoomMember를 생성·commit → 동일 이름 게스트 2명, 또는 캡 경계에서 _GUEST_CAP+1명까지 초과 가능. 멤버십 유니크 제약이 없으면 member_count 부풀림으로 합의 차단(주석이 우려한 바로 그 시나리오)이 재현될 수 있음.
- **근거**: rooms.py:207 중복검사 SELECT와 rooms.py:268 commit 사이에 락 없음. 캡 검사(rooms.py:240-247)도 동일 트랜잭션 격리 밖. 인증 없는 엔드포인트라 자동화 동시 호출이 쉬움.
- **영향**: 드물지만 동시 게스트 join 시 중복/캡 초과로 member_count가 부풀어 _maybe_emit_proposal 합의가 막힐 수 있음. 인증 불요라 의도적 동시 요청으로 유발 가능.
- **제안 수정**: room_id 기준 pg_advisory_xact_lock으로 중복·캡 검사+삽입을 직렬화(share_message가 쓰는 패턴), 또는 (room_id, lower(name), is_guest) 부분 유니크 인덱스로 DB 차원 보장.

### [P3] users-1 — respond_to_friend_request reject가 row 삭제 → 거절 사실 소실 및 무한 재요청 가능
`edge-case/data-integrity` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/users.py:419-447`
- **메커니즘**: 1) addressee가 action='reject' 호출 → line 445 friendship row를 DELETE. 2) requester는 거절을 알 수 없고(알림 없음), 즉시 다시 send_friend_request 가능(line 331-340의 중복 검사가 row 부재로 통과). 3) requester가 자동/반복 요청을 보내면 addressee에게 FRIEND_REQUEST_RECEIVED 알림이 계속 생성됨(notify, line 350-360). 차단/거절 영속 상태가 없어 스팸 방지 불가.
- **근거**: users.py:444-447 reject 시 session.delete(friendship) — rejected 상태를 남기지 않음(주석 '재요청 가능하도록'은 의도지만 스팸 방지 부재). users.py:331-340 중복 검사는 기존 row 존재에만 의존.
- **영향**: 거절한 상대로부터 친구요청 알림을 무제한 받을 수 있음(알림 스팸). 데모엔 무해하나 자유체험존에서 악용 가능. 의도된 trade-off(주석)지만 rate-limit/차단 부재가 가정 붕괴 조건.
- **제안 수정**: rejected 상태를 일정 기간 보존하거나 거절 후 N분 재요청 쿨다운, 또는 차단 플래그 도입. 최소한 동일 (requester,addressee) 재요청 빈도 제한.

### [P3] events-1 — POST /events: 방 멤버 누구나 이벤트 생성(호스트 권한 검사 없음)
`security/authorization` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/events.py:66-83`
- **메커니즘**: create_event는 payload.room_id가 호출자의 소속 방 집합에 있는지만 검사(events.py:73-75)하고 host/owner 권한은 보지 않음. 따라서 게스트 포함 모든 방 멤버가 임의 title/시간/장소의 Event를 방에 생성 가능. delete_event도 동일하게 멤버 누구나 삭제 가능(events.py:95-98).
- **근거**: events.py:73 `room_ids = await _user_room_ids(...)` 후 line 74 멤버십만 확인, role 검사 없음. delete_event(events.py:95-98)도 멤버십만 확인.
- **영향**: 방 멤버(게스트 포함) 누구나 타인 생성 이벤트 삭제·임의 이벤트 추가 가능. Event가 UI 일정에 노출되면 멤버 간 신뢰 경계 약함. 데모 영향은 낮음.
- **제안 수정**: 이벤트 생성/삭제를 owner 또는 작성자(created_by 필드 추가)로 제한, 게스트 차단 여부 정책 확정.

### [P3] rooms-4 — guest_join_room: member_joined publish용 Redis 연결 생성 실패 시에도 _publish_social_message에 None 전달
`resource/edge-case` · conf 5/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/rooms.py:282-319`
- **메커니즘**: rooms.py:302-309에서 redis from_url이 예외나면 r=None으로 두고, line 311에서 _publish_social_message(r=None,...)을 호출. 이 wrapper가 None을 받아 처리하는지 미확인. 전체가 try/except로 감싸져 join 자체는 실패하지 않으므로(silent) 알림 누락만 발생. 같은 핸들러에서 T6 캐시 무효화(line 322-344)가 별도 Redis 연결을 또 열어 guest-join 1회에 Redis 연결을 최대 2~3개 생성/종료 — 누수는 아니나 비효율.
- **근거**: rooms.py:308-311 `except: r=None` 후 곧바로 _publish_social_message(r, ...) 호출. rooms.py:273-277/321-344에 free-slots 무효화가 invalidate_free_slots_cache + 직접 scan 2중으로 존재.
- **영향**: 기능 결함 가능성 낮음(알림은 best-effort). _publish_social_message가 None을 안전 처리하면 무해. join당 Redis 연결 다중 개설은 부하 시 비효율. 확인 필요 항목으로 표시.
- **제안 수정**: r is None일 때 publish 스킵 가드 추가. free-slots 무효화 경로 중복(invalidate_free_slots_cache vs 직접 scan) 통합.
