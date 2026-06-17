# 코드 감사: WS agent.py: 구독자·요약·예산·공유·일반 메시지 처리

> 영역키 `ws-agent` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/api/ws/agent.py`
- `backend/app/api/ws/manager.py`
- `backend/app/api/ws/social.py`
- `backend/app/core/rate_limit.py`
- `backend/app/services/scheduling_round.py`
- `backend/app/services/pipeline/helpers/date_classify.py`
- `backend/app/services/pipeline/graph.py`
- `backend/app/services/pipeline/nodes/conversation_analyzer.py`

## 감사 노트
검토 범위: agent.py 전체(구독자 _redis_subscriber, 요약 _build_conversation_summary/background summary, 예산 check_ws_llm_budget 호출부, 공유/private 채널 분기, direct_request·slot_select·auto_trigger 처리)와 의존 함수(scheduling_round, rate_limit, manager, social.py publish, date_classify, graph.run_pipeline). 확인한 핵심 불변식: (1) _room_card_generating의 check(1225)+add(1236) 사이 await 없음 → 단일 워커 cooperative 모델에서 원자적, 주석 정확. (2) check_ws_llm_budget는 fixed-window INCR, redis 장애 fail-open, direct_request 진입부에서 1회 소비 — quick_classify+general call_gemini 모두 커버. (3) shared/user 채널 분기: 일반 메시지 echo는 req_vis 따름, 카드(vote/place/maedeup)는 의도적으로 항상 shared(주석 1052-1053) — 정상. (4) _emit_auto_trigger_greeting은 NameError/AttributeError/ImportError 재raise로 코딩오류 surface. (5) finally의 task cleanup·r.aclose 정상. 가장 영향 큰 신규 발견은 ws-agent-1(direct_request run_pipeline 미보호 예외 → WS 연결 절단, P1)과 ws-agent-5(subscriber read 실패 시 inbound 영구 중단, P2). ws-agent-2는 Codex 진행 중 5버그 #2와 동일(overlaps_codex=true). ws-agent-4는 memory의 project_pattern_skip_rejected_blindspot 및 해결점 P 백로그와 같은 영역이나 발현 조건(stalemate에서 trigger_author로 fallback)을 코드로 확정. Codex 담당 제외 영역(확정 NX락·location-first 분기)은 깊게 파지 않음.

## 발견 (활성)

### [P2] ws-agent-1 — direct_request 경로의 run_pipeline 미보호 예외가 WS 연결 전체를 끊음
`correctness/reliability` · conf 8/10 · ⤵ 강등됨(원래 P1)

- **위치**: `backend/app/api/ws/agent.py:966,1238,1447-1459`
- **메커니즘**: 1) 사용자가 AI 패널에 직접 메시지 입력(direct_request) → while True 루프 본문에서 run_pipeline(line 1238) 호출. 2) run_pipeline은 graph.py:347 GRAPH.ainvoke를 try/except 없이 호출 → 노드(LLM/DB/카카오) 예외가 그대로 전파. 3) agent_ws의 while True 루프(line 966)를 감싸는 except는 WebSocketDisconnect(line 1447) 단 하나뿐. 4) 그 외 모든 예외는 루프 밖으로 전파되어 finally(1449)가 실행 → stop_event.set + subscriber/auto_trigger task cancel + manager.remove + r.aclose로 WS 연결이 통째로 닫힘. 비교: _run_auto_trigger_pipeline은 line 663에서 try/except로 전체를 감싸 detached task만 죽고 연결은 유지됨 — direct_request만 무방비.
- **근거**: line 966 while True 본문에 except Exception 부재; line 1447 except WebSocketDisconnect만 존재; line 1238 run_pipeline 호출은 _room_card_generating finally(1242)만 있고 예외를 삼키지 않음; graph.py:347 GRAPH.ainvoke 미보호. _room_card_generating.discard는 finally로 처리되나 예외 자체는 전파됨.
- **영향**: 전시 인터랙티브 데모의 핵심 경로(사용자가 AI에게 직접 일정/장소 요청)에서 LLM rate limit·Gemini 5xx·카카오 장애·DB 일시오류 한 번에 사용자의 AI 패널 WS가 끊기고 재연결 전까지 AI 응답 불가. 동일 방의 다른 멤버는 영향 없으나 해당 사용자 세션은 중단.
- **제안 수정**: while True 루프 본문(payload 파싱 이후~카드 발행까지)을 try/except Exception으로 감싸 한 메시지 처리 실패가 연결을 끊지 않도록 하고, 실패 시 user_channel로 안내 메시지만 발행 후 continue. 최소한 run_pipeline 호출(1238)을 try/except로 감싸 graceful degrade.
- **검증 판단**: 구조적 사실은 확인됨: direct_request 경로의 run_pipeline은 try/finally만 있고 except 없음(agent.py:1331-1335, finally는 _room_card_generating.discard+slot cleanup만). while 루프(agent.py:1014)를 감싸는 유일한 핸들러는 except WebSocketDisconnect(agent.py:1447)뿐이며, 그 외 예외는 finally(agent.py:1449)로 흘러 WS 전체가 닫힘. _run_auto_trigger_pipeline이 except Exception으로 전체를 감싸(agent.py:724) detached task만 죽는 것과의 비대칭도 사실. 주장한 라인(1238)은 현재 1286/1332로 시프트됐으나 동일 경로. 그러나 주장의 핵심 mechanism("LLM rate limit·Gemini 5xx·카카오 장애가 노드→ainvoke로 전파되어 WS 끊김")은 노드/서비스 레벨 가드로 대부분 막힘: (1) call_gemini(gemini.py:65-89)는 ResourceExhausted(rate limit)·GoogleAPICallError(5xx)·bare Exception 모두 잡아 return "" degrade → LLM 경로 전파 없음. (2) 등록된 9개 graph 노드(graph.py:231-239) 전부 top-level try/except Exception→_handle_node_exception로 감쌈(place.py:609-610 카카오 포함, intent.py:200/302 등); _handle_node_exception(messaging.py:94-107)은 예외를 삼키고(re-raise 안 함) status=error set + friendly emit + return state, emit 실패도 재차 삼킴 → 카카오/DB 노드내부 예외도 graph 밖으로 전파 안 됨. (3) 라우터는 _has_node_error로 END 라우팅(graph.py:94,111,139). quick_classify(quick_classify.py:87-90)·check_ws_llm_budget(rate_limit.py:80,89)도 자체 try로 fail-safe. 따라서 주장의 P1 impact 묘사(LLM/카카오 한 번에 끊김)는 거짓에 가까움. 잔존 실위험은 노드 가드 밖 unguarded 호출(MessageReader.load_agent_context agent.py:1264/messages.py:46 try 없음, run_pipeline의 ensure_branded/_default_state/ GRAPH.ainvoke 진입단계, LangGraph 프레임워크 자체 예외)에 국한 — DB 커넥션 자체 장애 등 훨씬 드문 조건에서만 WS 단절. 구조적 비대칭과 잔존 결함은 실재하나 트리거 조건·빈도가 주장보다 좁아 P1→P2 다운그레이드.

### [P2] ws-agent-5 — _redis_subscriber read 실패 시 루프 break → 해당 연결 inbound 영구 중단
`resource/reliability` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/ws/agent.py:714-744`
- **메커니즘**: pubsub.get_message(line 716)가 예외를 던지면 except에서 break(line 721)로 while 루프 종료 → finally에서 unsubscribe/close 후 task 종료. 그러나 agent_ws의 WS는 여전히 열려 있고 stop_event는 set되지 않음. 이후 정상 redis.publish는 성공하지만(=manager fallback 미발동) 이 연결의 subscriber가 죽어 send_text가 더는 호출되지 않아 카드/메시지가 클라이언트에 도달하지 않음. 재연결 전까지 inbound 무음.
- **근거**: line 719-721 except: logger.exception + break; finally(739)에서 pubsub/r 정리만; agent_ws는 subscriber_task 종료를 감지하지 않고 while True(line 966)에서 inbound 수신만 계속. _publish_agent_message(line 61-72)는 redis.publish 성공 시 manager.broadcast fallback 미수행.
- **영향**: 전시 중 일시적 redis read 오류로 한 사용자의 AI 패널이 메시지/카드 수신만 조용히 끊김(전송은 됨). 사용자는 멈춤으로 인식, 재진입 필요.
- **제안 수정**: subscriber read 예외 시 break 대신 재구독 재시도 또는 stop_event.set으로 연결을 명확히 종료(클라 재연결 유도). 혹은 subscriber_task에 done callback을 달아 비정상 종료 시 WS close.

