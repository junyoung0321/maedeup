# 설계: 대화 흐름 기반 추천 갱신 트리거 (`constraint_added`)

- 작성일: 2026-06-03
- 스코프: **(B) 갱신만** — AI가 이미 개입해 추천 카드를 띄운 뒤, 대화에서 새 제약이
  나오면 같은 카드를 다듬어 갱신. (A) 초기 트리거 조건 확장은 이 스펙에서 제외.
- 상태: 설계 승인됨 (브레인스토밍 2026-06-03), 구현 계획 대기.

## 1. 문제 / 동기

현재 AI 자동 개입 트리거는 2개뿐 (`backend/app/api/ws/social.py`):
- `conclusion_detected` — 결론 키워드 정규식(`_CONCLUSION_PATTERNS`) + 의도가
  meeting/place일 때 즉시.
- `stalemate_judged` — NOTIFIABLE 메시지 카운터 ≥ 3 + 60초 쿨다운 해제 →
  `judge_stalemate` LLM이 교착 판정 시.

개입해서 추천 카드가 뜬 뒤, 대화방에서 이야기가 더 진행돼도(예: "토요일은 안 돼",
"오후가 좋아") **활성 카드를 다시 다듬는 자동 루프가 없다.** 카드는 다음 트리거
(또 결론/또 교착)가 우연히 떠야만 거칠게 갱신된다. 카드 갱신 설계 문서
(`docs/handoff/diagrams/06-card-update-flow.mmd`)에 "확장 A: 자동 추출 트리거는
운영 누적 후 검토 — 보류"로 명시돼 있던 미구현 확장이다.

## 2. 이미 존재하는 인프라 (재사용)

- **카드 upsert**: 프론트는 `cardsByMeetingId`로 meeting_id 기반 upsert
  (`frontend/src/hooks/useAgentWebSocket.ts`). 같은 meeting_id 재발행 → 그 자리 갱신.
- **제약 추출**: 엔티티 노드가 대화에서 `rejected_dates`를 LLM + 2단계 구조화
  추출(`backend/app/services/pipeline/nodes/entity.py`, eval 0.34→0.66). `blocked_dates`는
  Redis 기반(`_load_blocked_dates`, 캘린더 X 표시).
- **슬롯 재필터/재정렬**: `function_call.py`가 `_filter_out_blocked` /
  `_filter_out_rejected` 적용. 시간옵션 슬롯은 멤버 캘린더 교집합 반영
  (2026-06-03 Bug 3 fix, `_build_time_option_slots`).
- **pending 재사용**: `_ensure_pending_meeting_id`(`nodes/vote_card.py:68`)가
  30분/같은날짜 내 기존 pending MeetingSchedule을 재사용 → 같은 meeting_id.
- **auto-trigger 경로**: `agent.py _process_auto_triggers`(NX 락 + 디바운스 +
  intent 필터) → `_run_auto_trigger_pipeline`. Redis 구독자가 메시지를 클라이언트로
  verbatim 전달(`agent.py:722`).

즉 신규로 만들 것은 **트리거 게이트 1개 + 활성카드 플래그 + 멘트 1종**뿐이다.

## 3. 설계

### 3.1 활성 카드 플래그 (Redis)

- 키: `maedeup:active_reco:{room_id}` = 활성 추천의 meeting_id (문자열), TTL **30분**
  (`_ensure_pending_meeting_id` 재사용 윈도우와 정렬).
- **SET**: vote_card 페이로드가 shared 채널로 발행되는 지점에서 set.
  현재 두 곳 — auto-trigger 경로(`_run_auto_trigger_pipeline` 내 vote_card 발행)와
  direct_request 경로(`agent.py` vote_card_payload 발행, ~1301). 헬퍼
  `mark_active_reco(redis, room_id, meeting_id)`로 통일.
- **CLEAR**: 확정/취소 시 `clear_active_reco(redis, room_id)`.
  - 확정: `meetings.py confirm` 라우트(2026-06-03 Bug 2 fix가 이미 `meeting_confirmed`를
    agent 채널로 발행하는 지점)에서 같이 clear.
  - 취소: 모임 취소 경로에서 clear.
- Redis 장애 시 graceful: set/clear 실패는 silent log. 플래그 없으면 갱신 미발동(보수적).

### 3.2 감지 게이트 (`social.py`, conclusion/stalemate 옆)

새 소셜 메시지 처리 시, **다음 조건이 모두 참**이면
`ai_auto_trigger(trigger_reason="constraint_added")`를 agent 채널로 발행:

1. `maedeup:active_reco:{room_id}` 존재 (활성 추천 카드 있음).
2. 메시지가 **제약 신호 정규식**에 매칭(`_CONSTRAINT_PATTERNS`):
   - 거절: `안\s?돼|안됨|안 ?될|못\s?[가오]|힘들|어려[워울]|빼고|말고|제외|불가|바[쁘빠]|패스|스킵`
   - 시간선호: `(오전|오후|저녁|점심|아침|밤|낮)\s*(이|가|에|으로|로|만|쪽)?\s*(좋|선호|하자|했으면|괜찮)`
   - 정규식은 **싼 게이트**일 뿐. 정밀 추출은 파이프라인의 엔티티 노드가 수행.
3. 디바운스: `maedeup:constraint_cooldown:{room_id}`(TTL **20초**)가 없을 때만.
   발행 시 setex로 20초 쿨다운 설정 → 연속 제약 메시지를 한 번으로 묶음.

