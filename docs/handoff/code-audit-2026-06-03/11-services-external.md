# 코드 감사: 외부 서비스: kakao·gemini·llm·openai·ml·embedding·personal_data

> 영역키 `services-external` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/services/kakao_maps.py`
- `backend/app/services/gemini.py`
- `backend/app/services/llm.py`
- `backend/app/services/openai_client.py`
- `backend/app/services/ml_recommend.py`
- `backend/app/services/embedding.py`
- `backend/app/services/personal_data_extractor.py`
- `backend/app/services/meeting_history.py`
- `backend/app/services/reminder.py`
- `backend/app/services/notify.py`
- `backend/app/services/intent_classifier.py`
- `data/serving/quick_recommend.py`
- `backend/app/api/routes/intents.py`
- `backend/app/api/routes/meetings.py (부분)`
- `backend/app/api/routes/users.py (부분)`
- `backend/app/models/meeting.py`
- `backend/app/models/intent.py`
- `backend/app/services/pipeline/nodes/intent.py (부분)`
- `backend/app/services/pipeline/nodes/place.py (부분)`
- `backend/app/services/pipeline/nodes/vote_card.py (부분)`
- `backend/app/main.py (스케줄러 부분)`

## 감사 노트
검토 완료. 외부 서비스 영역(kakao/gemini/openai/llm/ml/embedding/personal_data/meeting_history/reminder/notify) 전수 read.

[깨끗하다고 확인한 핵심 불변식]
- kakao_maps.py: KakaoApiError 분리(transport/5xx=raise, 404/400/빈=[]/None) 일관. timeout=5s, key 없거나 빈 쿼리면 조기 반환. address.json의 x/y/address_name 폴백 체인 정상. AsyncClient를 with로 닫음 — 누수 없음.
- gemini.py call_gemini: 25s wait_for + 1회 retry(Timeout/ResourceExhausted/GoogleAPICallError), response.text의 ValueError(safety 차단) try-catch 후 candidates 폴백 — 견고. effective_gemini_api_key 없으면 즉시 ''.
- openai_client.py: 모듈 싱글톤 AsyncOpenAI 지연 생성·재사용(단일 이벤트루프 FastAPI에서 안전), key 없으면 '' 반환, 모든 예외 흡수. timeout=25s wait_for. 결함 없음.
- llm.py: 단순 분기 wrapper, tier_env_map.get(tier,'gemini') 안전 기본값. 결함 없음.
- ml_recommend.py: to_thread로 sync quick_recommend 호출, 결과 정규화(float 캐스팅, .get 기본값). 후보 0건 시 빈 추천 정상 반환(quick_recommend.py:108-113). 모델/이미지 파일 부재는 documented Gemini fallback. 결함 없음.
- notify.py: 단일 caller(users.py:350)가 contract대로 먼저 commit 후 호출. Redis publish 실패는 로깅만, DB 유지. per-call redis from_url+aclose. 결함 없음.
- personal_data_extractor: confidence<0.7 drop, _filter_invalid_time_preference 정규식 후처리(value만 검사 — false negative 방지 의도 명시), canned는 User.email 매칭, force_demo/DEMO_FALLBACK 분기 정상. Gemini 실패는 canned fallback 흡수. (timeout/hang은 extract-3로 보고)
- meeting_history.save_meeting_record: 호출 시점(meetings.py:1108) 세션은 이미 1050에서 commit된 클린 상태라 add+commit 안전. meeting None 가드 있음. dedup(seen_meeting_ids) 정상.
- reminder.py 시간 경계: KST today window→UTC-naive 변환 정확(astimezone(utc).replace(tzinfo=None)), DB가 naive-UTC 저장과 일치. created_at<=cutoff 필터는 vote_card.py:343-364에서 meeting이 vote_options와 동시 생성되므로 created_at≈vote-start로 의미상 정합(과거 우려 해소).

[Codex 5버그와의 겹침] intent-1만 overlaps_codex=true 후보(임베딩 zero-vector→general 오분류는 free-use findings JSON에 기록된 기존 known issue, Codex 별도 5버그 목록과는 직접 겹치지 않으나 진행 중 이슈일 수 있어 표시). 나머지는 독립.

[추가 위임 제안] (a) embed-1/intent-1의 운영 발현 빈도는 전시 콜드스타트 시 Gemini rate-limit 실측 필요 — qa-runtime 담당. (b) extract-2/extract-3 fire-and-forget GC·hang은 런타임 부하 테스트(장소확정 직후 추출 완주율)로 검증 권장. (c) search_meeting_history(history-1)는 라우트 미연결 — 의도된 dead code인지 PM 확인 필요.

## 발견 (활성)

### [P2] embed-1 — embedding 실패 시 zero-vector를 IntentExample.embedding에 영구 저장 → RAG 예시 영구 오염 (seed/add는 success 보고)
`data-integrity` · conf 8/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/embedding.py:17-33, backend/app/api/routes/intents.py:111-114, intents.py:144-152`
- **메커니즘**: 1) Gemini embedding API가 rate-limit/장애면 get_embedding이 [0.0]*768을 반환(로그 warning만, 예외 없음). 2) seed_examples / add_example는 반환값을 그대로 IntentExample(embedding=embedding)으로 INSERT·commit. 3) 저장된 zero-vector 행은 embedding IS NOT NULL 이라 classify_intent의 select(...where embedding.isnot(None))에 항상 로드됨. 4) _cosine_similarity는 norm_b==0이면 0.0 반환 → 이 예시는 어떤 입력과도 매칭 0점. 5) 결과적으로 해당 의도 예시가 RAG에서 영구히 죽은 행이 되어 분류 품질이 silent하게 저하되는데, seed 엔드포인트는 '시드 완료 N개 삽입' 성공 응답을 돌려준다.
- **근거**: embedding.py:28-33는 ResourceExhausted/GoogleAPICallError/Exception 모두 [0.0]*768 반환. intents.py:111-113은 그 반환값을 검증 없이 IntentExample에 저장하고 116에서 commit. intent_classifier.py:64는 embedding.isnot(None)만 필터 → zero-vector 통과. _cosine_similarity(intent_classifier.py:44-45)는 norm 0이면 0.0.
- **영향**: 전시 부스 첫 기동 시 Gemini rate-limit/콜드스타트 중 POST /intents/seed가 돌면 일부(혹은 전부) 예시가 0-벡터로 박혀 RAG 매칭이 죽고, 의도 분류가 패턴/general fallback에만 의존하게 됨. 재-seed 전까지 지속, 에러 신호 없음.
- **제안 수정**: get_embedding이 실패를 호출자에 신호하도록 분리(예: None 또는 예외)하거나, seed/add 경로에서 all(v==0 for v in embedding) 또는 norm==0 검사 후 저장 거부+명시적 실패 카운트 응답. 최소한 seed 응답에 '임베딩 실패 N건' 표기.