### [P2] ws-agent-3 — detached auto-trigger 파이프라인 task에 강한 참조 미유지 (GC 회수 위험)
`resource` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/ws/agent.py:945-959`
- **메커니즘**: _run_auto_trigger_pipeline task를 asyncio.create_task로 생성(line 945) 후 지역변수 task에만 보관하고 add_done_callback(_log_detached_task_result)만 붙임. 지역변수는 다음 큐 dequeue 반복에서 덮어써짐. 같은 파일의 다른 fire-and-forget(line 1139-1141 summary task)은 명시적으로 _background_tasks set에 add하고 done 시 discard하는데, 이 핵심 파이프라인 task는 그 패턴을 따르지 않음. add_done_callback은 task에 대한 강한 참조를 유지하지 않음.
- **근거**: line 955 add_done_callback만 존재, _background_tasks.add 없음. 대조: line 758 주석 'GC가 mid-execution에 task를 회수' 경고 + line 1140 _background_tasks.add(_summary_task)로 동일 위험 방어. auto-trigger task는 같은 방어 미적용.
- **영향**: 이론상 이벤트루프가 task 참조를 잃으면 GC가 실행 중 파이프라인을 회수해 카드 생성이 조용히 중단될 수 있음. 실제로는 asyncio 구현이 pending task를 일부 참조 유지하므로 발현은 드물지만, 프로젝트 자체 fix 규칙과 불일치하는 잠재 누락.
- **제안 수정**: summary task와 동일하게 task를 connection-scope set(_background_tasks)에 add하고 add_done_callback에서 discard. _log_detached_task_result 호출과 병행 가능.

### [P2] ws-agent-4 — user=null 거부날짜가 트리거 발화자에게 일괄 귀속 → 타인의 unavailability 오기록
`data-integrity/privacy` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/ws/agent.py:301-348,485-490; date_classify.py:357-360`
- **메커니즘**: _run_auto_trigger_pipeline이 trigger_reason 무관하게 _sync_chat_rejected_to_unavailability를 speaker_user_id=viewer_user_id(=trigger 발화자, line 489)로 호출. signals.rejected_dates는 conversation_analyzer가 전체 대화에서 추출하며, 화자 미상 시 to_rejected_dates가 user=None 항목 생성(date_classify.py:360). _toggle_and_publish는 user 이름 매핑 실패 또는 user=null 항목을 speaker_user_id로 fallback(line 312-313) → 발화자 본인이 거부하지 않은 날짜(다른 멤버 A가 '금요일 안돼'라 했으나 이름 미명시)를 trigger 발화자 B의 unavailability로 기록.
- **근거**: line 312-313 elif speaker_user_id is not None: uid = speaker_user_id; line 489 speaker_user_id=viewer_user_id; date_classify.py:357-360 화자 미상 시 user=None; stalemate 경로는 trigger_author_id가 resolve됨(agent.py:924-930)이라 fallback 발동 가능.
- **영향**: compute_majority_slot의 per-date 차단 임계에 영향(blocked_by_date) → 잘못된 멤버가 불가로 표시되어 다수결 슬롯 계산 왜곡, peer_unavailable_update가 엉뚱한 user_id로 broadcast되어 TimeBar에 타인 불가 잘못 표시. (memory project_pattern_skip_rejected_blindspot + 해결점 P 백로그로 인지된 영역이나 발현 조건 명시.)
- **제안 수정**: user=null 항목은 speaker_user_id fallback을 stalemate 등 '발화자=거부자'가 보장되는 경우로 한정하거나, conversation_analyzer가 화자 귀속 실패한 날짜는 sync 대상에서 제외(reflect-back으로만 확인). 최소한 fallback 적용 시 로그/가드 추가.

