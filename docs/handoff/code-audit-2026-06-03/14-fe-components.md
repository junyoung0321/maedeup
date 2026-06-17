# 코드 감사: 프론트 컴포넌트: TimeBar·Calendar·Info·VoteCard·Finalization·Place/Schedule 카드 등

> 영역키 `fe-components` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `frontend/src/components/meeting/TimeBarSelector.tsx`
- `frontend/src/components/meeting/VoteCardSection.tsx`
- `frontend/src/components/meeting/InfoPane.tsx`
- `frontend/src/components/meeting/CalendarPane.tsx`
- `frontend/src/components/meeting/ScheduleRecommendationCard.tsx`
- `frontend/src/components/meeting/PlaceRecommendationCard.tsx`
- `frontend/src/components/meeting/FinalizationProposalCard.tsx`
- `frontend/src/components/meeting/MiniTimeBar.tsx`
- `frontend/src/components/meeting/HostTimeAdjustModal.tsx`
- `frontend/src/components/meeting/PlaceDetailPane.tsx`
- `frontend/src/components/meeting/CompletionPage.tsx`
- `frontend/src/components/meeting/GuestJoinGate.tsx`
- `frontend/src/components/meeting/MeetingPreferencePopup.tsx`
- `frontend/src/components/meeting/PlaceInputModal.tsx`
- `frontend/src/components/meeting/LeaveRoomButton.tsx`
- `frontend/src/components/meeting/AiAssistantPane.tsx`
- `frontend/src/contexts/MeetingContext.tsx`
- `frontend/src/hooks/useSocialWebSocket.ts (참조)`
- `backend/app/api/routes/rooms.py (schedule-confirm 계약 검증)`
- `backend/app/api/routes/meetings.py (confirm/vote/place 권한 검증)`

## 감사 노트
검토 범위: meeting/ 디렉토리의 모든 대상 컴포넌트 17개 + MeetingContext + useSocialWebSocket(참조) + 백엔드 schedule-confirm/confirm/vote/place 라우트(권한 계약 검증). 모두 직접 읽음.

확인한 핵심 불변식(정상 동작):
- 호스트 권한은 서버에서 일관 가드됨: schedule-confirm(rooms.py:542), /meetings/confirm(meetings.py:467), /place(meetings.py:988) 모두 room.created_by 검사. FE의 비호스트 확정 버튼 노출(schedule-1)은 보안 누수가 아니라 UX 결함.
- vote 집계 계약 일치: 백엔드 vote_update는 votes(옵션인덱스별 집계) + user_votes(user_id→옵션) + total_voters(현재 멤버수)를 보냄(meetings.py:744-749). VoteCardSection/ScheduleRecommendationCard의 user_votes[String(currentUserId)] 복원 로직(VoteCardSection:115-120)은 정확.
- HostTimeAdjustModal onConfirm 페이로드 {date,start_idx,end_idx}가 백엔드 ChosenTime 스키마(rooms.py:501-505)와 정확히 일치. start>end/범위초과/0명슬롯은 서버가 재검증(rooms.py:559-594)하여 FE strict mode 우회도 방어됨.
- peer 자기-echo 필터는 user_id 기준으로 견고(useSocialWebSocket:611-613,705-706). 동명이인 안전.
- MeetingContext value useMemo의 deps 배열은 노출 함수/state를 모두 포함(누락 없음 — 재확인).
- 과거 날짜 클릭 차단(CalendarPane:402), guest 이름 trim/필수 검증(GuestJoinGate:23-27), PlaceInputModal trim 검증 등 입력 가드 정상.

심각도 분포: P2 5건(모두 다중 동시 모임 또는 비표준 확정 순서라는 엣지 조건에서만 발현 — 단일 모임 전시 데모 happy-path에선 대체로 미발현), P3 5건(표시/UX 결함, 데이터 손상 없음). P0/P1 없음.

코덱스 5버그와의 겹침: votecard-2(vote_update 좁히기)가 코덱스 backlog #6과 동일 계열로 overlaps_codex=true 표기. 코덱스가 현재 수정 중인 5버그(스케줄 확정 후 카드 잔존, NX 소비락 우회, 지명 키워드, context_meeting_id, location-first 채널)와는 직접 중복 없음.

