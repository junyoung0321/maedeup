# 코드 감사: scheduling_round.py: 다수 슬롯·proposal 생명주기·투표·supersede

> 영역키 `scheduling-round` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/services/scheduling_round.py`
- `backend/app/services/finalization_reason.py`
- `backend/app/api/routes/finalization.py`
- `backend/app/api/routes/meetings.py`
- `backend/app/api/ws/social.py`
- `backend/app/api/ws/agent.py`
- `backend/scripts/seed_demo_proposal.py`
- `frontend/src/components/meeting/FinalizationProposalCard.tsx`
- `frontend/src/components/meeting/TimeBarSelector.tsx`

## 감사 노트
[프로덕션 도달성 핵심 사실] sr.propose()는 앱 코드 어디서도 호출되지 않고 backend/scripts/seed_demo_proposal.py에서만 쓰인다(grep 확인). 라이브 일정 합의 흐름은 propose/record_vote 라이프사이클을 타지 않고 social.py:_maybe_emit_proposal → schedule_consensus_ready 노티 → 호스트 클릭 → publish_schedule_auto_trigger → LangGraph 파이프라인 경로다. 따라서 FinalizationProposalCard(propose/record_vote/host_confirm/mark_confirmed)는 (a) seed 스크립트로 주입된 proposal에 대한 투표(finalization.py POST vote)와 (b) meetings.py /confirm의 host_confirm/mark_confirmed 검증에서만 실제로 작동한다. slot-1·slot-2는 이 투표·확정 경로가 실행될 때(seed된 데모 proposal 포함) 재현되며, slot-2는 프론트 게이트까지 확인했다.

[안전 확인된 불변식] (1) 크로스룸 IDOR 없음: 투표는 user_id=int(current_user.sub) 토큰에서만 오고(finalization.py:142), room_id는 _verify_room_membership로 검증되며(143), proposal_id는 _load_proposal_by_id가 로드된 proposal의 id와 일치 검사(309-315)하므로 타 방 proposal 투표 불가. (2) 투표 스푸핑 불가: choice 외 user_id 클라이언트 미입력. (3) 멤버십 검증: finalization·meetings 양 경로 모두 RoomMember 확인 후 진행. (4) host-only 확정: meetings.py:467 room.created_by 검사 + host_confirm:467 이중 검사. (5) confirm 동시성: meetings.py:473-483 별도 Redis NX 락(maedeup:confirm_lock)으로 이중 confirm 차단(BUG-27-1). (6) compute_majority_slot의 run 분할 로직(683-698)·tie alternate(709-715)·인덱스 클램프(661-663)·_format_slot 경계(end_idx 25→slot_idx_to_time(26)=22:00, 오버플로 없음)는 정확. (7) naive/aware datetime: 이 두 파일은 epoch float(time.time)만 다루고 datetime 비교 없음 — meetings.py:519-520에서 .replace(tzinfo=None) 처리. (8) compute_snapshot_hash는 정렬 후 해시라 순서 무관 결정적.

[정상 동작인 fail-open/degrade] _check_room_rate_limit·_acquire_lock·_load_proposal_by_room·record_availability 등은 Redis 장애 시 graceful degrade(주석 명시 trade-off)로 의도된 설계 — 결함 아님. _release_lock/clear_* 의 except pass도 post-commit cleanup 보호 의도.

[잡음으로 미보고] VOTE_DECAY_SECONDS(35)·RateLimitedError(163)는 정의되었으나 미사용 dead code. finalization_proposal:version:{room_id} INCR 키는 EXPIRE 미설정으로 영구 잔존(monotonic counter, 누수라기보다 미정리). _save_proposal이 매 저장마다 24h TTL을 리셋해 deadline_at(고정) 경과 후에도 proposal이 살아있을 수 있으나 deadline은 표시/리마인더 용도로만 쓰이고 어디서도 enforce되지 않아 기능 결함 아님(주석 'Approach D reminder target'). is_majority_reached의 eligible<2 솔로방 가드(121-140)는 의도된 additive 방어, 정상.

[PM 후속 제안] slot-1(투표 500)·slot-2(majority 단방향 전이)는 finalization 투표·확정 경로의 정합성 이슈로, 리뷰 담당이 finalization.py 라우트 예외 처리와 record_vote 상태머신을 함께 점검 권장. slot-3(stale vote prune)은 join/leave 정책 backlog(미해결 #1 '게스트 정책')과 연계 검토. slot-4·slot-5는 '다수 슬롯' 데이터 모델 계약 명확화 필요 — 다수 슬롯 spec(v2 PR 후보)을 다루는 담당에게 위임 적절. 모든 finding은 read-only 정적 분석 결과이며 동적 재현은 미수행.

## 발견 (활성)

### [P1] slot-1 — 동시 투표 시 락 경합이 미처리 예외(SchedulingRoundError)로 새어 HTTP 500 발생
`race-condition` · conf 8/10 · ✅ 검증됨

- **위치**: `backend/app/services/scheduling_round.py:431-432, backend/app/api/routes/finalization.py:153-158`
- **메커니즘**: record_vote()는 진입 시 _acquire_lock()으로 finalization_proposal:lock:{room_id} SETNX 락을 잡는다. 두 멤버가 거의 동시에 같은 proposal에 투표하면 두 번째 호출의 _acquire_lock이 False를 반환 → record_vote가 `raise SchedulingRoundError("propose_lock_contention")`(431-432)를 던진다. 그런데 vote_on_proposal 라우트(finalization.py:145-158)는 NotFoundError / SupersededError / ValueError만 catch한다. 기반 클래스 SchedulingRoundError(및 그 인스턴스인 lock-contention)는 어디서도 잡히지 않아 FastAPI 기본 500으로 전파된다. 전역 exception_handler도 없음(grep 확인).
- **근거**: scheduling_round.py:431 `if not await _acquire_lock(...): raise SchedulingRoundError("propose_lock_contention")`. finalization.py:153-158 except 블록에 SchedulingRoundError 베이스 미포함. grep 결과 app 전역에 SchedulingRoundError용 add_exception_handler 없음.
- **재현**: 한 room의 active proposal에 사용자 A·B가 동일 시각(수 ms 이내) POST /finalization/{id}/vote. 락을 먼저 잡은 쪽은 성공, 다른 쪽은 _acquire_lock False → SchedulingRoundError → 500.
- **영향**: 제안 카드가 막 뜬 직후처럼 여러 멤버가 동시에 [좋아요]/[다른 시간]을 누르는, 라이브 모임에서 가장 흔한 순간에 한 명이 재시도 가능한 409 대신 HTTP 500을 받는다. 클라이언트는 영구 실패로 인식, 투표가 유실될 수 있음. 락 TTL이 5s라 사실상 동시성 윈도우는 좁지만 동시 클릭은 현실적.
- **제안 수정**: vote_on_proposal에 `except sr.SchedulingRoundError as exc: raise HTTPException(status_code=409, detail="vote_contention_retry")`를 (NotFound/Superseded보다 뒤에) 추가하거나, record_vote의 lock-contention을 짧은 재시도(예: 50ms backoff 1~2회) 후에도 실패 시에만 던지도록. 클라이언트가 409를 재시도하도록 처리.
- **검증 판단**: 주장의 사실관계 전부 코드에서 확인됨. (1) scheduling_round.py:431-432 — record_vote는 _acquire_lock 실패 시 베이스 SchedulingRoundError("propose_lock_contention")를 던진다(자식 클래스 아님). (2) scheduling_round.py:143-163 — SchedulingRoundError(Exception)이 베이스이고 NotFoundError/SupersededError 등이 자식. (3) finalization.py:153-158 — except는 sr.NotFoundError/sr.SupersededError/ValueError만 잡고 베이스 SchedulingRoundError 미포함 → 베이스 인스턴스는 어느 except 절에도 매치 안 됨. (4) main.py 전체 확인: 전역 add_exception_handler 없음(backend 전역 grep 0건), http 미들웨어 log_requests는 예외를 잡지 않고 call_next 결과만 반환 → 미처리 예외는 FastAPI 기본 ServerErrorMiddleware로 전파되어 HTTP 500 확정. 반증 시도 결과 막는 가드/상위 catch/early-return 전혀 없음. 오히려 락 키가 finalization_proposal:lock:{room_id}로 room 단위(scheduling_round.py:181)라 같은 room의 동시 투표는 같은 락을 경합 → 주장보다 충돌 가능성이 약간 더 큼. _acquire_lock의 예외 분기는 Redis 자체 장애 시에만 True를 반환(degraded)하므로 정상 Redis에서의 락 경합 raise 경로는 유효. 따라서 false_positive 아님 — confirmed. 다만 P1→P2 하향: (a) record_vote 임계구간이 load→save Redis 라운드트립 몇 개뿐이라 실제 락 보유 시간이 ms 단위로 동시성 윈도우가 매우 좁고(TTL 5s는 stale 방어용 상한일 뿐), (b) 충돌해도 락이 즉시 풀려 클라이언트 재시도로 회복 가능하며, (c) 데이터 영구 유실이 아니라 동시 클릭한 두 번째 사용자 1명의 단발 500(재시도 가능한 409가 아닌 점이 결함). proposed_fix(except sr.SchedulingRoundError → 409 retry, 자식 except보다 뒤에 배치)는 타당.

### [P2] slot-2 — 과반 도달 후 표 변경(like→other)으로 과반이 깨져도 status가 majority_reached로 고정 → 호스트 확정 버튼 활성 유지, 클릭 시 409
`correctness` · conf 8/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/scheduling_round.py:441-443, frontend/src/components/meeting/FinalizationProposalCard.tsx:86,243-251, backend/app/api/routes/meetings.py:498-512`
- **메커니즘**: record_vote에서 상태 전이는 단방향이다: `if proposal.is_majority_reached and proposal.status == ProposalStatus.active: proposal.status = majority_reached`(442-443) — active→majority_reached만. majority_reached 도달 후 한 멤버가 like→other로 바꿔 like_count가 과반 미만으로 떨어져도 status를 active로 되돌리는 분기가 없다. 따라서 broadcast 페이로드의 status는 majority_reached로 남고, 프론트 FinalizationProposalCard는 status==="majority_reached"일 때만 호스트 확정 버튼을 enable(86,243)한다. 호스트가 클릭하면 meetings.py /confirm → host_confirm가 라이브 like_count로 majority_reached_for를 재검증(485-488)하여 BelowMajorityError → 409.
- **근거**: record_vote는 다운그레이드 분기 없음(441-443). FinalizationProposalCard.tsx:86 `majorityReached = proposal.status === "majority_reached"`, 243 `disabled={!majorityReached || confirming}`. host_confirm은 like_count*2>eligible 재검증(scheduling_round.py:131-140,485).
- **재현**: 3인 방, 2명 like → majority_reached. 그 중 1명이 [다른 시간]으로 전환(record_vote, status 그대로 majority_reached). 호스트 버튼 여전히 활성. 호스트 확정 클릭 → 409 below_majority.
- **영향**: 과반이 깨진 상태인데 호스트 화면에는 '이 시간으로 확정' 버튼이 활성으로 보여, 클릭 시 below_majority 409 에러로 혼란. 데이터 손상은 없지만(서버가 잘못된 확정을 막음) UX 정합성 깨짐 + 라이브 데모에서 호스트가 에러를 보게 됨.
- **제안 수정**: record_vote에서 양방향 재계산: 투표 반영 후 `proposal.status = ProposalStatus.majority_reached if (proposal.is_majority_reached and proposal.status in (active, majority_reached)) else ProposalStatus.active`로 다운그레이드 허용(단 confirmed/superseded은 제외). 프론트는 like_count/total 기준으로도 버튼을 가드하면 이중 안전.