### [P2] ws-agent-6 — detached 파이프라인이 shallow-copy(sc)만 변경 → 연결 slot_context로 결과 미전파
`correctness` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/ws/agent.py:913-952,608-624`
- **메커니즘**: _process_auto_triggers가 sc=dict(slot_context)(line 913, shallow)를 _run_auto_trigger_pipeline에 전달. 파이프라인은 sc(=local slot_context 파라미터)에만 confirmed_date/confirmed_time/slot_filling_turns 등을 기록(line 608-624)하고 결과를 연결의 slot_context로 되돌리지 않음. detached task라 호출 직후 함수가 반환되어 동기적 propagation 경로도 없음.
- **근거**: line 913 sc = dict(slot_context); line 945 _run_auto_trigger_pipeline(... sc ...); 파이프라인 내부 line 608-623은 slot_context(=sc) 키만 갱신; 호출부에 sc→slot_context 병합 코드 부재.
- **영향**: auto-trigger(예: all_members_selected로 일정 확정)가 끝나도 연결의 slot_context.confirmed_date/time은 여전히 None. 이후 같은 사용자의 direct_request가 확정된 슬롯을 이어받지 못해 재질문/재추출 발생 가능. 단일 워커·다중 멤버 환경에서 진행상태 유실.
- **제안 수정**: detached 결과를 연결 slot_context로 되먹이려면 task 완료 콜백에서 주요 confirmed_* 키를 병합하거나, slot_context를 연결-공유 가변 객체 대신 방-스코프 redis 상태로 통일. 최소한 의도된 trade-off면 주석 명시.

### [P3] ws-agent-7 — consensus_label 종료시각 off-by-one (마지막 셀 도달 시 30분 누락)
`correctness` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/ws/agent.py:172-173`
- **메커니즘**: best run의 inclusive end slot에서 exclusive 종료시각을 만들 때 end_idx = min(best_end+1, TIME_SLOT_MAX-1) = min(best_end+1, 25)로 클램프(line 172). 표준 변환(scheduling_round._format_slot:596)은 slot_idx_to_time(end_idx+1)을 클램프 없이 사용. run이 마지막 셀(slot 25, 21:30~22:00)까지 가면 exclusive end는 slot 26(=22:00)이어야 하나 25(=21:30)로 클램프되어 30분 손실.
- **근거**: line 172 min(best_end + 1, sr.TIME_SLOT_MAX - 1); scheduling_round.py:38 TIME_SLOT_MAX=26, line 596 slot_idx_to_time(end_idx+1) 클램프 없음; slot_idx_to_time(25)=21:30, (26)=22:00.
- **영향**: all_members_selected greeting narration 및 manual_chosen_time 부재 시 fallback confirmed_time 힌트가 '...~21:30'로 표시(실제 22:00까지). 표시·힌트용이라 확정 시간 자체는 slot.py가 manual_chosen_time/majority로 재계산하므로 데이터 손상 아님. 마지막 셀 경계에서만 발현.
- **제안 수정**: min(best_end + 1, sr.TIME_SLOT_MAX)로 수정(exclusive end는 26까지 허용) 또는 _format_slot 재사용.

