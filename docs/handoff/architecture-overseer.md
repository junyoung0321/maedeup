# Architecture Overseer (Claude 전용 작업 메모)

**작성**: 2026-05-07
**용도**: Claude가 3개 터미널 동시 작업 중 contract / state 흐름 / 충돌 zone을 실시간으로 검토할 때 reference로 쓰는 살아있는 doc.
**Source of truth가 아님** — 코드가 SoT. 본 문서는 stale 가능성 있음. 의심 시 Grep / Read로 코드 재확인.

---

## 0. 동시 작업 4터미널 역할

| 터미널 | 책임 | 절대 안 건드림 |
|---|---|---|
| **L** (langgraph) | `langgraph_pipeline.py`, `quick_classify.py`, `personal_data_extractor.py`, `intent_classifier.py` (= AI 파이프라인 본체) | F 영역 전부 |
| **F** (그 외 코드 전부) | frontend 전부 + backend non-langgraph: `ws/social.py`, `ws/agent.py`, `routes/meetings.py`, `routes/rooms.py`, `agent_messaging.py`, 신규 router 등 | langgraph_pipeline 본체 |
| **G** (git + 라이브 검증) | commit / merge / push / Docker rebuild + chromium UI 라이브 검증 | 코드 수정 0 |
| **O** (overseer, 본 세션) | contract / 충돌 zone / regression 분석 + 본 doc 갱신 | 코드 수정 0 (paste-relay만) |

L과 F가 동시에 한 파일을 건드리는 zone이 충돌 위험. 아래 §3 충돌맵 참조.

**참고**: F 범위가 "frontend"보다 넓음 — backend도 langgraph services만 빼고 다 F 담당.

---

## 1. 시스템 한 장 (텍스트 다이어그램)

```
                          ┌─────────────────────────────────────┐
                          │           프론트엔드 (Next.js)          │
                          │                                     │
   ChatPane ◄──social WS──┤  useSocialWebSocket   useAgentWebSocket  ├─agent WS──► AiAssistantPane
   (채팅 + peer)            │   ↓ scheduleConsensus    ↓ cardsByMeetingId          │  (AI 카드)
                          │   ↓ peerSelections       ↓ voteUpdate              │
                          │                                                    │
                          │            ┌────── MeetingContext ──────┐          │
                          │            │ voteCard, placeRecommend.   │          │
   InfoPane ◄──phase/state┤            │ scheduleConsensus           ├──────────┤  setVoteCard, etc.
   (TimeBar + 추천 + 확정)  │            │ infoPanePhase, confirmedDate│          │
                          │            └─────────────────────────────┘          │
                          └─────────────────────────────────────┘
                                    │ REST (apiFetch)                  ▲
                                    ▼                                  │
                          ┌─────────────────────────────────────┐      │
                          │            FastAPI 백엔드             │      │
                          │  routes/                            │      │
                          │   ├ rooms.py                        │      │
                          │   │  • POST /preferences            │      │
                          │   │  • GET  /preferences            │      │
                          │   │  • POST /schedule-confirm  ────►├──────┼─pub agent:room (ai_auto_trigger)
                          │   ├ meetings.py                     │      │
                          │   │  • POST /confirm           ────►├─pub agent:room (assistant msg)
                          │   │  • PATCH /meetings/{id}/place ─►├─pub agent:room (maedeup_card)
                          │   ├ assistant.py (AI 패널 입력)      │      │
                          │   │   └─ run_shortcut_pipeline ────►│      │
                          │   └ ...                             │      │
                          │  ws/                                │      │
                          │   ├ social.py                       │      │
                          │   │  • _maybe_emit_proposal ───────►├─pub social:room (schedule_consensus_ready)
                          │   │  • _detect_and_notify_intent ──►├─pub agent:room (ai_auto_trigger)
                          │   │  • publish_schedule_auto_trigger      │
                          │   └ agent.py                        │      │
                          │      • _process_auto_triggers ──────┼──┐   │
                          │      • _publish_agent_message  ◄────┼──┘   │
                          │                                     │      │
                          │  services/                          │      │
                          │   ├ langgraph_pipeline.py (8노드)    │      │
                          │   │   START                         │      │
                          │   │    ├─ trigger=stalemate/conclusion/direct → entity_extraction
                          │   │    ├─ trigger=all_members_selected   → slot_filling
                          │   │    └─ trigger=None                   → intent_detection
                          │   │   intent_detection → entity_extraction (or general_response → END)
                          │   │   entity_extraction → slot_filling
                          │   │   slot_filling ─┬─ function_calling (OK / time_only_ready)
                          │   │                 └─ END (no_slots_yet / partial_info_ack)
                          │   │   function_calling → supervisor_validation
                          │   │   supervisor_validation ─┬─ vote_card_creation
                          │   │                          ├─ place_recommendation
                          │   │                          ├─ maedeup_card_creation (conclusion / time_only)
                          │   │                          └─ END
                          │   │   vote_card_creation → maedeup_card_creation (if confirmed_place) / END
                          │   │   place_recommendation → maedeup_card_creation / END (direct_request)
                          │   │   maedeup_card_creation → memory_extraction → END
                          │   ├ quick_classify.py (정규식 → schedule/place/general)
                          │   ├ personal_data_extractor.py (memory_extraction이 호출)
                          │   ├ agent_messaging.py (emit_agent_message + format_korean_meeting_time)
                          │   └ scheduling_round.py (sr.* — availability snapshot, host_confirm)
                          └─────────────────────────────────────┘
                                              │
                                              ▼
                                          PostgreSQL
                                          Redis (channels: social:N, agent:N)
                                          Kakao Maps API
                                          Google Calendar API
                                          Gemini 2.5 Flash
```