### [P2] slot-3 — 확정 시 votes가 현재 멤버십과 대조 정리되지 않아 탈퇴 멤버의 stale like가 과반 판정에 잔존
`data-integrity` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/scheduling_round.py:113-114,131-140,485-488, backend/app/api/routes/meetings.py:492-505`
- **메커니즘**: #19 fix는 확정 시점 현재 RoomMember 수(_current_eligible)를 재조회해 eligible_override로 넘겨 분모를 최신화한다(meetings.py:492-505). 하지만 분자인 like_count는 proposal.votes 전체에서 'like' 개수를 센다(scheduling_round.py:113-114). votes는 어디서도 현재 멤버 집합과 대조해 prune되지 않는다(grep: votes 변경은 441 한 곳뿐). 따라서 like 투표 후 방을 나간 멤버의 표가 like_count에 그대로 남아, majority_reached_for(effective_eligible) = like_count*2 > eligible 판정에서 유령 표로 과반을 부풀릴 수 있다.
- **근거**: scheduling_round.py:113-114 like_count는 votes 전체 집계. 138-140 majority_reached_for는 like_count 사용. meetings.py:492-497 eligible만 현재 멤버 수로 재계산, votes 정리 없음. grep 결과 votes prune 로직 부재.
- **재현**: 4인 방에서 A·B가 like(2/4, 과반 미달). 이후 C·D가 방을 나감 → eligible=2. like_count는 여전히 2(A·B) → 2*2>2 True로 과반 성립, 호스트 확정 가능. (잔류 2인 모두 like이므로 이 케이스는 정당하지만) A like 후 A가 나가고 잔류 3인 중 like 0이면: like_count=1(나간 A), eligible=3 → 1*2>3 False, 안전. 위험 케이스는 like한 멤버가 다수 나가 eligible이 줄되 like 표가 남아 비율이 역전되는 조합.
- **영향**: 투표 후 탈퇴가 발생하는 모임에서, 현재 잔류 멤버 기준으로는 과반 미달인데 떠난 멤버의 like가 분자에 남아 호스트가 확정 가능해질 수 있음(과반 우회). 데모는 중간 변동 없어 happy path 불변이지만, 자유체험존/실사용에서 join·leave가 섞이면 발현. 발생 빈도 낮음.
- **제안 수정**: host_confirm(또는 meetings.py 확정 직전)에서 현재 RoomMember user_id 집합을 받아 like_count를 `sum(1 for uid,v in votes.items() if v=='like' and int(uid) in current_member_ids)`로 필터해 분자·분모를 동일 모집단으로 맞춘다.

### [P3] slot-4 — record_availability/load_room_availability는 유저당 단일 슬롯만 지원 — compute_majority_slot의 다중 슬롯 처리 코드가 사실상 사문화
`correctness` · conf 8/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/scheduling_round.py:523-545,553-572,644-666`
- **메커니즘**: record_availability는 redis.hset(key, str(user_id), entry)로 유저당 1개 엔트리를 덮어쓴다(544). load_room_availability는 `result[uid] = [parsed]`로 항상 길이 1 리스트를 반환(571). 따라서 compute_majority_slot의 `for sel in slots`(645) 루프와 _is_explicit의 다중 엔트리 가정(social.py:88-93)은 실제로는 항상 1개 요소만 순회한다. 멤버가 같은 날 분리된 두 구간(예: 오전+저녁)을 선택해도 마지막 선택만 반영되고 앞 선택은 유실된다.
- **근거**: scheduling_round.py:544 hset로 user당 단일 필드 덮어쓰기. 571 `result[uid] = [parsed]` 단일 원소 리스트. compute_majority_slot:644-645 다중 sel 순회 코드 존재하나 입력이 단일이라 미작동.
- **재현**: 동일 유저가 peer_time_selection을 두 번(다른 date/range) 보내면 두 번째가 첫 번째를 덮어씀. compute_majority_slot는 마지막 것만 본다.
- **영향**: 다수 슬롯(같은 유저가 여러 가용 구간) 시나리오가 데이터 모델 차원에서 미지원. 현재 TimeBar UI가 단일 연속 구간만 보내므로 실사용 영향은 없으나, '다수 슬롯' 기능 확장 시 즉시 깨지는 잠재 결함. 현재는 silent overwrite.
- **제안 수정**: 다중 슬롯 지원이 목표라면 hset 대신 유저별 리스트(JSON 배열)로 저장하고 load에서 그대로 펼친다. 단일 슬롯이 의도라면 compute_majority_slot/_is_explicit의 다중 순회 코드를 단순화하고 계약을 문서화(현재 코드가 미지원을 암시하지 않도록).