추가 조사 권고(PM): (1) 다중 동시 모임 방 시나리오를 백엔드 담당이 검토 — context-1/aipane-1/votecard-2가 모두 'meeting_id 동치 미검증'이라는 공통 뿌리. (2) member_busy_periods를 이름 키→user_id 키로 바꾸는 계약 변경은 백엔드+FE 동시 작업 필요(timebar-1). (3) ScheduleRecommendationCard 비호스트 정책을 VoteCardSection과 통일(schedule-1)은 FE 단독 가능 — 리스크 낮음.

## 발견 (활성)

### [P2] schedule-1 — ScheduleRecommendationCard 비호스트에게 '확정하기' 버튼이 enable 상태로 노출 — 클릭 시 서버 403
`correctness/permission-ux` · conf 8/10 · 미검증(P2/P3)

- **위치**: `frontend/src/components/meeting/ScheduleRecommendationCard.tsx:604-617`
- **메커니즘**: isHost가 아닌 분기(604)에서도 활성화된 '…로 확정' 버튼을 그려 handleConfirm(195) → POST /meetings/confirm 호출. 백엔드 meetings.py:467이 room.created_by != current_user.sub면 403을 반환하므로 보안 누수는 아니나, 비호스트가 버튼을 눌러 '일정 확정에 실패했습니다' 에러를 보게 됨.
- **근거**: 백엔드 meetings.py:467 host 가드 확인됨(403 '방장만'). FE 비호스트 분기 605-616에 disabled=호스트조건 없이 selectedSlotId/isConfirming만 검사.
- **영향**: 전시 자유체험에서 게스트가 확정 버튼을 눌러 에러 토스트를 보면 흐름이 깨진 것처럼 보임. VoteCardSection은 동일 상황을 '⏳ 방장이 확정하기를 기다리는 중' placeholder로 처리(443-458)하는데 ScheduleRecommendationCard는 비호스트도 확정 버튼 노출 — 두 카드 정책 불일치.
- **제안 수정**: 비호스트 분기를 VoteCardSection처럼 대기 placeholder로 교체하거나 disabled 처리.

### [P2] votecard-1 — handleConfirmSchedule useCallback가 isPlaceConfirmed를 stale 캡처 — 일정 마지막 확정 시 'done' 전이 누락
`correctness/stale-closure` · conf 7/10 · 미검증(P2/P3)

- **위치**: `frontend/src/components/meeting/VoteCardSection.tsx:204, 212`
- **메커니즘**: handleConfirmSchedule는 본문에서 isPlaceConfirmed(204), setContextMode(205), setCalendarSyncStatus(198), activeMeetingId(186)를 읽지만 deps 배열(212)은 [voteCard, selectedSlotId, roomId, refreshCalendar]만 가짐. voteCard reference가 안 바뀌는 동안 isPlaceConfirmed=false로 굳어, '장소 먼저 확정 → 일정 나중 확정' 순서에서 line 204의 if(isPlaceConfirmed) 가드가 false로 평가 → setContextMode('done') 2초 전이가 발화하지 않음.
- **근거**: deps 배열에 isPlaceConfirmed/setContextMode/activeMeetingId 부재. 대비되게 handleConfirmPlace(262)는 confirmedMeetingId를 dep으로 가져 일정 확정 시 재생성되며 self-heal됨. handleConfirmSchedule은 그런 self-heal 트리거가 없음.
- **영향**: VoteCardSection 경로에서 장소가 confirmedMeetingId 선행을 요구(223)하므로 일반 흐름(일정→장소)에서는 schedule이 항상 먼저라 영향 적음. 다만 재확정/예외 순서에서 완료 페이지 자동 전환이 막혀 사용자가 'done' 화면을 못 봄.
- **제안 수정**: deps 배열에 activeMeetingId, isPlaceConfirmed, setContextMode, setCalendarSyncStatus 추가. 또는 isPlaceConfirmed를 ref로 읽어 최신값 보장.