### [P2] intent-1 — embedding zero-vector fallback 시 classify_intent가 Gemini 폴백 구간을 건너뛰고 패턴매칭만으로 분류 (의도 silent 저하)
`edge-case` · conf 7/10 · 미검증(P2/P3) · ⚠겹침:Codex

- **위치**: `backend/app/services/intent_classifier.py:59-90, 153-173`
- **메커니즘**: 런타임 classify에서 get_embedding이 zero-vector를 반환하면 모든 예시 cosine=0 → top_similarity=0. 0 < LOW_THRESHOLD(0.60)이라 line 82 HIGH 분기, line 90 Gemini-폴백 분기를 모두 건너뛰고 line 153 이하 저-유사도 경로로 직행. 거기서는 Gemini 재판단 없이 _contains_korean_place/_contains_schedule_keyword 정규식만으로 의도를 결정하고, 둘 다 아니면 무조건 general 반환. 즉 임베딩 장애 시 분류가 LLM 판단 없이 좁은 정규식+general로 degrade.
- **근거**: embedding.py:28-33 zero-vector 반환 경로. intent_classifier.py:82(HIGH), 90(LOW 게이트) 둘 다 top_similarity 비교 → 0이면 진입 불가. 153-167은 패턴만, 169-173은 general.
- **재현**: Gemini embedding rate-limit 상태에서 '강남에서 모이자' 외 패턴 미스 발화 입력 → general.
- **영향**: Gemini embedding 장애 동안 장소/일정 관련 발화가 정규식에 안 걸리면 general로 떨어져 AI 개입(투표·장소 카드)이 trigger되지 않음. 사용자 입장에선 'AI가 반응 안 함'. 정규식이 좁아 한글 지명+모임키워드 동시조건 필요(line 178-181).
- **제안 수정**: classify_intent 진입부에서 query_embedding이 zero-vector(또는 norm 0)면 임베딩 단계를 신뢰하지 않고 곧장 Gemini 폴백(call_llm_tier)으로 라우팅하거나 패턴+LLM 병행. 최소한 zero-vector 감지 시 method='embedding_unavailable' 로깅으로 가시화.