### [P3] slot-5 — 단일 셀(start==end, 30분) 선택이 _is_explicit에서 제외돼 전원합의 트리거 누락 가능 (compute_majority_slot은 해당 셀을 유효 처리해 불일치)
`edge-case` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/ws/social.py:88-93,97-103, backend/app/services/scheduling_round.py:659-666, frontend/src/components/meeting/TimeBarSelector.tsx:345`
- **메커니즘**: 프론트 TimeBar는 end를 inclusive로 보내고(TimeBarSelector.tsx:345 `slotToTime(selectionEnd+1) // +1 because end is inclusive`), 단일 셀 선택은 start==end로 전송된다(유효한 30분 선택). social.py의 _is_explicit는 `int(e.get('end',0)) > int(e.get('start',0))`로 strict greater를 요구(91)하므로 start==end 단일 셀은 '명시적 선택 아님'으로 간주돼 explicit_count에서 빠진다(97-101). 반면 compute_majority_slot은 range(s, e+1)로 s==e 셀을 1칸으로 정상 집계한다(665). 두 모듈의 '유효 선택' 정의가 불일치.
- **근거**: social.py:91 `int(e.get('end',0)) > int(e.get('start',0))` strict. scheduling_round.py:665 `for idx in range(s, e+1)` (s==e도 1셀). TimeBarSelector.tsx:345 end inclusive 주석.
- **재현**: N인 방에서 N-1명은 범위 선택, 1명이 단일 셀(start==end) 선택 → explicit_count = N-1 < N → _maybe_emit_proposal이 line 102에서 return, 합의 노티 미발생.
- **영향**: 한 멤버가 정확히 30분(단일 셀)만 가능으로 표시하면 그 멤버는 '전원 선택 완료' 카운트에 들지 않아 schedule_consensus_ready 트리거가 발생하지 않고 합의 흐름이 멈춤. 빈도는 낮음(보통 2칸 이상 드래그). 30분 단위 선택을 막는 UI 가드가 있으면 비발현.
- **제안 수정**: _is_explicit의 비교를 `>=`로 바꿔 단일 셀도 명시적 선택으로 인정하거나, 프론트가 단일 셀 선택을 보내지 않도록 최소 길이를 강제. 단, compute_majority_slot과 정의를 일치시키는 것이 핵심.
