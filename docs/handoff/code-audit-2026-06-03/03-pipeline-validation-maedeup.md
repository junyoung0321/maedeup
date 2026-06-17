# 코드 감사: 파이프라인: 검증·매듭카드·메모리·function_call

> 영역키 `pipeline-validation-maedeup` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/services/pipeline/nodes/validation.py`
- `backend/app/services/pipeline/nodes/maedeup.py`
- `backend/app/services/pipeline/nodes/memory.py`
- `backend/app/services/pipeline/nodes/function_call.py`
- `backend/app/services/pipeline/nodes/vote_card.py`
- `backend/app/services/pipeline/nodes/place.py`
- `backend/app/services/pipeline/graph.py`
- `backend/app/services/pipeline/helpers/dates.py`
- `backend/app/services/pipeline/helpers/slot_state.py`
- `backend/app/services/pipeline/helpers/slots.py`
- `backend/app/services/pipeline/state.py`
- `backend/app/services/personal_data_extractor.py`
- `backend/app/models/user.py`
- `backend/app/models/meeting.py`
- `backend/data/demo_extraction_canned.json`

## 감사 노트
검토 범위: 담당 4파일(validation/maedeup/memory/function_call)을 전수 정독하고, 의존 헬퍼(dates._parse_iso_datetime, slot_state._coerce_headcount, vote_card._ensure_pending_meeting_id/_card_payload_meeting_id, slots._find_free_slots/_filter_out_blocked/_filter_out_rejected), graph.py 라우터, state.py, personal_data_extractor, User/MeetingSchedule 모델, canned JSON까지 cross-check.

검증 후 '결함 아님'으로 판정해 보고에서 제외한 핵심 불변식:
1. validation.py datetime 비교는 naive/aware 일관: _parse_iso_datetime(dates.py:405-407)이 항상 aware UTC 반환, now=datetime.now(timezone.utc)도 aware. start_at<now / end_at<=start_at 비교 안전.
2. 과거 슬롯 필터(validation.py:71-89)는 errors에 추가하지 않고 조용히 제외(주석 명시 trade-off). 전부 과거면 valid_slots=[] → next-week expansion(validation.py:101-109 + function_call.py:87-102). expansion 플래그는 function_call.py:87에서 pop으로 즉시 소거 → 무한루프 가드 확인.
3. block/reject 날짜 필터의 UTC-date vs KST-date off-by-one 우려는 비발현: 슬롯은 WORK_HOUR 09~22 KST(constants.py:12-13)에서만 생성되고 09~21 KST = 00~12 UTC라 UTC date == KST date. start_at[:10](slots.py:350,364) 비교가 항상 동일 날짜. 즉 day-boundary 슬롯이 working-hour 밖이라 안전.
4. maedeup_card_creation의 _spawn_memory_extraction_async는 partial(time_only) 경로(maedeup.py:82-178, return at 178)와 full 경로(215)가 상호배타 → 단일 spawn(이중 호출 없음).
5. memory_extraction write는 단일 트랜잭션 + 부분실패 전체 rollback(memory.py:232-236), Redis publish는 commit 성공 후(memory.py:239) — 순서 정합. is_ai_filled는 dict 신규 할당 재대입(memory.py:228)이라 SQLAlchemy JSON change-detection 동작.
6. _filter_invalid_time_preference는 VALUE만 검사(quote 제외, Codex 2026-05-07 의도) — false-negative 방지 설계 확인.
7. _ensure_pending_meeting_id의 pending 재사용 가드(date 매칭 + 30분 fallback, vote_card.py:84-137)는 stale flow 차단 의도대로. scheduled_at 매칭 naive vs naive 일관.

미확인/추가 위임 제안:
- memory-1의 실제 재현은 Gemini가 str 카테고리에 list를 반환하는 빈도에 의존 → 운영 로그/실측 필요(QA 담당). AIMemory 모델의 unique 제약 유무는 models/ai_memory.py 미정독(별도 모델 담당 확인 권장).
- memory-2는 Codex #2(NX 소비락) 수정 범위와 직접 연동 → Codex 수정 후 잔여 중복 가능성 재검증 필요.
- _load_busy_by_user_for_state / get_free_slots 내부의 busy period tz 처리는 slots.py 일부만 확인했고 GCal busy 변환부(별도 helper)는 미정독 — 슬롯 담당에 위임 권장.

## 발견 (활성)

### [P2] memory-1 — Gemini 추출 value=list가 str 컬럼(time_preference/transport_mode)에 setattr → commit 실패 → 전체 추출 배치 silent rollback
`data-integrity` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/nodes/memory.py:197,203; backend/app/services/personal_data_extractor.py:75; backend/app/models/user.py:24-25`
- **메커니즘**: 1) extract_personal_data(Gemini 경로)는 CategoryExtraction.value를 Union[list[str], str]로 선언(personal_data_extractor.py:75) — time_preference/transport_mode 카테고리에도 list 허용. 2) Gemini가 time_preference에 ["평일 저녁","주말 오후"] 같은 list를 반환하면 _filter_invalid_time_preference는 list를 join해 패턴 검사만 할 뿐 value를 str로 변환하지 않음(personal_data_extractor.py:218). 3) memory_extraction Case A/B에서 setattr(user, category, ext.value)를 coercion 없이 호출(memory.py:197,203). 4) User.time_preference는 max_length=255 str, transport_mode는 max_length=32 str 컬럼(user.py:24-25). 5) await db.commit() 시 SQLAlchemy/asyncpg가 list→VARCHAR 어댑트 실패로 DBAPIError → memory.py:233 except가 잡아 db.rollback()(memory.py:235). 6) 같은 트랜잭션의 다른 멤버 list/str 카테고리 추출(food_*, areas 등)까지 전부 롤백되어 그 모임의 personal-data 학습 전체가 silent 손실.
- **근거**: personal_data_extractor.py:75 `value: Union[list[str], str]` (모든 카테고리 공통 schema). user.py:24 `time_preference: Optional[str] = Field(..., max_length=255)`, user.py:25 `transport_mode: Optional[str] = Field(..., max_length=32)`. memory.py:197 `setattr(user, category, ext.value)` / :203 동일 — 어디에도 isinstance(list)→join/str 변환 없음. memory.py:232-236 단일 commit + 실패 시 전체 rollback + return(log only).
- **영향**: Gemini가 str 카테고리에 list를 반환하는 한 번의 응답으로 해당 모임의 6카테고리 personal-data 학습 전체가 무음 유실(holiday/✨ 학습 카드 미노출). 데모에선 canned fallback(올바른 타입)이라 미발현하나, 실 Gemini 운영(자유체험존) 경로에서 비결정적으로 재현. 모임 진행 자체는 안 깨짐(이미 카드 발행 후 detached task).
- **제안 수정**: memory.py setattr 직전 또는 personal_data_extractor에서 str 컬럼 카테고리(time_preference/transport_mode)에 대해 value가 list면 ', '.join(...)으로 평탄화 + max_length 절단. 또는 CATEGORY 타입 맵을 두고 카테고리별 기대 타입으로 정규화.

