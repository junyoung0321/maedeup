# 코드 감사: API: meetings.py(확정·장소 patch·캘린더 sync·취소)·finalization route

> 영역키 `route-meetings` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/api/routes/meetings.py`
- `backend/app/api/routes/finalization.py`
- `backend/app/services/scheduling_round.py`
- `backend/app/services/google_calendar.py`
- `backend/app/models/meeting.py`
- `backend/app/models/room.py`
- `backend/app/schemas/meetings.py`
- `backend/app/services/pipeline/nodes/vote_card.py`

## 감사 노트
검토 범위: meetings.py 전체(confirm/vote/place/cancel/refresh + 조회 GET들), finalization.py 전체, 의존 서비스 scheduling_round.py·google_calendar.py·vote_card 노드·관련 모델. 

확인한 핵심 불변식(정상 동작):
- confirm_meeting: room.created_by host-only + RoomMember 검증(459-468) OK, fresh-INSERT 경로 Redis NX confirm_lock(473-483)으로 동시 confirm 직렬화 OK, lock release 토큰 비교 안전(648-656), proposal 경로 eligible 재조회 후 host_confirm(492-516) OK, 모든 Redis post-commit bookkeeping 이 DB commit 을 되돌리지 않음(try/except warning) OK, naive UTC 변환(519-520) 일관.
- vote_meeting: 확정/취소 상태가드(684), option_index 범위검사(688), stale 멤버 votes 교차검증(699-711)·total_voters 동일기준 산정(736-742)·동점 가드(724-732) 일관. Redis publish 실패가 투표 commit 을 막지 않음.
- finalization.py: vote/get 모두 _verify_room_membership(143/189)로 멤버십 검증, record_vote 가 Redis 락 안에서 원자적, majority_reached_for eligible<2 자동확정 차단(scheduling_round.py:138) OK.
- google_calendar: sync/delete 모두 best-effort, 게스트·미동의·미연동 멤버 스킵(_user_can_receive_calendar_event 142-151), DISABLE_CALENDAR_SYNC/AUTO_CALENDAR_PUSH 가드 OK.

주요 결함은 cancel 인가 모델 불일치(finding-1/5, P1/P2) — confirm·place 는 free-use audit 에서 room.created_by 로 하드닝됐으나 cancel 만 meeting.created_by(파이프라인 임의 first_member, ORDER BY 없는 limit(1), 게스트 가능) 기준이라 docstring 'Host-only' 와 실제 동작이 어긋나고 권한 우회/방장 차단 양방향 가능.

Codex 수정 중 5버그와의 겹침: 모든 finding overlaps_codex=false. 단 confirm_meeting 의 meeting_confirmed 발행이 social: 채널이고 schedule_finalized 미발행 여부는 Codex 버그 #1 영역이라 의도적으로 분석 회피함(재보고 안 함).

추정(미검증): vote_card 노드 first_member 의 실제 DB 정렬은 환경 의존 — Postgres 는 보통 물리 순서지만 보장 없음. 'host 가 항상 first_member 가 아님'은 룸 생성/가입 순서·게스트 합류 시나리오에서 깨질 수 있어 finding-1 의 재현 빈도는 멤버 구성에 의존(자유체험존 게스트 다수 환경에서 상승). 더 봐야 할 부분: 룸 생성 시 owner RoomMember row 가 항상 가장 먼저/낮은 PK 로 insert 되는지(rooms.py 가입 로직) 확인 시 finding-1 빈도 정밀화 가능. PM 후속 제안: rooms.py 담당에게 RoomMember insert 순서·role='owner' 세팅 시점 교차확인 위임 권장.

## 발견 (활성)

### [P2] route-meetings-1 — cancel_meeting authorizes by meeting.created_by (arbitrary pipeline member/guest), not room owner — inconsistent with confirm/place 권한 모델
`security/authorization` · conf 8/10 · ⤵ 강등됨(원래 P1)

- **위치**: `backend/app/api/routes/meetings.py:1149, backend/app/services/pipeline/nodes/vote_card.py:147-173, backend/app/services/pipeline/nodes/vote_card.py:336-363`
- **메커니즘**: 1) LangGraph vote_card 노드가 pending MeetingSchedule을 만들 때 created_by = first_member.user_id 로 채운다. first_member 는 `select(RoomMember).where(room_id==).limit(1)` 즉 ORDER BY 없는 임의 1행(보통 가입순/PK순이지 방장 보장 X, 게스트일 수도 있음). 2) confirm_meeting 의 meeting_id 승격 경로(meetings.py:522-543)는 status/title/scheduled_at 등만 갱신하고 created_by 는 그대로 둠 → 확정 후에도 created_by 는 그 임의 멤버. 3) cancel_meeting(meetings.py:1149)은 `meeting.created_by != current_user.sub` 로만 인가. docstring(1137)은 'Host-only'라 명시하나 실제로는 '모임 생성자(임의 멤버) only'. 4) confirm_meeting(467)·patch_meeting_place(988)는 free-use audit round3에서 명시적으로 room.created_by 로 하드닝됐는데 cancel 만 누락됨.
- **근거**: meetings.py:1149 `if meeting.created_by != int(current_user.sub)`; vote_card.py:147 `select(RoomMember).where(RoomMember.room_id == room_pk).limit(1)` (ORDER BY 없음); vote_card.py:173/363 `created_by=first_member.user_id`; 대조: meetings.py:467 `if room.created_by != int(current_user.sub): host_only`, meetings.py:988 동일. confirm 승격 분기(537-543)에 created_by 재할당 없음.
- **영향**: (a) 실제 방장이 자신이 만들지 않은(파이프라인 생성) 확정 모임을 취소 못 함 — 403. (b) 방장이 아닌 일반 멤버/게스트가 우연히 first_member 이면 확정 모임을 취소하고 전원 Google Calendar 이벤트 삭제 fan-out(delete_events_for_meeting_members)을 발동 가능 → 권한 없는 멤버가 전체 일정 파기 + 타인 캘린더 이벤트 삭제. 전시 자유체험존에서 게스트 다수 환경이면 재현 여지. happy path(방장이 직접 fresh confirm)는 created_by=호스트라 무증상이라 가려짐.
- **제안 수정**: cancel_meeting 인가를 confirm/place 와 동일하게 `Room.created_by` 기준으로 변경(meeting.room_id 로 Room 조회 후 room.created_by 비교), 또는 vote_card 노드에서 created_by 를 room.created_by 로 채우도록 통일. 둘 다 적용해 방어 권장.
- **검증 판단**: 주장의 코드 사실관계는 모두 정확히 확인됨. cancel_meeting(meetings.py:1149)은 meeting.created_by 단일 비교만 인가하며 RoomMember 멤버십 체크조차 없음(confirm/place는 membership+host 이중 체크). 대조: confirm_meeting(meetings.py:467)·patch_meeting_place(meetings.py:988)는 room.created_by 기준으로 free-use audit round3에서 하드닝됨(주석 #07/#24 확인), cancel만 누락. confirm의 meeting_id 승격 분기(meetings.py:537-543)는 created_by 재할당 없이 status/scheduled_at/end_at/title/vote_options/updated_at만 갱신 — 확인됨, 즉 pending→confirmed 후에도 파이프라인이 채운 created_by 유지. vote_card.py 두 경로 모두(173, 363) created_by=first_member.user_id이고 first_member는 ORDER BY 없는 select(RoomMember).where(room_id==).limit(1) — 확인됨. delete_events_for_meeting_members(google_calendar.py:259-281)는 google_event_ids의 전 멤버 캘린더 이벤트를 각자 캘린더에서 fan-out 삭제 — impact 확인됨. 막는 가드 없음. 단 P1→P2 다운그레이드: (1) 가장 신뢰성 높은 impact는 (a) 방장이 파이프라인 생성 confirmed 모임을 취소 못 함(403 lock-out)으로, 이는 권한상승이라기보다 가용성/권한모델 불일치 결함이다. (2) impact (b)의 권한상승(비방장 게스트가 전원 캘린더 삭제 발동)은 rooms.py:125에서 owner(방장)가 항상 첫 RoomMember로 insert되고 PG가 ORDER BY 없는 limit(1)을 통상 PK/insert 순으로 반환하는 경향상 first_member≈owner가 되어 실제 재현 조건이 좁다 — "다수 게스트 환경 재현 여지"는 owner row 삭제/재가입·PG 플랜 변화 같은 비happy-path 조건이 필요해 과장됨. 결함 실재는 confirmed이나 권한모델 일관화 누락(주로 기능 lock-out, 부수적으로 좁은 권한상승)이라 P2가 적절.

### [P2] route-meetings-2 — patch_meeting_place: Kakao search_keyword 결과가 사용자가 명시한 body.name 을 무조건 덮어씀
`correctness` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/meetings.py:991, backend/app/api/routes/meetings.py:1011-1020`
- **메커니즘**: 991에서 location_name 을 body.name(있으면) 또는 place 로 세팅. 이후 1011 가드 `if not location_address or not kakao_place_id or not kakao_place_url:` 는 address/id/url 중 하나라도 비면 진입한다. 사용자가 name 은 줬지만 address/place_id/url 은 안 준 흔한 케이스에서 진입 → 1015 `meeting.location_name = str(first.get('place_name') ...)` 로 Kakao 첫 결과 이름이 사용자가 지정한 이름을 덮어씀.
- **근거**: meetings.py:991 `meeting.location_name = body.name.strip() if body.name and body.name.strip() else place`; meetings.py:1011 가드 조건; meetings.py:1015 `meeting.location_name = str(first.get("place_name") or meeting.location_name or place)`.
- **영향**: 프론트가 사용자/카드 선택 장소명(body.name)을 넘겨도 Kakao 검색 best-match 이름으로 치환됨 → 확정 카드·캘린더 location 에 의도와 다른 상호명 표시 가능. 검색어 place 와 표시명 name 이 다른 경우(예: name='우리 동아리방', place='천안 신부동 카페')에 오표기.
- **제안 수정**: 1015 라인을 사용자 명시 name 우선으로: `meeting.location_name` 가 body.name 에서 온 경우 덮어쓰지 않도록 별도 플래그로 보존하거나, 가드 진입 조건을 'address 만 없을 때'로 좁혀 메타데이터(좌표/주소)만 보강하고 name 은 유지.