### [P2] context-1 — setVoteCard의 phaseAlreadyAdvanced에 dateConfirmed 포함 — 다른 meeting의 새 vote_card 도착 시 옛 날짜 TimeBar에 멈춤
`correctness/state-machine` · conf 6/10 · 미검증(P2/P3)

- **위치**: `frontend/src/contexts/MeetingContext.tsx:340-356`
- **메커니즘**: setVoteCard에서 infoPanePhase가 dateConfirmed면 phaseAlreadyAdvanced=true로 보아 phase/confirmedDate를 리셋하지 않음(351). 같은 meeting의 identity 재발행을 막으려는 의도(R6 fix)지만, meeting_id가 다른 완전히 새로운 vote_card가 dateConfirmed 상태에서 도착해도 confirmedDate가 옛 날짜로 유지되어 TimeBarSelector가 새 카드와 무관한 옛 날짜를 계속 렌더.
- **근거**: 주석(337-339)은 '같은 meeting identity 재발행' 보호만 의도. 그러나 조건은 card.meeting_id를 비교하지 않고 phase만 검사. confirmedMeetingId는 356에서 새 card.meeting_id로 갱신되나 confirmedDate는 갱신/리셋 안 됨 → meeting과 date 불일치.
- **영향**: 한 방에서 두 번째 모임 조율이 시작되어 첫 모임이 dateConfirmed 상태로 남아있을 때 발생. 전시 단일 모임 데모에선 드묾. 데이터 손상 아님(로컬 표시 불일치).
- **제안 수정**: phaseAlreadyAdvanced 판정에 prev.confirmedMeetingId === card.meeting_id 동치 조건을 AND로 추가해, meeting_id가 바뀌면 phase/confirmedDate를 리셋.

### [P2] aipane-1 — activeVoteCard/activePlaceRecommendation을 meeting 무관하게 각각 '마지막 카드'로 선택 — 서로 다른 meeting 카드 혼합 가능
`correctness/data-integrity` · conf 6/10 · 미검증(P2/P3)

- **위치**: `frontend/src/components/meeting/AiAssistantPane.tsx:139-148, 185-194`
- **메커니즘**: activeVoteCard는 전체 activeCards 중 마지막 vote_card payload(139-141), activePlaceRecommendation은 마지막 place_recommendation(144-148)을 독립적으로 고름. 두 카드가 서로 다른 meeting_id에서 왔을 때 setPlaceRecommendationCtx에 place 카드의 meeting_id를 넘겨(193) confirmedMeetingId가 place 쪽 meeting으로 설정될 수 있어 vote 카드의 meeting과 어긋남.
- **근거**: 두 useMemo가 meeting_id를 교차검증하지 않음. setPlaceRecommendationCtx 2번째 인자로 place 카드 meeting_id만 전달(193). MeetingContext.setPlaceRecommendation은 confirmedMeetingId가 null일 때만 채택(378-385)이라 부분 완화되나, vote 카드가 먼저 meeting을 설정 안 한 경우 어긋날 수 있음.
- **영향**: 다중 동시 모임 방에서 vote/place가 다른 meeting일 때 확정 대상 meeting_id 오선택 위험. 단일 모임 데모에선 미발현.
- **제안 수정**: activeVoteCard와 activePlaceRecommendation을 동일 meeting_id로 묶어 선택(예: 가장 최근 maedeup/vote 카드의 meeting_id를 SoT로 두고 그 meeting의 카드만 publish).

### [P3] schedule-2 — hostLoading 동안 isHost를 낙관적 true 처리 — 비호스트가 mount 직후 호스트 전용 '시간대 변경' 클릭 가능
`correctness/permission-ux` · conf 6/10 · 미검증(P2/P3)