### [P3] ws-agent-8 — record_unavailable_toggle 비원자 read-modify-write로 동시 토글 유실 가능
`race` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/scheduling_round.py:749-771; backend/app/api/ws/agent.py:317-323`
- **메커니즘**: record_unavailable_toggle는 hget→파싱→set 수정→hset(line 751-767) 사이에 await가 있어 원자적이지 않음. 같은 (room,user)에 대해 detached auto-trigger sync(agent.py:317)와 social.py 직접 토글이 거의 동시에 실행되면 한쪽 갱신이 덮어써져 날짜 추가/제거 1건 유실 가능(lost update).
- **근거**: line 751 hget, line 767 hset 사이 await 다수; 동일 user에 대한 동시 호출 보호(락/WATCH/Lua) 부재.
- **영향**: 드물게 사용자의 불가 날짜 토글 1건이 사라져 TimeBar/다수결에 반영 누락. 데모 happy path(순차 입력)에서는 미발현.
- **제안 수정**: redis WATCH/MULTI 또는 Lua 스크립트로 원자화, 혹은 per-(room,user) 짧은 락. 데모 영향 적어 운영 단계 처리 가능.

### [P3] ws-agent-9 — 방 탈퇴(/leave) 후에도 기존 WS가 shared 채널 수신 지속 (membership 연결시 1회만 검증)
`security/privacy` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/ws/agent.py:770-786; backend/app/api/routes/rooms.py:751`
- **메커니즘**: agent_ws는 connect 시점에 RoomMember 존재만 1회 확인(line 774-783). 이후 rooms.py:751 sa_delete(RoomMember)로 멤버가 방을 떠나도 기존 WS 연결은 stop되지 않아 shared agent:{room} 채널 메시지(카드·요약·타 멤버 발화 에코)를 계속 수신.
- **근거**: line 774-783 멤버십 1회 검증 후 재검증 경로 없음; rooms.py:751 RoomMember 삭제 존재; subscriber/슬롯 처리에 멤버십 재확인 부재.
- **영향**: 탈퇴한 사용자가 소켓을 닫기 전까지 방의 AI 패널 스트림을 열람. 자발적 탈퇴라 위험 제한적이나, 강제 추방 시나리오에서는 데이터 노출. 데모 영향 없음.
- **제안 수정**: 멤버 삭제 시 해당 user_channel/연결에 종료 신호 publish하거나, 주기적/메시지마다 경량 멤버십 재검증. 운영 단계 검토.