---

## 2. Contract 명세 (깨지면 시스템 고장)

### C1. WS payload `schedule_consensus_ready` (social channel)

- **Publisher**: `backend/app/api/ws/social.py::_maybe_emit_proposal` line 96-106
- **Subscriber**: `frontend/src/hooks/useSocialWebSocket.ts::isScheduleConsensusReadyPayload` line 226 + setter line 564
- **Bridge**: `ChatPane.tsx` line 154 → `MeetingContext.setScheduleConsensus` → `InfoPane.tsx` 호스트 banner
- **Schema**:
  ```json
  {"type":"schedule_consensus_ready", "room_id":int, "snapshot_hash":str, "host_user_id":int, "member_count":int}
  ```
- **NX Lock**: `schedule_consensus_ready:{room_pk}:{snapshot_hash}` (Redis, 300s TTL)
- **깨짐 증상**: A3-2 호스트 banner 미발동 → 자동 트리거 영영 안 발화

### C2. REST `POST /api/v1/rooms/{id}/schedule-confirm`

- **Handler**: `backend/app/api/routes/rooms.py::schedule_confirm` line 380-415
- **Caller**: `frontend/src/components/meeting/InfoPane.tsx` 호스트 "확정하기" 버튼
- **Body**: `{snapshot_hash: str}` → `ScheduleConfirmRequest`
- **Validation**:
  1. 호스트 권한 (room.created_by == current_user.sub) → 403
  2. snapshot_hash가 현재 availability hash와 일치 → 409 `snapshot_outdated`
  3. availability 비어있음 → 409 `schedule_not_ready`
- **Side effect**: `publish_schedule_auto_trigger` → `agent:{room_pk}` pub `ai_auto_trigger` (idempotent via `schedule_auto_trigger_fired:` NX)
- **Trigger payload**: `{type:"ai_auto_trigger", trigger_reason:"all_members_selected", intent:"meeting_schedule"}`
- **깨짐 증상**: 호스트 클릭해도 파이프라인 발화 X

### C3. REST `GET /api/v1/rooms/{id}/preferences`

