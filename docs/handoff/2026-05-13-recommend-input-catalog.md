# 추천 노드 인풋 카탈로그 — "쓸 수 있는 재료" 목록

작성: 2026-05-13
대상 노드: `vote_card_creation` (시간 추천), `place_recommendation` (장소 추천)
목적: 팀원이 노드 내부 로직을 짤 때 "어떤 재료들 중 골라서 어떻게 조합할지" 결정할 수 있도록, **활용 가능한 모든 정보**를 카탈로그로 정리.

## 사용법

각 재료는 3가지 마크 중 하나:
- ✅ **노드가 이미 활용 중** — 그대로 쓰면 됨
- ⚠️ **state에 들어오지만 안 쓰임 / 일부 케이스에서 누락** — 활용 가능, 조건 확인 필요
- 🔧 **데이터는 있지만 노드까지 전달 안 됨** — 아키텍처 측에서 plumbing 해줘야 함

활용 가능 노드:
- 🗓 = vote_card_creation
- 📍 = place_recommendation
- 🗓📍 = 둘 다

---

## 1. 사용자가 직접 말한 것 (이번 발화에서 추출)

`quick_classify` + `entity_extraction`이 만드는 신호들.

| 정보 | 마크 | 데이터 출처 | 노드 | 비고 |
|---|:---:|---|:---:|---|
| 의도 분류 (schedule/place/both/general) | ⚠️ | `quick_classify` → `direct_request_kind` | 🗓📍 | `state["intent"]`로 변환 안 됨 — direct_request 경로 |
| 명시 날짜 (date_hint) | ✅ | `entity_extraction` | 🗓 | "내일" → "2026-05-14" 변환됨 |
| 다중 날짜 (date_hints) | ✅ | `entity_extraction` | 🗓 | 2개 이상이면 multi_date_vote 분기 |
| 명시 시간 (parsed_time_hint) | ⚠️ | `entity_extraction` | 🗓 | state엔 있지만 vote_card가 직접 안 씀. slot label에만 간접 반영 |
| 명시 장소 (place_hint) | ✅ | `entity_extraction` | 📍 | "천안터미널" 같은 미등록 지명은 None |
| 장소 좌표 (place_coord) | ✅ | `_resolve_place_coord` Kakao geocode | 📍 | 없으면 Kakao 검색 반경 무제한 |
| 인원 (headcount) | ⚠️ | `entity_extraction` | 🗓📍 | direct_request에서 대부분 None. supervisor_validation이 에러 처리 |
| 모임 종류 (meeting_type) | ✅ | `entity_extraction` | 🗓📍 | 없으면 "모임" 기본값 |
| cuisine 키워드 | ⚠️ | `_detect_cuisine_type` | 📍 | place_recommendation 내부에서 자체 감지. state 밖 |
| 거부 표현 (rejected_dates) | ✅ | `entity_extraction` | 🗓 | "월요일 안돼" — 슬롯에서 자동 제외 |
| 충돌 옵션 (conflict_options) | ✅ | `entity_extraction` | 🗓 | "A는 X, B는 Y" — 투표 분기 |
| 긴급도 ("지금", "1시간 안") | 🔧 | 아직 추출 안 함 | 🗓📍 | entity_extraction에 키워드 추가 필요 |
| 시간 범위 (time_window: start~end ISO) | 🔧 | parsed_time_hint를 정규화해야 함 | 🗓 | 명시 시간을 단일 슬롯으로 만들려면 필수 |

---

## 2. 발화자 본인 정보 (요청한 사람)

`viewer_user_id`로 User 테이블 lookup. 발화자 의도/맥락이 그룹 평균보다 중요한 경우 1순위.

| 정보 | 마크 | 데이터 출처 | 노드 | 비고 |
|---|:---:|---|:---:|---|
| 발화자 식별 (user_id) | ⚠️ | GraphState `viewer_user_id` 있음 | 🗓📍 | 두 추천 노드 모두 안 씀 |
| 거주지 (home_base) | 🔧 | User.home_base 컬럼 존재 | 📍 | place_coord fallback 1순위로 좋음 |
| 음식 선호 (food_preferences) | 🔧 | User.food_preferences JSON | 📍 | 지금은 방 전체 합산만 씀 |
| 음식 비선호 (food_restrictions) | 🔧 | User.food_restrictions | 📍 | 발화자 본인 제약 명시 가능 |
| 선호 지역 (liked_areas) | 🔧 | User.liked_areas | 📍 | 가산점 후보 |
| 비선호 지역 (disliked_areas) | 🔧 | User.disliked_areas | 📍 | 제외 후보 |
| 시간 선호 (time_preference) | 🔧 | User.time_preference | 🗓 | "주말저녁" 같은 텍스트 |
| 이동수단 (transport_mode) | 🔧 | User.transport_mode | 📍 | 대중교통 → 역세권, 도보 → 가까운 곳 |
| 캘린더 busy (GCal) | ✅ | `_get_user_busy_periods` | 🗓 | viewer_user_id 기반 호출됨 |

