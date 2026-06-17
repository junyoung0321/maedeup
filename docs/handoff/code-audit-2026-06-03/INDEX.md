# 코드베이스 로직 감사 — INDEX (2026-06-03)

매듭 코드베이스 14영역 read-only 로직 감사. Codex가 수정 중인 멀티유저 5버그는 제외(겹치는 항목은 별도 표).
P0/P1은 적대적 검증자가 재확인(✅확정 / ⤵강등 / 기각). P2/P3는 미검증(1차 감사 의견).

- 활성 P0: **0** · P1: **3** · P2: **41** · P3: **46**
- 검증: 확정 3 · 강등 7 · 기각 0 · 추가확인 0 · 미검증(P2/P3) 80
- Codex 5버그 겹침 4 · 기각 1

## 영역별 문서
| # | 영역 | 활성 | 기각 | 문서 |
|---|---|---|---|---|
| 01 | 파이프라인: 슬롯 필링·시간 산출·랭킹 | 7 | 0 | [`01-pipeline-slot.md`](01-pipeline-slot.md) |
| 02 | 파이프라인: 엔티티 추출·의도 분류 | 7 | 0 | [`02-pipeline-entity-intent.md`](02-pipeline-entity-intent.md) |
| 03 | 파이프라인: 검증·매듭카드·메모리·function_call | 4 | 0 | [`03-pipeline-validation-maedeup.md`](03-pipeline-validation-maedeup.md) |
| 04 | 파이프라인: 그래프 라우팅·헬퍼 | 6 | 0 | [`04-pipeline-graph-helpers.md`](04-pipeline-graph-helpers.md) |
| 05 | WS social.py: 날짜·시간 선택, 스냅샷, 합의 감지, 미가용 sync | 5 | 0 | [`05-ws-social.md`](05-ws-social.md) |
| 06 | WS agent.py: 구독자·요약·예산·공유·일반 메시지 처리 | 8 | 1 | [`06-ws-agent.md`](06-ws-agent.md) |
| 07 | scheduling_round.py: 다수 슬롯·proposal 생명주기·투표·supersede | 5 | 0 | [`07-scheduling-round.md`](07-scheduling-round.md) |
| 08 | API: meetings.py(확정·장소 patch·캘린더 sync·취소)·finalization route | 6 | 0 | [`08-route-meetings.md`](08-route-meetings.md) |
| 09 | API: calendar.py(free-slots·busy·GCal)·recommendations·places route | 4 | 0 | [`09-route-calendar-reco.md`](09-route-calendar-reco.md) |
| 10 | API: rooms.py(멤버십·leave·host 이양·guest)·auth·chat share·intents 등 | 9 | 0 | [`10-route-rooms-auth.md`](10-route-rooms-auth.md) |
| 11 | 외부 서비스: kakao·gemini·llm·openai·ml·embedding·personal_data | 7 | 0 | [`11-services-external.md`](11-services-external.md) |
| 12 | 모델·core: SQLModel 모델·security·config·rate_limit·log_filters | 6 | 0 | [`12-models-core.md`](12-models-core.md) |
| 13 | 프론트 상태·훅: MeetingContext·useAgentWebSocket·useSocialWebSocket | 6 | 0 | [`13-fe-state-hooks.md`](13-fe-state-hooks.md) |
| 14 | 프론트 컴포넌트: TimeBar·Calendar·Info·VoteCard·Finalization·Place/Schedule 카드 등 | 10 | 0 | [`14-fe-components.md`](14-fe-components.md) |

