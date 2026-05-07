# 시연 시나리오 v3 ↔ 코드베이스 검수 (2026-05-07)

> SoT: `demo-scenario.md` (노션 9주차 통합 시나리오 반영)
> 본 문서는 **시나리오 vs 실제 코드 불일치** 만 정리. 우선순위는 시연 임팩트 기준.

---

## ✅ 동작 (코드 확인 끝, 시나리오대로 작동)

| ACT | 기능 | 위치 |
| --- | --- | --- |
| 0 | PersonalData / MeetingList / MiniCalendar / UpcomingMeeting / NotificationPanel / InviteModal / ExplorePage 위젯 | `frontend/src/components/home/*` |
| 1 | 게스트 카톡 링크 입장 | `rooms.py:174 /guest-join` |
| 2 | rejected_dates LLM 추출 (F) | `_analyze_conversation` (langgraph_pipeline.py:4309) |
| 2 | 다음주 자동 확장 (N) | `expanded_to_next_week` flag (line 2429) |
| 2 | 채팅 거부 → 캘린더 sync (P) | `_sync_chat_rejected_to_unavailability` (agent.py:184) |
| 3 | TimeBar all_members_selected 트리거 | langgraph_pipeline.py:2805 |
| 4 | Partial maedeup_card (time-only) | "time-only partial card" (line 2805) |
| 5 | meeting_id 카드 갱신 (J) | "Fix J: place cards join the same lifecycle" (line 3534) |
| 5 | Personal Data → reasoning 합성 | `_get_room_member_constraints` + line 3631 |
| 6 | 모임 종료 → personal_data 추출 | maedeup_card_creation → memory_extraction → END |
| 6 | PersonalData 실시간 갱신 publish | `personal_data:user:{uid}:updated` (line 3884) |

---

## ❌ 시나리오 ↔ 코드 불일치 (수정 1순위)

| # | 시나리오 박힌 멘트 | 실제 코드 | 영향 |
| --- | --- | --- | --- |
| **A5-1** | ACT 5: "3~5초 단축 경로" + "강남에서 다 같이 갈만한 한식집" | quick_classify 정규식이 이 문구 못 잡음 → entity_extraction 6초 + place 9초 = **14~21초** | 시연 임팩트 ≈ 0 (말과 화면 불일치) |
| **A5-2** | ACT 5: reasoning에 *"수현님 채식·홍대 비선호 ✨ 반영"* (이름 인용) | 실제 reasoning 톤은 익명 그룹 — *"멤버 중 채식주의자가 있어요"* (line 1915 "익명 group constraint 요약") | 임팩트 ↓↓ — "수현이 한 마디도 안 했는데 자동 반영" 멘트 효과 약화 |
| **A4-1** | ACT 4: confirm 후 "일정이 확정되었습니다" 박스 | 백엔드 confirm은 정상이나 후속 메시지 emit 안 함 | 화면 변화 없어 어색함 |
| **A5-3** | ACT 5: 첫 카드 "한식" 추천 | Kakao 검색이 첫 카드로 중식/일식 줌 (장소 카테고리 매핑 부족) | 멘트 "한식 맛집"과 화면 불일치 |

---

## ⚠️ 잠재 리스크 (직접 검증 필요)

| # | 항목 | 우려 |
| --- | --- | --- |
| **A1-1** | ACT 1 NotificationPanel 알림 흐름 | 컴포넌트는 있으나 모임 초대 발송/수신 end-to-end 동작 확인 안 함 |
| **A6-1** | ACT 0→6 메인 복귀 시 ✨ 갱신 | `personal_data:user:{uid}:updated` publish는 있지만 프론트가 받아 메인 위젯 invalidate하는지 미검증 |
| **A2-1** | ACT 2 P 게스트 동명이인 | 시뮬용으로 게스트 필터 푼 상태 — 시연 4명 이름 다 다르니 OK, 현실 깨짐 (시연 후 보완) |
| **A0-1** | 사전 ✨ 시드 (지민·수현·민수) | 시연 D-1에 PersonalData seed 스크립트로 박아둬야 함 |

---

## 우선순위 (시연 안전선)

### 🔴 P0 — 시연에 직접 보임 (수정 1순위)
1. **A5-1** ACT 5 quick_classify 단축 (정규식 보강)
2. **A5-2** ACT 5 reasoning 톤 — 이름 인용으로 변경 (프롬프트 강화)
3. **A4-1** ACT 4 confirm 후속 메시지 emit
4. **A5-3** ACT 5 한식 정확도 (Kakao 카테고리 매핑)

