# 코드 감사: 프론트 상태·훅: MeetingContext·useAgentWebSocket·useSocialWebSocket

> 영역키 `fe-state-hooks` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `frontend/src/contexts/MeetingContext.tsx`
- `frontend/src/hooks/useAgentWebSocket.ts`
- `frontend/src/hooks/useSocialWebSocket.ts`
- `frontend/src/components/meeting/ChatPane.tsx`
- `frontend/src/components/meeting/AiAssistantPane.tsx`
- `frontend/src/components/meeting/VoteCardSection.tsx`
- `frontend/src/components/meeting/ScheduleRecommendationCard.tsx`
- `frontend/src/components/meeting/TimeBarSelector.tsx`
- `frontend/src/components/meeting/CalendarPane.tsx`
- `frontend/src/components/meeting/FinalizationProposalCard.tsx`
- `frontend/src/app/m/chat/place/page.tsx`

## 감사 노트
검토 범위: MeetingContext.tsx / useAgentWebSocket.ts / useSocialWebSocket.ts 3개 핵심 파일을 정독하고, 실제 소비처(ChatPane, AiAssistantPane, VoteCardSection, ScheduleRecommendationCard, TimeBarSelector, CalendarPane, FinalizationProposalCard, m/chat/place/page)와 백엔드 social WS 발행부를 교차 확인해 데이터 흐름을 추적했다.

확인한 핵심 불변식(정상 동작):
- WS 클로저 안전성: onmessage/onclose 전부 `isActive && wsRef.current === socket` 가드로 stale 소켓 콜백을 차단(agent:507, social:520). cleanup에서 isActive=false + shouldReconnect=false + 소켓 close 정상.
- self-echo 필터: peer_date/peer_time 핸들러가 myUserId(JWT sub) 우선 + sender fallback 2단(social:611-612,705-706). myUserId 경로가 주력이라 견고.
- finalization out-of-order drop 가드(social:540,564 `prev.version > data.version`)와 my_vote 재계산(votes[myKey]) 정상. deadline=0이면 UI에서 가드(FinalizationProposalCard:261).
- vote_update user_votes 부분 dict 방어: `myVote !== undefined ? myVote : null`로 in 연산자 대신 값 비교(VoteCardSection:119, SRC:131). user_votes 없으면 votedOptionIndex 미변경(유지) — 정상.
- setVoteCard의 phaseAlreadyAdvanced 가드(MeetingContext:340-344)로 카드 재발행 시 dateConfirmed/timeConfirmed phase 보존 — 의도된 R6 fix. 
- useMemo value의 의존성 배열이 모든 state/setter를 망라(MeetingContext:535-601) — 누락 없음 확인.
- start/end 슬롯 인덱스 0 falsy 함정: availability_snapshot(social:642 `start === null` null 체크)과 peer_time(617)에서 `=== null`로 명시 비교 → 0 안전.

추가 의심(보고 제외, 확신 부족): ScheduleRecommendationCard.tsx:604-617에서 비호스트에게도 handleConfirm '확정' 버튼이 노출됨(isAwaitingTimeChange/isHost 둘 다 false인 분기). 이는 카드 컴포넌트(내 담당 외 영역)이고 백엔드 권한 검증이 confirm 엔드포인트에 있는지에 따라 IDOR 여부가 갈림 — 백엔드/카드 담당에게 위임 권고. VoteCardSection은 비호스트에 '방장 대기' 안내만 노출(443-458)해 일관되지 않으므로 교차 확인 가치 있음.

PM 후속 제안: (1) hooks-2(스냅샷 머지 순서)는 재현 쉬움 — QA 담당에게 '재접속 후 peer 시간선택 stale' 시나리오 검증 위임. (2) ScheduleRecommendationCard 비호스트 confirm 버튼 권한은 백엔드 라우트 담당에게 confirm/place 엔드포인트의 host 검증 유무 확인 위임. (3) hooks-1 sender stale은 게스트(user_id null) 정책과 연동되므로 backlog #1(게스트 정책)과 함께 검토.

## 발견 (활성)

### [P2] hooks-2 — availability_snapshot / date_selection_snapshot 머지 순서가 stale peer를 덮어쓰지 못함
`correctness/state-merge` · conf 7/10 · 미검증(P2/P3)

