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

### C8. maedeup 카드 시간 SoT (DB ↔ payload 메모리)

같은 `meeting_id`로 발행되는 maedeup 카드의 시간 정보는 **두 path에서 서로 다른 source 사용**:

| 발행 path | 시간 source | 위치 |
|---|---|---|
| **partial maedeup** (langgraph `maedeup_card_creation` 노드 partial 분기) | payload 메모리 — `confirmed_time` slot_context (TimeBar 합의 결과 또는 manual host pick) | `langgraph_pipeline.py:4290~` |
| **갱신 maedeup** (REST `/meetings/{id}/place` 후 발행) | DB `meeting.scheduled_at` + `meeting.end_at` | `meetings.py:_publish_maedeup_place_update` → `_meeting_card_time` |

**일관성 보장 규칙**:
- partial maedeup 발행 시 **DB row의 시간도 같이 동기화** (fb0a6ab 적용). 안 그러면 갱신 path가 stale DB 시간 박아 회귀.
- 향후 같은 meeting_id 라이프사이클에서 시간 변경되는 path 추가 시 — DB / payload 메모리 둘 다 갱신 보장 또는 단일 source로 통합.

**시연 후 정교화 권장**: 단일 formatter 헬퍼 (`_format_maedeup_time(start_at, end_at) -> str`) 도입 — partial(`~` 틸드) vs 갱신(` - ` 대시) format 불일치도 통일.

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
| **A3-3 통과** (2026-05-08 라이브 검증 7건) | manual path 백엔드+frontend 모두 정상. [확정] backward-compat 회귀 0. F-1 v2 라이프사이클 manual path에서도 정상 (voteSurvived false). 백엔드 가드 chain (snapshot_outdated → chosen_time_required → out_of_range → zero_member_slots) code-level 검증. partial 영역 1~3명 인라인 경고 + 호스트 권한 진행 정상. | L: GraphState `manual_chosen_time` + `_slot_filling_all_members` 분기 + maedeup partial 빌더 `confirmed_time` 보존. F: schedule_confirm body 확장(mode/chosen_time) + manual mode validation (TIME_SLOT_MAX 가드 + 모든 슬롯 ≥ 1명 검증) + InfoPane 2-버튼 + HostTimeAdjustModal heatmap+슬라이더+경고. C7 (TimeBar 슬롯 상수 미러) 신규 contract 등록. | wall-clock 변환 brief 첫 라운드 09:00 base 누락 → L이 `sr._slot_idx_to_time` 헬퍼 재사용으로 자연 정정. **lesson**: 슬롯 인덱스 ↔ wall clock 변환은 backend 헬퍼 단일 source 권장 (TIME_SLOT_FIRST_HOUR + TIME_SLOT_MINUTES). 시연 후 정교화: `_slot_idx_to_time` private → public + frontend export. **검증 미달 항목**: discontinuous segments(#3) + 0명 영역 클릭 차단(#4) — CDP 자동화 한계로 시연자 직접 확인 권장. |
| **A3-3 slider default 부정확** (2026-05-08 #2 ⚠️) | HostTimeAdjustModal 모달 open 시 슬라이더 default가 18:00~18:30 (2명 partial)로 잡힘. 19:00~21:00 4명 전원 segment가 있는데도. | F Phase 3 모달 안 default segment 계산 로직 추정 — 첫 번째 가능한 슬롯 또는 myTimeSelection 기반으로 잡고, "가장 긴 전원 segment" 우선 알고리즘 미구현 또는 회귀. | F 영역 1~10줄 fix. computeAvailabilityHeatmap 결과에서 `count === memberCount` segments 추출 → `length` desc sort → 첫 번째 segment의 [start, end]로 default. 시연 임팩트 中 (호스트 drag 한 번 더 필요). |
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

**5/8 후속 사이클 — 추가 회귀 7건 모두 종결**:
1. **deepcopy silent fail** (f72ed42 → f67a30d) — 단순 dict revert + 진단 logging 영구화
2. **C7 slot_idx_to_time public화** (dc9d66b) — 안전 적용 (alias backward-compat)
3. **F-5 v2** (cab4330) — partial maedeup 발행 시 phase auto-advance
4. **F-7 SoT** (cab4330) — `aiRecommendedTimeRange` MeetingContext + MiniTimeBar consume
5. **F-9** (cab4330) — `confirmedPlaceId` + PlaceDetailPane disabled
6. **F-2 cleanup** (cab4330) — console.info 진단 로그 제거
7. **UpcomingMeeting refresh** (cab4330) — focus/visibility 재fetch
8. **member_joined wrapper** (Codex P2) — Redis 다운 시 fallback 보장
9. **A3-3 slider default** (b86041c) — 가장 긴 전원 segment 우선
10. **F-5** (43bb1b2) — TimeBar individual confirm 라이프사이클
11. **consensus_label slot_context 누락** (c786ebb) — partial maedeup 시간 정확
12. **F-8 v2 preference path** (d3323d4 + b56aa4b) — `_build_preference_time_slots` busy_by_user
13. **F-8 v2 multi_date path** (17eba08) — `_build_multi_date_slots` busy_by_user
14. **🔥 maedeup 시간 SoT 분리** (fb0a6ab) — partial 발행 시 DB scheduled_at/end_at 동기화

**남은 항목 (시연 후 정교화 / 또는 시간 여유 시 추진)**:
- ~~A3-3~~ ✅ 통과 (2026-05-08, 검증 7건. discontinuous + 0명 차단은 시연자 직접 확인 항목)
- 🔴 **F-6 카드/채팅 시간순 정렬** — 시연 D-7 + 검증 9건 통과 직후 회귀 누적 risk → **시연 후 정교화 1순위**로 박음. 시연 시 멘트로 우회 ("AI 카드 위에, 대화 아래에 — 모임 진행 단계 보존").
| **🚨 deepcopy slot_context 회귀 (해결 — 단순 dict revert)** (2026-05-08) | dc9d66b `copy.deepcopy(slot_context)` 도입 후 trigger pipeline silent fail. selective deepcopy(f72ed42)도 fail. 진단 logging 박은 후 NX lock state 점검에서 정상 작동 확인 — deepcopy가 진짜 원인이었음. f67a30d로 단순 `dict()` 완전 revert + 진단 logging 영구 박음. | Codex P1 finding (nested mutable race 위험) 의도는 정합하나 **agent.py loop 컨텍스트의 `_log_detached_task_result` callback이 deepcopy 예외를 swallow**하면서 silent fail 만듦. 진단 logging 추가 후 위치 정확히 잡힘. **lesson 1**: `try-except`/callback이 import + copy 같은 인프라 예외를 silent swallow → production runtime까지 안 드러남. **lesson 2**: silent fail 추적 시 (a) Redis NX state 먼저 점검, (b) 진단 logging 박아 단계 좁히기 두 단계 권장. | f67a30d로 종결. P1 finding은 시연 후 재처리 (deepcopy 대신 `pre_extracted_signals`만 selective copy로 격리하는 방향). |
| **C7 + slot_idx_to_time silent path 결합 회귀** (2026-05-08, dc9d66b 묶음) | dc9d66b가 `_slot_idx_to_time` private → public + deepcopy 둘 묶음 commit. 회귀 진단 시 어느 변경이 원인인지 분리 어려움. | **lesson**: 의미 다른 변경(C7 contract 정리 + Codex P1 fix)을 단일 commit에 묶지 말 것. 회귀 발생 시 revert/bisect 단위가 커짐. | 시연 후 정교화 — 향후 commit 분리 정책 강화. |
| **F-8 v2 — preference path GCal busy 무시** (2026-05-08, d3323d4 + b56aa4b) | `_build_preference_time_slots`이 호스트 GCal busy 시간대 무시 → "(전원 가능)" 거짓 라벨. d3323d4가 함수 안 검사 추가, b56aa4b가 호출처 `function_calling:3666 preference_based path`에 `_load_busy_by_user_for_state` 헬퍼 호출 + `busy_by_user` 인자 전달 추가. | **n개 슬롯 빌더 + GCal busy 적용 누락 패턴**이 회귀 source. 빌더 N개에 같은 fix 분산. | 시연 후 정교화: 슬롯 빌더 단일 헬퍼 + busy_by_user contract 묶음으로 통합. |
| **F-8 v2 #2 — multi_date 빌더 GCal busy 무시** (2026-05-08, 17eba08) | b56aa4b 통과 후에도 ACT 2 stalemate path "(전원 가능)" 거짓 라벨. 진단 결과 stalemate path가 `_build_multi_date_slots` (line 3413) 거침 — 거기도 같은 패턴. 17eba08로 같은 fix 적용. | 한 패턴 회귀가 N개 빌더에 분산 누적되어 있음을 확인. | 시연 후 정교화 — line 923 `_build_time_option_slots` + line 1732/1740 `get_free_slots` no-GCal-client fallback도 같은 패턴 적용 필요. |
| **consensus_label slot_context 누락** (2026-05-08, c786ebb) | TimeBar 합의 후 partial maedeup 카드 시간이 "18:00 - 19:00" (1h fallback) 표시. agent.py `_build_entities_from_timebar`이 `consensus_label = "18:00~21:00"` 만들지만 `slot_context["confirmed_time"]`로 안 박힘. partial maedeup 빌더 (line 4290~)가 confirmed_time None이면 `+1h fallback`. | timebar_data → slot_context 전달 시 의도 명확하게 박힌 키만 통과 → consensus_label drop. **lesson**: 새 정보 필드 만들 때 데이터 흐름 끝점까지 매핑 확인 필수. | c786ebb로 `slot_context["confirmed_time"] = consensus_label` 박음. partial maedeup 빌더가 "HH:MM~HH:MM" 분기 잡아 정확한 end 추출. |
| **🔥 SoT 분리 — partial maedeup payload vs DB scheduled_at** (2026-05-08, fb0a6ab) | TimeBar 합의 19:00~21:00 → partial maedeup 카드 19:00~21:00 정확. ACT 5 [이 장소로 확정] 클릭 후 maedeup 갱신 → 시간 "18:00 - 19:00" (1h) 회귀. | **두 maedeup 발행 path가 다른 시간 source 사용**: (1) partial — payload 메모리 `confirmed_time` slot_context 정확. (2) 갱신 — `meetings.py:_publish_maedeup_place_update` → `_meeting_card_time(meeting)` → DB `meeting.scheduled_at/end_at`. DB 시간은 `_ensure_pending_meeting_id`가 vote_card 시점에 박은 30min/1h slot 그대로. partial 발행 시 DB row 갱신 누락. **lesson (P0)**: 같은 meeting_id 카드 라이프사이클에서 시간 source를 단일화하지 않으면 진화 단계마다 회귀. C8 contract로 등록. | fb0a6ab — partial 분기 (line 4290~)에서 `start_dt`/`end_dt` 계산 후 DB meeting row `scheduled_at`/`end_at` 동기화. silent commit (실패해도 payload 정상 발행). |
- **AI 응답 variance** — Gemini scoring 22~53s 변동. 캐싱 또는 모델 변경.
- **슬롯 빌더 단일 헬퍼 + busy_by_user contract 통합** — N개 빌더에 같은 fix 분산 (`_build_preference_time_slots` ✅ / `_build_multi_date_slots` ✅ / line 923 `_build_time_option_slots` ❌ / line 1732 / 1740 `get_free_slots` no-GCal-client fallback ❌). 단일 헬퍼로 묶고 busy_by_user 인자 mandatory.
- **maedeup 시간 단일 formatter** (C8 contract) — partial(`~`) vs 갱신(` - `) format 통일.
- **slot_context P1 정교화** — `pre_extracted_signals`만 selective copy 격리 (전체 deepcopy는 silent fail 회귀로 폐기).
- **commit 분리 정책 강화** — 의미 다른 변경(C7 contract + Codex P1)을 단일 commit에 묶지 않기 (dc9d66b 회귀 lesson).
- **`[AUTO_TRIGGER]` 진단 logging 영구화 검토** — f67a30d로 박힌 로그 운영 utility 평가.
- **`_publish_schedule_auto_trigger` NX skip 시 logger.info** — 현재 silent return. 시연 후 진단 가시성 ↑.

## 7. Lessons 누적 (시연 후 architecture review용)

5/7~8 사이클 + 후속 회귀 fix에서 정착된 anti-pattern + 권장 패턴:

| ID | Lesson | 사례 |
|---|---|---|
| L-1 | **Schema 미러 contract 양쪽 동시 commit** — backend payload 필드 추가 시 frontend interface 누락이 silent ignore 패턴 | A5-2 v2 (`group_constraints_summary`) / C4 (`PREFERRED_TIME_RANGES`) / C7 (TimeBar 슬롯 상수) |
| L-2 | **`try-except: pass`가 import + copy 같은 인프라 예외 silent swallow** → production 런타임까지 안 드러남 | AsyncSessionLocal import 누락 / deepcopy silent fail |
| L-3 | **silent fail 추적은 (a) Redis NX state 먼저, (b) 진단 logging 추가 두 단계** — 코드 회귀 가설 점프 전 환경 점검 | deepcopy 회귀 |
| L-4 | **LLM 멀티필드 추출은 example 짝지어 + parser shape contract 명시** | F-4 v2 (`signals.preferred_dates` dict shape) |
| L-5 | **N개 빌더 같은 패턴 — 단일 헬퍼로 통합** — fix 분산이 회귀 source | F-8 v2 (`_build_preference_time_slots` / `_build_multi_date_slots` 등) |
| L-6 | **같은 meeting_id 라이프사이클 시간 source 단일화** — DB / payload 메모리 분리 시 진화 단계마다 회귀 | C8 (partial maedeup vs `_publish_maedeup_place_update`) |
| L-7 | **commit 분리 정책** — 의미 다른 변경 묶지 말 것 (revert/bisect 단위) | dc9d66b (C7 + deepcopy 묶음) |
| L-8 | **데이터 흐름 끝점까지 매핑 확인** — 새 필드 만들 때 producer만 보지 말고 consumer까지 trace | consensus_label slot_context drop |
| L-9 | **slot_idx ↔ wall clock 변환은 backend 헬퍼 단일 source** — `TIME_SLOT_FIRST_HOUR + TIME_SLOT_MINUTES` 분산 시 혼란 | A3-3 wall-clock 변환 09:00 base 누락 |
| L-10 | **외부 영향 큰 객체 (`copy.deepcopy`) hot path 도입은 라이브 검증 필수** — Codex 정적 분석으로 silent fail 못 잡음 | deepcopy 회귀 |

---

## 8. 변경 영향 분석 체크리스트 (terminal이 변경 brief 줄 때 내가 돌리는 절차)

1. **파일 매핑** — §3 충돌 zone 표에서 해당 파일 위치 → L/F/G 어느 영역?
2. **Contract 매핑** — §2 C1~C8 중 어느 contract 건드림?
   - WS payload 추가/변경? → C1 / C5 (양쪽 동시)
   - REST schema? → C2 / C3 (caller 확인)
   - 상수? → C4 (양쪽 미러)
   - LangGraph state 키? → C6 (라우터 영향)
   - TimeBar 슬롯 상수? → C7 (양쪽 미러)
   - maedeup 시간 source? → C8 (DB ↔ payload 메모리 일관성)
3. **회귀 hot zone 교차 검증** — §4의 ID 중 영향 받는 거 있나?
4. **Lessons 교차 검증** — §7 L-1 ~ L-10 중 해당하는 anti-pattern 있나?
5. **다른 터미널 미커밋 영역과 겹침?** — 핸드오프 doc 3개 + git status로 확인
6. **검증 포인트 제시** — 어느 로그 / 어느 UI 흐름 통과해야 OK
7. **commit 단위 권고** — L-7 (의미 다른 변경 분리) 따름

---

## 9. 살아있는 reference 갱신 정책

본 doc은 **session 단위로 내가 갱신**. 갱신 시점:
- 새 contract 추가 (예: A3-2처럼 신규 endpoint) → §2에 항목 추가
- 회귀 발생 → §4에 ID 추가 + 원인 / 방어 포인트
- 충돌 zone 발견 → §3 표 업데이트
- 노드 / 라우터 변경 → §1 다이어그램 + §5 매핑 갱신

코드 SoT가 우선이므로 본 doc과 코드 충돌 시 **코드 따라간다**. 본 doc의 line 번호는 stale 가능성 있음.
