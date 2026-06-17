# 코드 감사: WS social.py: 날짜·시간 선택, 스냅샷, 합의 감지, 미가용 sync

> 영역키 `ws-social` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/api/ws/social.py`
- `backend/app/api/ws/manager.py`
- `backend/app/services/scheduling_round.py`
- `backend/app/api/ws/agent.py`
- `backend/app/api/routes/rooms.py`
- `frontend/src/components/meeting/TimeBarSelector.tsx`
- `frontend/src/hooks/useSocialWebSocket.ts`
- `frontend/src/contexts/MeetingContext.tsx`

## 감사 노트
검토 범위: social.py 전체(801줄) + manager.py(30줄) + 의존 헬퍼 scheduling_round.py(869줄) + 소비측 agent.py(majority/timebar 구간) + 프론트 TimeBarSelector/useSocialWebSocket/MeetingContext. 데이터 흐름 양방향(WS in→Redis→agent 파이프라인, snapshot 복원→프론트) 추적 완료.\n\n확인한 핵심 불변식(정상): (1) time_selection start/end는 프론트·백엔드 모두 inclusive slot(0..25), TIME_SLOT_MAX=26 일치(social.py:391 ↔ TimeBarSelector.tsx:15). (2) sender/user_id는 서버 인증값만 사용(스푸핑 방지, social.py:418-424,535). (3) 룸 멤버십 검증 후에만 채널 join(283-289), 비멤버 4003 차단 — IDOR 없음. (4) _maybe_emit_proposal의 member_user_ids 필터(100)로 탈퇴 유저 잔재 카운트 제외, member_count<2 솔로 가드(79). (5) snapshot NX dedup(108)·conclusion idem(665)·auto_trigger NX(149)로 중복 발행 방어. (6) _redis_subscriber self-echo는 프론트 guard(useSocialWebSocket.ts:611)로 무시. (7) finally에서 stop_event/subscriber_task/manager.remove/redis.aclose 정리 — 자원 누수 없음(social.py:589-595).\n\n주의: manager.broadcast(manager.py:20-26)는 단일 이벤트 루프 가정 하 순차 await라 race 없으나, 멀티워커 환경에선 in-memory rooms가 워커별 분리 — 다만 평시 redis publish 경로를 쓰고 manager.broadcast는 redis 장애 fallback이라 영향 제한적.\n\n[Codex 5버그와의 겹침] 본 영역 발견은 모두 비겹침(overlaps_codex=false). Codex 항목2(all_members_selected NX 우회)는 publish_schedule_auto_trigger의 NX(social.py:149)와 인접하나, 본 ws-social-1/2/4는 다른 결함(합의 판정 기준 불일치·unavailable broadcast 정합성·majority None silent). schedule_finalized 발행(Codex 항목1) 구간은 social.py에 없어 검토 제외.\n\n신뢰도 보정: ws-social-1은 프론트 단일 셀 전송 가능성을 handleSlotClick 분기로 확인했으나 실제 UI에서 더블클릭 빈도가 낮아 confidence 7. ws-social-4/5는 데모(겹치게 유도)에선 잘 안 보이는 자유체험존 엣지라 6/5.

## 발견 (활성)

### [P2] ws-social-1 — 단일 슬롯(start==end) 선택자가 있으면 _is_explicit가 그를 미선택으로 보아 consensus 영구 차단 — 합의 감지와 실제 시간 산출 로직 불일치
`correctness` · conf 7/10 · ⤵ 강등됨(원래 P1)

- **위치**: `backend/app/api/ws/social.py:88-103, backend/app/services/scheduling_round.py:680-695, backend/app/api/ws/agent.py:136-143`
- **메커니즘**: 1) 프론트 TimeBarSelector.handleSlotClick(322-339): 한 셀 클릭 후 같은 셀을 다시 클릭하면 selectionEnd===null && slotIndex>=selectionStart 분기를 타 selectionEnd=slotIndex가 되어 selectionStart==selectionEnd(단일 셀)가 가능. 2) sendTimeSelection(useSocialWebSocket.ts:823-827)이 start==end를 그대로 WS time_selection으로 전송. 3) social.py _to_slot은 0..25 inclusive를 허용하므로 단일 셀 통과 → record_availability가 {start:n,end:n} 저장. 4) _maybe_emit_proposal의 _is_explicit(88-93)는 'int(end) > int(start)'인 entry가 하나라도 있어야 explicit으로 카운트 → 단일 셀만 가진 유저는 explicit_count에서 제외 → explicit_count < member_count(102) 영구 참 → consensus_ready 노티가 절대 발화 안 됨. 5) 반면 실제 시간 산출 경로(agent.py:136-143, scheduling_round.py compute_majority_slot:665)는 range(s,e+1)로 단일 셀도 정상 슬롯으로 처리. 즉 합의 감지측과 산출측의 '선택했다' 기준이 불일치.
- **근거**: social.py:91 `if isinstance(e, dict) and int(e.get('end', 0)) > int(e.get('start', 0))` — strict greater라 start==end 제외. 반면 agent.py:136 `for slot_idx in range(start_idx, end_idx + 1)` 와 scheduling_round.py:665 `for idx in range(s, e + 1)` 는 단일 셀(s==e)도 1개 셀로 포함. 프론트는 단일 셀 전송을 막지 않음(useSocialWebSocket.ts:823-827 무조건 send).
- **영향**: 한 멤버라도 30분(단일 셀)만 선택하면 '전원 선택' 합의 노티가 호스트에게 영영 뜨지 않아 확정하기 버튼이 노출 안 됨 → 시간 조율 흐름 교착. 시연 중 의도치 않은 단일 셀 클릭으로 재현 가능.
- **제안 수정**: _is_explicit 기준을 majority/agent 측과 통일: 단일 셀도 명시 선택으로 인정하려면 `int(e.get('end',0)) >= int(e.get('start',0))` 또는 entry 존재만으로 카운트(server prefill 잔재 구분이 목적이면 prefill을 별도 마커로 식별). 또는 프론트에서 단일 셀 선택을 금지/2셀 최소 강제. 두 경로의 '선택 유효성' 정의를 단일 helper로 공유.
- **검증 판단**: 메커니즘 본체는 코드상 사실로 확인됨. (1) social.py:91 `_is_explicit`가 strict `>`라 start==end 단일 셀을 explicit에서 제외 → explicit_count < member_count(social.py:102) early-return → schedule_consensus_ready 노티 미발화. (2) record_availability(scheduling_round.py:543)는 단일 셀을 {date,start:n,end:n}으로 정상 저장하고, _to_slot(social.py:432-443)은 0..25만 검사할 뿐 start==end를 막지 않으며 start==end시 swap도 없이 그대로 _maybe_emit_proposal에 전달(social.py:445-481). (3) 프론트 handleSlotClick(TimeBarSelector.tsx:326-328)에서 같은 셀 재클릭 시 selectionEnd=slotIndex로 start==end 생성 가능, sendTimeSelection effect(TimeBarSelector.tsx:254)는 selectionEnd===null만 보류하므로 단일 셀(end!==null)은 useSocialWebSocket.ts:823-827로 무조건 전송됨. (4) 산출측 compute_majority_slot(scheduling_round.py:665 range(s,e+1))·agent.py:158-159는 단일 셀을 inclusive로 정상 처리 → 감지측(strict >)과 산출측(inclusive)의 '선택했다' 기준 불일치 실재. 여기까지 false_positive 아님.

그러나 impact가 과장됨 → 다운그레이드. 주장은 "확정하기 버튼이 영영 노출 안 됨 → 시간 조율 흐름 교착"이라 했으나, consensusReached===false일 때 TimeBarSelector.tsx:760-794의 일반 확정 버튼(handleConfirm→onConfirm)이 합의 노티와 완전 독립으로 노출되고, InfoPane.tsx:164-201 handleTimeConfirm이 POST /api/v1/meetings/confirm을 직접 호출해 일정 확정이 가능함. 즉 막히는 것은 '전원 합의 자동 감지→호스트 in-card 확정→AI 자동 장소 정리' 자동화 흐름뿐이고 시간 확정 자체는 우회 가능. 또한 영구성도 과장: handleSlotClick(TimeBarSelector.tsx:334-337)에서 다른 셀 또는 재클릭으로 2셀+ 범위가 되면 즉시 해소되므로 '그 단일 셀 상태인 동안만' 노티 미발화. 덧붙여 social.py:87 주석의 'server prefill 잔재' 가정은 코드와 어긋남 — availability는 유저 time_selection으로만 기록되고 availability_snapshot(social.py:376-394)은 기존 선택 echo일 뿐 단일 셀 자동 주입 경로는 없음. 정합성 결함(두 경로 유효성 정의 불일치)은 실재하나 사용자 차단 영향이 '자동화 흐름 일부 미발화 + 수동 확정 우회 가능'으로 제한되므로 P1→P2.

### [P2] ws-social-2 — record_unavailable_toggle가 Redis 장애 시 빈 리스트를 반환 → social이 그 []를 broadcast → 타 클라이언트가 해당 유저의 불가능 날짜 전체를 화면에서 삭제
`data-integrity` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/scheduling_round.py:772-777, backend/app/api/ws/social.py:464-484, frontend/src/hooks/useSocialWebSocket.ts:687-699`
- **메커니즘**: 1) record_unavailable_toggle는 정상 마지막-날짜-제거 케이스와 Redis 예외 케이스 둘 다 빈 리스트 []를 반환(772-777 except 핸들러). 2) social.py:465는 반환된 dates_after를 그대로 peer_unavailable_update.dates로 broadcast(475-484). 3) 프론트 useSocialWebSocket.ts:692 `if (data.dates.length === 0) delete next[uid]` — 빈 배열이면 그 유저의 불가능 날짜 맵을 통째로 삭제. 따라서 Redis hget/hset이 일시 실패해 []가 나오면, 실제로는 여러 날짜를 막아둔 유저인데도 모든 피어 화면에서 그 유저의 빨간 테두리(불가능)가 사라짐. 게다가 Redis에는 실제 값이 남아있어(쓰기 실패) 서버 스냅샷 복원과 화면이 불일치.
- **근거**: scheduling_round.py:773-777 except 블록이 `return []` — 성공 시 빈 리스트(마지막 제거)와 실패 시 빈 리스트가 구분 불가. social.py:465 `dates_after = await sr.record_unavailable_toggle(...)` 후 484에서 무검증 broadcast. useSocialWebSocket.ts:692-693 빈 배열→delete.
- **영향**: Redis 일시 장애 중 누군가 토글하면 해당 유저의 모든 불가능 날짜 표시가 전 클라이언트에서 사라져 잘못된 가용성으로 합의/추천이 진행될 수 있음. 드문 장애 조건이지만 데이터 정합성 훼손.
- **제안 수정**: record_unavailable_toggle 실패 시 빈 리스트 대신 sentinel(None) 반환하거나 예외 전파. social.py에서 None이면 broadcast skip. 또는 broadcast 전에 load_room_unavailability로 실제 값 재조회해 신뢰 가능한 dates만 송신.