발행 페이로드는 기존 ai_auto_trigger와 동일 형태 + `intent`는 활성 카드 종류
(시간 추천이면 `meeting_schedule`, 장소면 `place_suggestion`; 기본 `meeting_schedule`)로
실어 `agent.py:899` intent 게이트를 통과시킨다. 활성 카드가 establish한 모임 맥락이
있으므로 메시지 자체의 intent 재분류는 생략(오분류 리스크 회피).

### 3.3 갱신 실행 (기존 파이프라인)

`constraint_added` 트리거는 기존 `_process_auto_triggers` → `_run_auto_trigger_pipeline`을
그대로 탄다:
- NX 락(room-singleton) 적용 → N개 연결이 동시에 굴리지 않음.
- 엔티티 노드가 최근 대화에서 `rejected_dates` 재추출.
- `function_call`이 `blocked_dates`/`rejected_dates` 필터 + 슬롯 재정렬
  (멤버 교집합 포함).
- `_ensure_pending_meeting_id`가 같은 meeting_id 재사용 → 같은 카드 갱신 발행.

**No-op 억제**: 갱신 결과 `vote_options`가 직전 카드와 동일하면 카드 발행과 멘트를
둘 다 skip. **비교 대상은 기존 pending `MeetingSchedule.vote_options`(DB, 단일
소스)**. 갱신 전 값을 읽어 두고 재계산 결과와 비교. 잡음 방지.

**전부 거절 시**: 슬롯 0개가 되면 기존 zero-slot 동작을 그대로 따른다 —
zero-slot 내레이터를 shared로 발행("이번 후보가 다 빠졌어요. 다른 날짜를
알려주세요" 류)하고 카드 자체는 별도 삭제 없이 유지(새 제약을 더 받으면 다시 갱신).

### 3.4 한 줄 멘트 (shared 채널)

갱신이 **실제로 일어났을 때만**(no-op 아님) reason 기반 한 줄 발행:
- 거절/제약을 구체적으로 알면 인용: **"토요일은 빼고 다시 추천했어요 👇"**,
  **"오후로 좁혀서 다시 골라봤어요 👇"**.
  - 인용 소스: 이번 run에서 새로 추가된 `rejected_dates`(요일/날짜 라벨) 또는 감지된
    시간 선호. 한국어 요일/날짜 포맷은 기존 `helpers/dates`·`formatting` 재사용.
- 추출이 불확실하면 일반형 fallback: **"새 의견 반영해서 추천을 업데이트했어요 👇"**.

## 4. 가드레일 / 엣지 케이스

- 활성 카드 플래그 없으면 절대 미발동 → 확정/취소 후엔 조용.
- WS LLM 예산(`check_ws_llm_budget`) 준수 — 기존 direct/auto 경로와 동일.
- 데모 happy-path 불변: 새 게이트는 (활성 카드 + 제약 신호 + 쿨다운 해제) 동시 충족
  시에만. 기존 conclusion/stalemate 경로는 변경 없음.
- 같은 제약 반복 발화 → 20초 쿨다운으로 흡수. 쿨다운 경계 밖 동일 제약은 no-op
  억제로 흡수(추출 결과 동일 → 발행 skip).
- 제약 정규식 false positive → 추가 파이프라인 1회(비용)만 발생, no-op 억제로
  사용자엔 무영향. false negative → 해당 갱신만 누락(다음 제약/트리거로 복구).

## 5. 테스트

- 단위: `_CONSTRAINT_PATTERNS` 매칭(거절/시간선호 pos, 잡담/일반 neg).
- 단위: `mark_active_reco`/`clear_active_reco` set·clear·TTL.
- 통합(fakeredis): 
  - 활성 카드 플래그 O + 제약 메시지 → `constraint_added` ai_auto_trigger 발행.
  - 플래그 X → 무발행.
  - 쿨다운 내 두 번째 제약 → 두 번째는 억제.
  - confirm 라우트 → active_reco 플래그 clear.
- No-op 억제: 동일 `vote_options` → 카드/멘트 미발행 (가능하면 단위 레벨).
- 슬롯 재정렬·교집합은 기존 테스트(`test_time_option_slots.py`)로 커버.

## 6. 파일 터치포인트 (예상)

- `backend/app/api/ws/social.py` — `_CONSTRAINT_PATTERNS`, 감지 게이트, 발행.
- `backend/app/services/scheduling_round.py` 또는 신규 헬퍼 — `mark_active_reco`/
  `clear_active_reco`/조회.
- `backend/app/api/ws/agent.py` — vote_card 발행 지점에서 `mark_active_reco`;
  `constraint_added` reason 처리(멘트). intent 게이트 통과 확인.
- `backend/app/api/routes/meetings.py` — confirm 시 `clear_active_reco`(Bug 2
  fix의 meeting_confirmed 발행 지점 인근).
- `backend/app/services/pipeline/nodes/vote_card.py` 또는 발행부 — no-op 비교.
- 테스트: `backend/tests/unit/`, `backend/tests/integration/`.

## 7. 범위 외 (Out of scope)

- (A) 초기 개입 트리거 조건 확장(결론/교착 외 신호).
- 장소 추천의 제약 기반 갱신(이번엔 시간 추천 중심; 장소는 동일 패턴으로 후속).
- 멤버 입·퇴장 / 캘린더 변경에 따른 자동 갱신(별도).