## 검증에서 기각된 항목 (false positive)

### ~~ws-agent-2 — all_members_selected 트리거가 NX락+로컬 debounce 모두 우회 → 연결 N명이 각자 파이프라인 실행~~ (원래 P0)
- 주장: social.py publish_schedule_auto_trigger가 trigger_reason='all_members_selected'를 shared 채널 agent:{room}에 publish(social.py:165). agent.py _redis_subscriber는 연결마다 동일 shared 채널 구독 → N명의 _process_auto_triggers가 같은 트리거를 각자 dequeue(line 735-736). is_user_explicit_confirm=(reason=='all_members_selected')(line 865)이 True면 acquired=True로 NX락 우회(line 873-874) + 로컬 debounce도 예외(line 895) → N개의 _run_auto_trigger_pipeline detached task가 동시에 run_pipeline 실행.
- 기각 사유: 주장의 핵심 메커니즘("NX락 무조건 우회 → acquired=True → N명 동시 실행")이 실제 코드와 정반대다. 주장이 인용한 line 번호(864-904, 873-874 "무조건 acquired=True", 895 debounce skip)는 현재 파일과 어긋나며, 실제 로직은 agent.py:890-983에 있다.

반증 근거:
1) agent.py:890 is_user_explicit_confirm=(reason=='all_members_selected'). 이 분기에서 NX락을 우회하지 않고 오히려 별도 1회성 소비락을 획득한다. agent.py:931-950 — build_auto_trigger_lock_key로 키 생성 후 r.set(nx_key, str(user_id_check), nx=True, ex=300)(line 940)으로 NX락 시도.
2) build_auto_trigger_lock_key (agent.py:52-53): all_members_selected는 `nx_confirm_consume:{room_id}:{snapshot_hash}` 키 사용 → 같은 snapshot에 대해 room 전체에서 단 1명만 NX 승자.
3) Redis 부재 시 agent.py:950 → _try_local_confirm_consume_lock(agent.py:57-69) 로컬 dict 기반 1회성 소비락으로 폴백.
4) agent.py:965-970: `if not acquired: continue` — NX 패배자는 _run_auto_trigger_pipeline(line 1026-1037)에 도달하지 못하고 skip. 즉 N명 중 1명만 파이프라인 실행.
5) line 974의 "debounce 예외"는 NX락 통과 *이후*의 belt-and-suspenders 로컬 debounce일 뿐. all_members_selected는 NX 소비락(snapshot 기반)이 이미 1회성을 보장하므로 로컬 debounce 예외가 의도된 설계.
6) 이중 가드: social.py:148-151 publish_schedule_auto_trigger 자체가 `schedule_auto_trigger_fired:{room_pk}:{snapshot_hash}` NX로 idempotent — 같은 snapshot은 애초에 1번만 publish.

주장이 제안한 fix("별도 1회성 소비락")가 이미 agent.py:52-53,931-950에 구현되어 있다. "NX락 우회" "무조건 acquired=True"는 코드에 존재하지 않으며, 묘사된 N명 동시 실행을 막는 NX 소비락+패배자 skip이 명확히 존재한다. confidence 9 주장이지만 인용 line이 실제 코드와 불일치하고 핵심 가드를 누락했다. false_positive.