### [P2] route-meetings-3 — refresh_recommendations: idempotency 캐시가 pipeline 이후에만 SET → 동시 동일 요청이 락 없이 중복 run_pipeline + 중복 broadcast
`race-condition` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/meetings.py:1357-1424, backend/app/api/routes/meetings.py:1481-1492`
- **메커니즘**: idempotency 는 1) GET idem_key(1358) → 미스면 2) 무거운 run_pipeline(1419) → 3) 끝나고 SET idem_key(1482) 순. GET 과 SET 사이에 락이 없어, 같은 viewer 가 동일 (meeting,scope,source) 로 빠르게 2회(또는 더블탭) 호출하면 둘 다 GET 미스 → 둘 다 run_pipeline 실행 → 둘 다 vote/place 카드 + narrator 를 agent:{room} 으로 broadcast. daily INCR(1377)도 2회 소진.
- **근거**: meetings.py:1358 GET, 1419 run_pipeline, 1482 SET ex=300. 이 구간에 _acquire_lock/NX 가드 없음(confirm_meeting 의 confirm_lock_key NX 패턴과 대조 — meetings.py:473-483).
- **영향**: 방 전체에 중복 추천 카드/내레이터 2건이 거의 동시에 뜸(혼선). LLM 비용 2배. 동점/소실 수준은 아니나 멀티유저 토글 시연 중 더블 broadcast 가능. 빈도는 사용자 더블클릭/네트워크 재시도에 의존.
- **제안 수정**: INCR 이전(또는 GET 직후)에 idem_key 에 'in-progress' sentinel 을 NX SET(짧은 TTL)으로 선점 → 점유 실패 시 짧게 폴링하거나 200 cached-pending 반환. 또는 confirm_meeting 처럼 room/meeting 단위 NX 락으로 직렬화.

### [P2] route-meetings-5 — confirm_meeting meeting_id 승격 경로: 다른 user 가 만든 pending 을 host 가 확정해도 created_by 보존 → 이후 cancel 권한이 host 에게서 분리됨 (finding-1 연쇄)
`data-integrity` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/meetings.py:522-543`
- **메커니즘**: 승격 분기는 meeting.status/scheduled_at/end_at/title/vote_options/updated_at 만 갱신하고 created_by 는 건드리지 않음(537-543). 따라서 '누가 확정했는가(host)'와 '레코드상 created_by(임의 first_member)'가 영구히 어긋난다. confirm/place 는 room.created_by 로 인가하므로 동작하지만, cancel(finding-1)·_calendar_response_fields 의 self 판정·향후 created_by 기반 로직이 일관성을 잃음.
- **근거**: meetings.py:537-543 갱신 필드 목록에 created_by 없음. fresh INSERT 분기(545-555)는 created_by=current_user.sub 로 올바름 — 두 경로가 created_by 의미가 달라짐.
- **영향**: 확정 모임의 created_by 가 확정자(host)와 불일치 → finding-1 의 cancel 인가 결함이 happy-path 확정 모임에서도 그대로 발현. 데이터 의미 혼란(누가 주인인지 불명확).
- **제안 수정**: 승격 시 `meeting.created_by = int(current_user.sub)` 도 함께 세팅(또는 finding-1 처럼 cancel 을 room.created_by 로 전환해 created_by 의존 제거).

