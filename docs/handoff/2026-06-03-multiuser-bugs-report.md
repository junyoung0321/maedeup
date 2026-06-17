# 멀티유저 실측 버그 리포트 3건 (2026-06-03)

브랜치: `fix/speaker-attribution-concurrency` (main 미머지)
화면: 모바일=웹 통합 `/m/chat/ai` (데스크탑 ChatPane+InfoPane+AiAssistantPane 재사용)
상태: **근본 원인 규명 완료 (코드 추적, file:line 근거). 수정 미착수 — 방향 확인 대기.**
전시: 2026-06-04(수)·05(목), 멀티유저 시연 직결.

> 모든 근본 원인은 실제 코드를 읽어 확인했고 각 주장에 file:line 근거가 있다.
> 재현 환경(데스크탑/모바일, 동시 접속 인원, 입력 문구)은 아직 사용자 확인 대기 — 일부 분기는 그에 따라 좁혀짐.

---

## 요약

| # | 증상 | 근본 원인 한 줄 | 핵심 위치 |
|---|---|---|---|
| 1 | 호스트가 TimeBar로 확정 → 다른 멤버 화면에서 시간 추천(vote) 카드가 안 사라짐 | 호스트 확정 버튼이 `meeting_confirmed`를 안 쏘는 경로(`schedule-confirm`)라 멤버의 `scheduleConsensus`가 안 풀리고, 그게 maedeup_card 자동 advance를 막음 | `InfoPane.tsx:400`, `useSocialWebSocket.ts:596`, `AiAssistantPane.tsx:127` |
| 2 | 시간 추천이 사용자마다 다름 / 중복 카드 | 확정 트리거가 방-단위 동시성 락을 우회 → 연결된 N명이 각자 파이프라인 실행 → meeting 생성 race로 서로 다른 카드 N개 | `agent.py:873`, `agent.py:945`, `vote_card.py:124` |
| 3 | "천안 신부동 추천해줘" 장소 추천 안 나옴 | `_extract_korean_place_keyword`가 광역지명(천안)을 세부지명(신부동)보다 먼저 매칭·반환 → 쿼리가 "천안 맛집"이 되어 신부동 손실 (**재현 확인**) | `places.py:193-195` |
| 4 | 시간 확정 후 별도 장소 요청이 새 meeting에 붙음 | place 노드가 meeting_id를 현재 run vote_card에서만 찾고 없으면 새 pending 생성 | `place.py:197`, `vote_card.py:124` |
| 5 | location-first 장소 카드가 요청자에게만(private) | direct_request `is_location_first` 경로가 user_channel로만 발행(다른 경로는 shared) | `agent.py:1296-1310` |

버그 1·2는 **같은 확정 경로**(`all_members_selected` / `schedule-confirm`)에 뿌리가 얽혀 있다. 버그 3은 독립(지명 추출). 버그 4·5는 멀티유저 동기화·meeting 정합성 부수 이슈.

> 본 문서는 `docs/handoff/2026-06-03-time-place-issue-audit.md`(직전 라운드 정적 분석 + 함수 재현)와 교차검증해 통합한 버전이다. 버그 1·2 결론은 양쪽 동일, 버그 3은 audit의 함수-실행 증거가 더 정확해 그쪽으로 교정했다. 버그 4·5는 audit의 추가 발견.

---

## 버그 1 — 확정 후 시간 추천 카드가 다른 사용자 화면에 잔존

### 증상
호스트가 TimeBar로 시간을 확정하면 본인 화면은 정상(추천 카드 사라지고 최종 매듭 카드 표시)인데, **다른 멤버 화면에는 옛 시간 추천(vote) 카드가 그대로 남는다.** 확정 자체(최종 카드)는 멤버에게도 적용됨.

### 근본 원인 (확정)
호스트의 확정 버튼이 `meeting_confirmed`를 발행하지 않는 경로를 탄다.

1. 호스트 "✅ 추천 시간 그대로 확정" 버튼 → `POST /api/v1/rooms/{id}/schedule-confirm` (`InfoPane.tsx:400`).
   이 경로(`rooms.py:520` → `publish_schedule_auto_trigger`, `social.py:133`)는 agent 채널에 `ai_auto_trigger`만 publish하고 **`meeting_confirmed`는 안 쏜다.**