### [P3] history-1 — search_meeting_history Gemini 필터가 hallucinated/임의 JSON을 그대로 반환 (검증 없는 LLM 출력 패스스루)
`correctness` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/meeting_history.py:125-142`
- **메커니즘**: call_llm_tier 응답을 json.loads한 뒤 isinstance(filtered, list)만 확인하고 그대로 return. 원본 unique_records와의 멤버십 검증이 없어 LLM이 record를 변형/날조하거나 일부 필드만 반환해도 그대로 호출자에게 전달됨. 예외 시 fallback은 unique_records(방의 전체 기록) 반환이라 '관련 필터링'이라는 의미가 무너짐.
- **근거**: meeting_history.py:131 filtered = json.loads(response); 132 isinstance list만 검사 후 return. 134-140 except에서 return unique_records (전체).
- **영향**: 히스토리 기반 답변에 잘못된 과거 모임 정보가 섞일 수 있음(품질). 보안 영향은 낮음 — 함수가 현재 어떤 API 라우트에도 연결돼 있지 않음(grep 결과 라우트 호출 없음, get_recent_meeting_records만 intent 노드에서 사용). 실사용 경로 미연결이라 P3.
- **제안 수정**: LLM이 반환한 항목을 meeting_id 기준으로 unique_records와 교집합 필터링(화이트리스트)해 날조/변형 차단. 또는 LLM에 meeting_id 배열만 반환시키고 코드에서 record를 조립.

### [P3] extract-3 — _gemini_extract의 model.generate_content가 timeout 없이 to_thread 실행 → 노드/추출 hang 가능
`resource-leak` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/personal_data_extractor.py:347-354`
- **메커니즘**: gemini.py의 call_gemini는 asyncio.wait_for(timeout=25s)로 감싸 hang을 차단하지만, personal_data_extractor._gemini_extract는 genai.GenerativeModel을 직접 생성하고 await asyncio.to_thread(model.generate_content, prompt)를 timeout 없이 호출. SDK가 hang하면 추출 코루틴(및 이를 호출한 memory_extraction)이 무한 대기.
- **근거**: personal_data_extractor.py:339-348 — generation_config에 timeout 없음, wait_for 미사용. 대비: gemini.py:55-58 wait_for(timeout=timeout). embedding.py도 to_thread 무 timeout(:22-27)이나 그쪽은 짧은 호출.
- **영향**: Gemini SDK 응답 hang 시 ACT6 학습 코루틴이 영구 대기(앞 extract-2 fire-and-forget이면 누수). 일반 호출 경로(call_gemini)는 보호돼 있어 영향 국소적.
- **제안 수정**: _gemini_extract도 asyncio.wait_for(asyncio.to_thread(...), timeout=...)로 감싸고 TimeoutError를 RuntimeError로 변환해 기존 canned fallback에 흡수시키기.

