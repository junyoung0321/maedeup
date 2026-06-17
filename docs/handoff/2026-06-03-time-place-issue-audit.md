# 시간/장소 추천 이슈 코드 감사 (2026-06-03)

목적: 사용자 제보 이슈를 파일별로 추적하고, 다음 세션에서 이어서 볼 수 있도록 증거와 가설을 남긴다. 이번 라운드는 수정 없이 정적 분석 + 최소 함수 재현만 수행했다.

현재 브랜치: `fix/speaker-attribution-concurrency`

## 사용자 제보

1. 의도 분석 후 시간 추천은 잘 되지만, 호스트가 TimeBar로 확정하면 다른 사용자에게 적용은 되는데 다른 사용자 화면의 시간 추천 카드가 사라지지 않는다.
2. 시간 추천이 모든 사용자에게 같은 시간대로 보이지 않는다.
3. "천안 신부동 장소 추천" 요청이 기대대로 추천되지 않는다.

## 결론 요약

### P1. 다른 사용자 화면의 시간 추천 카드 잔존

유력 원인: `schedule-confirm` 흐름이 모든 클라이언트의 `infoPanePhase`와 agent 카드 상태를 확정 상태로 전환하지 않는다.

파일별 증거:

- `frontend/src/contexts/MeetingContext.tsx`
  - `confirmTime()`은 로컬 상태만 `timeConfirmed`로 바꾸고 `voteCard`를 지우지 않는다.
  - `setVoteCard(null)`가 호출되거나, 렌더 조건이 `timeConfirmed`로 바뀌어야 카드가 숨는다.

- `frontend/src/components/meeting/AiAssistantPane.tsx`
  - vote card 렌더 조건은 `currentPhaseCtx !== "timeConfirmed" && !== "placeConfirmed" && !== "done"`이다.
  - 다른 사용자가 `meeting_confirmed`를 받아도 `currentPhaseCtx`가 바뀌지 않으면 카드는 계속 렌더된다.
  - `maedeup_card` 수신 시 phase를 `timeConfirmed`로 올리는 effect가 있지만, `scheduleConsensusCtx`가 남아 있으면 early return 한다.

- `frontend/src/hooks/useSocialWebSocket.ts`
  - `meeting_confirmed` 수신 시 하는 일은 `setLastConfirmedMeeting(data)`, `setScheduleConsensus(null)`, finalization proposal status 변경뿐이다.
  - `MeetingContext.setInfoPanePhase("timeConfirmed")` 또는 `confirmTime()`로 연결되지 않는다.

- `backend/app/api/routes/rooms.py`
  - `POST /api/v1/rooms/{room_id}/schedule-confirm`은 `publish_schedule_auto_trigger()`만 호출하고, social 채널에 `meeting_confirmed` 또는 `schedule_confirmed`를 직접 발행하지 않는다.
  - 따라서 비호스트는 `scheduleConsensus`가 계속 남을 수 있고, 이후 `maedeup_card`가 와도 phase advance가 막힌다.

후속 확인/수정 후보:

- schedule-confirm 성공 시 social 채널에 명시적 `schedule_confirmed` 이벤트를 발행하고, 프론트에서 모든 사용자가 `scheduleConsensus=null`, `infoPanePhase=timeConfirmed`, 관련 vote card 제거를 수행.
- 또는 agent 채널에 `meeting_confirmed`/`meeting_resolved`를 meeting_id와 함께 발행해 `useAgentWebSocket`의 `cardsByMeetingId` 제거 경로를 태운다.

### P1. 사용자별 시간 추천 불일치

유력 원인: `all_members_selected` auto trigger가 모든 연결에서 파이프라인을 실행할 수 있다.

파일별 증거:

- `backend/app/api/ws/agent.py`
  - `_redis_subscriber()`는 shared `agent:{room_id}`에서 받은 `ai_auto_trigger`를 각 WebSocket 연결의 `auto_trigger_queue`에 넣는다.
  - 주석은 "N users connected = N subscribers ... Redis SET NX picks one winner"라고 설명한다.
  - 하지만 `_process_auto_triggers()`에서 `trigger_reason == "all_members_selected"`이면 `is_user_explicit_confirm=True`로 보고 `acquired=True`를 바로 설정한다. 이 경로는 Redis NX lock과 local debounce를 모두 우회한다.
  - 결과적으로 연결된 사용자 수만큼 `_run_auto_trigger_pipeline()`이 실행될 수 있고, 각 실행이 vote/place/maedeup card를 shared channel에 다시 broadcast할 수 있다.

영향:

- LLM/컨텍스트/slot_context 차이로 사용자별 또는 시점별 다른 추천 카드가 덮어써질 수 있다.
- 마지막으로 도착한 카드가 사용자마다 다르면 "같은 방인데 서로 다른 시간 추천"으로 보일 수 있다.

후속 확인/수정 후보:

- `all_members_selected`도 room-level NX lock을 타게 한다. 호스트 확정 명령 유실 방지는 `schedule_auto_trigger_fired:{room}:{snapshot}` 같은 producer-side idempotency가 이미 있으므로 consumer-side N회 실행을 허용할 필요가 낮다.
- auto trigger 처리 주체를 WebSocket 연결별 task가 아니라 단일 room worker/서버 task로 이동하는 구조도 검토.

### P1/P2. "천안 신부동" 지명 손실

확인 결과:

- `quick_classify("장소 천안 신부동 추천해달라")` 결과: `{'kind': 'place', 'confidence': 0.9, 'method': 'regex'}`
- `_extract_korean_place_keyword("장소 천안 신부동 추천해달라")` 결과: `천안`