### 🟡 P1 — 시연 멘트 차원 (검증 + 백업 멘트 준비)
1. **A1-1** ACT 1 NotificationPanel 정상 동작 검증
2. **A6-1** ACT 6 메인 위젯 ✨ 실시간 반영 검증

### 🟢 P2 — 시연 사전 작업 (D-1 일과)
1. **A0-1** PersonalData D-1 시드 스크립트
2. **A2-1** 해결점 P 게스트 필터 + 발신자 ID 매핑 (시연 후 보완)

---

## 참고
- 시나리오 SoT: `demo-scenario.md`
- 누적 해결점 A~P 원장: `audit-findings.md`
- 노션 원천: 9주차 (2026-05-06) 토글 "수정안 05-06"

---

## 2026-05-07 라이브 검증 결과

> chromium UI 통한 시연 시나리오 풀-루프 검증. 4명 멤버 (지민 호스트 + 수현/민수/예린 게스트), Personal Data 시드 후.

### 통과 ✅

| ACT | 항목 | 비고 |
| --- | --- | --- |
| 2 | 4번째 메시지 자동 교착 감지 + "대화가 길어지네요" narration (해결점 A·B) | 즉시 발화 |
| 2 | 자연어 거부 ISO 추출 5/8·9·10 모두 (해결점 F) | "동아리 MT", "본가", "쉬고 싶다" 모두 매핑 |
| 2 | 캘린더 sync 5/8·9·10 빨간 카운트 1 표시 (해결점 P) | `_sync_chat_rejected_to_unavailability` |
| 2 | 선호 시간 18:00 반영 (시나리오 "평일 저녁") | ACT 1 선호도 입력 필수 — 누락 시 14:00 기본값 |
| 2 | meeting_summary 카드 자동 발행 ("날짜: 다음 주 / 시험 끝나고 / 이번 주 금/토/일 불가") | 추가 가치 |
| 3 | narration "모두 시간 선택 완료! 19:00~21:00이 겹쳐요" | **A3-1 fix 적용 후** (commit `22b235b`) |
| 4 | vote_card "시간대 변경" → 캘린더 자동 highlight + "시간대 합의 중..." placeholder | 4b 분기 정상 |
| 5 | quick_classify 단축 → 장소 카드 발행 (한식집 query) | **A5-1 fix 적용 후** (commit `13110cb`). 18s — 시나리오 3~5s보다 길지만 일반 채팅 fallback 회피 ✓ |
| 6 | `personal_data_extractor` 자동 호출 — 거부 발화에서 멤버별 정보 학습 | `is_ai_filled` 갱신 확인 |

### 신규 미해결 ❌

| # | 우선 | 항목 | 위치 / 노트 |
| --- | --- | --- | --- |
| **A3-2** | 🔥 P0 | TimeBar 전원 합의 즉시 자동 파이프라인 발동 — **사용자 의도 없이 AI가 마음대로 확정**으로 보임. 합의 시각 narration도 자동으로 떠버림. | 기대: TimeBar 합의 → 시각화만 (전원 row 색칠) → 호스트 "확정하기" 클릭 → 그제서야 narration + 파이프라인. <br>변경 위치: `social.py:_maybe_emit_proposal:104` 의 `redis.publish(agent_channel, trigger_payload)` 자동 호출 제거. 새 WS msg type `schedule_consensus_ready` 송출 (호스트에 "확정하기" 버튼 노출용). 호스트 클릭 → 새 핸들러 (`schedule_confirm` WS 또는 REST) → `ai_auto_trigger` publish. agent.py 측은 변경 없음. |
| **A4-3** | 🔥 P0 | `all_members_selected` trigger → 시나리오 ACT 4 = **Partial maedeup 카드** 기대인데 실제 **place_recommendation 카드 직행**. | 호스트 PD(한식·강남·저녁형) 영향으로 trigger_intent가 place로 분기 추정. `langgraph_pipeline` trigger 분기 로직 검토. Partial 카드 (시간만, 장소 placeholder) 강제 발행 옵션 또는 trigger_reason 기반 분기. |
| **A6-1** | ⚠️ P1 | `memory_extraction`이 채팅 거부 발화를 `time_preference` 카테고리에 저장 — *"5월 8일 동아리 MT로 인해 불가능"* 같은 거부 메시지가 `time_preference` 필드에 들어감. | 카테고리 misclassification. `time_preference`는 "저녁형/오전형" 같은 정성 값이어야 함. 거부는 별도 unavailability 또는 rejected_dates로. extractor 프롬프트/스키마 보강 필요. |