### [P2] ws-social-4 — compute_majority_slot/transient None일 때 social은 consensus_ready를 발화하지만 agent는 confirmed_time/manual_chosen_time 없이 파이프라인 진행 — silent 시간 누락
`edge-case` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/ws/social.py:97-130, backend/app/api/ws/agent.py:534-606`
- **메커니즘**: social _maybe_emit_proposal은 '전원이 explicit range 선택'(explicit_count>=member_count)만 보고 consensus_ready를 발화할 뿐, 슬롯이 실제로 겹치는지(과반/전원 교집합)는 검사하지 않음. 호스트가 확정 클릭 → schedule-confirm → ai_auto_trigger. agent.py:534-563에서 manual_chosen_time이 없으면 compute_majority_slot 호출하는데, 멤버들의 선택이 서로 겹치지 않으면(예: A는 10-11시, B는 19-20시) 과반 슬롯 없음 → majority_result None → manual_chosen_time 미설정. 이어 _build_entities_from_timebar(agent.py:142)는 '전원 교집합'(>= member_ids)을 요구 → 교집합 없으면 빈 dict → consensus_label 없음 → confirmed_time도 미설정(603-606). 결과적으로 시간 신호 없이 LangGraph slot_filling 진입.
- **근거**: social.py:102 `if explicit_count < member_count: return` — 겹침 여부 미검사. agent.py:547 `if majority_result is not None:` 만 처리(None 분기 없음). agent.py:145-146 `if not common_slots: return {}` (전원 교집합 없으면 빈 dict). agent.py:603-606 confirmed_time은 consensus_label 있을 때만 설정.
- **영향**: 전원이 시간은 골랐지만 서로 안 겹치는 정상적 갈등 상황에서, 합의 노티가 떠 호스트가 확정을 누르면 시간이 비어 파이프라인이 엉뚱하게 동작하거나(시간 없이 진행) narration 라벨 누락. 데모에선 겹치게 유도하므로 잘 안 보이나 자유체험존에서 발현 가능.
- **제안 수정**: _maybe_emit_proposal에서 consensus_ready 발화 전 compute_majority_slot(또는 교집합) 존재를 확인해 '겹치는 합의'에서만 노티. 또는 agent.py에서 majority None & timebar 빈 dict일 때 호스트에게 '겹치는 시간 없음' 안내 카드로 분기.

### [P3] ws-social-3 — cache-invalidate 블록의 except (NameError, AttributeError, ImportError): raise 가 graceful 의도와 모순 — 해당 예외 발생 시 unavailable_toggle 핸들러 전체가 죽음
`edge-case` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/ws/social.py:503-519`
- **메커니즘**: T6 free-slots cache invalidate 블록(503-519)이 try 내부에서 새 redis 연결을 열고 scan_iter/delete 후, except (NameError, AttributeError, ImportError): raise / except Exception: warning 구조를 가짐. 의도는 'graceful'(주석 519)인데, NameError/AttributeError/ImportError는 의도적으로 re-raise됨. 이 raise는 social_ws의 receive 루프(373 while True)를 빠져나가 except WebSocketDisconnect로 잡히지 않으므로(이 예외들은 WebSocketDisconnect 아님) finally로 직행 → 소켓 정리되고 연결 종료. 현재 코드상 _r_inv/_inv_key는 모두 try 내부에서 정의되므로 NameError 가능성은 낮으나, aioredis API 변경/부분 import 실패 시 AttributeError/ImportError로 정상 동작 중 연결이 끊길 수 있음.
- **근거**: social.py:516-517 `except (NameError, AttributeError, ImportError): raise` 가 바로 위 519의 `[T6_CACHE] invalidate 실패 (graceful)` 주석과 충돌. 이 raise는 상위에 try/except로 감싸여 있지 않아(불가능 토글 처리 블록은 while 루프 본문 직속) WS 루프를 종료시킴.
- **영향**: 정상 운영에선 거의 발현 안 하나, redis 클라이언트/모듈 상태 이상 시 cache invalidate 부수 작업 실패가 사용자 WS 연결을 끊어 재접속을 유발(가용성 broadcast/스냅샷 흐름 중단). fail-open 의도 위반.
- **제안 수정**: 재현 의도가 디버깅용이면 제거하고 모든 예외를 warning으로 흡수(graceful). cache invalidate는 best-effort 부수효과이므로 어떤 예외도 핸들러를 죽이면 안 됨.