- **위치**: `frontend/src/hooks/useSocialWebSocket.ts:652, 670`
- **메커니즘**: 재접속/스냅샷 수신 시 setPeerTimeSelections((prev) => ({ ...nextPeers, ...prev }))로 머지한다. spread 순서상 prev가 nextPeers를 덮어쓴다. 즉 서버 스냅샷(nextPeers)이 권위 있는 최신 상태인데도, 같은 peerKey(`u{uid}`)에 대해 클라이언트가 들고 있던 이전 값(prev)이 우선 적용된다. peer가 선택을 해제했거나 다른 시간으로 바꿨는데 그 사이 클라이언트가 끊겼다 재연결하면, 스냅샷의 최신값이 적용되지 않고 끊기기 전 stale 값이 남는다. date_selection_snapshot(670행)도 동일 패턴.
- **근거**: useSocialWebSocket.ts:652 `setPeerTimeSelections((prev) => ({ ...nextPeers, ...prev }))`; 670 `setPeerSelections((prev) => ({ ...nextPeers, ...prev }))`. 반면 unavailable_snapshot(675-684)은 next dict를 통째로 setUnavailabilityByUser(next)로 덮어써 일관되지 않다.
- **영향**: TimeBar/Calendar의 peer 선택 표시가 재접속 후 실제 서버 상태와 어긋날 수 있다(다른 멤버가 이미 바꾼 시간이 옛 값으로 표시). 합의 카운트 계산(TimeBarSelector peerSelectionStats)에도 영향. 데모 중 새로고침이 잦으면 가시적.
- **제안 수정**: 스냅샷은 권위 소스이므로 머지 순서를 ({ ...prev, ...nextPeers })로 바꾸거나, unavailable_snapshot처럼 nextPeers로 완전 대체. 주석상 '덮어쓰기' 의도와 코드가 불일치하므로 의도 재확인 필요.

### [P2] hooks-1 — WS 훅 재연결 effect가 roomId만 의존 — sender 변경 시 stale closure로 잘못된 이름 broadcast
`correctness/stale-closure` · conf 6/10 · 미검증(P2/P3)

- **위치**: `frontend/src/hooks/useSocialWebSocket.ts:801, frontend/src/hooks/useAgentWebSocket.ts:631`
- **메커니즘**: 두 훅의 메인 connect useEffect는 의존성 배열이 [roomId]뿐이다. 그러나 onmessage 핸들러 내부의 self-echo 필터(useSocialWebSocket:611-612, 705-706: `data.sender === sender`)와 sendMessage/sendDateSelection/sendTimeSelection(useCallback([sender]))은 effect가 처음 실행될 때 캡처한 sender를 쓴다. 호출처(ChatPane:103, AiAssistantPane:79)는 sender로 `currentUserName`/`user?.name`을 넘기는데, ChatPane은 마운트 후 useEffect로 setCurrentUserName(getNameFromToken())을 비동기 세팅한다(ChatPane:76-78). 따라서 첫 렌더에서 sender='익명'으로 effect가 실행되어 WS가 연결되고, 직후 토큰에서 진짜 이름이 들어오면 sendMessage useCallback은 새 sender로 갱신되지만 onmessage 클로저 내부의 echo 필터 비교용 sender는 여전히 '익명'으로 고정된다.
- **근거**: useSocialWebSocket.ts:801 의존성 `[roomId]`; onmessage echo 필터는 클로저 sender 사용(611,706); ChatPane.tsx:72,77 currentUserName 초기값 '익명' 후 effect로 갱신; sendMessage는 wsRef를 통해 항상 최신 ws를 쓰지만 onmessage 핸들러는 connect() 시점 클로저에 묶임.
- **영향**: user_id 기반 echo 필터(myUserId, 611행 첫 조건)가 정상 동작하면 sender fallback(둘째 조건)은 거의 타지 않아 실제 영향은 작다. 단 user_id가 null로 오는 구버전/게스트 이벤트에서 self-echo 필터가 깨져 본인 날짜/시간 선택이 peer로 표시될 수 있다. 또한 sendMessage가 보내는 sender는 useCallback이 최신화하므로 정상.
- **제안 수정**: connect effect 의존성에 sender 추가하거나, onmessage 내부에서 senderRef.current를 참조하도록 ref 패턴 적용. myUserId 필터가 주력이고 sender는 fallback이므로 우선순위는 낮음.