- **Handler**: `backend/app/api/routes/rooms.py::get_preferences` line 323-360
- **Caller**: `frontend/src/components/meeting/InfoPane.tsx` line 121 (mount + `preferenceRefreshTrigger` 변경 시)
- **Response**: `{submitted_count, all_submitted, preferences: [{user_id, preferred_times[], ...}]}`
- **Frontend 사용**: `computePreferredTimeRange(date, prefs)` → TimeBar `recommendedRange`
- **깨짐 증상 (현재 F-2 의심)**: TimeBar 추천이 9-13 fallback 고정. 진단 console.info 3종으로 추적 중.

### C4. 미러 상수 `PREFERRED_TIME_RANGES`

- **Backend**: `backend/app/services/langgraph_pipeline.py:49-56`
- **Frontend**: `frontend/src/components/meeting/InfoPane.tsx:19-26`
- **Schema**:
  ```
  평일오전: [9, 12], 평일오후: [13, 17], 평일저녁: [18, 21]
  주말오전: [9, 12], 주말오후: [13, 17], 주말저녁: [18, 21]
  ```
- **깨짐 증상**: 한쪽만 키 추가/변경 → frontend가 unknown key → range null → 9-13 fallback. 또는 backend 슬롯 빌더 결과와 frontend 추천 범위 어긋남.
- **변경 시 양쪽 commit 1건에 묶을 것**.

### C5. WS payload — agent 카드 스키마 (`agent:{room_pk}` channel)

- **Publisher**: `backend/app/api/ws/agent.py::_publish_agent_message` (line 469-501)
- **Subscriber**: `frontend/src/hooks/useAgentWebSocket.ts` (type guards line 139-258)
- **카드 종류**:

  | type | meeting_id 필요 | maedeup_card_creation 통과해야 | 비고 |
  |---|---|---|---|
  | `vote_card` | ✓ | ✓ | `_ensure_pending_meeting_id` (line 3734) |
  | `place_recommendation` | ✓ | ✓ | direct_request "place" 시 vote 스킵 후 발화 |
  | `maedeup_card` | ✓ | (자기 자신) | partial_mode="time_only"이면 place_pending=true |
  | `vote_update` | ✓ | × | `vote_meeting` endpoint가 직접 publish |
  | `meeting_summary` | × | × | `_analyze_conversation` 결과 |
  | `meeting_confirmed` / `meeting_cancelled` | ✓ | × | confirm_meeting / cancel_meeting endpoint |

- **Frontend 카드 라이프사이클** (`useAgentWebSocket.ts:276` `cardsByMeetingId`):
  - 같은 `meeting_id`로 새 payload 들어오면 upsert (해결점 J)
  - vote_card → vote_update → maedeup_card (place_pending) → maedeup_card (place 채워짐 + calendar_registered)
  - 모두 같은 `meeting_id` 묶음. 새 카드 누적 X.
- **깨짐 증상**:
  - `meeting_id` 누락 → `Record<number, CardPayload>` 키 깨짐 → 카드 안 사라짐 (F-1 회귀)
  - vote_card 발행 시 partial maedeup이 같은 meeting_id 안 쓰면 두 카드 동시 표시

### C7. TimeBar 슬롯 상수 미러 (backend ↔ frontend)

- **Backend**: `backend/app/services/scheduling_round.py:36-38`
  - `TIME_SLOT_FIRST_HOUR = 9` — TimeBar 09:00 시작
  - `TIME_SLOT_MINUTES = 30` — 30분 슬롯
  - `TIME_SLOT_MAX = 26` — 26 cells = 09:00~22:00, idx 0~25
- **Frontend**: `frontend/src/components/meeting/TimeBarSelector.tsx:9-12`
  - `HOUR_START = 9`, `SLOT_MINUTES = 30`, `TOTAL_SLOTS = 26`