- **위치**: `frontend/src/components/meeting/ScheduleRecommendationCard.tsx:84, 576-603`
- **메커니즘**: isHost = hostLoading ? currentUserId!==null : (...). GET /rooms/{id} 응답 도착 전까지 로그인된 모든 사용자가 isHost=true로 취급되어 '시간대 변경' 버튼(590)이 노출됨. 비호스트가 그 짧은 창에서 클릭하면 requestTimeChange(237)가 로컬 MeetingContext phase를 dateConfirmed로 전이시켜 본인 화면을 TimeBar로 보냄(서버 권한과 무관한 클라 상태).
- **근거**: line 82-84 주석이 '낙관적 렌더'를 명시. requestTimeChange는 순수 클라 state 변경(MeetingContext.tsx:388-398)이라 서버 가드가 없음.
- **영향**: 비호스트가 자기 화면만 잘못된 phase로 보내는 로컬 혼선. 다른 멤버엔 영향 없음. API 왕복(보통 <100ms) 동안만 노출되는 좁은 창.
- **제안 수정**: hostLoading 동안 시간대 변경/확정 액션 버튼은 disabled로 두고, 라벨만 낙관적 노출하거나 hostLoading=true면 비활성.

### [P3] completion-1 — formatMeetingDate의 tz 분기가 no-op (양쪽 가지 동일) — tz 마커 있는 ISO도 보정 없이 로컬 해석
`correctness/datetime` · conf 6/10 · 미검증(P2/P3)

- **위치**: `frontend/src/components/meeting/CompletionPage.tsx:41-42`
- **메커니즘**: const date = new Date(hasTz ? iso : iso) — 삼항의 두 가지가 동일 문자열이라 hasTz 검사가 무의미. 의도는 'tz 마커 없으면 그대로(KST naive 로컬해석), 있으면 그대로'였으나, 만약 백엔드가 'Z'(UTC) 붙은 값을 보내면 브라우저가 UTC→로컬(+9) 변환해 KST로 잘 표시되지만, '+00:00'류 표기와 naive 표기가 섞이면 일관성 깨질 여지.
- **근거**: line 41 hasTz 계산 후 line 42에서 양쪽 동일 iso 사용. 주석(37-40)은 naive KST 가정. 현재 DB가 naive 직렬화면 hasTz=false라 실질 영향 없음 — 잠재적 함정.
- **영향**: 현재 백엔드 직렬화(naive)에서는 올바르게 동작. 향후 직렬화가 tz-aware로 바뀌면 시간 오표시 가능. 즉시 버그 아님.
- **제안 수정**: 분기를 실제로 구현(예: hasTz면 그대로 new Date(iso), 아니면 명시적 KST 처리) 하거나, 의도가 동일이면 삼항 제거하고 주석으로 명시.

### [P3] timebar-1 — TimeBarSelector myBusyPeriods를 myName(표시이름) 키로 조회 — 동명이인/이름변경 시 내 일정 매칭 실패
`edge-case` · conf 6/10 · 미검증(P2/P3)

- **위치**: `frontend/src/components/meeting/TimeBarSelector.tsx:202-205, 217`
- **메커니즘**: memberData는 {표시이름: busyPeriods} 형태이고 myBusyPeriods = memberData[myName](202), othersBusyPerSlot은 m.name!==myName로 자기 제외(217). user.name과 서버가 내려준 키가 정확히 일치해야 동작. 게스트 동명이인 또는 이름에 공백/이모지 차이가 있으면 내 캘린더 충돌(주황)이 '다른 분들' row로 잘못 집계되거나 내 row에 안 뜸.
- **근거**: 키가 user_id가 아닌 표시이름. JWT는 user_id를 가지나 여기선 myName=user?.name으로만 매칭.
- **영향**: 동명이인/이름변경 시 본인 외부일정 시각화가 어긋남. 확정 로직은 서버 availability 기준이라 실제 집계엔 무영향 — 시각 표시 결함.
- **제안 수정**: member_busy_periods를 user_id 키로 내려주거나, 응답에 user_id 매핑을 추가해 이름 대신 id로 self 식별.

### [P3] votecard-2 — vote_update useEffect가 activeMeetingId null일 때 다른 meeting의 카운트를 무필터 반영
`correctness/data-integrity` · conf 6/10 · 미검증(P2/P3) · ⚠겹침:Codex