### [P2] memory-2 — 동시 finalization 시 memory_extraction 중복 실행 → 동일 AIMemory 중복 INSERT + User 컬럼 write 경합(last-writer-wins)
`race-condition` · conf 6/10 · 미검증(P2/P3) · ⚠겹침:Codex

- **위치**: `backend/app/services/pipeline/nodes/maedeup.py:177,215; backend/app/services/pipeline/nodes/memory.py:99-104,181-232`
- **메커니즘**: 1) maedeup_card_creation은 카드 발행마다 asyncio.create_task(_spawn_memory_extraction_async(state)) 호출(maedeup.py:177 partial, :215 full). 2) Codex #2(all_members_selected NX 소비락 우회)로 N명이 각자 파이프라인을 돌리면 같은 room에 대해 maedeup_card_creation이 여러 번 도달 → memory_extraction이 N개의 독립 세션(AsyncSessionLocal, memory.py:99)에서 동시 실행. 3) 각 태스크가 동일 transcript를 읽어(memory.py:147) 같은 카테고리 AIMemory row를 각각 INSERT(memory.py:217) → 중복 row 누적. 4) User 컬럼 setattr+commit이 락 없이 경합(memory.py:197/232) → last-writer-wins. is_ai_filled도 각 태스크가 dict(user.is_ai_filled or {}) 스냅샷 후 덮어써 한쪽 갱신이 유실 가능.
- **근거**: memory.py:99 `async with AsyncSessionLocal() as new_session` — 태스크별 독립 세션(공유 락 없음). memory.py:116 주석 '매 추출에 대해 AIMemory row INSERT' — 멱등 키/유니크 제약 없음(AIMemory 모델에 source 조합 unique 미확인). maedeup.py:177,215 무조건 create_task. graph.py에 run 단위 dedup 가드 없음(파이프라인 진입은 상위 트리거 락에 의존).
- **영향**: AIMemory 테이블에 동일 추출 중복 row 누적(시점기록 의도와 별개로 동일 run에서 N배), User personal-data 동시 write로 일부 카테고리 갱신 유실. 모임 종료 흐름 자체는 비차단. Codex #2 락 수정 시 자동 완화.
- **제안 수정**: 근본은 Codex #2(소비락) 수정. 추가로 memory_extraction에 room+run 단위 멱등 가드(예: Redis SETNX memory:run:{run_id}) 또는 AIMemory에 (user_id,memory_type,source_message_id,source_room_id) 부분 멱등 체크.