- **Backend 헬퍼**: `_slot_idx_to_time(idx)` (line 551, private — 필요 시 export)
- **변환 공식**: `wall_minutes = TIME_SLOT_FIRST_HOUR * 60 + idx * TIME_SLOT_MINUTES`
- **깨짐 증상**:
  - 한쪽만 변경 → idx ↔ 시간 mismatch (09:00이 다른 시간으로 보이거나 storage 영역 밖 idx 통과)
  - **A3-3 P2 (2026-05-08)**: rooms.py에 `0~47` 하드코딩한 게 실제 storage 상한 25와 어긋남 → 26~47 idx 통과 후 0명 거부 분기 잘못 작동. `sr.TIME_SLOT_MAX` 참조로 정정.
- **변경 시 양쪽 commit 1건에 묶을 것** (C4 PREFERRED_TIME_RANGES 미러 동일 패턴)

### C6. LangGraph state 키 (노드 간 계약)

| 키 | 누가 set | 누가 read | 라우팅 분기 |
|---|---|---|---|
| `trigger_reason` | `agent.py` (PUB), `assistant.py` (direct), `social.py` (host confirm) | `_route_from_start`, `_route_after_validation` | "stalemate_judged" / "conclusion_detected" / "all_members_selected" / "direct_request" / None |
| `direct_request_kind` | `assistant.py` (quick_classify 결과 주입) | `_route_after_validation` (line 4568) | "schedule" / "place" / "schedule+place" / "general" |
| `place_hint` | entity_extraction, `_enrich_with_preferences`, `_slot_filling_all_members` | function_calling, place_recommendation, `_route_after_validation` | 비어있으면 partial 카드 분기 가능 |
| `partial_mode` | `_slot_filling_all_members` (else 분기), `_route_after_validation` (line 4553) | maedeup_card_creation | "time_only" / None |
| `status` | 모든 노드 | 모든 라우터 | `time_only_ready`, `location_first_ready`, `slots_filled`, `validation_failed`, `conclusion_false_positive`, `vote_card_skipped`, `place_skipped`, ... |
| `confirmed_date` / `confirmed_place` | confirm endpoint 재진입 시 slot_context 통해 주입 | `_route_after_validation`, `_route_after_vote_card_creation` | maedeup 카드 직진 |
| `pre_extracted_signals` | `_analyze_conversation` (1회 LLM) | entity_extraction (Gemini 호출 회피) | place_hint sentinel 분기 (line 2747) |

- **깨짐 증상**:
  - `trigger_reason` enum에 새 값 추가 시 `_route_from_start` 업데이트 누락 → 미지정 fallback (intent_detection 경로) → 의도 다른 곳으로 흘러감
  - `place_hint` 잔존 (slot_context 보존) → `_slot_filling_all_members`가 partial 분기 못 타고 location_first_ready로 빠짐 → A4-3 회귀 (현재 시연 시 입력 패턴 정정으로 회피 중)

---

## 3. 충돌 zone 매트릭스 (L vs F)