---

## 3. 방 멤버 정보 (방 전체)

| 정보 | 마크 | 데이터 출처 | 노드 | 비고 |
|---|:---:|---|:---:|---|
| 멤버 수 (total_members) | ✅ | `_load_meeting_preferences` | 🗓📍 | headcount fallback 후보 |
| 각자 모임 선호 (MeetingPreference) | ✅ | DB | 🗓📍 | 시간대/장소/음식. 입장 팝업에서 수집 |
| 비선호 음식 합집합 | ✅ | `_get_room_member_food_preferences` | 📍 | place 점수 페널티 |
| 6 카테고리 personal data 익명 합산 | ✅ | `_get_room_member_constraints` | 📍 | place_recommendation Gemini prompt에 |
| 명명된 personal data (시연용) | ✅ | `_get_room_member_constraints_named` | 📍 | privacy 트레이드오프 의식적 |
| 멤버별 GCal busy | ✅ | `_load_busy_by_user_for_state` | 🗓 | 슬롯 라벨에 "OOO님 불참" 박힘 |
| 멤버별 거주지 | 🔧 | User.home_base 합집합 | 📍 | 중간 지점 계산 가능 |
| 친구 관계 (Friendship) | 🔧 | DB | 🗓📍 | 우선순위 가중치? (P2) |
| 공통 가능 시간대 (preference_common_times) | ✅ | `_load_meeting_preferences` 교차 | 🗓 | "평일저녁" → vote_card 평일만 필터 |
| 모임 메모 (notes) | ⚠️ | `_load_meeting_preferences` | 🗓📍 | state까지 옴, 추천에 활용 안 됨 |

---

## 4. 방 컨텍스트 (대화 흐름 / 과거)

| 정보 | 마크 | 데이터 출처 | 노드 | 비고 |
|---|:---:|---|:---:|---|
| 최근 메시지 (message_records) | ✅ | `MessageReader.load_agent_context` | 🗓📍 | cuisine 감지 fallback 등 |
| 대화 요약 (conversation_summary) | ⚠️ | 10개 단위로 Gemini 갱신 | 🗓📍 | state엔 있지만 추천에 활용 안 됨 |
| 소셜 채널 최근 (social_recent) | ✅ | DB | 🗓📍 | entity/general 노드만 씀 |
| 누적 거부 날짜 (rejected_dates) | ✅ | `entity_extraction` 누적 | 🗓 | vote_card 안전망 필터 |
| trigger_message_text | ✅ | agent.py | 📍 | cuisine 감지 1순위 |
| 이전 추천 카드 (재추천 방지) | 🔧 | meeting 테이블에 vote_options 있음 | 🗓📍 | "다시 추천해줘"에 활용 안 됨 |
| 과거 모임 기록 (AIMemory meeting_record) | 🔧 | AIMemory 테이블 | 🗓📍 | 종료된 모임 패턴, 안 씀 |
| "다시" / "재추천" 신호 | ⚠️ | function_calling에서 noise filter만 | 🗓📍 | 명시적 재추천 분기 없음 |

---

## 5. 외부 신호 (API / ML)

| 정보 | 마크 | 데이터 출처 | 노드 | 비고 |
|---|:---:|---|:---:|---|
| Kakao 검색 결과 (place_search_results) | ✅ | `search_place` | 📍 | name, address, category, distance_m, x, y |
| 거리 점수 (distance_m → score) | ✅ | `search_place` 자체 계산 | 📍 | 500m이내 1.0 / 2km 0.5 / 5km+ 0.2 |
| ML 추천 점수 (LGBMRanker) | ✅ | `_ml_place_search` | 📍 | top 5 |
| Gemini scoring | ✅ | `place_recommendation` 내부 | 📍 | top 5 결과를 reranking |
| 휴일 정보 (Korean holiday) | ✅ | `_get_korean_holiday` | 🗓 | 슬롯 라벨에 박힘 |
| 주말 여부 | ✅ | `_is_weekend` | 🗓 | preference_common_times "평일~"과 매칭 |
| 영업시간 | 🔧 | Kakao API 일부 제공 | 📍 | 현재는 Gemini prompt로만 "시간대 어울리는 곳" 안내 |
| 날씨 | 🔧 | 외부 API 필요 | 📍 | P2 후보 |

---

## 6. 시스템 상태 (LangGraph state)