### [P2] hooks-3 — finalization_vote_update가 proposal보다 먼저 도착하면 deadline_at/created_at이 0으로 소실
`edge-case/data-loss` · conf 6/10 · 미검증(P2/P3)

- **위치**: `frontend/src/hooks/useSocialWebSocket.ts:579-580`
- **메커니즘**: finalization_vote_update 핸들러는 deadline_at/created_at을 새 페이로드가 아니라 `prev?.deadline_at ?? 0` / `prev?.created_at ?? 0`에서만 가져온다(vote_update 페이로드에는 이 필드가 없음). 정상 흐름은 proposal이 먼저 와서 prev에 deadline이 세팅되지만, REST 복구(417-458)가 실패했거나 WS 메시지 순서가 역전되어 vote_update가 proposal보다 먼저 도착하면 prev=null → deadline_at=0, created_at=0이 된다. 이후 proposal이 늦게 와도, 같은 proposal_id에 version이 더 낮으면 out-of-order drop 가드(540,564)에 걸려 deadline이 영영 복구 안 될 수 있다.
- **근거**: useSocialWebSocket.ts:562-583 vote_update 핸들러는 data에 없는 deadline_at/created_at을 prev에서만 채움; 540,564 `prev.version > data.version`이면 frame drop. FinalizationProposalCard.tsx:261 `proposal.deadline_at > 0`일 때만 마감 표시 → 0이면 마감 카운터 영구 미표시.
- **영향**: 마감 타이머 UI가 사라짐(치명적이진 않음). 데이터 정합성 측면에서 created_at도 0이 되어 정렬/로깅에 영향 가능. 드문 순서역전/복구실패 조건에서만 발생.
- **제안 수정**: vote_update 수신 시 prev가 없으면 해당 proposal의 메타를 REST로 재요청하거나, 백엔드 vote_update 페이로드에 deadline_at/created_at 포함. 최소한 prev=null이면 proposal 도착까지 vote_update를 버퍼링.

### [P2] ctx-4 — MeetingContext.setVoteCard가 voteUpdate를 초기화하지 않아 새 meeting 카드에 이전 meeting의 투표 카운트가 잠시 잔존
`correctness/race` · conf 5/10 · 미검증(P2/P3)

- **위치**: `frontend/src/contexts/MeetingContext.tsx:327-360, frontend/src/components/meeting/AiAssistantPane.tsx:184-190`
- **메커니즘**: useAgentWebSocket은 vote_card 수신 시 setVoteUpdate(null)을 호출해(useAgentWebSocket.ts:531-533) hook-local voteUpdate를 비운다. 하지만 MeetingContext로의 전파는 AiAssistantPane의 두 개별 useEffect를 거친다: setVoteCardCtx(activeVoteCard)(186)와 setVoteUpdateCtx(voteUpdate)(189). 둘은 서로 다른 의존성으로 비동기 실행되어, 새 vote_card가 컨텍스트에 먼저 반영되고 voteUpdate=null 전파가 한 렌더 뒤에 일어날 수 있다. 그 사이 VoteCardSection/ScheduleRecommendationCard의 voteUpdate sync effect(VoteCardSection:109-121, SRC:124-133)는 activeMeetingId 가드가 있지만, 새 카드의 meeting_id와 이전 voteUpdate.meeting_id가 (드물게 동일 meeting 재발행 시) 일치하면 stale 카운트가 잠깐 표시된다. 또한 setVoteCard 자체는 voteUpdate를 전혀 건드리지 않아 컨텍스트 단독 소비자에겐 stale가 더 길게 남는다.
- **근거**: MeetingContext.tsx:327-360 setVoteCard 반환 객체에 voteUpdate 리셋 없음; AiAssistantPane.tsx:184-190 voteCard와 voteUpdate를 별도 effect로 브릿지; VoteCardSection.tsx:111 가드 `voteUpdate.meeting_id !== activeMeetingId`는 meeting_id가 같으면 통과.
- **영향**: 동일 meeting의 vote_card 재발행(preference toggle refresh 등) 직후, 새 카드 초기화 effect(VoteCardSection:91-106가 voteCounts={}로 리셋)와 stale voteUpdate sync가 경합해 카운트가 깜빡이거나 옛 값이 잠깐 보일 수 있다. 다른 meeting이면 가드로 차단되어 영향 없음.
- **제안 수정**: setVoteCard가 새 카드 수신 시(특히 meeting_id 변경 시) voteUpdate도 null로 함께 리셋, 또는 AiAssistantPane에서 voteCard+voteUpdate를 단일 effect로 원자적 전파.