### Docs 정정 (시나리오 자체 수정)

| # | 시나리오 박힌 값 | 실제 / 권장 | 노트 |
| --- | --- | --- | --- |
| **D-A2-1** | 추천 카드 "5/12 (월) 18:00" — 다음주 N-확장 가정 | 실제 5/11 (월) — 5/8·9·10만 거부, 5/11 살아있어 N 미발동 | "가장 가까운 가능 후보 노출" 로직 정상. 시나리오 멘트 정정 또는 5번째 메시지 추가 (예: "11일도 시험"). |
| **D-A2-3** | "5/12 (월)" | 실제 5/12는 **화요일** | 요일 표기 단순 오류 |
| **D-A3-1** | narration "19:00~20:30이 겹쳐요" | 실제 A3-1 fix는 longest contiguous overlap = "19:00~21:00이 겹쳐요" | 시나리오 selections 산수상 19:00~21:00이 맞음 |

### 우선순위 (이 세션 기준)

- 🔥 P0 신규: **A3-2** (자동 발동 차단), **A4-3** (Partial 카드 분기)
- ⚠️ P1 신규: **A6-1** (extractor 카테고리), 기존 **A5-2** (reasoning ✨ 이름 인용 미검증, 카드 detail 확인 또는 프롬프트 보강)
- 🟡 docs: **D-A2-1**, **D-A2-3**, **D-A3-1** — `demo-scenario.md` 단순 정정

### 이미 fix됨

- ✅ **A5-1**: quick_classify 정규식 3-갈래 OR + langgraph `_PLACE_INTENT_PATTERN` 보강 — commit `13110cb`
- ✅ **A3-1** (신규 추적): narration 합의 시간대 동적 주입 — commit `22b235b`
- ✅ **A0-1**: PersonalData D-1 시드 스크립트 (`backend/scripts/seed_demo_personal_data.py`) — idempotent + `--dry-run` 지원
- ✅ **D 카테고리**: TimeBar 추천 범위 선호도 동기화 (옵션 A) — commit `6877461`
- ✅ **A3-2 backend + frontend**: 자동 발동 차단 + 호스트 확정 게이트 — commits `4478608` + `7b3fce7`
- ✅ **A4-1**: confirm 후속 안내 박스 emit (`agent_messaging.py` 헬퍼 + meetings.py 통합) — commit `5d709f2`
- ✅ **A4-3**: all_members_selected → time-only Partial maedeup 카드 정상 발행 (`[TRIGGER] all_members_selected time-only partial card` 로그 확인) — A3-2 fix 이후 자연스럽게 정정
- ✅ **A6-1**: memory_extractor 카테고리 misclass 차단 (거부 발화 → time_preference 저장 중단, `0 users affected` 로그 확인) — commit `cd2d7c2`

---

## 2026-05-07 후속 라이브 검증 (A3-2 frontend 적용 후)

> 풀-루프 재검증 (room 35). A3-2 게이트 + A4-3 Partial 카드 + A6-1 카테고리 차단 모두 통과.
> 단 신규 4건 발견.

### F 시리즈 — 모두 fix 완료 ✅

F-1 ~ F-4 5/7 검증 + 5/8 회귀 fix 모두 commit + 라이브 검증 통과.

| # | 결과 | Commit |
| --- | --- | --- |
| **F-1 v2** | ✅ pending meeting 재사용 가드 (date_hint 매칭 + 30분 fallback) — vote_card → maedeup_card 같은 meeting_id로 라이프사이클 | `74779ba` |
| **F-2** | ✅ TimeBar 추천 18-21 정확 (refresh trigger + InfoPane 디버깅으로 자연 회복) | `42fef84` (overflowX 제거) + 진단 로그 |
| **F-3** | ✅ entity_extraction direct_request fast-skip 0.09s (이전 15s) | `4c5ce48` |
| **F-4 (1차)** | ✅ meeting_summary 풍부화 (멤버별 거부 사유 + 합의 흐름) | `4c5ce48` |
| **F-4 (회귀)** | ✅ signals.preferred_dates ISO 변환 강제 — 풍부 카드 + slot 빌드 양립 | `b8dd909` |
| F-5 | 무시 OK | (오늘 추천 없음 — 의도된 skip) |

### 5/8 후속 — 모두 ✅ 통과