| 파일 | L | F | 충돌 가능성 | 처리 |
|---|---|---|---|---|
| `backend/app/services/langgraph_pipeline.py` | ✓ | × | 낮음 | L 단독 |
| `backend/app/services/quick_classify.py` | ✓ | × | 낮음 | L 단독 |
| `backend/app/services/personal_data_extractor.py` | ✓ | × | 낮음 | L 단독 |
| `backend/app/services/agent_messaging.py` | × | ✓ | 낮음 | F 단독 |
| `backend/app/api/ws/social.py` | × | ✓ | 낮음 | F 단독 |
| `backend/app/api/ws/agent.py` | × | ✓? | **중간** | C5 schema 변경 시 양쪽 합의 필요 |
| `backend/app/api/routes/meetings.py` | × | ✓ | 낮음 | F 단독 (A4-1 emit + place patch) |
| `backend/app/api/routes/rooms.py` | × | ✓ | 낮음 | F 단독 |
| `frontend/src/contexts/MeetingContext.tsx` | × | ✓ | 낮음 | F 단독 |
| `frontend/src/hooks/useSocialWebSocket.ts` | × | ✓ | 낮음 | F 단독 |
| `frontend/src/hooks/useAgentWebSocket.ts` | × | ✓ | **중간** | C5 schema 변경 시 backend(L)와 양쪽 합의 |
| `frontend/src/components/meeting/InfoPane.tsx` | (간접) | ✓ | **높음** | C4 상수 미러. L이 backend `PREFERRED_TIME_RANGES` 바꾸면 F도 같이 |
| `frontend/src/components/meeting/TimeBarSelector.tsx` | × | ✓ | 낮음 | F 단독 |
| `frontend/src/components/meeting/ChatPane.tsx` | × | ✓ | 낮음 | F 단독 |
| `frontend/src/components/meeting/AiAssistantPane.tsx` | × | ✓ | 낮음 | F 단독 |
| `docs/handoff/*` | ✓ | ✓ | **높음** | merge conflict 자주 발생. G 터미널이 정리. |

**규칙**:
1. C5 (agent WS payload) 추가/변경은 L+F 양쪽 동시 commit
2. C4 (PREFERRED_TIME_RANGES) 키 변경은 L+F 동시 commit
3. 동일 파일 동시 작업 금지 — 한쪽 commit 후 다른쪽 시작

---

## 4. 알려진 회귀 hot zone (지금까지 자주 깨진 곳)

