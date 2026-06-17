# 코드 감사: 파이프라인: 엔티티 추출·의도 분류

> 영역키 `pipeline-entity-intent` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/services/pipeline/nodes/entity.py`
- `backend/app/services/pipeline/nodes/intent.py`
- `backend/app/services/pipeline/nodes/conversation_analyzer.py`
- `backend/app/services/intent_classifier.py`
- `backend/app/services/stalemate_judge.py`
- `backend/app/services/pipeline/helpers/places.py`
- `backend/app/services/pipeline/helpers/date_classify.py`
- `backend/app/services/pipeline/helpers/dates.py`
- `backend/app/services/pipeline/helpers/slot_state.py`
- `backend/app/services/pipeline/state.py`
- `backend/app/services/embedding.py`
- `backend/app/api/ws/social.py`
- `backend/app/services/pipeline/graph.py`
- `backend/app/services/pipeline/helpers/preferences.py`

## 감사 노트
검토 범위: entity.py / intent.py / conversation_analyzer.py / intent_classifier.py / stalemate_judge.py 전부 + 의존 헬퍼(places, date_classify, dates, slot_state, state, embedding) + 트리거 호출부(social.py _detect_and_notify_intent, graph.py 라우터, preferences._load_social_context). 모두 직접 읽고 file:line 확인.

핵심 불변식 확인 결과:
- _pattern_extract_entities의 M월D일 과거→내년 롤(line 130-138)과 13월/2월30일 datetime 검증(line 129-131 try/except)은 정상.
- _resolve_rejected_date(dates.py:72-103)는 ISO 직통 + 슬래시 정규화 + fallback; naive/aware는 datetime.now(KST)(aware)로 일관, 비교는 strftime ISO 문자열이라 안전.
- date_classify _resolve의 화자 그룹화(g_rej -= g_avail)와 comp_exc 전역 차감(line 243-246)은 화자 라벨이 있는 social 경로에서 의도대로 동작. 화자 라벨 없으면 None 단일 그룹(하위호환) — 의도된 trade-off.
- _cosine_similarity 길이 불일치 가드(intent_classifier.py:39-40) 정상 — 임베딩 모델 차원 변경 시 0 반환으로 안전.
- intent_classifier examples 빈/1~2개 엣지: line 68 early return + top3[0] 안전.
- _expand_date_hint range 14일 캡(dates.py:438) + end<start 가드(line 434) 정상.
- _parse_natural_date_sync는 @lru_cache 키에 today_iso 포함(dates.py:341) → 날짜 경계 자동 invalidate 정상.
- conversation_analyzer의 Redis 캐시 GET/SET은 (TypeError/ValueError/AttributeError/NameError) 재raise + 그 외 graceful(line 96-99,281-284) — 코드버그 무음 방지 의도대로.

영역에 P0는 없음. 가장 영향 큰 것은 intent-1(stalemate 중복 트리거 race, P1)과 entity-1(비-pre 경로 rejected 필터 누락, P1). 둘 다 Codex 5버그와 클래스는 인접하나 경로/원인이 달라 overlaps_codex=false로 표기. entity-1은 Codex #1(옛 vote 카드 잔존) 증상과 겹쳐 보일 수 있으니 PM이 교차 확인 권장.

PM 후속 제안: (1) intent-1/entity-1은 슬롯·검증 담당(slot.py/validation.py)과 vote_card 담당에게 '거부 날짜가 후보/카드에 잔존하는 데이터 흐름' 전구간 추적을 위임해 교차 검증. (2) entity-3(화자 라벨)은 AI 패널 멀티유저 담당과 _message_to_text 변경 영향 범위(general_response 프롬프트, 다른 노드 컨텍스트) 평가 필요. (3) preferred_dates가 양쪽 경로 모두 state로 전파되지 않는 점(slot_state가 미처리)은 슬롯 영역 담당이 소비처를 확인.

## 발견 (활성)

### [P2] entity-2 — multi-date 경로에서 resolve 실패한 raw 한글 hint가 문자열 past-필터를 통과해 비-ISO 값으로 downstream 유입
`correctness` · conf 8/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/nodes/entity.py:742-766`
- **메커니즘**: _resolve_one은 날짜 해석 실패 시 raw hint를 그대로 반환(line 748 `return hint`, 예: '목요일','15일'). 이후 past 필터는 ISO 문자열 비교 `d >= _today_kst.isoformat()` (line 756). 한글/비-ISO 문자열은 유니코드 코드포인트가 ASCII 숫자('2')보다 커서 비교가 항상 True → raw 한글 hint가 date_hints에 살아남음. ISO를 기대하는 slot_filling/vote_card로 비-ISO 값이 흘러감. (단일 hint 경로 line 768-781은 _is_iso_date_hint 가드가 있어 안전.)
- **근거**: line 748 raw 반환, line 756 `[d for d in resolved_hints if d >= _today_kst.isoformat()]` — 타입/형식 검증 없는 사전식 비교. _is_iso_date_hint 가드 부재(단일 경로와 비대칭).
- **영향**: Gemini와 fallback이 모두 실패한 드문 경우 비-ISO 날짜 토큰이 투표 후보로 유입 → 슬롯 빌드/날짜 파싱 오류 또는 무의미한 후보. 발생 빈도는 낮음(_parse_natural_date가 대부분 fallback으로 해석).
- **제안 수정**: line 756 필터를 `[d for d in resolved_hints if _is_iso_date_hint(d) and d >= _today_kst.isoformat()]`로 강화해 비-ISO 값을 명시적으로 drop.