### [P3] agent-6 — 1008 종료 시 토큰 삭제 후 즉시 리다이렉트하나, in-flight reconnect 타이머가 무력화되지 않을 수 있는 cleanup 미세 누수
`resource/cleanup` · conf 7/10 · 미검증(P2/P3)

- **위치**: `frontend/src/hooks/useAgentWebSocket.ts:601-608, 478-481`
- **메커니즘**: onclose에서 code===1008이면 shouldReconnectRef=false 후 window.location.href='/'로 리다이렉트한다. 하지만 이미 scheduleReconnect로 예약된 reconnectTimeoutRef 타이머가 있으면 clearReconnectTimeout이 호출되지 않는다(1008 분기에서 early return). 리다이렉트가 즉시 일어나면 페이지 언로드로 무해하지만, 라우터 SPA 전환이 지연되는 환경에선 예약된 connect()가 한 번 더 시도될 여지가 있다. shouldReconnectRef=false 가드가 connect 진입 전 scheduleReconnect에서 막아주므로 실제 재연결까지 가진 않는다.
- **근거**: useAgentWebSocket.ts:601-606 1008 분기에서 clearReconnectTimeout 미호출; scheduleReconnect:463 shouldReconnectRef 가드 존재. useSocialWebSocket.ts:771-776 동일 패턴.
- **영향**: 실질 영향 거의 없음(가드로 재연결 차단, 리다이렉트로 언마운트). 타이머가 잠깐 살아있는 정도. 보고는 완전성 차원.
- **제안 수정**: 1008 분기에서도 clearReconnectTimeout() 명시 호출. 선택적.

### [P3] tbs-5 — TimeBarSelector restore guard가 selection 무변화 + sendTimeSelection identity 변경 시 잘못 소비되어 첫 broadcast 유실 가능
`race/effect-deps` · conf 5/10 · 미검증(P2/P3)

- **위치**: `frontend/src/components/meeting/TimeBarSelector.tsx:156-162, 241-256`
- **메커니즘**: restore effect(156-162)가 `restoredFromServer.current=true`로 echo guard를 세팅하고 selection을 채운다. broadcast effect(241-256)는 의존성 [selectionStart, selectionEnd, date, sendTimeSelection]을 가진다. sendTimeSelection은 useSocialWebSocket에서 useCallback([sender])로 생성되어 WS 재연결/sender 변경 시 identity가 바뀐다. restore로 guard가 true가 된 뒤 실제 selection 변화 없이 sendTimeSelection identity만 바뀌어 broadcast effect가 재실행되면, guard가 그 빈 트리거에 소진(true→false)되어 정작 사용자가 처음 실제 선택을 했을 때의 broadcast가 정상 진행되거나(문제없음), 반대로 restore와 동시기 selection set이 한 배치로 묶이면 guard 1회 소비가 사용자 첫 선택과 겹쳐 skip될 수 있다.
- **근거**: TimeBarSelector.tsx:110 restoredFromServer ref; 156-162 restore가 guard set; 241-256 broadcast effect 의존성에 sendTimeSelection 포함(불안정 identity); useSocialWebSocket.ts:823-831 sendTimeSelection useCallback([sender]).
- **영향**: 본인 TimeBar 선택이 한 번 broadcast 누락되면 다른 멤버 화면/합의 카운트에 본인 선택이 반영되지 않을 수 있다. 발생 조건이 좁고(재연결 또는 sender 변경 + restore 동시) 드물다.
- **제안 수정**: broadcast effect 의존성에서 sendTimeSelection을 ref로 빼거나, guard를 boolean ref 대신 '복원된 값과 동일하면 skip' 값 비교로 전환해 identity 변경에 둔감하게.