| ID | 증상 | 원인 메커니즘 | 방어 포인트 |
|---|---|---|---|
| **F-1** | maedeup 카드 발행 후 vote_card 안 사라짐 | C5 카드 라이프사이클 — `_ensure_pending_meeting_id` 가드 (74779ba에서 강화) | meeting_id 같은 카드끼리 upsert. 새 meeting 생성 안 되도록 pending 재사용. |
| **F-2** | TimeBar 추천 9-13 fallback (선호 평일저녁 미반영) | C3 GET /preferences 데이터 흐름 어딘가 단절. 진단 console.info 3종 활성. | 1. fetch 성공? 2. count > 0? 3. range 계산? 4. prop 도착? — 콘솔에서 4개 다 통과 확인. |
| **F-2 종결** (2026-05-08) | 라이브 재진단 시 정상 작동 — fetch 성공 / range {18,21} / prop 정상 / "오후 6:00~9:00" 라벨. **자연 정정**. | 이전 9-13 fallback은 docker rebuild 사이 일시 race condition 또는 stale 빌드 추정 (정확한 원인 미특정). | 시연 직전 console.info 3종 cleanup만 남음. C3 contract 자체는 견고. 재발 시 동일 4분기 매핑 사용. |
| **AsyncSessionLocal import 누락** (2026-05-08, P0-2 작업 중 발견) | `langgraph_pipeline.py` line 3860 / 3968 / 4213의 `AsyncSessionLocal()` 호출이 import 없이 try-except로 감싸짐 → `NameError`로 매번 except 진입 → silent broken. | **🔥 F-1 (vote_card 라이프사이클 깨짐) 회귀의 진짜 root cause 후보**. `_ensure_pending_meeting_id` 등 helper가 silent NameError로 실패 → meeting_id 없이 진행 → 카드 라이프사이클 깨짐 가능성. 74779ba (F-1 v2)의 가드 강화는 표면 증상 fix였고 진짜는 import 누락. | L의 P0-2 작업에서 `from app.database import AsyncSessionLocal` 추가로 자연 정정. **검증 시 F-1 v2 재검증 필수** — 가드와 import 둘 다 수정된 상태에서 vote_card → maedeup 라이프사이클 안정성 확인. **lesson**: `try-except: pass` 패턴이 import 오류를 silently swallow함. 의존성 누락이 production 런타임까지 안 걸림. |
| **place tail-slice 버그** (2026-05-08, place top 5 + P0-2 묶음에서 Codex 잡음) | `top_candidates[:10]` → `[:5]` 변경 시 짝맞는 `ranked_places = reranked + place_results[10:]` 도 `[5:]`로 같이 안 바꿔서 인덱스 5-9 후보 누락. | 머리(scoring 대상 N개) + 꼬리(tail) 두 슬라이스가 같은 N에 의존. 한쪽만 바꾸면 중간 누락. | 변경 시 두 슬라이스 짝 검색 (`grep place_results\[`). top N 같은 매직 상수는 single source로 묶는 정교화 시연 후 권장. |
| **P0-2 통과** (2026-05-08 라이브 검증 room 39) | ACT 4 TOTAL 4.51s → **0.02s (-99.5%)**. memory_extraction 3.43s 별도 발생 (graph 후 fire-and-forget). DetachedInstanceError 0건. | graph edge 변경 + `_spawn_memory_extraction_async` + AsyncSessionLocal import 누락 동반 fix. F-1 v2 root cause 정정 효과까지 확인 (vote_card 깨끗이 사라짐). | a0d6136 + 493f48e 두 commit. lesson 누적: try-except가 import 오류 silent swallow + 이런 path는 production 런타임까지 안 드러남. |
| **place top 10→5 통과** (2026-05-08) | ACT 5 first 22.14s (이전 38.27s, **-42%**), second 53.18s — variance 큼. 점수 정상화 50-60% (이전 fallback 10% 탈출). | top 5만 Gemini scoring → prompt + output 토큰 절반. variance dominance는 Gemini API 자체 latency. | a0d6136. 추가 lever 필요 시 Gemini 호출 캐싱 또는 모델 변경. function_calling은 0.10s로 small이라 P0-1 (busy_periods 병렬화) 효과 미미 확인 — **시연 후 정교화로 보류**. |
| **A5-2 v2 통과** (2026-05-08) | reasoning ✨ 정상 노출 — "수현님 채식 식단 · 홍대 비선호 ✨ · 김창윤님 한식 선호 · 다른 멤버 강남 선호 지역 / 선호 시간 저녁형 / 이동수단 지하철 반영" 완벽. | 642f50b — frontend `PlaceRecommendationPayload`에 `group_constraints_summary` interface 추가 + PlaceRecommendationCard 렌더 영역. backend는 line 4180에서 이미 박고 있었음. | lesson: backend payload 필드 추가 시 frontend interface 누락이 silent ignore 패턴. **schema 양쪽 동시 commit 강제**가 향후 회귀 방지. C5 contract 견고화. |
| **F-4 v2 통과** (2026-05-08) | `[DATE_HINTS] Expanded: [] -> ['2026-05-11', ..., '2026-05-15']` 5건. vote_card 5/11 + 다음 주 5건. 해결점 N(다음 주 자동 확장) 정상 발동. | b8dd909 — prompt example에 signals 출력 짝지어 추가 + `{"date": "YYYY-MM-DD"}` dict 형태 강제. | lesson: LLM 멀티필드 추출은 example 전부 짝지어 줘야 누락 없음 + parser shape contract도 prompt에 박아야. |
| **member_joined 통과** (2026-05-08) | "4/4" → "5/5" reload 없이 즉시 갱신. Codex P2 wrapper(`_publish_social_message`) 적용으로 Redis 다운 시 manager.broadcast fallback. | f2c2cde + Codex P2 wrapper. C1 contract 새 type `member_joined` 양쪽 동시 commit. | A5-2 v2 lesson 적용 첫 사례 — schema 미러 누락 0건. |
| **F-3** | "강남에서 다 같이 갈만한 한식집" → entity_extraction Gemini 15s | direct_request fast-skip 추가 (4c5ce48) — 정규식 매칭 실패 시 fallback Gemini 그대로 | quick_classify의 `_PLACE_RE`와 entity_extraction `_PLACE_INTENT_PATTERN` 두 군데 동기화 필요 |
| **F-4** | meeting_summary "시험 끝나고 모임" 한 줄 | `_analyze_conversation` 프롬프트 보강 (4c5ce48) | Gemini few-shot 프롬프트 — bullet 3-5개 강제 |
| **F-4 v2** (2026-05-08) | F-4 본 효과는 살아났는데 `signals.preferred_dates` / `signals.date_hints`가 빈 배열로 떨어져 슬롯 빌드 실패 + 해결점 N(다음 주 자동 확장) 동반 사망 | (1) 4c5ce48 prompt example이 card 출력만 풍부하게 보여주고 signals 출력은 짝지어 안 줘서 Gemini가 자연어를 card에만 쏟음. (2) entity_extraction (line 2638-2643) parser는 `preferred_dates` 항목을 dict로만 expand — plain string array면 silent skip. | prompt example에 signals 출력 짝지어 추가 + dict 형태(`{"date": "YYYY-MM-DD"}`) 강제 + "card 자연어 → signals ISO 변환 필수" 규칙. **lesson**: LLM 멀티필드 추출은 example을 전부 짝지어 줘야 한쪽 빠뜨리지 않음. parser shape contract(dict vs array)도 prompt에 명시. |
| **A3-2** | TimeBar 합의 → AI 자동 발동 (사용자 의도 무시) | C1 + C2 — 호스트 게이트로 차단. 4478608 + 7b3fce7 | `schedule_consensus_ready` NX, `schedule_auto_trigger_fired` NX 둘 다 체크 |
| **A4-3** | all_members_selected → partial 카드 안 뜨고 place 직행 | C6 — `place_hint` 잔존이 `_slot_filling_all_members` (line 3158) 분기 흐트림 | **시연 입력 패턴 정정으로 회피 중**. 코드 수정 안 함. 향후 재발 시 trigger_reason 우선 분기로 단순화. |
| **A6-1** | 거부 발화가 time_preference에 학습됨 | personal_data_extractor 카테고리 misclass | 3중 안전망 (cd2d7c2): 프롬프트 + 부정 예시 + post-process 정규식 |