### [P3] memory-3 — fire-and-forget memory_extraction 태스크 미참조 → 이벤트루프 GC로 완료 전 회수 가능(개인정보 학습 누락)
`resource-leak` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/nodes/maedeup.py:177,215; backend/app/services/pipeline/nodes/memory.py:88-104`
- **메커니즘**: asyncio.create_task의 반환 Task를 어디에도 저장하지 않음(maedeup.py:177,215). CPython asyncio는 강한 참조가 없는 태스크를 GC 대상으로 보며, 완료 전 회수되면 추출(~4s 소요, memory.py:92)이 중도 취소될 수 있음. detached_state는 dict(state_snapshot) 얕은 복사라 원본 state mutation과 분리는 되지만 태스크 수명은 보호되지 않음.
- **근거**: maedeup.py:177 `asyncio.create_task(_spawn_memory_extraction_async(state))` — 변수 바인딩/태스크 집합 등록 없음. 동일 :215. memory.py docstring(88-97)은 fire-and-forget을 명시하나 GC 보호는 언급 없음.
- **영향**: 고부하/짧은 요청 수명에서 personal-data 학습이 비결정적으로 누락(✨ 학습 카드 미출현). 모임 핵심 흐름엔 무영향. 설계상 silent 허용 영역이라 severity 낮음.
- **제안 수정**: 모듈 레벨 set에 태스크 add 후 add_done_callback(set.discard)로 강한 참조 유지(표준 패턴).

### [P3] validation-1 — state['headcount']가 slot_context에서 미정규화로 들어올 경우 validation.py headcount>20 비교가 str>int TypeError 유발(노드 예외 경로)
`edge-case` · conf 5/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/state.py:209; backend/app/services/pipeline/nodes/validation.py:63`
- **메커니즘**: _default_state는 `state['headcount'] = ctx.get('headcount')`를 coercion 없이 박음(state.py:209). validation.py:63 `elif headcount is not None and headcount > 20`는 headcount가 str이면 Python3에서 'N' > 20 → TypeError. 정상 파이프라인은 _coerce_headcount(slot_state.py:34/64)로 int를 보장하고 graph.py:390이 그 int를 라운드트립하므로 미발현. 다만 외부 호출부가 slot_context에 raw str headcount를 주입하면 노드 try/except(validation.py:158)가 잡아 _handle_node_exception으로 전환 → vote/maedeup 미생성(무음 실패).
- **근거**: state.py:209 coercion 부재(인접 필드 date_is_flexible:207, slot_filling_turns:214는 bool()/int()로 강제하는 것과 대비). validation.py:60-64 headcount 비교. slot_state.py:34 _coerce_headcount는 _update_slot_state 경로에서만 적용되어 직접 주입 시 우회.
- **영향**: 현재 알려진 라우트(meetings.py headcount는 타입드)로는 비재현. 향후 신규 엔드포인트/테스트 주입이 str headcount를 넣으면 해당 트리거가 카드 없이 무음 종료. 낮은 발현 가능성.
- **제안 수정**: state.py:209를 `_coerce_headcount(ctx.get('headcount'))`로 정규화하거나 validation.py:63에서 int 캐스팅 가드.