2. `meeting_confirmed`는 오직 `POST /meetings/confirm`만 발행(`meetings.py:578`). TimeBar 합의 확정은 이 엔드포인트를 안 거침.
3. 프론트에서 멤버의 `scheduleConsensus`를 푸는 **유일한 경로**가 `meeting_confirmed` 수신(`useSocialWebSocket.ts:596-607`, `setScheduleConsensus(null)`). 안 오니 멤버는 `scheduleConsensus`가 영구 set.
4. vote_card 숨김 조건은 `infoPanePhase === "timeConfirmed"`(`AiAssistantPane.tsx:544-551`). 멤버가 거기 도달하는 유일한 길은 maedeup_card 도착 시 자동 advance인데, 그 effect 맨 앞 가드 `if (scheduleConsensusCtx) return`(`AiAssistantPane.tsx:127`)에 막힌다.
5. 호스트만 사라지는 이유: 호스트는 본인 클릭 핸들러에서 로컬로 `setScheduleConsensus(null)` + `setInfoPanePhase("timeConfirmed")`(`InfoPane.tsx:407-411`)를 직접 호출. 멤버는 이 로컬 호출이 없다.

→ "확정은 적용되는데(maedeup 카드 표시) 추천 카드는 안 사라짐(멤버만)"과 정확히 일치.

### 데이터 흐름 (멤버 관점)
```
호스트 클릭 → schedule-confirm → ai_auto_trigger(shared agent)
  → 파이프라인 → maedeup_card(shared agent) → 멤버 수신
     → AiAssistantPane 자동 advance effect 실행
        → if (scheduleConsensusCtx) return   ← 여기서 막힘 (scheduleConsensus 미해제)
        → infoPanePhase 그대로 → vote_card 숨김 조건 미충족 → 잔존
  (meeting_confirmed 미발행 → 멤버 scheduleConsensus 영영 set)
```

### 수정 방향 (제안, 미결정)
- **(A) 백엔드 확정 신호 broadcast (권장):** `schedule-confirm` 확정 완료 시 social 채널에 확정 신호(`meeting_confirmed` 또는 전용 `schedule_finalized`)를 함께 발행 → 모든 멤버가 `scheduleConsensus` 해제 → maedeup_card 자동 advance 정상 작동. 새로고침·늦은 입장에도 일관. 기존 in-card 확정 보호 가드를 안 건드려 안전.
- **(B) 프론트 가드 완화:** maedeup_card 도착 시 `scheduleConsensus`를 강제 해제하거나 `if (scheduleConsensusCtx) return` 가드 제거. 최소 변경이지만 그 가드가 보호하던 호스트 in-card 확정 race가 재발할 여지.

---

## 버그 2 — 시간 추천이 사용자마다 다름 / 중복

### 증상
같은 모임인데 화면(사용자)마다 추천 시간대가 다르게 보이거나 추천 카드가 중복/엇갈려 뜬다.

> ⚠ 정확한 증상(추천 시각 숫자 차이 vs 카드 중복 vs TimeBar 하이라이트 차이)은 사용자 확인 대기. 아래는 코드상 가장 유력한 원인.

### 근본 원인 (확정)
확정 트리거가 방-단위 동시성 락(race condition — 두 실행이 동시에 같은 자원을 건드려 어긋나는 것 — 을 막는 잠금)을 우회한다.

1. `all_members_selected` 트리거는 NX 소비락을 **우회**한다(`agent.py:873-875`): `is_user_explicit_confirm` → `acquired = True`로 무조건 통과.
   (의도: stalemate가 60s NX락을 잡고 있으면 호스트 확정이 묵음 폐기되는 걸 막으려던 것 — 의도는 맞으나 "정확히 1회"가 아니라 "전원 실행"으로 풀림.)
2. `ai_auto_trigger`는 shared 채널로 1회만 발행(멱등, `social.py:148` `schedule_auto_trigger_fired:{room}:{hash}` NX). 그러나 shared 채널이라 **연결된 N명 클라이언트가 각자 dequeue**(`agent.py:735`) 후 NX 우회로 전원이 `_run_auto_trigger_pipeline`를 **각각 실행**(`agent.py:945`).
3. N개 동시 실행이 `_ensure_pending_meeting_id`(`vote_card.py:124-181`)에서 race: 각자 "기존 pending" SELECT → (아직 아무도 commit 전) 미발견 → 각자 새 `MeetingSchedule` INSERT → **서로 다른 meeting_id N개**.
4. 각 실행이 자기 meeting_id로 카드(vote/maedeup/place)를 shared 채널에 broadcast → 프론트 `cardsByMeetingId`가 meeting_id로 키잉 → **다른/중복 카드가 화면에 쌓임.** LLM 비결정성까지 겹치면 추천 시각 자체도 갈림.