### [P2] intent-2 — 임베딩 실패/키 부재 시 zero-vector 반환 → 모든 코사인 유사도 0 → intent confidence 0으로 silent degradation
`edge-case` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/embedding.py:14-33, backend/app/services/intent_classifier.py:38-46,82,90`
- **메커니즘**: get_embedding은 API 키 부재(line 17-18)나 예외(line 28-33) 시 [0.0]*768 zero-vector를 반환. classify_intent의 _cosine_similarity는 norm_a==0이면 0.0 반환(line 44-45) → 모든 예시 유사도 0 → top_similarity=0 → HIGH/LOW threshold 미달 → 패턴 폴백 또는 general 분류(confidence=0.0). intent_detection은 fast-path 미히트 시 이 결과로 confidence_score를 채우고(intent.py:289-291), graph의 _route_after_intent는 confidence<0.7이면 general_response로 분기(graph.py:96).
- **근거**: embedding.py:18 `return [0.0]*_EMBEDDING_DIM`, intent_classifier.py:44-46 norm 0 가드, intent.py:290 `float(intent_result.get('confidence',0.0))`. zero-vector는 모든 입력을 동일하게 미분류로 만듦.
- **영향**: Gemini 키 누락/일시 장애 시 RAG 분류가 통째로 무력화되고, 패턴 매칭이 못 잡는 발화는 전부 general로 떨어져 모임 트리거가 누락됨. fail-soft 의도(주석상 패턴 fallback)이나, fast-path가 없는 발화에선 silent하게 모임 의도가 사라짐.
- **제안 수정**: get_embedding이 빈/실패 시 sentinel(None 또는 예외)을 던지고 classify_intent에서 그 경우 패턴 매칭 분기로 명시적으로 빠지게 하여, '진짜 0 유사도'와 '임베딩 실패'를 구분. 최소한 zero-vector 반환 시 WARNING이 classify 단까지 전파되도록.

### [P2] entity-3 — AI 패널 경로의 recent_messages는 'role: content' 직렬화라 date_classify 화자 귀속(_SPEAKER_LINE)이 무력화
`correctness` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/state.py:284-287,300-301; backend/app/services/pipeline/helpers/date_classify.py:55-56,68-74`
- **메커니즘**: date_classify의 _detect_complement_constraints/_resolve는 줄을 `_SPEAKER_LINE`(`이름: 발화`)로 파싱해 화자별로 rejected를 귀속(B 화자귀속). social_recent는 _load_social_context에서 `{sender}: {content}`로 만들어져 귀속이 동작(preferences.py:67-68). 그러나 _serialize_context가 합치는 recent_messages(AI 대화)는 _message_to_text가 `{role}: {content}` (role='user'/'assistant')로 만듦(state.py:284-287) → 화자명이 아니라 role이 speaker로 잡혀, 같은 'user' 한 명으로 그룹화됨. 멀티유저가 AI 패널에서 직접 입력한 거부의 화자 구분이 사라짐.
- **근거**: _message_to_text line 286 `return f'{role}: {content}'` (sender 미사용). date_classify _SPEAKER_LINE은 콜론 앞 1~20자를 speaker로 취함 → 'user'/'assistant'를 화자로 오인.
- **영향**: AI 패널(recent_messages 경로) 멀티유저 입력에서 멤버별 unavailability 귀속이 'user' 단일 그룹으로 뭉개져, A의 거부를 B의 가능이 못 지우는 화자별 정정 정확도 손실. social 경로(채팅방)는 정상이라 영향은 AI 패널 직접 입력에 한정. 단일 화자/eval은 영향 없음(하위호환).
- **제안 수정**: _message_to_text에서 sender가 있으면 `{sender}: {content}`로 직렬화하거나(role 라벨은 별도 유지), date_classify가 보는 컨텍스트에는 화자 라벨이 있는 social_recent만 쓰도록 입력을 분리.