- **위치**: `frontend/src/components/meeting/VoteCardSection.tsx:109-121`
- **메커니즘**: if(activeMeetingId!==null && voteUpdate.meeting_id!==activeMeetingId) return (111). activeMeetingId가 null(아직 meeting 미해결)인 동안 도착한 voteUpdate는 meeting_id 불문하고 setVoteCounts/setTotalVoters로 반영됨. 다중 모임 방에서 다른 모임의 vote_update가 현재 카드 집계로 새어들 수 있음.
- **근거**: null 가드가 'activeMeetingId!==null'로만 걸려 있어 null 케이스는 통과. activeMeetingId = confirmedMeetingId ?? voteCard?.meeting_id이므로 voteCard.meeting_id가 있으면 보통 null 아님 — 그러나 voteCard.meeting_id가 undefined인 pending 카드에선 null 가능.
- **영향**: 단일 모임 데모에선 미발현. 두 모임 병행 시 투표 표수 오염 가능. 코덱스 backlog #6 'vote_update 좁히기'와 동일 계열.
- **제안 수정**: activeMeetingId가 null이면 voteUpdate 반영을 보류하거나, voteUpdate.meeting_id === voteCard?.meeting_id를 명시 비교.

### [P3] minitimebar-1 — MiniTimeBar aiHighlight가 자정/익일로 끝나는 슬롯을 음수 인덱스로 계산 — 하이라이트 누락
`edge-case` · conf 5/10 · 미검증(P2/P3)

- **위치**: `frontend/src/components/meeting/MiniTimeBar.tsx:96-98`
- **메커니즘**: eIdx = Math.min(TOTAL_SLOTS, (en.getHours()-BAR_START)*2 + floor(min/30)). end_at이 자정(00:00)이거나 다음날이면 en.getHours()=0 → (0-9)*2 = -18 → eIdx 음수, for(i=sIdx;i<eIdx) 루프가 0회 → AI 슬롯 하이라이트가 사라짐.
- **근거**: BAR_START=9 기준 hours<9면 음수. 22:00 종료는 getHours()=22로 정상이나 24:00 표기는 익일 00:00으로 파싱됨.
- **영향**: AI 추천 시간이 밤 늦게(예: ~24:00) 끝나는 드문 케이스에서 미니바의 파란 밑줄 하이라이트만 누락. 데이터/확정엔 무영향, 표시 결함.
- **제안 수정**: end가 start보다 작거나 자정이면 TOTAL_SLOTS로 clamp(예: en이 익일이면 eIdx=TOTAL_SLOTS).

### [P3] hostadjust-1 — HostTimeAdjustModal isFullConsensus가 host 본인의 myTimeSelection 누락 시 절대 충족 불가
`edge-case` · conf 5/10 · 미검증(P2/P3)

- **위치**: `frontend/src/components/meeting/HostTimeAdjustModal.tsx:68-74, 107-115`
- **메커니즘**: heatmap은 peerTimeSelections(타인) + myTimeSelection(본인) 합산(60-74). isFullConsensus = minAvailableInRange === memberCount(115). 호스트가 TimeBar에서 자기 시간을 안 골랐거나 myTimeSelection이 confirmedDate와 다르면 본인 카운트가 0이 되어, 모든 슬롯이 최대 memberCount-1 → 영원히 '⚠️ N명만 가능' 표시. 확정 자체는 isValid(>=1명)면 가능하므로 차단은 아님.
- **근거**: myTimeSelection.date !== confirmedDate면 본인 합산 건너뜀(68). scheduleConsensus 도달 시 보통 본인도 선택했지만, 호스트가 echo restore 전이나 다른 날짜 선택 상태면 누락 가능.
- **영향**: 호스트 조율 모달에서 '전원 가능' 초록 안내가 안 떠 호스트가 불안해할 수 있음. 확정 동작엔 영향 없음(서버가 zero_member_slots만 거부).
- **제안 수정**: memberCount 기준을 'myTimeSelection 포함 여부'에 맞춰 조정하거나, 본인 미선택 시 안내 문구를 분리.