### [P3] ws-social-5 — reconnect 스냅샷이 송신 소켓에만 전송되어 동일 user_id의 다중 탭/디바이스 접속 시 다른 탭은 최신 availability/date 스냅샷을 못 받음
`edge-case` · conf 5/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/ws/social.py:324-371`
- **메커니즘**: 접속 직후 unavailable/availability/date_selection 스냅샷은 websocket.send_text로 '방금 접속한 그 소켓에만' 전송(326-371). 이는 의도된 1회 복구. 그러나 같은 유저가 두 번째 탭/디바이스로 접속하면 두 번째 소켓도 자기 스냅샷은 받지만, 첫 탭에서 한 후속 변경은 peer_* broadcast로 받음(정상). 반대로 이미 접속해 있던 다른 멤버들은 신규 접속자의 '과거에 저장된' availability를 실시간으로 다시 받지 못함 — 신규 접속자가 새 time_selection을 보내야만 peer로 전파됨. 즉 신규 접속자가 아무 조작 없이 가만히 있으면, 그의 Redis에 남은 이전 선택은 기존 멤버 화면에 나타나지 않음(기존 멤버는 자기 접속 시점 스냅샷만 가짐).
- **근거**: social.py:339-357 availability_snapshot은 현재 소켓(websocket)에만 send. 신규 접속 시 다른 멤버에게 'user X의 저장된 선택'을 재broadcast하는 경로 없음. peer_time_selection은 오직 time_selection 수신 시에만 발행(384-428).
- **영향**: 여러 명이 시간차로 접속하는 일반적 흐름에서, 먼저 접속한 멤버 화면에 나중 합류자의 (이전 세션에 저장된) 가용성이 누락되어 집계/추천이 실제보다 적은 인원으로 계산될 수 있음. _maybe_emit_proposal은 Redis hash 기준이라 서버 집계는 맞지만 클라이언트 표시가 불일치.
- **제안 수정**: 신규 접속 시 해당 유저의 저장된 availability/date/unavailable을 채널 broadcast(peer_* 형태)로도 1회 발행하거나, 모든 클라이언트가 주기적으로 availability_snapshot을 재요청. 또는 컨센서스 노티에 by_user 분포를 포함해 클라이언트가 권위 데이터로 갱신.