파일별 증거:

- `backend/app/services/pipeline/helpers/places.py`
  - `_extract_korean_place_keyword()`가 `_WELL_KNOWN_PLACES`를 먼저 순회한다.
  - `_WELL_KNOWN_PLACES`에 `천안`이 포함되어 있어, 입력에 `천안 신부동`이 있어도 `천안`에서 즉시 반환한다.
  - 더 구체적인 `_KOREAN_PLACE_PATTERN`의 `신부동` 매칭이나 자유 텍스트 fallback까지 도달하지 않는다.
  - 이후 `search_place()` 쿼리는 대략 `천안 맛집`이 되어 사용자가 지정한 `신부동` 조건이 사라진다.

후속 확인/수정 후보:

- well-known place보다 구체 지명 패턴 또는 복합 지명 추출을 우선한다.
- 예: `천안 신부동`, `서울 강남역`, `부산 서면`처럼 광역/도시 + 동/역/구 조합을 하나의 `place_hint`로 보존.
- 회귀 테스트: `천안 신부동 추천`, `강남역 카페`, `천안 터미널 맛집`, `을지로 입구 술집`.

### P1. 시간 확정 뒤 별도 장소 요청이 새 meeting에 붙을 수 있음

파일별 증거:

- `backend/app/services/pipeline/nodes/place.py`
  - `meeting_id = _card_payload_meeting_id(state.get("vote_card_payload"))`로 현재 run의 vote card에서만 meeting_id를 가져온다.
  - 없으면 `_ensure_pending_meeting_id()`로 새 pending meeting을 만든다.
  - 오늘 세션 요약에도 `place.py:197 meeting_id를 현재 run vote_card에서만 찾음`으로 같은 의심이 남아 있다.

영향:

- 시간은 이미 확정된 meeting A에 있는데, 이후 "천안 신부동 추천해줘" 같은 별도 장소 요청이 meeting B를 만들 수 있다.
- 프론트에서는 장소 카드가 보이더라도 최종 `PATCH /meetings/{meetingId}/place`가 기존 확정 일정이 아닌 새 pending meeting을 대상으로 할 수 있다.

후속 확인/수정 후보:

- `place_recommendation` 진입 시 `confirmedMeetingId`에 해당하는 state 값 또는 DB의 active confirmed meeting을 우선 재사용.
- 별도 장소 요청에서는 새 pending 생성 전에 room의 최신 confirmed meeting을 조회.

### P2. location-first 장소 카드는 shared가 아니라 user channel로 발행됨

파일별 증거:

- `backend/app/api/ws/agent.py`
  - direct_request 결과가 `is_location_first`이고 `date_hint`가 없으면 `place_recommendation_payload`를 `user_channel`로 publish하고 continue 한다.
  - 같은 파일의 일반 장소 추천 경로는 "장소 추천도 모임 전체 공유" 주석과 함께 `shared_channel`로 publish한다.

영향:

- 시간 없이 장소만 먼저 묻는 경우, 요청자만 장소 카드를 보고 다른 사용자는 못 볼 수 있다.
- "추천 안 됨"이 요청자 화면 기준이면 이 원인은 아님. 다만 다중 사용자 동기화 관점에서는 불일치 위험이다.

후속 확인/수정 후보:

- 장소 카드는 정책상 항상 shared라는 주석/프론트 설계와 맞추려면 location-first도 `shared_channel`로 발행.
- private 모드에서도 카드는 shared라는 현재 UI 문구와도 일관화 필요.

## 이번 라운드에서 읽은 파일

- `frontend/src/contexts/MeetingContext.tsx`
- `frontend/src/components/meeting/AiAssistantPane.tsx`
- `frontend/src/components/meeting/ScheduleRecommendationCard.tsx`
- `frontend/src/components/meeting/InfoPane.tsx`
- `frontend/src/components/meeting/TimeBarSelector.tsx`
- `frontend/src/hooks/useSocialWebSocket.ts`
- `frontend/src/hooks/useAgentWebSocket.ts`
- `backend/app/api/routes/rooms.py`
- `backend/app/api/routes/meetings.py`
- `backend/app/api/ws/social.py`
- `backend/app/api/ws/agent.py`
- `backend/app/services/quick_classify.py`
- `backend/app/services/pipeline/helpers/places.py`
- `backend/app/services/pipeline/nodes/entity.py`
- `backend/app/services/pipeline/nodes/place.py`
- `backend/app/services/pipeline/graph.py`

## 다음 라운드 파일 후보

1. `backend/app/services/pipeline/nodes/slot.py`
   - 시간 추천 후보 생성이 group 기준인지, requester/user-specific 기준이 섞이는지 확인.
2. `backend/app/services/pipeline/helpers/slots.py`
   - 추천 슬롯 정렬/필터가 멤버별 busy data와 선호 기준을 어떻게 합치는지 확인.
3. `backend/app/services/pipeline/nodes/vote_card.py`
   - pending meeting 생성, vote_options 저장, payload `meeting_id` 보장 확인.
4. `backend/app/api/routes/calendar.py`
   - 기존 `BUG-26-1` free-slots 다양성/라벨 문제가 현재 시간 추천 불일치와 연결되는지 확인.
5. `frontend/src/components/meeting/PlaceRecommendationCard.tsx`
   - 장소 카드 확정 후 카드 제거/완료 전환이 모든 사용자에게 동기화되는지 확인.