---

## 5. Trigger → 노드 진입 매핑 (실시간 reference)

```
USER 채팅 ──► social.py classify_intent
                       ├─ 게이트2 (conclusion 정규식) → trigger=conclusion_detected → agent pub
                       ├─ 게이트3 (counter +1)
                       └─ 게이트4 (counter≥4 + 60s) → judge_stalemate LLM → trigger=stalemate_judged

USER TimeBar 전원 ──► social.py _maybe_emit_proposal → schedule_consensus_ready (호스트만 banner)
                       └─ 호스트 클릭 → /schedule-confirm → publish_schedule_auto_trigger
                                                                  → trigger=all_members_selected

USER AI 패널 입력 ──► assistant.py route → quick_classify → run_shortcut_pipeline
                                                                  → trigger=direct_request

         agent.py 진입
         ├─ NX lock + 디바운스
         ├─ _analyze_conversation (1회 Gemini, 50개 윈도우, pre_extracted_signals 추출)
         ├─ trigger별 분석중 메시지 즉시 emit
         └─ run_pipeline → GraphState init (trigger_reason + slot_context 주입)
                                  │
                                  ▼
                     _route_from_start (4499)
                     ┌──────────────────┬──────────────────┬─────────────────────┐
                     ▼                  ▼                  ▼                     ▼
            stalemate/         all_members_       direct_request          (None)
            conclusion         selected           
                     │                  │                  │                     │
                     ▼                  ▼                  ▼                     ▼
            entity_extraction  slot_filling       entity_extraction      intent_detection
                                                                                  │
                                                                                  ▼
                                                                          _route_after_intent
                                                                          (general → general_response → END)
```

---

## 6. 현재 main HEAD 기준 검증 상태