| 정보 | 마크 | 데이터 출처 | 노드 | 비고 |
|---|:---:|---|:---:|---|
| trigger_reason | ✅ | agent.py | 🗓📍 | stalemate/conclusion/all_members/direct_request |
| direct_request_kind | ✅ | quick_classify | 🗓📍 | place 분류 시 vote 스킵 분기 ([:4842](../../backend/app/services/langgraph_pipeline.py)) |
| calendar_strategy | ✅ | function_calling | 🗓 | multi_date_vote / preference_based / natural_language_time_options |
| partial_mode (time_only) | ✅ | slot_filling | 🗓 | maedeup 직행 분기 |
| expanded_to_next_week | ✅ | entity_extraction | 🗓 | 모든 후보 거부 시 다음주 확장 |
| is_location_first | ✅ | slot_filling | 📍 | date 없이 place만 |
| awaiting_user_reply | ✅ | slot_filling | 🗓📍 | 현재 슬롯 진행 단계 |
| 슬롯 진행 차수 (slot_filling_turns) | ✅ | slot_filling | 🗓📍 | acknowledgment 중복 방지 |

---

## 우선순위 권장 (P0~P2)

### P0 — 오늘/내일 plumbing 필수 (BUG fix와 직결)

오늘 발견된 "내일 6시 잡아줘" / "천안터미널 식당" 카드 미생성 버그가 이 6개로 해결:

| # | 재료 | 작업 | 영향 |
|---|---|---|---|
| 1 | `intent` 명시 세팅 | agent.py에서 quick_classify kind → state["intent"] 매핑 | direct_request 경로의 모든 intent 분기 dead → 살아남 |
| 2 | `requester_user_id` 노출 | viewer_user_id를 추천 노드에서 활용 | 발화자 정보 lookup 가능 |
| 3 | `requester_home_base` | User.home_base lookup → state | place_hint 없을 때 검색 중심점 |
| 4 | `requester_preferences` 묶음 | User.food_*, *_areas, transport_mode → state dict | 발화자 의도 우선 반영 |
| 5 | `time_window` | parsed_time_hint를 ISO range로 정규화 | "내일 6시"를 단일 슬롯 vote_card로 변환 가능 |
| 6 | `cuisine` state 명시 | place_recommendation 내부 감지를 state로 끌어올림 | vote_card도 cuisine 알 수 있음 (음식점-친화 시간 추천) |

### P1 — 1주차 (추천 품질 ↑)

| # | 재료 | 효과 |
|---|---|---|
| 7 | `room_member_home_bases` (멤버 거주지 합집합) | 중간 지점 자동 계산 |
| 8 | `previous_recommendations` (이 방 이전 카드들) | "다시" 케이스 = 직전 결과 제외 |
| 9 | `urgency_signal` (지금/오늘/1시간 안) | 영업시간/거리 가중치 동적 조정 |
| 10 | `group_constraints_summary` precomputed | vote_card_creation도 같은 컨텍스트 활용 (현재 place만) |
| 11 | `notes` (방 멤버 메모) 활용 | 추천 이유에 멤버 노트 반영 |

### P2 — 시연 후

| # | 재료 | 비고 |
|---|---|---|
| 12 | `AIMemory.meeting_record` 활용 | 과거 모임 패턴 (식당 카테고리 분포 등) |
| 13 | `Friendship` 우선순위 | 친한 친구 선호 가중치 |
| 14 | `weather_forecast` | 야외/실내 추천 |
| 15 | `place_business_hours` 정규화 | Kakao API 추가 호출 |

---

## 결정 안건 (회의에서 정해야 할 것)

재료가 많은 만큼 "어떻게 조합할지" 정책 결정 필요. 노드 짜는 사람이 혼자 결정하기 어려운 5개:

| # | 결정 | 선택지 |
|---|---|---|
| Q1 | vote_card: 슬롯 1개일 때도 카드 발행? | A) direct_request만 허용 / B) 항상 허용 / C) single이면 maedeup 직행 |
| Q2 | place_hint 없을 때 fallback 순서 | requester_home_base → 멤버 home_base 중간 → preference best_location → 강남 |
| Q3 | headcount None 시 기본값 | A) 멤버 수 / B) 2 / C) None 허용 |
| Q4 | 추천 점수 통합 공식 (현재 묻혀있음) | 예: `final = 0.4*ML + 0.3*거리 + 0.2*Gemini - dislike_penalty` |
| Q5 | 발화자 vs 그룹 충돌 시 | A) 그룹 제약 우선 / B) 발화자 명시 우선 / C) UI에서 확인 |

---

## 한 줄 요약

> **추천 노드 2개가 활용 가능한 재료는 6 카테고리, 약 40개. 그중 ✅(즉시 사용 가능) 22개, ⚠️(있는데 안 씀) 8개, 🔧(plumbing 필요) 10개.** P0 6개만 plumbing 끝내면 오늘 발견한 "내일 6시" / "천안터미널" 두 버그가 해결되고, 팀원이 노드 안 로직을 짤 재료가 충분히 갖춰진다. Q1~Q5 결정 후 P1 5개 추가하면 추천 품질이 다음 단계.