### 수정 방향 (제안, 미결정)
- 확정도 **정확히 1회만** 실행되게. blanket 우회 대신 **per-snapshot 소비락** 도입:
  - publish 시 trigger payload에 `snapshot_hash`를 실어 보내고, 소비측에서 `nx_consume:{room}:{snapshot_hash}`를 NX SET → **첫 소비자만 실행, 나머지 skip.**
  - 이러면 stalemate의 `nx_autotrigger:{room}` 락과 키가 분리돼 묵음 폐기도 안 나고(우회 목적 달성), N중 실행도 막힌다(버그 해결).
- 보강: `_ensure_pending_meeting_id`에 멤버/스냅샷 기준 멱등 또는 DB unique 제약으로 중복 meeting 방지.

---

## 버그 3 — "천안 신부동 추천" 장소 미동작

### 증상
AI 패널에 "천안 신부동 추천해줘" 류를 입력해도 사용자가 지정한 동네(신부동) 기준 추천이 안 나온다.

### 근본 원인 (확정 — 함수 재현으로 검증)
`_extract_korean_place_keyword`가 광역 지명을 세부 지명보다 우선해 세부 지명을 버린다.

1. `_extract_korean_place_keyword`(`places.py:187-201`)는 **① `_WELL_KNOWN_PLACES` 순회 → 첫 매칭 즉시 반환**(line 193-195) **② 그 다음에야** `_KOREAN_PLACE_PATTERN`(XX동/역/구…) 매칭(line 197-201) 순서다.
2. `_WELL_KNOWN_PLACES`에 "천안"·"강남"·"을지로" 등 광역/지역명이 등록돼 있어, "천안 신부동"에서 **"천안"이 먼저 매칭되어 반환** → 더 구체적인 "신부동"(XX동 패턴)에 **도달 못 함.**
3. 결과 `place_hint = "천안"` → `search_place` 쿼리가 대략 "천안 맛집"(`places.py:285`) → 사용자가 지정한 **신부동이 사라지고** 천안 전역 기준 추천 → "내가 말한 데 추천 안 해줌"으로 체감.

**재현 (maedeup-api 컨테이너, 2026-06-03):**
```
'장소 천안 신부동 추천해달라' → quick_classify={kind:place, regex} ,  place_keyword='천안'
'천안 신부동 추천해줘'        → quick_classify={kind:place, gemini},  place_keyword='천안'
'천안 신부동 맛집 추천해줘'    → quick_classify={kind:place, regex} ,  place_keyword='천안'
'강남역 카페 추천'            → quick_classify={kind:place, regex} ,  place_keyword='강남'  (역 손실)
'을지로입구 술집'            → quick_classify={kind:place, gemini},  place_keyword='을지로' (입구 손실)
```
→ quick_classify는 대부분 정상 `place` 분류. **분류는 주원인이 아님.** 세부 지명 손실이 핵심.

> 정정: 초기 정적 분석에서 "quick_classify 정규식 미매칭 → general 오분류"를 주원인으로 봤으나, 재현 결과 분류는 잘 됨. audit 문서의 `_extract_korean_place_keyword` 지적이 맞다.

### 수정 방향 (제안, 미결정)
- **(A) 세부 지명 우선 (핵심):** `_extract_korean_place_keyword`에서 well-known 단독 매칭보다 **복합 지명(광역/도시 + 동/역/구)**을 우선 보존. 예: "천안 신부동" → "천안 신부동", "강남역 카페" → "강남역". 패턴 매칭을 먼저 돌리거나, well-known 매칭 뒤에 인접 세부 토큰을 합치는 방식.
- **(B) search_place 쿼리 보강:** place_hint만 있고 cuisine/type 없으면 쿼리에 "맛집" 기본 append(direct_request_kind=="place"에도 적용, 현재 `intent=="place_suggestion"`에만 — `places.py:261`).
- 회귀 테스트: `천안 신부동 추천`, `강남역 카페`, `천안 터미널 맛집`, `을지로입구 술집`, `부산 서면`.