## 활성 발견 마스터 (severity 정렬)
| sev | 영역 | id | 제목 | 위치 | conf | 검증 |
|---|---|---|---|---|---|---|
| P1 | scheduling_round.py: 다수  | slot-1 | 동시 투표 시 락 경합이 미처리 예외(SchedulingRoundError)로 새어 HTTP 500 발생 | `backend/app/services/scheduling_round.py:431-432, backend/app/api/routes/finalization.py:153-158` | 8 | ✅ 검증됨 |
| P1 | API: rooms.py(멤버십·leave· | chat-1 | GET /chat/messages: room_id 미지정 시 멤버십 검사 우회 → 전 방 메시지 IDOR | `backend/app/api/routes/chat.py:58-92` | 8 | ✅ 검증됨 |
| P1 | API: rooms.py(멤버십·leave· | chat-2 | GET /chat/messages: pane_type 미지정 시 타 유저 personal_assistant 대화 노출 | `backend/app/api/routes/chat.py:71-90` | 8 | ✅ 검증됨 |
| P2 | 모델·core: SQLModel 모델·sec | core-1 | HTTP rate limiter(check_rate_limit) 전혀 미사용 — 모든 REST 엔드포인트 무제한 | `backend/app/core/rate_limit.py:18-65` | 9 | 미검증(P2/P3) |
| P2 | 파이프라인: 엔티티 추출·의도 분류 | entity-2 | multi-date 경로에서 resolve 실패한 raw 한글 hint가 문자열 past-필터를 통과해 비-ISO 값으로 downstream 유입 | `backend/app/services/pipeline/nodes/entity.py:742-766` | 8 | 미검증(P2/P3) |
| P2 | WS agent.py: 구독자·요약·예산·공 | ws-agent-1 | direct_request 경로의 run_pipeline 미보호 예외가 WS 연결 전체를 끊음 | `backend/app/api/ws/agent.py:966,1238,1447-1459` | 8 | ⤵ 강등됨(원래 P1) |
| P2 | scheduling_round.py: 다수  | slot-2 | 과반 도달 후 표 변경(like→other)으로 과반이 깨져도 status가 majority_reached로 고정 → 호스트 확정 버튼 활성 유지, 클릭 시 409 | `backend/app/services/scheduling_round.py:441-443, frontend/src/components/meeting/FinalizationProposalCard.tsx:86,243-251, backend/app/api/routes/meetings.py:498-512` | 8 | 미검증(P2/P3) |
| P2 | API: meetings.py(확정·장소 p | route-meetings-1 | cancel_meeting authorizes by meeting.created_by (arbitrary pipeline member/guest), not room owner — inconsistent with confirm/place 권한 모델 | `backend/app/api/routes/meetings.py:1149, backend/app/services/pipeline/nodes/vote_card.py:147-173, backend/app/services/pipeline/nodes/vote_card.py:336-363` | 8 | ⤵ 강등됨(원래 P1) |
| P2 | API: calendar.py(free-sl | reco-1 | available-friends의 available_at은 UTC-naive인데 프론트는 KST-naive로 해석 → '곧 가능' 시간 9시간 오류 | `backend/app/api/routes/recommendations.py:60-63,77,79; frontend/src/lib/datetime.ts:11-14; frontend/src/components/home/AiRecommendCard.tsx:44; frontend/src/components/home/QuickMatchPopup.tsx:24` | 8 | ⤵ 강등됨(원래 P1) |
| P2 | API: calendar.py(free-sl | cal-1 | free-slots: Google 이벤트가 dateTime/date 둘 다 없으면 _get_busy_periods가 KeyError로 500 (my-events는 가드, free-slots는 미가드) | `backend/app/api/routes/calendar.py:143-156,466` | 8 | 미검증(P2/P3) |
| P2 | 외부 서비스: kakao·gemini·llm | embed-1 | embedding 실패 시 zero-vector를 IntentExample.embedding에 영구 저장 → RAG 예시 영구 오염 (seed/add는 success 보고) | `backend/app/services/embedding.py:17-33, backend/app/api/routes/intents.py:111-114, intents.py:144-152` | 8 | 미검증(P2/P3) |
| P2 | 모델·core: SQLModel 모델·sec | core-3 | JWT_SECRET 기본값 검증이 dev 환경에서 우회됨 — 운영자 실수 시 공개 시크릿로 서명 | `backend/app/core/config.py:14, 66-67, 83-84; docker-compose.yml:12` | 8 | 미검증(P2/P3) |
| P2 | 프론트 컴포넌트: TimeBar·Calend | schedule-1 | ScheduleRecommendationCard 비호스트에게 '확정하기' 버튼이 enable 상태로 노출 — 클릭 시 서버 403 | `frontend/src/components/meeting/ScheduleRecommendationCard.tsx:604-617` | 8 | 미검증(P2/P3) |
| P2 | 파이프라인: 슬롯 필링·시간 산출·랭킹 | slot-1 | F1 다수결 fallback 슬롯의 total_count 분모가 정상 경로(BUG-26-D)와 불일치 — 캘린더 미동의 멤버가 누락된 비율 표시 | `backend/app/services/pipeline/helpers/slots.py:264, backend/app/services/pipeline/nodes/function_call.py:236-246` | 7 | 미검증(P2/P3) |
| P2 | 파이프라인: 검증·매듭카드·메모리·funct | memory-1 | Gemini 추출 value=list가 str 컬럼(time_preference/transport_mode)에 setattr → commit 실패 → 전체 추출 배치 silent rollback | `backend/app/services/pipeline/nodes/memory.py:197,203; backend/app/services/personal_data_extractor.py:75; backend/app/models/user.py:24-25` | 7 | 미검증(P2/P3) |
| P2 | 파이프라인: 그래프 라우팅·헬퍼 | dates-2 | 요일 경로와 일(日) 경로의 '오늘' 처리 불일치 (요일은 +7 미룸, 일은 당일 허용) | `backend/app/services/pipeline/helpers/dates.py:230-260,158-162` | 7 | 미검증(P2/P3) |
| P2 | WS social.py: 날짜·시간 선택,  | ws-social-1 | 단일 슬롯(start==end) 선택자가 있으면 _is_explicit가 그를 미선택으로 보아 consensus 영구 차단 — 합의 감지와 실제 시간 산출 로직 불일치 | `backend/app/api/ws/social.py:88-103, backend/app/services/scheduling_round.py:680-695, backend/app/api/ws/agent.py:136-143` | 7 | ⤵ 강등됨(원래 P1) |
| P2 | WS social.py: 날짜·시간 선택,  | ws-social-2 | record_unavailable_toggle가 Redis 장애 시 빈 리스트를 반환 → social이 그 []를 broadcast → 타 클라이언트가 해당 유저의 불가능 날짜 전체를 화면에서 삭제 | `backend/app/services/scheduling_round.py:772-777, backend/app/api/ws/social.py:464-484, frontend/src/hooks/useSocialWebSocket.ts:687-699` | 7 | 미검증(P2/P3) |
| P2 | WS agent.py: 구독자·요약·예산·공 | ws-agent-5 | _redis_subscriber read 실패 시 루프 break → 해당 연결 inbound 영구 중단 | `backend/app/api/ws/agent.py:714-744` | 7 | 미검증(P2/P3) |
| P2 | API: meetings.py(확정·장소 p | route-meetings-2 | patch_meeting_place: Kakao search_keyword 결과가 사용자가 명시한 body.name 을 무조건 덮어씀 | `backend/app/api/routes/meetings.py:991, backend/app/api/routes/meetings.py:1011-1020` | 7 | 미검증(P2/P3) |
| P2 | API: meetings.py(확정·장소 p | route-meetings-3 | refresh_recommendations: idempotency 캐시가 pipeline 이후에만 SET → 동시 동일 요청이 락 없이 중복 run_pipeline + 중복 broadcast | `backend/app/api/routes/meetings.py:1357-1424, backend/app/api/routes/meetings.py:1481-1492` | 7 | 미검증(P2/P3) |
| P2 | API: meetings.py(확정·장소 p | route-meetings-5 | confirm_meeting meeting_id 승격 경로: 다른 user 가 만든 pending 을 host 가 확정해도 created_by 보존 → 이후 cancel 권한이 host 에게서 분리됨 (finding-1 연쇄) | `backend/app/api/routes/meetings.py:522-543` | 7 | 미검증(P2/P3) |
| P2 | API: rooms.py(멤버십·leave· | chat-3 | POST /chat/messages: 클라이언트가 user_id·sender·visibility·role을 임의 지정(메시지 위조) | `backend/app/api/routes/chat.py:95-117` | 7 | 미검증(P2/P3) |
| P2 | API: rooms.py(멤버십·leave· | rooms-1 | leave_room 호스트 이양 분기에서 떠나는 호스트의 캘린더 이벤트 정리 누락 → 고아 google_event_ids + 미삭제 GCal 이벤트 | `backend/app/api/routes/rooms.py:656-756` | 7 | 미검증(P2/P3) |
| P2 | 프론트 상태·훅: MeetingContext | hooks-2 | availability_snapshot / date_selection_snapshot 머지 순서가 stale peer를 덮어쓰지 못함 | `frontend/src/hooks/useSocialWebSocket.ts:652, 670` | 7 | 미검증(P2/P3) |
| P2 | 프론트 컴포넌트: TimeBar·Calend | votecard-1 | handleConfirmSchedule useCallback가 isPlaceConfirmed를 stale 캡처 — 일정 마지막 확정 시 'done' 전이 누락 | `frontend/src/components/meeting/VoteCardSection.tsx:204, 212` | 7 | 미검증(P2/P3) |
| P2 | 파이프라인: 슬롯 필링·시간 산출·랭킹 | slot-2 | date_hint 지정 시 extended 전략이 요청 날짜 외 날짜(+7~14일) 슬롯을 반환 — confirmed_date(요청일)와 슬롯 실제 날짜 불일치 가능 | `backend/app/services/pipeline/helpers/slots.py:513-519,566-640, backend/app/services/pipeline/nodes/vote_card.py:259-260` | 6 | 미검증(P2/P3) |
| P2 | 파이프라인: 슬롯 필링·시간 산출·랭킹 | slot-3 | _find_free_slots available_count가 검증되지 않은 비동의 멤버를 '가능'으로 합산 (headcount_total > 동의 인원) | `backend/app/services/pipeline/helpers/slots.py:183,200,202-206` | 6 | 미검증(P2/P3) |
| P2 | 파이프라인: 엔티티 추출·의도 분류 | intent-2 | 임베딩 실패/키 부재 시 zero-vector 반환 → 모든 코사인 유사도 0 → intent confidence 0으로 silent degradation | `backend/app/services/embedding.py:14-33, backend/app/services/intent_classifier.py:38-46,82,90` | 6 | 미검증(P2/P3) |
| P2 | 파이프라인: 엔티티 추출·의도 분류 | entity-3 | AI 패널 경로의 recent_messages는 'role: content' 직렬화라 date_classify 화자 귀속(_SPEAKER_LINE)이 무력화 | `backend/app/services/pipeline/state.py:284-287,300-301; backend/app/services/pipeline/helpers/date_classify.py:55-56,68-74` | 6 | 미검증(P2/P3) |
| P2 | 파이프라인: 그래프 라우팅·헬퍼 | graph-1 | _route_after_validation 라우터가 state를 in-place mutate (partial_mode) — LangGraph 안티패턴, 현재는 노드 중복 set으로 마스킹 | `backend/app/services/pipeline/graph.py:145-147` | 6 | 미검증(P2/P3) |
| P2 | WS social.py: 날짜·시간 선택,  | ws-social-4 | compute_majority_slot/transient None일 때 social은 consensus_ready를 발화하지만 agent는 confirmed_time/manual_chosen_time 없이 파이프라인 진행 — silent 시간 누락 | `backend/app/api/ws/social.py:97-130, backend/app/api/ws/agent.py:534-606` | 6 | 미검증(P2/P3) |
| P2 | WS agent.py: 구독자·요약·예산·공 | ws-agent-3 | detached auto-trigger 파이프라인 task에 강한 참조 미유지 (GC 회수 위험) | `backend/app/api/ws/agent.py:945-959` | 6 | 미검증(P2/P3) |
| P2 | WS agent.py: 구독자·요약·예산·공 | ws-agent-4 | user=null 거부날짜가 트리거 발화자에게 일괄 귀속 → 타인의 unavailability 오기록 | `backend/app/api/ws/agent.py:301-348,485-490; date_classify.py:357-360` | 6 | 미검증(P2/P3) |
| P2 | WS agent.py: 구독자·요약·예산·공 | ws-agent-6 | detached 파이프라인이 shallow-copy(sc)만 변경 → 연결 slot_context로 결과 미전파 | `backend/app/api/ws/agent.py:913-952,608-624` | 6 | 미검증(P2/P3) |
| P2 | scheduling_round.py: 다수  | slot-3 | 확정 시 votes가 현재 멤버십과 대조 정리되지 않아 탈퇴 멤버의 stale like가 과반 판정에 잔존 | `backend/app/services/scheduling_round.py:113-114,131-140,485-488, backend/app/api/routes/meetings.py:492-505` | 6 | 미검증(P2/P3) |
| P2 | 프론트 상태·훅: MeetingContext | hooks-1 | WS 훅 재연결 effect가 roomId만 의존 — sender 변경 시 stale closure로 잘못된 이름 broadcast | `frontend/src/hooks/useSocialWebSocket.ts:801, frontend/src/hooks/useAgentWebSocket.ts:631` | 6 | 미검증(P2/P3) |
| P2 | 프론트 상태·훅: MeetingContext | hooks-3 | finalization_vote_update가 proposal보다 먼저 도착하면 deadline_at/created_at이 0으로 소실 | `frontend/src/hooks/useSocialWebSocket.ts:579-580` | 6 | 미검증(P2/P3) |
| P2 | 프론트 컴포넌트: TimeBar·Calend | context-1 | setVoteCard의 phaseAlreadyAdvanced에 dateConfirmed 포함 — 다른 meeting의 새 vote_card 도착 시 옛 날짜 TimeBar에 멈춤 | `frontend/src/contexts/MeetingContext.tsx:340-356` | 6 | 미검증(P2/P3) |
| P2 | 프론트 컴포넌트: TimeBar·Calend | aipane-1 | activeVoteCard/activePlaceRecommendation을 meeting 무관하게 각각 '마지막 카드'로 선택 — 서로 다른 meeting 카드 혼합 가능 | `frontend/src/components/meeting/AiAssistantPane.tsx:139-148, 185-194` | 6 | 미검증(P2/P3) |
| P2 | 프론트 상태·훅: MeetingContext | ctx-4 | MeetingContext.setVoteCard가 voteUpdate를 초기화하지 않아 새 meeting 카드에 이전 meeting의 투표 카운트가 잠시 잔존 | `frontend/src/contexts/MeetingContext.tsx:327-360, frontend/src/components/meeting/AiAssistantPane.tsx:184-190` | 5 | 미검증(P2/P3) |
| P3 | 파이프라인: 그래프 라우팅·헬퍼 | formatting-1 | _format_slot_label 12시간제 변환에서 0시/12시 표기 부정확 (WORK_HOUR 범위 밖이라 비발현) | `backend/app/services/pipeline/helpers/formatting.py:22-23,35` | 8 | 미검증(P2/P3) |
| P3 | scheduling_round.py: 다수  | slot-4 | record_availability/load_room_availability는 유저당 단일 슬롯만 지원 — compute_majority_slot의 다중 슬롯 처리 코드가 사실상 사문화 | `backend/app/services/scheduling_round.py:523-545,553-572,644-666` | 8 | 미검증(P2/P3) |
| P3 | 모델·core: SQLModel 모델·sec | core-2 | check_rate_limit이 request.state.user_sub에 의존하나 어디서도 세팅 안 함 → 항상 IP 폴백 | `backend/app/core/rate_limit.py:29-31` | 8 | 미검증(P2/P3) |
| P3 | 파이프라인: 슬롯 필링·시간 산출·랭킹 | slot-5 | slot_ranker._lead_time_score 비단조 — days=3(0.9)이 days=4(0.95)보다 낮아 추천 순위 역전 가능 | `backend/app/services/slot_ranker.py:90-102` | 7 | 미검증(P2/P3) |
| P3 | 파이프라인: 엔티티 추출·의도 분류 | intent-1 | stalemate judge 쿨다운이 LLM 호출 *후*에 설정 → 동시 메시지가 중복 ai_auto_trigger 발행 (TOCTOU) | `backend/app/api/ws/social.py:741-786` | 7 | ⤵ 강등됨(원래 P1) |
| P3 | 파이프라인: 엔티티 추출·의도 분류 | entity-1 | 비-pre_extracted entity 경로에 rejected_dates→conflict_options/date_hints 필터링 누락 (pre 경로와 비대칭) | `backend/app/services/pipeline/nodes/entity.py:798-844 (누락) vs 538-575 (pre 경로)` | 7 | ⤵ 강등됨(원래 P1) |
| P3 | 파이프라인: 엔티티 추출·의도 분류 | intent-3 | _KOREAN_PLACE_PATTERN이 intent_classifier와 places에서 불일치 (길/산/공원/숲 누락) | `backend/app/services/intent_classifier.py:29 vs backend/app/services/pipeline/helpers/places.py:50-52` | 7 | 미검증(P2/P3) |
| P3 | 파이프라인: 그래프 라우팅·헬퍼 | dates-3 | _parse_natural_date_sync(@lru_cache)가 mutable dict를 반환 — 캐시 공유 객체 오염 가능성 (현 호출부는 read-only) | `backend/app/services/pipeline/helpers/dates.py:341-357,360-371` | 7 | 미검증(P2/P3) |
| P3 | WS agent.py: 구독자·요약·예산·공 | ws-agent-7 | consensus_label 종료시각 off-by-one (마지막 셀 도달 시 30분 누락) | `backend/app/api/ws/agent.py:172-173` | 7 | 미검증(P2/P3) |
| P3 | scheduling_round.py: 다수  | slot-5 | 단일 셀(start==end, 30분) 선택이 _is_explicit에서 제외돼 전원합의 트리거 누락 가능 (compute_majority_slot은 해당 셀을 유효 처리해 불일치) | `backend/app/api/ws/social.py:88-93,97-103, backend/app/services/scheduling_round.py:659-666, frontend/src/components/meeting/TimeBarSelector.tsx:345` | 7 | 미검증(P2/P3) |
| P3 | API: calendar.py(free-sl | cal-2 | consent 토글이 free-slots 캐시를 무효화하지 않아 최대 30초 stale 분자/분모 | `backend/app/api/routes/users.py:126-150; backend/app/api/routes/calendar.py:341-361,535-553` | 7 | 미검증(P2/P3) |
| P3 | API: calendar.py(free-sl | reco-2 | nearby-places는 x/y 없이 search_keyword 호출 → distance_label이 항상 없음 | `backend/app/api/routes/recommendations.py:223-242; backend/app/services/kakao_maps.py:85-90` | 7 | 미검증(P2/P3) |
| P3 | API: rooms.py(멤버십·leave· | rooms-3 | schedule_confirm manual 검증의 ChosenTime 주석/범위 불일치(0~47 vs TIME_SLOT_MAX=26) | `backend/app/api/routes/rooms.py:501-506,559-564` | 7 | 미검증(P2/P3) |
| P3 | 모델·core: SQLModel 모델·sec | core-4 | check_ws_llm_budget: INCR 직후 EXPIRE 미설정 시 키 영구 잔존 → 해당 room+user 영구 차단 가능 | `backend/app/core/rate_limit.py:90-92` | 7 | 미검증(P2/P3) |
| P3 | 모델·core: SQLModel 모델·sec | core-5 | get_current_user가 sub/email/name을 KeyError 없이 보장 못 함 → 비정상 토큰에 401 대신 500 | `backend/app/core/security.py:63-65` | 7 | 미검증(P2/P3) |
| P3 | 모델·core: SQLModel 모델·sec | core-6 | Notification.payload server_default가 sa.text 없이 bare '{}' — create_all 시 잘못된 DEFAULT (현재 무해) | `backend/app/models/notification.py:18-21` | 7 | 미검증(P2/P3) |
| P3 | 프론트 상태·훅: MeetingContext | agent-6 | 1008 종료 시 토큰 삭제 후 즉시 리다이렉트하나, in-flight reconnect 타이머가 무력화되지 않을 수 있는 cleanup 미세 누수 | `frontend/src/hooks/useAgentWebSocket.ts:601-608, 478-481` | 7 | 미검증(P2/P3) |
| P3 | 파이프라인: 슬롯 필링·시간 산출·랭킹 | slot-4 | get_free_slots date_hint에 날짜범위 문자열 유입 시 fromisoformat ValueError 미처리 (re.match prefix 매칭의 사각지대) | `backend/app/services/pipeline/helpers/slots.py:513-514, backend/app/services/pipeline/nodes/function_call.py:217-218` | 6 | 미검증(P2/P3) |
| P3 | 파이프라인: 슬롯 필링·시간 산출·랭킹 | slot-6 | _slot_filling_all_members manual pick: slot_idx_to_time 상한 미검증 (end_idx+1) — API 검증 우회 시 잘못된 confirmed_time | `backend/app/services/pipeline/nodes/slot.py:289-301, backend/app/services/scheduling_round.py:582-585` | 6 | 미검증(P2/P3) |
| P3 | 파이프라인: 검증·매듭카드·메모리·funct | memory-3 | fire-and-forget memory_extraction 태스크 미참조 → 이벤트루프 GC로 완료 전 회수 가능(개인정보 학습 누락) | `backend/app/services/pipeline/nodes/maedeup.py:177,215; backend/app/services/pipeline/nodes/memory.py:88-104` | 6 | 미검증(P2/P3) |
| P3 | 파이프라인: 그래프 라우팅·헬퍼 | dates-1 | _resolve_rejected_date가 거부 날짜를 미래 의미로 롤 → 잘못된 날짜를 거부 목록에 삽입 | `backend/app/services/pipeline/helpers/dates.py:72-103,239-260` | 6 | ⤵ 강등됨(원래 P1) |
| P3 | WS social.py: 날짜·시간 선택,  | ws-social-3 | cache-invalidate 블록의 except (NameError, AttributeError, ImportError): raise 가 graceful 의도와 모순 — 해당 예외 발생 시 unavailable_toggle 핸들러 전체가 죽음 | `backend/app/api/ws/social.py:503-519` | 6 | 미검증(P2/P3) |
| P3 | WS agent.py: 구독자·요약·예산·공 | ws-agent-8 | record_unavailable_toggle 비원자 read-modify-write로 동시 토글 유실 가능 | `backend/app/services/scheduling_round.py:749-771; backend/app/api/ws/agent.py:317-323` | 6 | 미검증(P2/P3) |
| P3 | WS agent.py: 구독자·요약·예산·공 | ws-agent-9 | 방 탈퇴(/leave) 후에도 기존 WS가 shared 채널 수신 지속 (membership 연결시 1회만 검증) | `backend/app/api/ws/agent.py:770-786; backend/app/api/routes/rooms.py:751` | 6 | 미검증(P2/P3) |
| P3 | API: meetings.py(확정·장소 p | route-meetings-4 | place patch 후 personal_data extraction 을 참조 미보유 create_task 로 띄움 — 완료 전 GC 가능 + 미대기 예외 | `backend/app/api/routes/meetings.py:1119, backend/app/api/routes/meetings.py:46-62` | 6 | 미검증(P2/P3) |
| P3 | API: meetings.py(확정·장소 p | route-meetings-6 | patch_meeting_place: search_address 폴백이 새 RuntimeError 를 광역 except 가 삼켜 외부 sync 실패를 사용자에게 알리지 않음 | `backend/app/api/routes/meetings.py:1022-1024, backend/app/api/routes/meetings.py:1053-1057` | 6 | 미검증(P2/P3) |
| P3 | API: rooms.py(멤버십·leave· | rooms-2 | guest_join_room: 게스트 생성과 RoomMember 추가 사이 동시성 — 게스트 캡/중복 검사 TOCTOU | `backend/app/api/routes/rooms.py:207-268` | 6 | 미검증(P2/P3) |
| P3 | API: rooms.py(멤버십·leave· | users-1 | respond_to_friend_request reject가 row 삭제 → 거절 사실 소실 및 무한 재요청 가능 | `backend/app/api/routes/users.py:419-447` | 6 | 미검증(P2/P3) |
| P3 | API: rooms.py(멤버십·leave· | events-1 | POST /events: 방 멤버 누구나 이벤트 생성(호스트 권한 검사 없음) | `backend/app/api/routes/events.py:66-83` | 6 | 미검증(P2/P3) |
| P3 | 외부 서비스: kakao·gemini·llm | history-1 | search_meeting_history Gemini 필터가 hallucinated/임의 JSON을 그대로 반환 (검증 없는 LLM 출력 패스스루) | `backend/app/services/meeting_history.py:125-142` | 6 | 미검증(P2/P3) |
| P3 | 외부 서비스: kakao·gemini·llm | extract-3 | _gemini_extract의 model.generate_content가 timeout 없이 to_thread 실행 → 노드/추출 hang 가능 | `backend/app/services/personal_data_extractor.py:347-354` | 6 | 미검증(P2/P3) |
| P3 | 프론트 컴포넌트: TimeBar·Calend | schedule-2 | hostLoading 동안 isHost를 낙관적 true 처리 — 비호스트가 mount 직후 호스트 전용 '시간대 변경' 클릭 가능 | `frontend/src/components/meeting/ScheduleRecommendationCard.tsx:84, 576-603` | 6 | 미검증(P2/P3) |
| P3 | 프론트 컴포넌트: TimeBar·Calend | completion-1 | formatMeetingDate의 tz 분기가 no-op (양쪽 가지 동일) — tz 마커 있는 ISO도 보정 없이 로컬 해석 | `frontend/src/components/meeting/CompletionPage.tsx:41-42` | 6 | 미검증(P2/P3) |
| P3 | 프론트 컴포넌트: TimeBar·Calend | timebar-1 | TimeBarSelector myBusyPeriods를 myName(표시이름) 키로 조회 — 동명이인/이름변경 시 내 일정 매칭 실패 | `frontend/src/components/meeting/TimeBarSelector.tsx:202-205, 217` | 6 | 미검증(P2/P3) |
| P3 | 파이프라인: 슬롯 필링·시간 산출·랭킹 | slot-7 | _enrich_with_preferences: place_hint를 preference best_location으로 주입하면 is_location_first가 True가 되어 사용자가 언급 안 한 장소로 location-first 카드 전환 | `backend/app/services/pipeline/nodes/slot.py:120-123,150-154` | 5 | 미검증(P2/P3) |
| P3 | 파이프라인: 엔티티 추출·의도 분류 | entity-4 | entity_extraction이 state['message_records']를 .get 없이 직접 인덱싱 (KeyError 가능) | `backend/app/services/pipeline/nodes/entity.py:697,848,866 (intent.py:130,220 동일 패턴)` | 5 | 미검증(P2/P3) |
| P3 | 파이프라인: 검증·매듭카드·메모리·funct | validation-1 | state['headcount']가 slot_context에서 미정규화로 들어올 경우 validation.py headcount>20 비교가 str>int TypeError 유발(노드 예외 경로) | `backend/app/services/pipeline/state.py:209; backend/app/services/pipeline/nodes/validation.py:63` | 5 | 미검증(P2/P3) |
| P3 | WS social.py: 날짜·시간 선택,  | ws-social-5 | reconnect 스냅샷이 송신 소켓에만 전송되어 동일 user_id의 다중 탭/디바이스 접속 시 다른 탭은 최신 availability/date 스냅샷을 못 받음 | `backend/app/api/ws/social.py:324-371` | 5 | 미검증(P2/P3) |
| P3 | API: rooms.py(멤버십·leave· | rooms-4 | guest_join_room: member_joined publish용 Redis 연결 생성 실패 시에도 _publish_social_message에 None 전달 | `backend/app/api/routes/rooms.py:282-319` | 5 | 미검증(P2/P3) |
| P3 | 외부 서비스: kakao·gemini·llm | extract-2 | place patch 경로 personal_data 추출이 참조 없는 create_task → GC 위험 + 장기 Gemini 호출 detach | `backend/app/api/routes/meetings.py:1119, _spawn_personal_data_extraction meetings.py:46-62 → personal_data_extractor.extract_personal_data` | 5 | 미검증(P2/P3) |
| P3 | 외부 서비스: kakao·gemini·llm | reminder-1 | reminder/vote_reminder의 flag-check-then-set이 row lock 없음 → 다중 인스턴스 시 중복 발행 | `backend/app/services/reminder.py:36-68 (reminder_sent), 90-174 (vote_reminder_sent)` | 5 | 미검증(P2/P3) |
| P3 | 외부 서비스: kakao·gemini·llm | reminder-2 | send_today_meeting_reminders: publish 성공·DB commit 실패 시 중복 리마인더(at-least-once만 보장) | `backend/app/services/reminder.py:54-68` | 5 | 미검증(P2/P3) |
| P3 | 프론트 상태·훅: MeetingContext | tbs-5 | TimeBarSelector restore guard가 selection 무변화 + sendTimeSelection identity 변경 시 잘못 소비되어 첫 broadcast 유실 가능 | `frontend/src/components/meeting/TimeBarSelector.tsx:156-162, 241-256` | 5 | 미검증(P2/P3) |
| P3 | 프론트 컴포넌트: TimeBar·Calend | minitimebar-1 | MiniTimeBar aiHighlight가 자정/익일로 끝나는 슬롯을 음수 인덱스로 계산 — 하이라이트 누락 | `frontend/src/components/meeting/MiniTimeBar.tsx:96-98` | 5 | 미검증(P2/P3) |
| P3 | 프론트 컴포넌트: TimeBar·Calend | hostadjust-1 | HostTimeAdjustModal isFullConsensus가 host 본인의 myTimeSelection 누락 시 절대 충족 불가 | `frontend/src/components/meeting/HostTimeAdjustModal.tsx:68-74, 107-115` | 5 | 미검증(P2/P3) |

## Codex 5버그와 겹치는 항목 (참고 — 별도 수정 중)
| sev | 영역 | id | 제목 | 위치 |
|---|---|---|---|---|
| P2 | 파이프라인: 검증·매듭카드·메모리·funct | memory-2 | 동시 finalization 시 memory_extraction 중복 실행 → 동일 AIMemory 중복 INSERT + User 컬럼 write 경합(last-writer-wins) | `backend/app/services/pipeline/nodes/maedeup.py:177,215; backend/app/services/pipeline/nodes/memory.py:99-104,181-232` |
| P2 | 파이프라인: 그래프 라우팅·헬퍼 | graph-2 | _route_after_place_recommendation에서 all_members_selected가 confirmed_place 없이 maedeup 직행 → 장소 미확정 매듭 카드 가능 | `backend/app/services/pipeline/graph.py:206-220, backend/app/services/pipeline/nodes/maedeup.py:64-81` |
| P2 | 외부 서비스: kakao·gemini·llm | intent-1 | embedding zero-vector fallback 시 classify_intent가 Gemini 폴백 구간을 건너뛰고 패턴매칭만으로 분류 (의도 silent 저하) | `backend/app/services/intent_classifier.py:59-90, 153-173` |
| P3 | 프론트 컴포넌트: TimeBar·Calend | votecard-2 | vote_update useEffect가 activeMeetingId null일 때 다른 meeting의 카운트를 무필터 반영 | `frontend/src/components/meeting/VoteCardSection.tsx:109-121` |

## 검증에서 기각된 항목 (false positive)
| 영역 | id | 제목 | 기각 사유(요약) |
|---|---|---|---|
| WS agent.py: 구독자·요약· | ws-agent-2 | all_members_selected 트리거가 NX락+로컬 debounce 모두 우회 → 연결 N명이 각자 파이프라인 실행 | 주장의 핵심 메커니즘("NX락 무조건 우회 → acquired=True → N명 동시 실행")이 실제 코드와 정반대다. 주장이 인용한 line 번호(864-904, 873-874 "무조건 acquired=True", |

---
생성: `scripts/audit_report_gen.py` (워크플로 `codebase-logic-audit` 결과 파싱). 발견 텍스트는 감사 에이전트 원문(검증 판단만 별도 표기).