`docs/handoff/2026-05-07-git-management-progress.md` (G 터미널 doc) 참조. 본 doc 작성 시점 HEAD: `e38f766`.

**완료**: A2 / A3-1 / A3-2 / A4-1 / A4-3(자연정정) / A5-1 / A6-1 / D / A0-1 / 시나리오 docs

**진행/미해결**:
- ~~F-1 v2~~ ✅ 종결 (2026-05-08 — AsyncSessionLocal import 누락 fix가 진짜 root cause였음 확정. vote_card 깨끗이 사라지는 라이프사이클 정상)
- ~~F-2~~ ✅ 종결 (2026-05-08 라이브 재진단 정상 — 자연 정정. console.info cleanup만 시연 후)
- ~~F-3~~ ✅ 종결 (2026-05-08 ACT 5 entity_extraction direct_request fast-skip 0.05~0.1s 정상)
- ~~F-4 v2~~ ✅ 종결 (2026-05-08 ISO 변환 + 다음 주 자동 확장 정상)
- ~~A5-2~~ ✅ 종결 (2026-05-08 ✨ reasoning 완벽 노출)

**시연 안전선 통과 (2026-05-08 라이브 검증 9건 / 0 회귀)**:
1. ACT 4 latency 0.02s (이전 4.51s) — P0-2 효과
2. ACT 5 latency first 22s (이전 38s) — top 10→5 효과, variance 53s spike 외부 API 의존
3. F-1 v2 root cause 정정 — AsyncSessionLocal import
4. A5-2 ✨ 멤버 인용 reasoning 정상
5. F-4 v2 preferred_dates ISO + 다음 주 자동 확장
6. member_joined 자동 갱신
7. DetachedInstanceError 0
8. ACT 6 ✨ 학습 카드 (A6-1 거부 발화 학습 거부 정상 작동, 시드된 PD ACT 5 reasoning 노출)
9. F-2 정상 유지

**남은 항목 (시연 후 정교화 / 또는 시간 여유 시 추진)**:
- A3-3 (2-버튼 분기 UX) — 추진 시 회귀 surface 中. user 결정 대기.
- AI 응답 variance — Gemini scoring 캐싱 또는 모델 변경 (시연 후)
- console.info cleanup (F-2 진단 로그 — 시연 후)

---

## 7. 변경 영향 분석 체크리스트 (terminal이 변경 brief 줄 때 내가 돌리는 절차)

1. **파일 매핑** — §3 충돌 zone 표에서 해당 파일 위치 → L/F/G 어느 영역?
2. **Contract 매핑** — §2 C1~C6 중 어느 contract 건드림?
   - WS payload 추가/변경? → C1 / C5 (양쪽 동시)
   - REST schema? → C2 / C3 (caller 확인)
   - 상수? → C4 (양쪽 미러)
   - LangGraph state 키? → C6 (라우터 영향)
3. **회귀 hot zone 교차 검증** — §4의 ID 중 영향 받는 거 있나?
4. **다른 터미널 미커밋 영역과 겹침?** — 핸드오프 doc 3개 + git status로 확인
5. **검증 포인트 제시** — 어느 로그 / 어느 UI 흐름 / 어느 console.info 통과해야 OK
6. **commit 단위 권고** — 단일 commit / 분할 / 다른 터미널 묶음

---

## 8. 살아있는 reference 갱신 정책

본 doc은 **session 단위로 내가 갱신**. 갱신 시점:
- 새 contract 추가 (예: A3-2처럼 신규 endpoint) → §2에 항목 추가
- 회귀 발생 → §4에 ID 추가 + 원인 / 방어 포인트
- 충돌 zone 발견 → §3 표 업데이트
- 노드 / 라우터 변경 → §1 다이어그램 + §5 매핑 갱신

코드 SoT가 우선이므로 본 doc과 코드 충돌 시 **코드 따라간다**. 본 doc의 line 번호는 stale 가능성 있음.