### [P3] intent-1 — stalemate judge 쿨다운이 LLM 호출 *후*에 설정 → 동시 메시지가 중복 ai_auto_trigger 발행 (TOCTOU)
`race` · conf 7/10 · ⤵ 강등됨(원래 P1)

- **위치**: `backend/app/api/ws/social.py:741-786`
- **메커니즘**: 메시지 수신마다 _detect_and_notify_intent 실행. (1) r.incr(counter) → count, (2) count>=3 통과, (3) r.get(cooldown_key) 체크(line 753), (4) judge_stalemate() — 수 초 걸리는 LLM 호출(line 784), (5) r.setex(cooldown_key,60) — 쿨다운을 LLM 호출이 끝난 *뒤*에 설정(line 786). check(3)와 set(5) 사이에 비싼 await가 끼어 있어, 짧은 간격으로 도착한 N개 메시지가 모두 count>=3 + cooldown 미설정 상태를 통과 → 각자 judge_stalemate 실행 + 각자 stalemate auto_trigger 발행. conclusion_detected 경로는 NX idem 키(line 700-707)로 보호되지만 stalemate_judged 경로엔 그런 보호가 없음.
- **근거**: line 753 `if await r.get(cooldown_key): return` 후 line 784 `judgment = await judge_stalemate(msgs_for_judge)` (LLM, 수초), line 786 `await r.setex(cooldown_key,60,'1')`. 쿨다운 set이 LLM await 뒤에 위치. trigger 발행(line 808 r.publish)에도 idempotency 키 없음.
- **영향**: 활발한 단톡에서 여러 멤버가 동시에 모임 메시지를 보내면 같은 교착에 대해 중복 ai_auto_trigger가 발행됨 → AI 패널에 중복/충돌 카드, 중복 LLM 비용. Codex #2(all_members_selected 중복 파이프라인)와 같은 클래스이나 경로가 다름(stalemate judge).
- **제안 수정**: judge_stalemate 호출 *전*에 NX 락(예: r.set(judge_lock_key, '1', nx=True, ex=60))을 잡아 동시 진입을 직렬화하고, 락 획득 실패 시 즉시 return. 또는 conclusion 경로처럼 trigger_message_id 기반 NX idem 키를 publish 직전에 적용.
- **검증 판단**: Producer 측 TOCTOU는 실재함(확인됨): social.py:620에서 메시지마다 asyncio.create_task로 직렬화 없이 _detect_and_notify_intent 실행, social.py:753 cooldown 체크와 social.py:786 setex 사이에 social.py:784 await judge_stalemate()(=stalemate_judge.py:85 call_llm_tier mid-tier, 수 초)가 끼어 있어 동시 메시지 N개가 cooldown 미설정 상태를 통과 → 각자 judge_stalemate + 각자 r.publish(stalemate_judged) 발행. conclusion 경로(social.py:700-707)의 NX idem이 stalemate 경로엔 없음도 사실.