### [P3] extract-2 — place patch 경로 personal_data 추출이 참조 없는 create_task → GC 위험 + 장기 Gemini 호출 detach
`resource-leak` · conf 5/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/meetings.py:1119, _spawn_personal_data_extraction meetings.py:46-62 → personal_data_extractor.extract_personal_data`
- **메커니즘**: _asyncio.create_task(_spawn_personal_data_extraction(...)) 반환 Task를 어디에도 저장하지 않음. asyncio는 task에 weak ref만 보유하므로 await I/O 경계에서 GC가 task를 수거해 추출이 silent하게 중단될 수 있음(특히 Gemini 25s 호출 중). 내부에서 별도 AsyncSessionLocal을 열어 memory_extraction(Gemini extract+User update+AIMemory insert)을 수행.
- **근거**: meetings.py:1119 create_task 결과 미보관(grep: _background_tasks/add_done_callback 부재). _spawn은 personal_data_extractor 경로로 들어가 _gemini_extract(asyncio.to_thread, 무 timeout)까지 도달(personal_data_extractor.py:348).
- **영향**: ACT6 '비린 거→✨' 학습이 간헐적으로 누락될 수 있음. fire-and-forget 의도이나 GC 수거 시 partial(User update만 되고 AIMemory 누락 등) 가능성. CPython이 보통 I/O 대기 중엔 살려두나 asyncio 공식 경고 대상.
- **제안 수정**: 모듈 레벨 set에 task 보관 후 add_done_callback(set.discard)로 강참조 유지. _gemini_extract에도 timeout 적용(현재 to_thread+generate_content 무 timeout).

### [P3] reminder-1 — reminder/vote_reminder의 flag-check-then-set이 row lock 없음 → 다중 인스턴스 시 중복 발행
`race` · conf 5/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/reminder.py:36-68 (reminder_sent), 90-174 (vote_reminder_sent)`
- **메커니즘**: SELECT ... WHERE reminder_sent=False 로 후보를 읽고, publish 성공 시 meeting.reminder_sent=True를 set 후 batch commit. 같은 행에 대한 SELECT FOR UPDATE/원자적 UPDATE가 없어, 동일 작업이 두 번 겹쳐 돌면(다중 워커/스케줄러 인스턴스, 또는 작업이 1시간 넘게 지연돼 다음 cron tick과 overlap) 두 실행이 모두 False를 보고 각각 Redis publish → 리마인더 중복.
- **근거**: reminder.py:38-44 status/reminder_sent 필터 후 46-68 루프 내 publish+flag set, 커밋은 67-68 루프 밖. 행 잠금/원자 UPDATE 부재.
- **영향**: 현 docker-compose는 fastapi-app 단일 컨테이너 + AAsyncIOScheduler(max_instances=1 기본 coalesce)라 실제 발현 가능성 낮음(그래서 P3). 스케일아웃/멀티프로세스 도입 시 중복 알림.
- **제안 수정**: UPDATE ... SET reminder_sent=True WHERE id=:id AND reminder_sent=False RETURNING 으로 원자적 클레임 후 publish, 또는 Redis NX 락(다른 곳에서 쓰는 패턴)으로 가드.

### [P3] reminder-2 — send_today_meeting_reminders: publish 성공·DB commit 실패 시 중복 리마인더(at-least-once만 보장)
`data-integrity` · conf 5/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/reminder.py:54-68`
- **메커니즘**: 각 meeting마다 Redis publish를 먼저 하고(side-effect 발생) reminder_sent=True를 메모리에 set, 커밋은 루프 종료 후 1회(line 67-68). 만약 일부 meeting publish 성공 후 session.commit()이 실패하면, 이미 발행된 리마인더의 reminder_sent 플래그가 롤백되어 다음 tick에서 재발행됨.
- **근거**: reminder.py:55-59 publish, 63-65 in-memory flag set, 67-68 단일 commit. publish와 commit 사이 원자성 없음.
- **영향**: DB commit 실패라는 드문 조건에서만 발생. 영향은 리마인더 1회 중복(데이터 손상 아님). 단일 batch commit이라 한 meeting commit 실패가 그 tick 전체 flag를 롤백.
- **제안 수정**: meeting 단위로 publish 직전이 아니라 직후 즉시 per-row commit, 또는 outbox 패턴(commit 후 publish). 최소한 commit을 먼저 시도하고 성공 행만 publish.