---

## 버그 4 — 시간 확정 후 별도 장소 요청이 새 meeting에 붙을 수 있음

### 근본 원인 (의심, 데스크탑 공통)
`place_recommendation`이 `meeting_id`를 **현재 run의 vote_card_payload에서만** 가져온다(`place.py:197` `_card_payload_meeting_id(state.get("vote_card_payload"))`). 없으면 `_ensure_pending_meeting_id`로 새 pending 생성.

- 시간이 이미 confirmed meeting A에 있는데, 시간 확정과 분리된 별도 발화로 "천안 신부동 추천"하면 현재 run에 vote_card가 없어 **새 pending meeting B 생성** 여지.
- 이후 `PATCH /meetings/{id}/place`가 confirmed A가 아니라 새 B를 대상으로 → 장소가 확정 일정에 안 붙음.

### 수정 방향 (제안)
- `place_recommendation` 진입 시 `confirmedMeetingId`/room의 active confirmed meeting을 **우선 재사용**, 없을 때만 새 pending. (정상 합의-확정 경로에선 한 meeting으로 수렴됨이 이미 검증 — 별도 발화 케이스만 보강.)

---

## 버그 5 — location-first 장소 카드가 요청자에게만(private) 발행

### 근본 원인 (확정)
direct_request 결과가 `is_location_first`이고 `date_hint` 없으면 `place_recommendation_payload`를 **`user_channel`(private)로만** publish(`agent.py:1296-1310`). 같은 파일의 일반 장소 경로는 "모임 전체 공유" 주석과 함께 `shared_channel`로 발행(`agent.py:1375-1385`).

- 시간 없이 장소만 먼저 묻는 경우 요청자만 카드를 보고 다른 멤버는 못 봄.
- "카드는 정책상 항상 shared"라는 프론트 설계·UI 문구와 불일치.
- ※ "추천 안 됨"이 **요청자 본인 화면 기준**이면 이 항목은 버그3과 별개(요청자는 봐야 정상). 다중 사용자 동기화 관점의 불일치.

### 수정 방향 (제안)
- location-first 장소 카드도 `shared_channel`로 발행해 카드 공유 정책과 일관화.

---

## 수정 범위 / 우선순위 메모

- **버그 1·2 (시연 직결, 최우선):** 동일 확정 경로(`all_members_selected`/`schedule-confirm`)에 얽힘 — 함께 수정 권장.
- **버그 3 (독립):** `places.py` 지명 추출 한 곳 — blast radius 작음, 회귀 테스트 쉬움.
- **버그 4·5 (부수):** meeting 정합성·카드 공유 — 시연 핵심 동선은 아니나 멀티유저 일관성에 영향.
- 예상 변경 파일(전체 수정 시): 백엔드 `agent.py`, `social.py`, `rooms.py`, `vote_card.py`, `places.py`, `place.py` / 프론트 `useSocialWebSocket.ts`, `AiAssistantPane.tsx`(또는 `MeetingContext.tsx`). 7~9파일 → blast radius 큼. (버그3은 `places.py` 단일이라 작게 떼어낼 수 있음.)
- 권장 검증: 각 수정 후 qa-runtime 2-브라우저(호스트+멤버) 인터랙티브로 ① 멤버 카드 소멸 ② 단일 추천 카드 ③ "천안 신부동" 세부지명 보존 추천 PASS 확인.

## 미해결 확인 사항 (사용자)
1. 재현 환경: 데스크탑 웹뷰 vs 모바일(/m), 동시 접속 인원(호스트+멤버 N).
2. 버그 2 정확한 증상: 추천 시각 숫자 차이 / 카드 중복 / TimeBar 하이라이트 차이 중 무엇.
3. ~~버그 3 입력 문구~~ → **해소**: 재현 결과 분류는 정상이고 지명 추출(`_extract_korean_place_keyword`)이 세부지명을 버리는 게 원인으로 확정.
4. 수정 범위·시점(내일 전시 전 어디까지).

## 관련 문서
- `docs/handoff/2026-06-03-time-place-issue-audit.md` — 직전 라운드 정적 분석 + 함수 재현 (버그1·2 동일 결론, 버그3 `_extract_korean_place_keyword` 지적, 버그4·5 추가 발견). 본 문서가 그 결과를 교차검증·통합.