| # | 검증 결과 | Commit |
| --- | --- | --- |
| **A5-2** | ✅ reasoning ✨ 멤버 이름 인용 — "수현님 채식 식단 · 홍대 비선호 ✨ · 김창윤님 한식 선호 ..." place card에 indigo 박스로 정상 노출 | `642f50b` (frontend 렌더) + 기존 `_build_named_constraints_summary` |
| **AI 응답 지연 (top 5 lever)** | ✅ place_recommendation 38.27s → 22.14s (-42%, first run). variance 큼 (53s second) — Gemini 외부 의존, 단축 효과는 명확 | `a0d6136` |
| **F-1 v2 root cause** | ✅ AsyncSessionLocal import 누락 fix — silent NameError 차단. 라이프사이클 정상 | `493f48e` |
| **G-1 member_joined** | ✅ 게스트 join 시 캘린더 X/N reload 없이 자동 갱신 ("4/4" → "5/5") | `f2c2cde` |
| **P0-2 ACT 4 단축** | ✅ TOTAL 4.51s → 0.02s (-99.5%). function_calling 신규 [TIMING] 라인 분리 / memory_extraction 4초 별도 fire-and-forget | `a0d6136` |

### 남은 P1 (시연 영향 미미)

| # | 우선 | 항목 |
| --- | --- | --- |
| **AI 응답 variance** | ⚠️ 외부 | place_recommendation Gemini scoring 22~53s 변동. 추가 단축 lever (캐싱/병렬화) 시연 후 |

### 5/8 A3-3 라이브 후 신규 발견

| # | 우선 | 항목 | 작업자 |
| --- | --- | --- | --- |
| **F-5** | 🔥 P1 | **TimeBar individual confirm 버튼 라이프사이클** — host TimeBar slot click 후 노출된 "오후 6:00 ~ 오후 9:00로 확정" 버튼이 그룹 확정 후에도 잔존. **F-5 v1 fix(`43bb1b2`) 적용했으나 회귀 — `isMeetingConfirmed` 판정이 partial maedeup 케이스 미포함** (`lastConfirmedMeeting`/`infoPanePhase==="timeConfirmed"` 둘 다 partial 시점 set 안 됨). | frontend `TimeBarSelector` — `isMeetingConfirmed` 판정 조건에 partial maedeup 발행 시점 포함 (e.g. `infoPanePhase==="dateConfirmed"`이고 maedeup_card 존재 시) |
| **F-6** | ⚠️ P1 | **AI 패널 카드/채팅 시간순 정렬 깨짐** — 채팅 메시지와 카드가 시간순으로 흐르지 않고 **카드가 항상 상단으로 누적**됨 | frontend AssistantPane — 카드 + 메시지 단일 timeline으로 통합 정렬 |
| **F-7** | 🔥 P1 | **캘린더 멤버 현황 창의 "AI 추천 날짜" 라벨이 vote_card 실제 추천(5/11 18:00)과 불일치** | frontend `CalendarPane` (또는 일자 상세 패널) — vote_card / maedeup_card의 `recommended_date`를 SoT로. 자체 휴리스틱(가능 인원 최대 날짜)은 fallback으로만 |
| **F-8** | 🔥 P1 | **TimeBar 추천 시간대 9-13으로 fallback** (평일저녁 18-21 시드인데도) — 추정 원인: host google calendar busy_periods가 18-21에 있어 그 영역 슬롯 점령 → `recommendedRange` longest-streak이 빈 9-13으로. preferredTimeRange prop은 들어가지만 busy 영역 안 빠지면 무력화 | frontend `TimeBarSelector.recommendedRange` — preferred 범위 안 가능 슬롯 1개라도 있으면 그쪽 우선 또는 visual 마커. 현재 1차 결과 0이면 2차로 빠지는 로직 보강 |
| **F-9** | ⚠️ P1 | **PlaceDetailPane 장소 확정 버튼 동기화 누락** — AI 패널 장소 카드 [이 장소로 확정] 클릭 → maedeup 갱신되나 우측 PlaceDetailPane의 [이 장소로 확정] 버튼은 활성 그대로 (중복 confirm 가능) | `MeetingContext`에 `confirmedPlaceId` state 추가 + `PlaceDetailPane`에서 매치 시 disabled / "확정됨" 안내로 교체 |
| **A3-3 slider default** | 🟢 fix됨 | HostTimeAdjustModal default 가장 긴 전원 segment 알고리즘 — `b86041c` 커밋 후 `findLongestFullCoverageSegment` 헬퍼로 정정 | (검증 후 재확인) |