그러나 주장이 명시한 핵심 impact("중복 ai_auto_trigger → 중복/충돌 카드, 중복 파이프라인 LLM")는 consumer 측에서 차단됨: agent.py:951-961에서 stalemate_judged(is_user_explicit_confirm=False)는 build_auto_trigger_lock_key가 반환하는 room별 고정 키 nx_autotrigger:{room_id}(agent.py:52-54)로 Redis NX 락(ex=60s)을 잡고, 실패 시 agent.py:965 continue로 파이프라인 진입을 skip. 추가로 agent.py:974-983 로컬 디바운스(60s)까지 belt-and-suspenders. agent.py:926-929 주석이 "N subscribers...Redis SET NX picks one winner per room; others skip"라고 명시. Redis NX는 멀티 프로세스 간에도 단일 승자 보장하므로 중복 publish가 N개여도 60초 내 파이프라인은 1회만 실행 → vote_card/AI 카드 1회만 생성, 사용자 가시 중복/충돌 없음.

잔존 실손해는 producer 측 judge_stalemate(저비용 mid-tier Gemini)가 동시 메시지 수만큼 중복 호출되는 LLM 비용 낭비뿐. 사용자 영향(중복 카드) 없음 + 낭비가 저비용 judge 호출로 국한 → P1 과대평가, P3로 다운그레이드. confidence 7은 consumer NX 락을 고려하지 않은 평가로 보임.

### [P3] entity-1 — 비-pre_extracted entity 경로에 rejected_dates→conflict_options/date_hints 필터링 누락 (pre 경로와 비대칭)
`data-integrity` · conf 7/10 · ⤵ 강등됨(원래 P1)

- **위치**: `backend/app/services/pipeline/nodes/entity.py:798-844 (누락) vs 538-575 (pre 경로)`
- **메커니즘**: pre_extracted 분기(line 538-575)는 cleaned_rejected로 (a) date_hints에서 거부 날짜 제거 + 전량 거부 시 expanded_to_next_week 플래그, (b) conflict_options에서 거부 날짜 제거 + 옵션<2면 conflict_detected=False로 mediation 차단 — 두 후처리를 수행. 그러나 비-pre 경로(Gemini/pattern 추출, line 798-819 rejected 처리)에는 이 두 후처리가 전혀 없음. pre_extracted_signals는 agent.py의 _analyze_conversation 성공 시에만 채워지고(agent.py:505), 실패하거나 signals가 dict가 아니면 None(agent.py:521) → 비-pre 경로 도달. 그 경로에서 Gemini가 같은 날짜를 rejected_dates와 conflict_options 양쪽에 넣으면 정합성이 깨지고, 거부된 날짜가 date_hints 후보로 살아남아 vote_card에 노출됨.
- **근거**: pre 경로 line 538-548(date_hints 필터)·line 559-575(conflict_options 필터+suppress) 존재. 비-pre 경로는 line 798-819에서 state['rejected_dates']만 세팅하고 conflict_options(line 789에서 그대로 세팅됨)나 date_hints 재필터 없음. line 786-790에서 conflict_options를 extracted 값 그대로 state에 반영.
- **영향**: AI 분석 실패(fallback) 경로에서 거부된 날짜가 투표 후보/mediation 선택지에 잔존 → 멤버가 이미 거부한 날짜에 투표 카드가 생성되거나, 사실상 후보 1개뿐인데 교착 mediation으로 진입. Codex #1(옛 vote 카드 잔존)과 증상이 겹칠 수 있으나 원인이 다름.
- **제안 수정**: line 798-819의 cleaned_rejected 계산 직후, pre 경로 line 538-575와 동일한 date_hints/conflict_options 필터 + conflict suppress 로직을 비-pre 경로에도 추가하거나, 두 경로가 공유하는 헬퍼로 추출.
- **검증 판단**: 코드 비대칭 주장 자체는 사실이나, P1으로 명시한 data-integrity impact("거부된 날짜가 투표 후보/vote_card에 잔존")는 하류 2중 가드로 차단되어 실현되지 않음 → P3 downgrade.

[사실 확인] 비-pre 경로(entity.py:786-819)에는 pre 경로(538-575)의 (a) date_hints rejected 필터+expanded_to_next_week 플래그(538-556), (b) conflict_options rejected 제거+옵션<2 시 conflict_detected=False suppress(559-575)가 모두 없음. line 810에서 state["rejected_dates"]만 세팅. 게다가 _extract_entities_from_context(entity.py:272)가 date_classify로 rejected_dates를 덮어쓰므로 conflict_options(Gemini)와 rejected_dates(date_classify)가 서로 다른 추출기 산출 → 정합성 불일치 여지는 실재.