### [P3] route-meetings-4 — place patch 후 personal_data extraction 을 참조 미보유 create_task 로 띄움 — 완료 전 GC 가능 + 미대기 예외
`resource-leak` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/meetings.py:1119, backend/app/api/routes/meetings.py:46-62`
- **메커니즘**: `_asyncio.create_task(_spawn_personal_data_extraction(...))` 의 반환 Task 를 어디에도 저장하지 않음. CPython 은 강참조가 없는 Task 를 실행 중에도 GC 할 수 있다(asyncio 문서 명시 경고). 또 fire-and-forget 이라 예외는 내부 try/except 로만 삼켜지고(54-62) 외부에서 await 안 됨.
- **근거**: meetings.py:1119 반환값 미할당. 내부 함수는 별도 AsyncSessionLocal 세션을 열어 memory_extraction 호출(55-60).
- **영향**: 드물게 이벤트 루프 부하 시 personal_data 학습(ACT6 ✨)이 silent 하게 시작도 안 되거나 중도 취소될 수 있음 → 학습 임팩트 누락. 데이터 손상은 아님(별도 세션). 시연 안정성에 미미한 비결정성.
- **제안 수정**: 모듈 레벨 set 에 task 참조 보관(`_bg_tasks.add(t); t.add_done_callback(_bg_tasks.discard)`) 또는 BackgroundTasks(FastAPI) 사용으로 생명주기 보장.

### [P3] route-meetings-6 — patch_meeting_place: search_address 폴백이 새 RuntimeError 를 광역 except 가 삼켜 외부 sync 실패를 사용자에게 알리지 않음
`edge-case/silent-fail` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/meetings.py:1022-1024, backend/app/api/routes/meetings.py:1053-1057`
- **메커니즘**: search_keyword 도 search_address 도 결과가 없으면 1024 `raise RuntimeError(...)` 가 발생하지만 이 raise 는 1002~1057 의 광역 `try/except Exception:`(1053) 안에 있어 곧바로 잡혀 warning 로그만 남기고 진행. 결과적으로 location_address/place_id/url 이 비거나 부정확한 채로 응답이 200 으로 반환되고, calendar_registered=False 만 신호.
- **근거**: meetings.py:1024 raise; 1053 `except Exception:` 가 try 블록(1002 시작) 전체를 덮어 RuntimeError 포함 모든 예외를 흡수.
- **영향**: 존재하지 않는/오타 장소를 patch 하면 사용자는 성공처럼 보이는 200 응답을 받지만 주소·카카오 메타가 비어 캘린더 location 이 부실. 에러 가시성 없음. 데모에서는 정상 장소만 써서 무증상.
- **제안 수정**: 검색 0건은 사용자 입력 오류이므로 400/404 로 분기(광역 except 밖에서 검증) 하거나, 응답에 place_resolved=False 플래그를 추가해 프론트가 재입력 유도.