[반증 — 핵심 impact 차단] mediation은 slot.py:239에서 state["date_hints"]=conflict_options로 넘기지만, function_call.py가 date_hints→slot 변환의 모든 경로(131 multi_date·160 pref·181/193 default)에서 _filter_out_rejected(..., rejected_dates)를 적용해 거부 날짜를 제거함. options>=2인 date conflict는 정확히 line 131 multi_date 경로로 감. 추가로 vote_card.py:292-305 rejected_safety가 "상위 노드 예외 중단 시에도" 거부 날짜를 _filter_out_rejected로 제거하고 전량 제거 시 카드 skip(302-305) → 이중 방어. 따라서 "멤버가 거부한 날짜에 투표 카드 생성/후보 노출"은 발생 불가.

[잔존 갭 — 그래서 false_positive가 아님] 비-pre 경로엔 conflict suppress가 없어, conflict_options에 거부 날짜가 섞여 실질 1옵션이어도 slot.py:222 mediation 가드(conflict_options 비어있지 않으면 통과)를 통과해 "의견이 나뉘네요"(slot.py:228,236) mediation 멘트가 불필요하게 발화될 수 있음. 단 후속 vote slot은 function_call에서 거부 제거 후 1개 이하 시 vote_card.py:302-305로 skip → 잘못된 카드는 안 만들어짐. 남는 증상은 UX 잡음(불필요 mediation 멘트)이고 data-integrity 손상 아님. 좁은 fallback 조합(_analyze_conversation 실패 → 비-pre 도달 + Gemini가 거부날짜를 conflict_options에 혼입 + 실질 1옵션)에서만 발생. → category는 data-integrity가 아니라 UX correctness에 가깝고 severity P3.

### [P3] intent-3 — _KOREAN_PLACE_PATTERN이 intent_classifier와 places에서 불일치 (길/산/공원/숲 누락)
`correctness` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/intent_classifier.py:29 vs backend/app/services/pipeline/helpers/places.py:50-52`
- **메커니즘**: intent_classifier._KOREAN_PLACE_PATTERN = `[가-힣]{1,10}(?:동|구|역|로|리|면|읍|시|군)` 에는 `길|산|공원|숲`이 빠짐. places._KOREAN_PLACE_PATTERN에는 포함됨. classify_intent의 패턴 폴백(_contains_korean_place)이 '○○길/○○산/서울숲' 같은 발화를 지명으로 인식하지 못해 place_suggestion 폴백을 놓침.
- **근거**: 두 정규식 리터럴 직접 비교. intent_classifier.py:29에 길/산/공원/숲 부재.
- **영향**: RAG 유사도가 낮고 Gemini도 실패한 경우, '서울숲에서 보자'·'관악산 가자' 류가 place_suggestion 폴백을 못 받고 general로 떨어질 수 있음. 정상 RAG/Gemini 경로에선 영향 없음(폴백 한정).
- **제안 수정**: places._KOREAN_PLACE_PATTERN을 단일 소스로 공유 import하거나 intent_classifier 패턴에 `길|산|공원|숲` 추가해 동기화.

### [P3] entity-4 — entity_extraction이 state['message_records']를 .get 없이 직접 인덱싱 (KeyError 가능)
`edge-case` · conf 5/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/nodes/entity.py:697,848,866 (intent.py:130,220 동일 패턴)`
- **메커니즘**: 노드 다수가 `state.get('message_records', [])`로 안전 접근하나, entity.py line 697/848/866과 intent.py line 130/220은 `state['message_records']`로 직접 접근. 정상 graph 진입 시 항상 채워져 실제 트리거되진 않지만, 부분 상태로 노드를 직접 호출하거나 _default_state 변형 시 KeyError로 노드 전체가 _handle_node_exception으로 빠짐.
- **근거**: entity.py:697 `for m in reversed(state['message_records'])` (대비: line 616 `state.get('message_records') or []`, dump 호출들은 .get 사용). 같은 함수 내 접근 방식 불일치.
- **영향**: 현재 호출 그래프에선 무해하나, 입력 불변식이 깨지는 미래 경로에서 entity/intent 노드가 통째 예외 처리로 빠져 무응답. 방어 일관성 결함.
- **제안 수정**: 해당 라인들을 `state.get('message_records') or []`로 통일.
