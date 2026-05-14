# 기능정의서 — 시간·장소 조율 (Time & Place Coordination)

작성: 2026-05-14
작성자: 본인 (장소/시간 조율 담당)
대상 노드: `slot_filling` (입력 처리) + `vote_card_creation` (시간 카드) + `function_calling`의 캘린더 path + `place_recommendation` (장소 카드) + `maedeup_card_creation` (확정·partial 카드)
관련 문서:
- [recommend-input-catalog.md](./2026-05-13-recommend-input-catalog.md) — 활용 가능 인풋 카탈로그
- [pipeline-structure.html](./pipeline-structure.html) — 파이프라인 구조

> **목적**: 채팅방에서 모임 **시간과 장소**를 합의하는 과정을 자동화한다. 사용자 발화·캘린더·선호도를 통합하여 (a) 합의 가능한 후보 시간을 투표 카드(vote_card)로, (b) 그룹·발화자 선호를 반영한 후보 장소를 추천 카드(place_recommendation)로 제시하고, (c) 합의된 결과를 매듭 카드(maedeup_card 확정/partial)로 마무리하는 책임.

---

## 1. 기능 개요

### 1.1 핵심 가치 (한 문장)
**채팅으로 흩어진 시간·장소 의사를 자동으로 모아 "투표 가능한 후보 슬롯"과 "그룹·발화자 선호를 반영한 후보 장소"로 변환하고, 합의 결과를 매듭 카드로 마무리한다.**

### 1.2 시스템 위치
- **slot_filling (노드 3)**: 사용자 발화·캘린더·선호도를 읽어 슬롯 상태 채우기 (시간·장소 공통 진입)
- **function_calling (노드 4)**: 캘린더 API 호출 (`get_free_slots`), 빈 슬롯 계산
- **vote_card_creation (노드 6a)**: 후보 슬롯을 투표 카드 페이로드로 직렬화 + meeting pending 생성
- **place_recommendation (노드 6b)**: place_hint·home_base·그룹/발화자 선호로 Kakao 검색 + ML/Gemini reranking → 장소 추천 카드 페이로드
- **maedeup_card_creation (노드 7)**: 시간·장소 확정 시 매듭 카드(확정), 시간만 결정된 경우 partial(time_only) 카드 발행

이 spec은 **입력 발화부터 vote_card / place_recommendation / maedeup_card payload 발행까지** 시간·장소 통합 경로를 다룬다.

### 1.3 책임 경계
- ✅ 이 spec이 정의함
  - 어떤 발화가 시간/장소 조율 흐름을 트리거하는가
  - 시간 슬롯을 어떻게 만들고 거르는가 (선호/거부/캘린더 통합)
  - 장소 후보를 어떻게 추출·검색·재정렬하는가 (place_hint·home_base fallback, ML/Gemini reranking, 비선호 페널티)
  - 어떤 형태의 카드 페이로드(vote_card / place_recommendation / maedeup_card 확정·partial)를 출력하는가
  - 발화자 vs 그룹 선호 토글 메타(Q7=B) 정책 (`preference_source`·`preference_toggle_enabled`)
- ❌ 이 spec이 정의하지 않음
  - intent 분류 자체 (동료 영역, `intent_detection`)
  - 검증/판단 supervisor (동료 영역, `supervisor_validation`)
  - 캘린더 API 자체 (외부, `google_calendar.py`)
  - Kakao Local API / ML ranker 내부 구현 (외부 서비스)

---

## 2. 사용자 시나리오 (= 골든 회귀 케이스)

각 시나리오는 "발화/이벤트 → 기대 출력"으로 정의. **이 표가 §10 회귀 테스트의 일대일 원본이 된다.**

| ID | 발화 / 이벤트 | trigger_reason | 기대 출력 | 검증 포인트 |
|---|---|---|---|---|
| **S1. 기본 케이스** | "다음주에 모이자" | `direct_request` | 평일 저녁 시간 3~5개 vote_card | 모든 멤버 가능한 슬롯만 추천 |
| **S2. 거부 누적** | "월요일은 안돼" (이후 새 추천 요청) | `direct_request` | 월요일 제외된 vote_card | `rejected_dates` 누적, 안전망 필터 작동 |
| **S3. 선호 매칭** | (방 설정: 평일 오전 선호) "이번주 모이자" | `direct_request` | 평일 오전 슬롯만 vote_card | `preference_common_times` 적용, 주말 자동 제외 |
| **S4. 다음주 확장** | "이번주 모이자" → 이번주 모두 안됨 | `direct_request` | 다음주로 확장된 vote_card + 사유 narrator | `expanded_to_next_week=true`, 사용자에게 사유 안내 |
| **S5. 명시 단일 시간** | "내일 6시 어때" | `direct_request` | 단일 슬롯 vote_card (날짜범위 확정 전제, Q1=B) | 단일이어도 명시적 동의 의식 부여 |
| **S6. 채팅 기반 충돌 감지** | (TimeBar에서 멤버 전원 선택 완료) | `all_members_selected` | TimeBar 데이터 기반 vote_card | 채팅에서 추출된 거부 시간 반영 |
| **S7. 시간대 충돌 투표** | "A는 토요일, B는 일요일이래" | `direct_request` | conflict_options 분기 vote_card | `conflict_options` 슬롯 생성 |
| **S8. 모두 불가 fallback** | 거부/캘린더로 가능한 슬롯 0개 | any | 가장 많은 멤버 가능한 슬롯 3개 vote_card + "전원 가능 시간 없음" narrator | "다수결 vote_card" 분기 — **v1.0 구현 대상 (Q6=A)**, 정렬: 시간 빠른 순 (Q8=A). 별도 우선 구현 PR-Y |
| **S9. 시간만 결정** | "다음주 화요일 6시" | `direct_request` | `time_only_ready` → maedeup 카드 직행 (vote_card 우회) | `partial_mode="time_only"` |
| **S10. 결론 자동 감지** | (멤버들이 채팅에서 "그럼 화요일 7시로 ㄱ") | `conclusion_detected` | maedeup 카드 직행 | vote_card 스킵, 결론 합의로 인식 |
| **S11. place_hint 명시** | "강남에서 모이자" | `direct_request` | 강남 좌표 기반 place_recommendation_payload (≤5 후보) | `place_hint="강남"`, `place_coord` 변환, `preference_source` 표기 (Q7=B) |
| **S12. place_hint 미지정 fallback** | "다음주에 모이자" (place_hint 없음) | `direct_request` | 선호 장소 다수결 → 동률 시 발화자 → 선호 없으면 방장 home_base 기준 추천 | F5 fallback 순서 (Q2), `preference_source="group"` 기본, 발화자 토글 시 `"speaker"` |
| **S13. cuisine 자동 감지** | "한식 먹자" | `direct_request` | 한식 카테고리 Kakao 검색 + reranking | `_detect_cuisine_type` → `meeting_type="한식"`, place_recommendation_payload |
| **S14. 그룹 비선호 음식 페널티** | (방 멤버 중 1명 disliked_food="갑각류") "맛집 추천해줘" | `direct_request` | 갑각류 키워드 포함 후보 score 0.1 강등 | `_contains_disliked_keyword` 패널티 (P4), 익명 합산 prompt |

### 2.1 비목표 시나리오 (Out of scope, §11)
- "매주 모이는 정기 모임" (recurring) — MVP에선 단일 약속만
- "오프라인 일정 import" (사용자가 따로 캘린더 등록) — Google Calendar로 한정
- "다른 모임과 시간 겹침 경고" — 다중 모임은 P2 이후

---

## 3. 출력 카드 페이로드 형식 (4종)

본 spec은 4종 카드 페이로드를 발행한다: `vote_card` (§3.1), `place_recommendation` (§3.2), `maedeup_card` 확정 (§3.3), `maedeup_card` partial/time_only (§3.4). narrator는 §3.5에 통합.

### 3.1 vote_card_payload (시간 투표)

실제 출력 JSON 스키마 (코드: `nodes/vote_card.py:259~279`).

```jsonc
{
  "type": "vote_card",
  "title": "저녁모임 시간 투표",          // meeting_type 기반. multi_date면 "날짜 투표 📅"
  "room_id": "abc123",
  "meeting_id": 42,                       // pending MeetingSchedule.id
  "time_options": [
    {
      "slot_id": "2026-05-19T18:00",
      "label": "5/19 (월) 18:00~20:00",   // _format_slot_label
      "start_at": "2026-05-19T18:00:00",
      "end_at":   "2026-05-19T20:00:00",
      "is_holiday": false,
      "holiday_name": null,
      "is_weekend": false
    }
    // ... 1~5개 (단일 슬롯도 발행 — Q1=B)
  ],
  "headcount": 4,                         // entity 추출 or 멤버수 fallback (Q3=A, 게스트 포함 Q12=A)
  "blocker_notification": null,           // F1 fallback 시 차단 멤버 (Q6=A, Q16=C 익명+더보기)
  "calendar_strategy": "natural_language_time_options",
                                          // multi_date_vote | preference_based | natural_language_time_options | n_minus_one | all_members_available
  "preference_source": "group",           // "group" | "speaker" (Q7=B)
  "preference_toggle_enabled": true       // false 조건 = C1 ∨ C3 ∨ C4 (Q7-c, C2 게스트 제외)
}
```

### 3.2 place_recommendation_payload (장소 추천)

실제 출력 JSON 스키마 (코드: `nodes/place.py:320~329`).

```jsonc
{
  "type": "place_recommendation",
  "room_id": "abc123",
  "meeting_id": 42,                       // pending MeetingSchedule.id (carry)
  "place_hint": "강남",                    // 발화 추출 or fallback (F5: 다수결 → 발화자 → 방장 home_base)
  "recommendations": [                    // ≤5개 (ML/Gemini reranking 결과)
    {
      "place_id": "12345",
      "name": "강남 OO식당",
      "category": "한식",
      "distance": 320,
      "score": 0.92,
      "address": "서울 강남구 ...",
      "url": "https://map.kakao.com/..."
    }
    // ...
  ],
  "group_constraints_summary": {          // 익명 합산
    "disliked_food": ["갑각류"],
    "disliked_areas": ["강북"],
    "transport_mode": "대중교통"
  },
  "preference_source": "group",           // "group" | "speaker" (Q7=B)
  "preference_toggle_enabled": true       // C1 ∨ C3 ∨ C4 시 false (Q7-c)
}
```

### 3.3 maedeup_card_payload (확정)

실제 출력 JSON 스키마 (코드: `nodes/maedeup.py:182~197`).

```jsonc
{
  "type": "maedeup_card",
  "room_id": "abc123",
  "meeting_id": 42,
  "title": "저녁모임 매듭",
  "intent": "schedule_decision",
  "date_hint": "2026-05-19",
  "place_hint": "강남",
  "headcount": 4,
  "meeting_type": "한식",
  "selected_time": {
    "label": "2026-05-19 19:00~21:00",
    "start_at": "2026-05-19T19:00:00",
    "end_at":   "2026-05-19T21:00:00"
  },
  "selected_place": {
    "name": "강남 OO식당",
    "place_id": "12345",
    "url": "https://map.kakao.com/..."
  },
  "vote_card": { /* carry */ },
  "place_recommendation": { /* carry */ },
  "calendar_registration": {              // 노드는 placeholder, 실제 등록은 confirm 라우터
    "provider": "google_calendar",
    "status": "skipped",
    "reason": "pending_confirmation"
  }
}
```

### 3.4 maedeup_card_payload (partial, time_only)

실제 출력 JSON 스키마 (코드: `nodes/maedeup.py:150~166`, 해결점 I·J·K).

```jsonc
{
  "type": "maedeup_card",
  "meeting_id": 42,
  "title": "저녁모임 매듭",
  "meeting_type": "저녁모임",
  "date_hint": "2026-05-19",
  "date": "2026-05-19",
  "time": "19:00~21:00",
  "selected_time": {
    "label": "2026-05-19 19:00~21:00",
    "start_at": "2026-05-19T19:00:00",
    "end_at":   "2026-05-19T21:00:00"
  },
  "selected_place": {},                   // 비어 있음
  "place": null,
  "place_pending": true,
  "place_pending_message": "멤버들이 장소를 정하면 자동으로 정리해드릴게요!",
  "headcount": 4,
  "calendar_registered": false
}
```

> **시간 번복 불가 (Q9=A)**: partial 카드 발행 후 장소가 채워져도 `selected_time`은 잠긴다. 시간 재선정은 `POST /meetings/{id}/recommendations/refresh` (§9) 명시 호출만 가능.

### 3.5 narrator 메시지 (4종 통합)

페이로드와 함께 발행되는 narrator 메시지.

- **vote_card**:
  ```
  "캘린더 확인 결과, 5/19 (월) 18:00~20:00을(를) 추천드려요. 📅 아래에서 확인해주세요."
  ```
  - `date_conflict=true`면: `"날짜가 엇갈리네요 (5/19: 3명, 5/20: 2명). 가장 많이 선택된 날짜 기준으로..."`
- **place_recommendation**: `"강남 근처 5곳을 찾아봤어요"` (`nodes/place.py:346~`)
- **maedeup_card (확정)**: `"확정됐어요!"`
- **maedeup_card (partial, time_only)**: `"장소는 멤버들이 정하면 자동으로 정리해드릴게요!"` (`place_pending_message`)
- **refresh 토글 (Q15=A)**: `"OOO님 선호 기준으로 다시 추천했어요"` — 발화자 실명 명시 (PII 노출 트레이드오프 인지). vote_card·place 양쪽 refresh 시 동일 문구.

### 3.6 페이로드 변경 시 영향 범위
- 프론트 `MeetingChatRoom.tsx` 카드 4종 렌더 (mock 컨트랙트)
- `confirm` 엔드포인트가 `meeting_id` + `slot_id`/`place_id`로 확정 호출
- `maedeup_card_creation`이 vote/place payload carry → `selected_time`/`selected_place` 추출
- `POST /meetings/{id}/recommendations/refresh` (§9 신설) 시 4종 모두 재발행 가능 (Q7-b 방 전체 broadcast)

---

## 4. 기능 상세 (Functional Detail Matrix)

> 사용자가 처음 던진 d1-1~d1-5는 성격이 다르므로 4개 레이어로 재정렬.

### 4.1 입력 인식 (Input Recognition)
| ID | 기능 | 트리거 | 처리 노드 | 데이터 출처 |
|---|---|---|---|---|
| R1 | 명시 날짜 추출 | "내일", "다음주 화요일" | entity_extraction | Gemini + `_parse_natural_date` |
| R2 | 명시 시간 추출 | "6시", "저녁 7시" | entity_extraction | Gemini → `parsed_time_hint` |
| R3 | 거부 날짜 추출 | "월요일 안돼", "주말 빼고" | entity_extraction | Gemini → `rejected_dates` |
| R4 | 다중 날짜 추출 | "월요일 vs 화요일" | entity_extraction | → `date_hints` (2+개면 multi_date) |
| R5 | 충돌 옵션 추출 | "A는 X, B는 Y" | entity_extraction | → `conflict_options` |
| R6 | 채팅 기반 거부 누적 | 채팅에서 멤버가 일정 언급 | conversation_analyzer | TimeBar payload → `rejected_dates` |
| R7 | `place_hint` 추출 | "강남", "홍대", "강남역" | entity_extraction | Gemini + 패턴 — `nodes/entity.py:66, 256, 366~547` |
| R8 | `place_coord` 변환 | place_hint → 좌표 | entity_extraction (`_resolve_place_coord`) | Kakao geocode — `nodes/entity.py:340~342, 560~562` |
| R9 | `cuisine` 추출 | "한식", "맛집", "양식" | entity_extraction / place_node | `helpers/places._detect_cuisine_type`, place 노드 카테고리 매핑 |

### 4.2 선호 매칭 (Preference Matching)
| ID | 기능 | 데이터 출처 | 처리 위치 |
|---|---|---|---|
| P1 | 방 멤버 공통 선호 시간대 | MeetingPreference 교차 | `_load_meeting_preferences` → `preference_common_times` |
| P2 | 평일/주말 필터 | `preference_common_times`에 "평일~" 포함 | vote_card_creation `weekday_only` 필터 |
| P3 | 발화자 개인 시간 선호 | User.time_preference (🔧 plumbing 필요) | **P0 plumbing 후 추가** |
| P4 | 음식 비선호 합집합 | `User.food_restrictions`/`food_preferences` (방 멤버) | `_get_room_member_food_preferences` → place prompt 익명 합산 + `_contains_disliked_keyword` 0.1 페널티 |
| P5 | 개인 지역 선호 | `User.liked_areas`/`disliked_areas` | `preferences.py:382~419` → place 노드 prompt (`place.py:244~251`) 익명 합산 |
| P6 | 이동수단 가중치 | `User.transport_mode` ("대중교통"/"도보"/"자차") | place 노드 prompt (`place.py:254~257`) — 역세권/도보 거리 가중치 힌트 |

### 4.3 탐색 정책 (Search Policy)
| ID | 기능 | 트리거 | 처리 |
|---|---|---|---|
| T1 | 이번주 우선 탐색 | date_hint 미지정 | `get_free_slots` default window = 7일 |
| T2 | 다음주 확장 | 이번주 0 슬롯 | `expanded_to_next_week=true`, window +7일 |
| T3 | 멤버 캘린더 합집합 | 항상 | `_load_busy_by_user_for_state` → 모든 멤버 busy 합집합 제외 |
| T4 | 휴일/주말 라벨 | 항상 | `_get_korean_holiday`, `_is_weekend` → 슬롯 메타 |
| T5 | 다중 날짜 빌더 | `date_hints` ≥2개 | `_build_multi_date_slots` |
| T6 | Kakao 장소 검색 | place_hint·place_coord 확정 | `search_place` (Kakao Local Keyword API) → 후보 장소 목록 |
| T7 | ML 점수화 | `_ML_AVAILABLE` 시 | `_ml_place_search` (LGBMRanker) — top 5 ranking, `nodes/place.py:64~67, 168~181` |
| T8 | Gemini reranking | 항상 (top candidates 진입 시) | `nodes/place.py:269~283` 점수화 + 비선호 페널티 → 최종 `reranked` 정렬 (score desc) |

### 4.4 Fallback 정책 (Fallback Policy)
| ID | 기능 | 트리거 | 출력 |
|---|---|---|---|
| F1 | 0 슬롯 → 다수결 | 전원 가능 슬롯 0개 | (**v1.0 구현 대상**, Q6=A) 가능 멤버 max인 슬롯 3개 + blocker_notification — **정렬: 시간 빠른 순 (Q8=A)**, 후보는 이미 선호·거부 반영된 상태 가정 |
| F2 | headcount=None | entity가 인원 추출 못함 | 방 멤버 수 fallback (**Q3=A**, 게스트 포함 — Q12=A) |
| F3 | 단일 슬롯도 vote_card | 슬롯 1개만 남음 | 단일 옵션 vote_card 발행 (**Q1=B**, 날짜범위 확정 전제) — skip 폐기 |
| F4 | 캘린더 권한 없음 | OAuth 미동의 멤버 | 해당 멤버 캘린더 무시 + narrator에 명시 |
| F5 | place_hint 미지정 fallback | 발화에 place_hint 없음 | **Q2 결정 순서**: ① 멤버 선호 장소 다수결(`pref_data["best_location"]`) → ② 동률 시 발화자 개인 선호 → ③ 선호 정보 없으면 방장(creator) `home_base` |
| F6 | cuisine 미감지 | `_detect_cuisine_type` 결과 없음 | `meeting_type` fallback (e.g. "저녁모임"→"음식점") 또는 일반 카테고리("맛집") — 카테고리 미특정 시 Kakao 일반 검색 |

---

## 5. 입력값 / 출력값

본 spec 노드(`slot_filling` · `function_calling`/캘린더 · `vote_card_creation` · `place_recommendation` · `maedeup_card_creation`)가 **소비**·**생성**하는 데이터를 정리한다. 전체 카탈로그(약 40개, 6 카테고리)는 [`2026-05-13-recommend-input-catalog.md`](./2026-05-13-recommend-input-catalog.md) 참조 — 본 절은 그중 본 spec이 실제로 읽거나 쓰는 항목만 추려 file:line을 표기한다.

마크: ✅ 활용 중 / ⚠️ state에 있으나 미활용 / 🔧 plumbing 필요 (§5.3에서 P0로 별도 다룸)

### 5.1 입력 (소비) — 기능별 데이터 카탈로그

본 절은 시간+장소 조율 파이프라인이 사용하는 약 40개 입력을 **7개 기능 서브섹션**으로 정리. 마크: ✅ 활용 중 / ⚠️ 부분·미활용 / 🔧 plumbing 필요 (P0/P1).

#### 5.1.1 날짜·시간 후보 생성

| 항목 | 의미 | 출처 | 사용처 | 예시 데이터 형태 | 마크 |
|---|---|---|---|---|:---:|
| `date_hint` | 첫 번째 날짜 표현 (ISO 또는 raw) | `nodes/entity.py:69~110, 472~502` | `slot_filling` 분기·`function_call`·vote_card 헤더 | `"2026-05-15"` | ✅ |
| `date_hints` | 다중 후보 날짜 리스트 (2개+면 multi_date_vote 분기) | `nodes/entity.py:108~111, 480~495` | multi_date_vote 라우팅 | `["2026-05-15","2026-05-16"]` | ✅ |
| `parsed_time_hint` | 자연어 시각 (HH:MM) | `nodes/entity.py:500` (`_parse_natural_date`) | partial maedeup `selected_time` | `"19:00"` | ✅ |
| `date_is_flexible` | 다중 후보 플래그 | `nodes/entity.py:495` | function_call multi_date 분기 | `true` | ✅ |
| `_load_busy_by_user_for_state()` | GCal freeBusy 4주 조회 (멤버 busy) | `helpers/slots.py:283~322` | `function_call` 자유슬롯 계산 — 모든 멤버 busy 합집합 제외 | `{"u:7":[{"start":"...","end":"..."}]}` | ✅ |
| `is_holiday`/`holiday_name`/`is_weekend` | 슬롯 메타 (휴일·주말) | `helpers/slots.py:82~102, 199~214, 608~631` | vote_card `time_options` 표시·weekday_only 필터 | `{"is_holiday":true,"holiday_name":"부처님오신날"}` | ✅ |
| `expanded_to_next_week` | 이번주 0 슬롯 시 +7일 확장 플래그 (해결점 N) | `nodes/entity.py:314` → 소비 `nodes/slot.py:110~170` | `_slot_filling_stalemate` 대체 후보 생성 | `true` | ✅ |

#### 5.1.2 거부 누적·필터링

| 항목 | 의미 | 출처 | 사용처 | 예시 데이터 형태 | 마크 |
|---|---|---|---|---|:---:|
| `rejected_dates` | 채팅에서 명시 거부된 날짜 (누적) | `nodes/entity.py:284~298, 519~533` | `date_hints` 필터·conflict_options 정합·stalemate 후보 제외 | `[{"date":"2026-05-15","user":"민수","reason":"알바"}]` | ⚠️ |
| `_REJECT_SIGNAL_PATTERN` | 거부 시그널 정규식 (단축 차단) | `helpers/places.py` import → `entity.py:135` | 단축 차단 게이트 | regex `r"안\s*돼\|못\s*가\|..."` (추정) | ✅ |
| `conflict_options` | 충돌 선택지 (date/place/time) | `nodes/entity.py:265, 510` | `_slot_filling_stalemate` 중재·multi_date_vote | `["목요일","금요일"]` | ✅ |
| `conflict_detected`/`conflict_type`/`conflict_users` | 충돌 메타 | `nodes/entity.py:263~266, 272~282` | 중재 분기·로그 | `true` / `"date"` / `["민수","수현"]` | ✅ |

> `rejected_dates` ⚠️ 사유: 정규식 단축 경로(`_pattern_extract_entities`, `entity.py:133~146`)에서 rejected 추출 누락 — **해결점 O 미해결**.

#### 5.1.3 선호 매칭

| 항목 | 의미 | 출처 | 사용처 | 예시 데이터 형태 | 마크 |
|---|---|---|---|---|:---:|
| `_load_meeting_preferences()` | `MeetingPreference` row 집계 (방 전체) | `helpers/preferences.py:447~541` | `_enrich_with_preferences` 진입점 | `{"has_preferences":true,"all_submitted":true,"best_location":"홍대","common_times":["주말 오후"],"total_members":4}` | ✅ |
| `preference_common_times` | 멤버 공통 가능 시간대 교차 | `helpers/preferences.py:493~509` → `nodes/slot.py:87,98` | `function_call` preference_based 슬롯 생성 (`helpers/slots.py:331~349`) | `["평일 저녁","주말 오후"]` | ⚠️ |
| `pref_data["best_location"]` | 다수결 선호 장소 | `helpers/preferences.py:493` | `_enrich_with_preferences` place_hint fallback (`slot.py:75`) | `"홍대"` | ✅ |
| `User.time_preference` | 개인 lifestyle 시간 (단일 str) | `personal_data_extractor.py:85~90`·`preferences.py:218` | personal_data 익명 합산 (점수화 미연결) | `"평일 저녁 7시 이후"` | ⚠️ |
| `User.food_restrictions`/`food_preferences` | 식이 제약/선호 | `preferences.py:263~272` | place 노드 prompt (P0-4 익명, 5.1.4 참조) | `["갑각류"]` / `["한식"]` | ✅ |
| 발화자 토글 (Q5 hybrid) | 동률 시 트리거 사용자 선호 우선 토글 | (Q5 결정, 미구현) | 5.1.4 place_hint fallback 순위·UI 토글 | — | 🔧 |

> `preference_common_times` ⚠️ 사유: 교차 set 비면 top-3 fallback. 시연 시나리오 한정 검증.
> **Q5 hybrid 토글 (Q7=B 결정)**: 카드 페이로드에 `preference_source: "group"|"speaker"` + `preference_toggle_enabled: bool` 두 키 (vote_card·place 양쪽). **Q7-b: 방 전체 갱신** — 토글 시 새 페이로드 broadcast (`POST /meetings/{id}/recommendations/refresh` 신설, §9). **권한 (Q13=B)**: 발화자 + 방장만 호출 가능. **Rate limit (Q14=C)**: Redis idempotency 캐시(같은 source/scope 조합 hit) + 일일 100회 상한. **Narrator (Q15=A)**: 재발행 시 "OOO님 선호 기준으로 다시 추천했어요" 실명 명시 — PII 노출 트레이드오프 인지 필요. **Q7-c (`preference_toggle_enabled=false` 트리거 조건)**: C1(발화자 `share_*_data == False`) ∨ C3(그룹 다수결과 발화자 선호 결과 동일) ∨ C4(발화자 본인 정보 비어있음). 게스트(C2 후보)는 채팅방 입장 후 선호 설정 가능하므로 토글 허용.

#### 5.1.4 장소 추출·검색·추천

| 항목 | 의미 | 출처 | 사용처 | 예시 데이터 형태 | 마크 |
|---|---|---|---|---|:---:|
| `place_hint` | 장소 키워드 | `nodes/entity.py:66, 256, 366~547` | `place_node` Kakao 검색·prompt | `"홍대"` | ✅ |
| `place_coord` | 좌표 (`_resolve_place_coord`) | `nodes/entity.py:340~342, 560~562` | Kakao 거리 정렬 기준 | `{"lat":"37.55","lng":"126.92"}` | ✅ |
| `cuisine`/`meeting_type` | 음식·모임 종류 | `helpers/places._detect_cuisine_type`·`nodes/place.py:367` | `meeting_type` fallback, Kakao 쿼리 | `"맛집"` | ✅ |
| `creator_home_base` | 방장 home_base fallback (Q2 결정) | `helpers/places.py:115~119` | place_hint 비었을 때 fallback (선호 다수결 → 동률 시 발화자 → 방장) | `"강남"` | ⚠️ |
| `User.liked_areas`/`disliked_areas` | 개인 지역 선호 | `preferences.py:382~419` | place 노드 prompt 익명 합산 (`place.py:244~251`) | `["성수"]` / `["강남"]` | ✅ |
| `User.transport_mode` | 이동수단 | `preferences.py:275~276, 357` | place 노드 prompt (`place.py:254~257`) | `"대중교통"` | ✅ |
| `ml_place_search` 결과 | ML 후보 (`_ML_AVAILABLE` 시) | `nodes/place.py:64~67, 168~181` | top_candidates 진입 | `[{"place_id":"...","name":"...","distance":120}]` | ✅ |
| Gemini 점수화 | place_id별 score | `nodes/place.py:269~283` | reranked 정렬 (`score` desc) | `[{"place_id":"abc","score":0.9}]` | ✅ |
| `_contains_disliked_keyword` 패널티 | 비선호 음식 0.1 강등 | `nodes/place.py:204~207, 288~289` | reranked 최종 score | `score=0.1` | ✅ |
| `place_search_results` | 최종 후보 리스트 | `nodes/place.py` (state set) | maedeup `selected_place` (`maedeup.py:178`) | `[{"name":"...","score":0.9,"place_id":"..."}]` | ✅ |

> `creator_home_base` ⚠️ 사유: state set 경로 plumbing 필요 (P0-3). Q2 결정에 따라 fallback 순서 = 선호 장소 다수결 → 동률 시 발화자 → 선호 없으면 방장 위치.
> **휴일·주말 안내 (Q10=C)**: Kakao Local API는 영업시간 미제공 → Gemini prompt(`nodes/place.py:220-230` `time_context`)에 요일·주말·한국 공휴일 라벨 추가. `helpers/dates.py:40-47` 헬퍼(`_get_korean_holiday`/`_is_weekend`) import → `confirmed_date`로 호출. 옵션 B(Kakao 필터)는 v2 후보 (Google Places 전환 시).

#### 5.1.5 투표 카드 발행

| 항목 | 의미 | 출처 | 사용처 | 예시 데이터 형태 | 마크 |
|---|---|---|---|---|:---:|
| `calendar_free_slots` | 후보 슬롯 리스트 | `nodes/function_call.py:92,114,134,146` | `vote_card.py:197~275` `time_options` | `[{"slot_id":"slot-1","label":"5/15(목) 19:00~21:00","start_at":"...","end_at":"...","is_holiday":false,"is_weekend":false}]` | ✅ |
| `vote_card_payload` | 최종 투표 카드 페이로드 | `vote_card.py:259~279` | publish + maedeup carry | `{"type":"vote_card","meeting_id":42,"time_options":[...],"headcount":4,"calendar_strategy":"all_members_available","blocker_notification":null}` | ✅ |
| `headcount` | 참가 인원 (None 시 방 멤버수 fallback — Q3=A, **게스트 포함 — Q12=A**) | `nodes/entity.py:114~116`·`slot._enrich:78~79` | vote_card 페이로드·UX | `4` | ✅ |
| `meeting_type` | 카드 타이틀 prefix | `nodes/entity.py:119~123`·`slot.py:81` | `vote_card.py:207~209` 타이틀 | `"맛집"` | ✅ |
| `calendar_strategy` | 슬롯 선정 전략 | `helpers/slots.py:458,474,500,547`·`function_call.py:93,115,138` | vote_card·validation·UX 분기 | `"all_members_available"` / `"n_minus_one"` / `"multi_date_vote"` / `"preference_based"` / `"natural_language_time_options"` | ✅ |
| `blocker_notification_payload` | n-1 차단 멤버 안내 (F1 fallback, Q6=A v1.0 구현 대상) | `function_call.py:160~`·소비 `vote_card.py:277` | UX 표시 — **정렬: 시간 빠른 순 (Q8=A)** | 추정: `{"blocked_user":"수현","blocked_dates":["2026-05-15"]}` | ⚠️ |

> **단일 슬롯도 vote_card 발행 (Q1=B)**: 날짜범위 확정 상태에서 후보 슬롯이 1개로 좁혀져도 vote_card 페이로드 생성 — `calendar_strategy="all_members_available"` 단일 옵션.
> `blocker_notification_payload` ⚠️ 사유: payload 생성 일부, UI 미연결. Q6=A 결정으로 v1.0 구현 대상. **UI 형식 (Q16=C)**: 기본 익명 ("1명 불참") + 사용자 클릭 시 실명 노출 — 점진 공개.

#### 5.1.6 확정·부분 카드 발행

| 항목 | 의미 | 출처 | 사용처 | 예시 데이터 형태 | 마크 |
|---|---|---|---|---|:---:|
| `partial_mode` | 부분 카드 모드 (해결점 I·J·K) | `state.py:49`·`nodes/slot.py:254,280` | `maedeup.py:74` time-only 분기 | `"time_only"` | ✅ |
| `confirmed_date`/`confirmed_time` | manual host pick 시각 (HH:MM~HH:MM) | `nodes/slot.py:250~251` | `maedeup.py:79~90` explicit_start/end 파싱 | `"2026-05-15"` / `"19:00~21:00"` | ✅ |
| `selected_time` (payload key) | maedeup 카드 시간 필드 (※ state 키 아님 — 로컬 변수 → payload) | `maedeup.py:108~120, 163, 192` | 프론트 카드 표시 | `{"label":"2026-05-15 19:00~21:00","start_at":"...","end_at":"..."}` | ✅ |
| `confirmed_place` | 확정 장소명 | `state.py:75`·`maedeup.py:171~180` | maedeup `selected_place.name` | `"홍대 OO식당"` | ✅ |
| `place_pending_message` | 부분 카드 안내 문구 | `maedeup.py:157` | 카드 UI | `"멤버들이 장소를 정하면 자동으로 정리해드릴게요!"` | ✅ |
| `vote_card_payload`/`place_recommendation_payload` carry | 상위 카드 meeting_id 재사용 | `maedeup.py:64~66, 194~195` | `_card_payload_meeting_id` lookup | dict carry | ✅ |
| `maedeup_card_payload` | 최종 매듭 카드 페이로드 | `maedeup.py:150~196` | publish | `{"type":"maedeup_card","meeting_id":42,"date":"...","time":"...","place":null,"place_pending":true,...}` | ✅ |
| `calendar_registration` | GCal 등록 결과 (현재 placeholder) | `maedeup.py:43~50, 181` | 카드 `calendar_registered` 필드 | `{"provider":"google_calendar","status":"placeholder"}` | ⚠️ |

> `calendar_registration` ⚠️ 사유: 노드는 `status="skipped"` placeholder만 반환. 실제 등록은 `routes/meetings.py` confirm 라우터 (§5.2.3 참조).
> **시간 확정 후 번복 불가 (Q9=A)**: time_only maedeup 발행 후 사용자가 장소를 채워도 **시간은 잠김 (immutable)**. 시간 재선정은 명시적 재추천 요청(`POST /meetings/{id}/recommendations/refresh`, §9)으로만 가능 — `partial_mode` 분기와 별개의 경로.

#### 5.1.7 공통 진입·상태

| 항목 | 의미 | 출처 | 사용처 | 예시 데이터 형태 | 마크 |
|---|---|---|---|---|:---:|
| `trigger_reason` | 자동 트리거 분기 키 (4종) | `state.py:47`·`slot_context` 주입 | `graph.py` entry edge·`slot_filling` 분기 (`slot.py:61~68`) | `"stalemate_judged"` / `"conclusion_detected"` / `"all_members_selected"` / `"direct_request"` | ✅ |
| `direct_request_kind` | quick_classify fast path 결과 | `state.py:52`·`quick_classify.py` | `entity.py:356~358` fast-skip | `"place"` / `"schedule"` / `"schedule+place"` / `"general"` | ✅ |
| `trigger_message_text` | 트리거 시점 user 메시지 원문 (해결점 G) | `state.py:44` | race-condition 방지 | `"홍대 맛집 추천해줘"` | ✅ |
| `awaiting_user_reply`/`wait_timed_out` | 대기 상태 | `state.py:87~88`·`slot.py` 다수 | 재트리거 게이트 | `false` / `false` | ✅ |
| `slot_filling_turns` | 부분 정보 acknowledgment 횟수 (1회 한정) | `state.py:85`·`slot.py:383~395` | 응답 게이트 | `1` | ✅ |
| `is_location_first` | 장소만 있고 날짜 없을 때 분기 | `entity.py:343~347, 565~569`·`slot._enrich:100~104` | location_first_ready 라우팅 | `true` | ✅ |
| `message_records`/`new_assistant_messages` | 채팅 히스토리·신규 발화 큐 | `state.py:39,65`·`helpers/messaging.py:155~167` | context serialize·publish (실제 WebSocket publish는 `messaging.py:155~157`) | `[{"id":12,"role":"assistant","content":"..."}]` | ✅ |
| `viewer_user_id` | 프라이버시 경계 | `state.py:114`·`messaging.py:132~137` | shared/private 메시지 분기 | `null` (shared) / `7` (private) | ✅ |

---

### 5.2 출력 (생성)

#### 5.2.1 카드 페이로드 (3종 4변형)
| 카드 | set 노드 | 핵심 키 | 출처 |
|---|---|---|---|
| `vote_card_payload` | vote_card_creation | `type`/`title`/`room_id`/`meeting_id`/`time_options[]`/`headcount`/`blocker_notification`/`calendar_strategy` | §3 참조 (`nodes/vote_card.py:259~279`) |
| `place_recommendation_payload` | place_recommendation | `type`/`room_id`/`meeting_id`/`place_hint`/`recommendations[≤5]`/`group_constraints_summary` | `nodes/place.py:320~329` |
| `maedeup_card_payload` (확정) | maedeup_card_creation | `type`/`room_id`/`meeting_id`/`title`/`intent`/`date_hint`/`place_hint`/`headcount`/`meeting_type`/`selected_time`/`selected_place`/`vote_card`/`place_recommendation`/`calendar_registration` | `nodes/maedeup.py:182~197` |
| `maedeup_card_payload` (partial, time_only) | maedeup_card_creation | `type`/`meeting_id`/`date`/`time`/`place=null`/`place_pending=true`/`place_pending_message`/`headcount`/`calendar_registered=false`/`title`/`meeting_type`/`date_hint`/`selected_time`/`selected_place={}` | `nodes/maedeup.py:150~166` (해결점 I·J·K) |

#### 5.2.2 DB 변경

**(a) 파이프라인 노드 직접 쓰기**
| 변경 | 노드 | 비고 |
|---|---|---|
| `MeetingSchedule` pending 생성 | vote_card_creation | `_ensure_pending_meeting_id` |
| `MeetingSchedule.vote_options` JSON 채움 | vote_card_creation | slot_id 배열 |
| `MeetingSchedule.scheduled_at` partial 동기화 | maedeup_card_creation | `nodes/maedeup.py:125~143` (time_only 분기만) |

**(b) confirm 라우터 다운스트림 쓰기** (파이프라인 외부 — §9에서 상세)
| 변경 | 위치 |
|---|---|
| `MeetingSchedule.scheduled_at`/`end_at` 확정 | `routes/meetings.py:501` |
| `MeetingSchedule.kakao_place_id`/`kakao_place_url` | `routes/meetings.py:748~749, 774~775` |
| `MeetingSchedule.google_event_ids` (JSON dict `user_id→event_id`) | `routes/meetings.py:501, 797, 915` |
| `MeetingParticipant` 일괄 추가 | `routes/meetings.py:345` |
| `Notification` 발행 | finalization_reason / meetings 라우터 |

#### 5.2.3 외부 효과
| 효과 | 위치 | 비고 |
|---|---|---|
| Google Calendar 이벤트 생성 | `nodes/maedeup.py:43~50` `_register_google_calendar` (현재 placeholder만 반환), 실제 등록은 `routes/meetings.py` confirm 라우터 (§9) | ❌ 노드 자체는 `status="skipped", reason="pending_confirmation"` placeholder |
| Redis 캐시 (`room_place_rec:{room_id}`) | `nodes/place.py:332~344` | 24h TTL, 새로고침 복구용 |
| Memory extraction (fire-and-forget) | 정의 `nodes/memory.py:88`, 호출 `nodes/maedeup.py:169` `_spawn_memory_extraction_async` | graph latency에서 분리 (추정: 코드 주석 `memory.py:91-92` 기반, 실측 미검증) |
| WebSocket publish queue (`new_assistant_messages` append) | `services/pipeline/helpers/messaging.py:155~157` (state 정의 `state.py:65`) | 카드·narrator 발행 queue. 실제 WS 송신은 graph 종료 후 호출자 (`ws/agent.py`) |

#### 5.2.4 narrator 메시지
- `vote_card`: "캘린더 확인 결과 ... 추천드려요" — §3.1 참조
- `place_recommendation`: "OOO 근처 5곳을 찾아봤어요" — `nodes/place.py:346~`
- `maedeup_card` (확정): "확정됐어요!"
- `maedeup_card` (partial): "장소는 멤버들이 정하면 자동으로 정리해드릴게요!" — `place_pending_message`

---

### 5.3 P0 plumbing 요구

카탈로그 P0 6 항목 중 본 spec(시간+장소)에 영향을 주는 항목.

| # | 재료 | 현재 상태 | 작업 | 본 spec 영향 |
|---|---|---|---|---|
| 1 | `state["intent"]` 명시 세팅 | quick_classify가 `direct_request_kind`만 채우고 `state["intent"]`는 dead | agent.py에서 `kind` → `state["intent"]` 매핑 | direct_request 경로의 intent 분기(슬롯·카드 양쪽) 정상화 |
| 2 | `requester_user_id` 노출 | `viewer_user_id`는 state에 있으나 추천 노드에서 미사용 | 추천 노드에서 명시적으로 lookup | 발화자 본인 정보 활용 가능 (5.1.2의 🔧 항목 활성화) |
| 3 | `requester_home_base` | `User.home_base` 컬럼 있음, state까지 안 옴 | viewer_user_id → `User.home_base` lookup → state | `place_hint` 없을 때 fallback — **Q2 결정: 선호 장소 다수결 → 동률 시 발화자 → 선호 없으면 방장 위치** (§4.4 F5 신설은 PR-2) |
| 4 | `requester_preferences` 묶음 | `User.food_*`/`*_areas`/`transport_mode` 미전달 | dict 묶음 state | 발화자 vs 그룹 충돌 시 가중치 — **Q5=hybrid** 정책 반영 (다수결 기본 + 토글) |
| 5 | `time_window` (ISO range) | `parsed_time_hint` 텍스트 그대로, 정규화 안 됨 | "내일 6시" → `{start: ISO, end: ISO}` | **Q1 결정 반영** — 단일 슬롯이어도 vote_card 발행 가능하게 |
| 6 | `cuisine` state 명시 | place_recommendation 내부에서만 감지 (`_detect_cuisine_type`) | 결과를 state로 끌어올림 | vote_card도 음식점-친화 시간 추천 가능 |

**의존 관계**:
- P0-1·2·6 — 단순 plumbing, 결정 의존 없음
- P0-3 — **Q2** (place_hint fallback 순서) 결정 필요, 본 spec 다음 결정 라운드 후보
- P0-4 — **Q5 hybrid 정책** 반영 (UI 토글 메타 §3·§9에 명세)
- P0-5 — **Q1 단일 슬롯 = vote_card** 반영

**v2 예고** (별도 spec 문서): P1 5항목 (`room_member_home_bases`, `previous_recommendations`, `urgency_signal`, `group_constraints_summary` 양 노드 공유, `notes` 활용)은 본 v1 범위 밖.

---

## 6. 상태 및 예외 처리

본 절은 §1~§5에서 정의된 정상 경로 밖에서 발생하는 모든 분기 — 노드 예외, 사용자 응답 대기, 부분 정보 acknowledgment, fallback narrator, 동시성, v2 backlog로 미뤄둔 갭 — 을 한 곳에 모아 정의한다. **운영 중 한 번이라도 관찰될 수 있는 상태는 모두 본 절에 명세된다**.

### 6.1 상태 머신 개요

본 spec 파이프라인은 발화 진입부터 카드 발행까지 다음 핵심 상태 키를 유지·전이한다 (`backend/app/services/pipeline/state.py:46~98`).

| 상태 키 | 타입 | 의미 | 전이 시점 |
|---|---|---|---|
| `trigger_reason` | str\|None | 진입 원인 (`stalemate_judged` / `conclusion_detected` / `all_members_selected` / `direct_request`) | 라우터 분기 시점, `graph.py:57~115` |
| `slot_filling_turns` | int | 같은 partial 상태에서 acknowledgment 발행 횟수 | `slot.py:384, 400` |
| `awaiting_user_reply` | bool | 멤버 응답 대기 중 (vote_card 발행 후) | vote_card 발행 시 true, 다음 발화 진입 시 reset |
| `wait_timed_out` | bool | 대기 timeout 경과 (재추천 트리거 조건) | timeout 워커 또는 timed-out 진입 시 |
| `partial_mode` | str\|None | `"time_only"` 잠금 모드 (Q9=A) | maedeup 카드(partial) 발행 시 set, refresh 명시 호출 전 immutable |
| `confirmed_date` / `confirmed_time` / `confirmed_place` | str\|None | 사용자 동의된 슬롯 값 | confirm 라우터 또는 conclusion 분기 |
| `status` | str | 노드별 종결 상태 (`slots_filled`, `slots_filled_with_defaults`, `partial_info_acknowledged`, `multi_date_vote`, `conclusion_false_positive`, `time_only_ready`, `<node>_error`) | 각 노드 종결 시 |
| `validation_passed` | bool | supervisor_validation 통과 여부 | validation 노드 종결 시 |

전이 패턴 (전형):

```
direct_request → entity_extraction(O) → slot_filling
                ↓ all_slots_filled=true              ↓ partial_info_acknowledged
              function_call → vote_card_creation → (사용자 투표 대기) → maedeup
                                                       ↑ awaiting_user_reply=true
```

trigger별 진입 분기는 `graph.py:63` (`stalemate_judged | conclusion_detected | direct_request` → 노드3부터, ~1s 절약).

### 6.2 슬롯 진행 차수 (slot_filling_turns)

부분 정보(날짜만 / 장소만)로 진입한 발화에 대한 **acknowledgment 1회 한정 응답 게이트**. 같은 partial 상태에서 사용자가 같은 정보를 두 번 발화해도 매듭 AI는 1회만 응답한다 (스팸 방지).

```python
# backend/app/services/pipeline/nodes/slot.py:382~395 (_slot_filling_default_partial)
async def _slot_filling_default_partial(state, has_date, has_place):
    if has_date and not has_place:
        state["slot_filling_turns"] += 1
        if state["slot_filling_turns"] <= 1:
            date_display = state.get("date_hint", "")
            confirm_msg = (
                f"{date_display} 좋아요! 👍 "
                "장소나 인원이 대화에서 나오면 제가 바로 정리해드릴게요~"
            )
            await _emit_assistant_message(...)
        state["awaiting_user_reply"] = False
        state["status"] = "partial_info_acknowledged"
```

- **재발화 시**: `slot_filling_turns >= 2` → acknowledgment 메시지 생략. `status="partial_info_acknowledged"` 유지.
- **상태 리셋**: 모든 슬롯이 채워져 `slots_filled` 또는 `slots_filled_with_defaults`로 전이될 때 자연 리셋 (해당 meeting 사이클 종료).
- **장소 단독 발화 (`has_place and not has_date`)**: 동일 게이트 적용 (`slot.py:399~410`). 단, `intent == "meeting_schedule"`는 우회 (날짜 필수 흐름).

### 6.3 대기 상태 (awaiting_user_reply / wait_timed_out)

vote_card 발행 후 또는 acknowledgment 후 사용자 응답을 기다리는 상태. 두 키는 mutually exclusive하게 동작한다.

| 키 | true 진입 | false 복귀 |
|---|---|---|
| `awaiting_user_reply` | vote_card 발행 직후 (`vote_card.py`), conflict 중재 발행 (`slot.py:155, 201`) | 다음 사용자 발화 진입, 또는 acknowledgment 후 (`slot.py:393, 410`) |
| `wait_timed_out` | 외부 timeout 워커가 set (대기 N분 초과) | 사용자 발화 또는 명시 refresh 후 reset |

**timeout 분기 동작**:
- `wait_timed_out=true` 진입 시 → narrator "다들 바쁘신가봐요. 다른 후보로 다시 추천해드릴까요?" 발행 (v1 구현 후보, 현재 코드상 wait_timed_out 키 정의만 존재 — **미확인**, `state.py:88`).
- timeout 후 동일 meeting에서 재추천 트리거 시 `previous_recommendations`(P1 후보, v2)를 활용해 같은 슬롯 재제시 방지.

### 6.4 노드 예외 처리 (`_handle_node_exception`)

모든 본 spec 노드는 try/except 블록으로 감싸이며, 미처리 예외는 단일 헬퍼로 격리된다.

```python
# backend/app/services/pipeline/helpers/messaging.py:93~106
async def _handle_node_exception(node_name, state, exc):
    logger.exception("LangGraph node failed: %s", node_name, exc_info=exc)
    state["status"] = f"{node_name}_error"
    state["validation_passed"] = False
    state["awaiting_user_reply"] = False
    await _emit_assistant_message(state["room_id"], state["db"],
                                   FRIENDLY_ERROR_MESSAGE, state)
    return state
```

- **공통 narrator**: `FRIENDLY_ERROR_MESSAGE = "잠깐, 뭔가 잘못됐어요 😅 다시 한번 말해줄래요?"` (`constants.py:29`).
- **적용 노드 (본 spec 범위)**: `slot_filling` (`slot.py:70`), `entity_extraction` (`entity.py:574`), `place_recommendation` (`place.py:363`), `supervisor_validation` (`validation.py:121`).
- **다운스트림**: `_has_node_error(state)`로 후속 노드가 진입 차단 (`messaging.py:89~90`, `status` 접미사 `_error` 검사).
- **카드 미발행**: 예외 발생 시 vote_card / place_recommendation / maedeup_card 모두 미발행. 사용자 인지: 친절 메시지 1회.

### 6.5 fallback narrator 매트릭스 (F1~F4)

§4.4의 F1~F4를 narrator 문구·사용자 인지 정책 관점으로 재정리.

| ID | 트리거 | 동작 | narrator 문구 | 사용자 인지 |
|---|---|---|---|---|
| **F1** | 0 슬롯 (전원 가능 슬롯 없음) | 가능 멤버 max인 슬롯 3개 발행 (Q6=A 구현 완료), 시간 빠른 순 정렬 (Q8=A) | `"전원 가능한 시간이 없어 가장 많은 멤버가 가능한 시간 3개로 추천드려요. 📅"` + `blocker_notification` (Q16=C 익명 + "더보기") | vote_card 위 narrator, `blocker_notification` 페이로드 키 |
| **F2** | `headcount == None` (entity가 인원 미추출) | 방 멤버 수 fallback (Q3=A, 게스트 포함 Q12=A) | (narrator 없음 — silent fallback) `headcount` 페이로드에 값만 설정 | 카드 헤더의 인원 표시로 간접 인지 |
| **F3** | 단일 슬롯만 남음 | vote_card 발행 유지 (Q1=B, skip 폐기) | `"이 시간으로 괜찮으실까요?"` (단일 옵션 vote_card) | 단일 옵션 카드 + 동의 의식 |
| **F4** | OAuth 미동의 멤버 존재 | 해당 멤버 busy 합집합 계산에서 제외, `google_event_ids` dict에 그 user_id 키 생략 | `"OOO님은 캘린더 권한이 없어 제외하고 추천했어요"` (실명 표기, Q15=A 정책과 유사) | narrator로 명시 |

> **F1·F4 동시 발생**: F1 narrator 우선, F4는 부가 안내로 후속 발행 (구현은 v1.0 단계 — 미확인).

### 6.6 동시성 race condition

여러 사용자가 동시에 발화하거나 동시에 투표할 때의 처리 정책.

| 상황 | 정책 | 코드 위치 |
|---|---|---|
| 동시 발화 (`agent_message_received` 다중) | LangGraph 파이프라인은 **room_id 단위 직렬화 가정** (큐 메커니즘 — **미확인**). 동시 진입 시 두 번째 발화는 첫 진입의 `awaiting_user_reply` 상태를 보고 진입 분기 조정 | `run_pipeline` 진입부 — 검증 필요 |
| 동시 투표 (`record_availability`) | DB row-level lock (`scheduling_round.py:499`), 동일 (user_id, date) UPSERT | `scheduling_round.py:499~` |
| 동시 unavailable 토글 (`record_unavailable_toggle`) | 동일 row-level lock, 마지막 쓰기 승리 | `scheduling_round.py:713~` |
| 동시 confirm | `MeetingSchedule.status` 트랜잭션 — `pending → confirmed` 1회만 허용. 두 번째 confirm은 409 또는 무시 (**미확인**) | confirm 라우터 |

> **트랜잭션 격리 수준**: PostgreSQL 기본값(`READ COMMITTED`) 가정. `SERIALIZABLE` 미사용. 동시 발화 직렬화 메커니즘 — **미확인**, v1.0 시연에서는 단일 사용자 발화 위주라 race 노출 가능성 낮음.

### 6.7 토큰 만료 / revoke 처리 (Google OAuth)

캘린더 freeBusy 조회 중 토큰이 만료되거나 사용자가 권한을 revoke한 경우.

```python
# backend/app/services/google_calendar.py:58~64
try:
    await asyncio.to_thread(credentials.refresh, Request())
except RefreshError as exc:
    raise GoogleCalendarAuthError() from exc
if not credentials.token:
    raise GoogleCalendarAuthError()
```

- **격리 정책**: 멤버 단위 try/except로 처리. 한 멤버 실패 시 그 멤버 freeBusy 데이터만 제외, 나머지 멤버는 정상 진행.
- **결과 페이로드**: `google_event_ids` dict에서 실패 멤버 user_id 키 생략 (`google_calendar.py:269, 338` `except GoogleCalendarAuthError` 블록).
- **사용자 인지**: F4 narrator로 노출 (실명, Q15=A 정책). PII 노출 트레이드오프 인지.
- **연관 키**: `User.google_access_token` / `google_refresh_token` null 또는 만료 → 동일 분기.

### 6.8 단일 슬롯 거부 흐름 (충돌 C3 해소)

Q1=B로 단일 슬롯도 vote_card 발행 → 사용자가 그 슬롯을 거부할 때의 흐름.

1. 거부 발화 ("이날 안 돼") → `entity_extraction`이 `rejected_dates`에 누적 (`entity.py:284~298, 519~533`).
2. 재추천 트리거: 사용자 추가 발화(`direct_request`) 또는 `awaiting_user_reply` 시간 초과(`wait_timed_out`) 후 명시 refresh.
3. 후보 슬롯 0개면 → **F1 fallback** (다수결 vote_card) 또는 **T2 다음주 확장** (`expanded_to_next_week=true`).
4. 무한 재시도 방지: `previous_recommendations` (P1 v2 후보)로 같은 슬롯 재제시 차단 — **현재 미구현**, v2.

> **C3 해소 명시**: Q1=B 결정 (단일 슬롯도 vote_card 발행)이 만들 수 있는 "거부할 곳도 없는 강제 동의" 우려를 본 6.8 흐름으로 해소. 거부 → rejected_dates 누적 → 재추천 → F1/T2 fallback의 일관된 경로 제공.

### 6.9 partial maedeup 시간 잠금 (충돌 C2 해소, Q9=A)

`partial_mode = "time_only"` 상태에서 후속 발화 처리 정책.

- **시간 immutable**: `selected_time`은 partial 카드(maedeup, §3.4) 발행 시점에 잠긴다. 후속 장소 발화가 들어와도 새 vote_card 발행 X.
- **장소 갱신**: 같은 `meeting_id`의 partial 카드를 update (해결점 J, `maedeup.py:150~166`). 별도 vote_card 미발행.
- **명시적 시간 재선정**: `POST /meetings/{id}/recommendations/refresh` (§9 신설, 권한 Q13=B 발화자+방장만, rate limit Q14=C Redis idempotency + 일일 100회) 호출 시에만.
- **refresh 동작**: partial 상태 감지 시 → `time_options` 잠금 + `place` 옵션만 재생성 (또는 명시 unlock 플래그 시 시간 재추천).

> **C2 해소 명시**: "시간만 결정 후 장소 발화 → 시간 재추천 충돌"을 Q9=A로 차단. 시간 결정은 한 번, 장소는 자유 갱신.

### 6.10 conclusion_false_positive 분기

"그럼 화요일 7시로 ㄱ" 같은 conclusion 발화가 실제 합의 아닌 경우 (예: 한 명만 발화, 다른 멤버 응답 없음).

```python
# backend/app/services/pipeline/nodes/slot.py:206~216 (_slot_filling_conclusion)
async def _slot_filling_conclusion(state, pref_data):
    has_date = bool(state.get("date_hint"))
    has_place = bool(state.get("place_hint"))
    if not has_date and not has_place:
        state["new_assistant_messages"] = []
        state["awaiting_user_reply"] = False
        state["status"] = "conclusion_false_positive"
        logger.info("[TRIGGER] conclusion_detected false positive, silent abort")
        return state
```

- **분기 조건**: trigger_reason이 `conclusion_detected`임에도 date/place 슬롯 모두 비어있을 때 → **silent abort** (카드·narrator 미발행).
- **다운스트림 처리**: `graph.py:85, 105` 및 `validation.py:36`에서 `status == "conclusion_false_positive"`면 후속 노드 진입 차단, 사용자에게 아무것도 노출 안 함.
- **추가 검증 필요**: 단일 발화자가 conclusion 표현을 썼지만 멤버 동의 부재인 경우의 별도 검증 로직 — 현재 silent abort만 존재, confirm 모달 등 정교화는 v2 backlog.

### 6.11 해결점 P 번복 처리 (v2 backlog)

사용자가 거부한 날짜 후 번복하는 케이스 ("월요일 안돼" → "아 8일 되네").

- **현재 동작**: `_analyze_conversation`이 `signals.rejected_dates`에 누적만 함. 번복 발언이 들어와도 자동 clear 안 됨.
- **갭**: `rejected_dates`에서 해당 항목 제거 또는 명시 `unavailable=False` 추출 경로 부재.
- **수정 방향 (audit-findings.md 해결점 P, line 1023)**: 인버스 토글 — 채팅 자연어 → `record_unavailable_toggle(unavailable=False)` 동기화. 함정: 시점 모호("아 8일 되네"의 "8일" 어느 8일?), LLM 환각 방어 필요.
- **상태**: 🟡 기능 갭, v2 spec backlog. 인용: `docs/handoff/audit-findings.md:1004~1029`.

### 6.12 해결점 O 정규식 사각지대 (v2 backlog)

정규식 단축 경로(`_pattern_extract_entities`)가 `rejected_dates` / `conflict_*` 키를 생성하지 않는 갭.

- **현재 동작 (`langgraph_pipeline.py:979~1062`)**: AI 패널 직접 요청 시 정규식 1차 단축 (date_hints≥2 OR date+place 존재) → Gemini 스킵 → 채팅방 누적 거부 발언이 vote_card 후보 필터에 반영 안 됨.
- **영향 범위**: AI 패널 `direct_request` 경로만. 자동 트리거 경로(`_analyze_conversation`)는 정상.
- **수정 방향 (옵션 B, audit-findings.md 해결점 O, line 996)**: shortcut 조건에 "context에 거부 키워드 없을 때만" AND 추가. Completeness 9/10, ~10min.
- **상태**: 🔴 부분 작동 (auto-trigger 정상, direct_request 갭). v2 spec backlog 또는 시연 직전 hotfix 후보. 인용: `docs/handoff/audit-findings.md:971~1002`.

### 6.13 확정 결정 사항 인라인 점검 (Q* 매핑)

본 §6에서 직접 다룬 결정 사항:

| Q | 결정 | 본 §6 반영 위치 |
|---|---|---|
| Q1=B | 단일 슬롯도 vote_card 발행 | §6.5 F3, §6.8 (C3 해소) |
| Q3=A | headcount=None → 방 멤버 수 | §6.5 F2 |
| Q6=A | 0 슬롯 → 다수결 vote_card | §6.5 F1 |
| Q7-b | refresh 시 방 전체 broadcast | §6.9 refresh 동작 |
| Q7-c | 토글 차단 조건 (C1∨C3∨C4) | §6.5/§6.9에서 참조 (페이로드 §3 인라인) |
| Q8=A | F1 정렬 시간 빠른 순 | §6.5 F1 |
| Q9=A | partial 시간 immutable | §6.9 (C2 해소) |
| Q12=A | 게스트 포함 headcount | §6.5 F2 |
| Q13=B | refresh 권한 발화자+방장 | §6.9 |
| Q14=C | Redis idempotency + 일일 100회 | §6.9 |
| Q15=A | 실명 narrator (PII 트레이드오프) | §6.7 F4, §6.9 |
| Q16=C | blocker 익명 + 더보기 | §6.5 F1 |

> **Q7-c 토글 차단 조건 재확인**:
> - **C1**: 발화자 `share_*_data == False` → 그룹/발화자 분리 불가
> - **C3**: 그룹 다수결 결과 = 발화자 선호 결과 (분리 의미 없음)
> - **C4**: 발화자 본인 정보 비어있음
> - C2(게스트)는 채팅방 입장 후 선호 설정 가능하므로 토글 허용 (§5.1.3 참조).

---

## 7. 권한 / 접근 조건

매듭의 권한 모델은 **`RoomMember` 기반 멤버십**과 **`viewer_user_id` 기반 privacy boundary** 두 축으로 구성된다. 모든 라우터·WebSocket 채널·파이프라인은 진입 시 멤버십을 검증하고, 응답 합성 단계에서 viewer 본인 외 멤버의 민감 정보(캘린더 busy, private agent 메시지)는 제외하거나 익명 처리한다.

### 7.1 사용자 역할 정의

| 역할 | 식별자 | 가입 경로 | calendar_consent |
|---|---|---|---|
| 방장 (owner) | `Room.created_by == user.id`<br>혹은 `RoomMember.role == MemberRole.owner` | 방 생성 시 자동 부여 (`rooms.py:119,125`) | True 가능 |
| 멤버 (member) | `RoomMember.role == MemberRole.member`<br>`User.is_guest == False` | 방장이 명시적으로 추가 (`rooms.py:134`) | True/False |
| 게스트 (guest) | `RoomMember.role == MemberRole.member`<br>`User.is_guest == True` | 카카오 링크 → 이름 입력 가입 (`rooms.py:235~244`, `models/user.py:45`) | **False 강제** (`rooms.py:239,295`) |
| 비멤버 (non-member) | `RoomMember` 행 없음 | — | — |

**게스트 pseudo_id**: synthetic email `guest-{uuid12}@maedeup.local` (`rooms.py:234`). 동일 방·동일 이름 재가입 시 신규 row를 만들지 않고 기존 user의 JWT만 재발급 (`rooms.py:202~232`) — `_maybe_emit_proposal`의 `len(availability) >= member_count` 영구 실패를 방지하기 위한 의도적 설계.

### 7.2 권한 매트릭스

| 작업 | 방장 | 멤버 | 게스트 | 비멤버 | 검증 위치 |
|---|---|---|---|---|---|
| 방 조회 (`GET /rooms/{id}`) | 있음 | 있음 | 있음 | 없음 | `rooms.py:154` 멤버십 검증 |
| 방 목록 (`GET /rooms`) | 자기 소속만 | 자기 소속만 | 자기 소속만 | 없음 | `rooms.py:301~319` |
| 소셜 메시지 발송 (`pane_type=social`) | 있음 | 있음 | 있음 | 없음 | `ws/social.py:509,522` |
| AI 발화 (`pane_type=agent`, private) | 있음 | 있음 | 있음 | 없음 | `ws/agent.py:871~892` |
| 카드 발행 트리거 (자동) | 있음 | 있음 | 있음 | 없음 | 파이프라인 `viewer_user_id` 멤버 검증 |
| 카드 발행 트리거 (`direct_request`) | 있음 | 있음 | 있음 | 없음 | 동일 |
| 시간 슬롯 투표 | 있음 | 있음 | 있음 | 없음 | `meetings.py` 멤버십 |
| 장소 추천 클릭 | 있음 | 있음 | 있음 | 없음 | UI only (PII 동의 별도) |
| 시간 확정 (`POST /meetings/confirm`) | 있음 | 있음 | 있음 (멤버십 동일) | 없음 | `meetings.py:365~372` "멤버라면 누구나 확정 가능" |
| 장소 확정 (`POST /meetings/confirm` 장소 필드) | 있음 | 있음 | 있음 | 없음 | 동일 |
| `POST /meetings/{id}/recommendations/refresh` | 있음 | 발화자 본인만 | 발화자 본인만 | 없음 | §7.5 (Q13=B) |
| 모임 취소 (`POST /meetings/{id}/cancel`) | 있음 | 없음 | 없음 | 없음 | `meetings.py:869` `meeting.created_by` 검증 |
| 방 나가기 (`DELETE /rooms/{id}/members/me`) | 있음 (위임/삭제 분기) | 있음 | 있음 | — | `rooms.py:565~600` (`is_host = room.created_by == user_id`) |
| 게스트 초대 링크 생성 | 있음 | 있음 (방 멤버라면) | 있음 | 없음 | 링크는 `room_id`만 필요 (`rooms.py:178`) |
| 캘린더 불가능 토글 (rejected_dates) | 있음 | 있음 | 있음 (Q12=A) | 없음 | calendar API, 게스트 포함 |
| Google Calendar OAuth 연결 | 있음 (`calendar_consent=True`) | 있음 | **불가** (`is_guest=True`) | — | OAuth flow guard |

게스트가 시간/장소 confirm을 호출할 수 있는 것은 의도된 동작 — 시연 시나리오에서 게스트도 멤버와 동등한 합의 권한을 가진다. `confirm`은 멤버십만 요구 (`meetings.py:371`).

### 7.3 멤버십 검증 흐름

모든 보호 라우터의 표준 패턴:

1. `Depends(get_current_user)` → JWT 해석 → `current_user.sub` (= `user_id`)
2. `select(RoomMember).where(user_id == ..., room_id == ...)` 조회
3. `scalar_one_or_none() is None` → `HTTPException(403)`

예시 (`meetings.py:365~372`):
```python
member_result = await session.execute(
    select(RoomMember).where(
        RoomMember.user_id == int(current_user.sub),
        RoomMember.room_id == body.room_id,
    )
)
if member_result.scalar_one_or_none() is None:
    raise HTTPException(status_code=403, detail="Host is not a room member")
```

방장 전용 작업은 추가로 `room.created_by != int(current_user.sub)` 또는 `RoomMember.role == MemberRole.owner` 비교. 모임 취소는 `meeting.created_by` (모임 생성자 = 발화자) 기준 (`meetings.py:869`).

### 7.4 viewer_user_id 기반 privacy boundary

LangGraph 파이프라인은 진입 시 JWT의 `user_id`를 `state["viewer_user_id"]`로 주입 (`state.py:113~114` 인근, `agent.py:812,920,976`).

**적용 지점**:

- **AI 메시지 가시성** (`pipeline/helpers/messaging.py:132~138`): `viewer_user_id` 있으면 `visibility=private`, `uid=viewer_user_id`. `shared=True` 명시 시에만 방 전체 broadcast.
- **WebSocket 라우팅** (`ws/agent.py:1020`): `new_msg["visibility"] == "shared"` → `shared_channel`, 그 외 → `user_channel` (개인 채널). private 메시지는 다른 멤버에게 절대 push되지 않는다.
- **캘린더 busy 합성**: 그룹 슬롯 계산 시 멤버 busy를 머지하되, 응답 narrator·UI에는 본인 외 멤버의 상세 시간 (`14:00~15:00 회의`) 노출 금지 — 점유 여부(`busy`) bool만 표시.

privacy boundary는 "내 화면에 보이는 정보 = 내 PII + 그룹 합성 결과(익명 카운트)" 원칙.

### 7.5 refresh 라우트 권한 (Q13=B)

`POST /meetings/{id}/recommendations/refresh` (PR-2 §6 도입):

- **허용**: 발화자(`requester_user_id == current_user.sub`) **OR** 방장(`room.created_by == current_user.sub`)
- **거부**: 멤버지만 비-발화자인 일반 사용자 → 403 `not_authorized_to_refresh`
- 게스트도 본인이 발화자이면 허용 (게스트 ≠ 비-발화자)

**구현 시 검증 순서**:
1. 멤버십 (§7.3) → 비멤버 403
2. `requester_user_id` 일치 또는 owner role → 둘 다 실패 시 403
3. §7.6 토글 차단 조건 평가 → C1/C3/C4 해당 시 422 `toggle_disabled`

### 7.6 토글 차단 조건 (Q7-c)

페이로드의 `preference_toggle_enabled: false` 산출 규칙 (§3 페이로드 메타). UI에서 토글 비활성화로 표현되며, 우회 호출 시 422로 거부:

- **C1 (PII 미동의)**: 발화자의 `share_food_data == False` AND `share_location_data == False` AND `share_schedule_data == False` → 합성할 PII 없음
- **C3 (의미 없는 토글)**: `recommendation_payload_group == recommendation_payload_speaker` (동일 결과 산출) → 토글해도 변화 없음
- **C4 (발화자 정보 부재)**: 발화자의 `home_base IS NULL` AND `MeetingPreference` 행 없음 → 발화자 기준 합성 불가
- **C2 제외**: 게스트(`is_guest=True`)도 채팅방 입장 후 `MeetingPreference`·`home_base` 설정 가능 → C2는 차단 사유 아님 (Q7-c 결정 명시)

차단 시 narrator는 "현재 선호 기준 전환은 사용할 수 없어요"로 안내 (구체 사유는 노출하지 않음 — PII 누설 방지).

### 7.7 게스트 정책 세부

- **가입 경로**: 카카오톡 공유 링크 → `POST /rooms/{id}/guests/join` (`rooms.py:178~298`)
- **계정 분리**: synthetic email, `is_guest=True`, `calendar_consent=False` 강제 — Google OAuth 진입 자체가 막힘
- **선호 설정**: 방 입장 팝업에서 음식/장소/시간/`home_base` 입력 가능 (§8 데이터 정책)
- **캘린더 불가능 토글**: Q12=A — 게스트 포함. Google busy는 없지만 rejected_dates 입력 경로는 동등 제공 → headcount fallback 분모(`member_count`)에도 포함
- **합의 권한**: 시간·장소 confirm 호출 가능 (§7.2). 방장 권한은 별도 (modal 취소·refresh 트리거)
- **부풀림 방지**: 동일 방·동일 이름 재가입 시 기존 row 재사용 (`rooms.py:202~232`) — `member_count` 분모 안정성 보장. 단, 다른 이름으로 재접속하면 새 게스트 생성됨 (알려진 한계, `rooms.py:189` 주석)

### 7.8 WebSocket 채널 권한

- **`pane_type=agent` 채널** (`ws/agent.py`): 사용자별 channel + 방 공유 channel 이원화. private 메시지(`visibility=private`)는 viewer 본인의 user channel로만 push (`ws/agent.py:1020`). shared 메시지(인사말 등, `agent.py:179`)만 shared_channel broadcast.
- **`pane_type=social` 채널** (`ws/social.py:509,522`): 방 멤버 전체 broadcast. PII 없는 사용자 발화·시스템 알림(`member_joined` `rooms.py:262~268`)만 전송.
- WS 연결 시 방 멤버십 검증 → 비멤버는 connect 단계에서 close.

### 7.9 데이터 접근 PII 정책 (§8 위임 요약)

- **narrator 실명 정책 (Q15=A)**: 토글 재발행 narrator는 "OOO님 선호 기준으로 다시 추천했어요" — 실명 명시. PII 노출 트레이드오프를 인지하고도 토글 행동 투명성을 우선. 세부 마스킹·opt-out은 **§8 데이터 정책**에서 본격 정의.
- **F1 blocker 익명/실명 토글 (Q16=C)**: 기본 "1명 불참" 익명 표시 → 사용자 클릭(`더보기`) 시 실명 공개. 점진 공개 원칙. 데이터 흐름·로그 보존 정책은 **§8**.
- **F4 캘린더 권한 없음 narrator**: 캘린더 미연결 멤버 안내 시 실명 노출 여부 — Q15=A 일관 적용 후보지만, **§8에서 narrator 정책 통합 검토 (open)**.
- **캘린더 busy 상세 마스킹**: §7.4 원칙(상세 시간 미노출, bool만) — **§8에서 저장·캐시 TTL·삭제 정책 정의**.

---

## 8. 데이터 정책

(작성 예정)
- Google Calendar busy 데이터: 메모리 캐시만, 영속 저장 안 함
- rejected_dates: meeting 단위 누적, 새 meeting 시작 시 초기화
- MeetingPreference: 방 입장 팝업에서 명시 수집

---

## 9. API / 이벤트 / 로그

(작성 예정)
- 진입 이벤트: `agent_message_received` → run_pipeline
- 출력 이벤트: WebSocket `vote_card` push
- 로그 키: `[TIMING] slot_filling`, `[TIMING] vote_card_creation`, `calendar_strategy=*`
- 메트릭: vote_card 발행 / skip 비율, fallback 트리거 빈도

---

## 10. 회귀 테스트 케이스

§2의 S1~S10을 pytest 시그니처로 변환 (작성 예정).

```python
# 예시
async def test_S1_basic_next_week_vote_card():
    """다음주 모이자 발화 → 평일 저녁 3~5개 슬롯 vote_card 발행."""
    result = await run_pipeline(...)
    assert result["vote_card_payload"]["type"] == "vote_card"
    assert 3 <= len(result["vote_card_payload"]["time_options"]) <= 5
```

---

## 11. 비기능 (Out of scope)

- 반복 모임 (recurring meeting)
- 비-Google 캘린더 (Outlook, Naver 등)
- 시간대 변환 (KST 외 멤버)
- 다중 모임 시간 겹침 경고
- AI 자동 협상 ("A님 양보해주실 수 있을까요?" 같은 능동 제안)

**알려진 한계 (Known Limitations)**

- **Gemini 휴일 라벨 (Q10=C)**: prompt의 휴일·요일 안내는 힌트 수준 — 실제 매장 영업시간·휴무 회피를 보장하지 않음 (Kakao Local Keyword API 영업시간 미제공). 정확한 휴무 필터는 v2 후보 (Google Places 또는 영업시간 데이터 plumbing).

---

## 결정 안건 (Open Questions)

| # | 결정 | 영향 시나리오 | 후보 |
|---|---|---|---|
| Q1 | 슬롯 1개만 남으면? | S5, S9 | **결정: B) 단일 슬롯도 vote_card** (날짜범위 확정 상태 전제) |
| Q2 | `place_hint` 없을 때 fallback 순서 | §4.4 F5 (예정), §5.3 P0-3 | **결정**: 선호 장소 다수결 → 동률 시 발화자 → 선호 없으면 방장 위치 (§4.4 F5 신설은 PR-2) |
| Q3 | headcount=None 시 기본값 | F2 | **결정: A) 방 멤버 수 사용** (게스트 포함 — Q12=A) |
| Q5 | 발화자 선호 vs 그룹 선호 충돌 시 | P3 | **결정: 다수결 기본 + 발화자 토글 hybrid** (UI 메타 = Q7=B) |
| Q6 | F1 fallback (전원 불가능 시 다수결) 구현 우선순위 | S8 | **결정: A) v1.0 구현 포함** (정렬 = Q8=A) |
| Q7 | Q5 hybrid 토글 UI 메타 키 이름·위치 | §3 페이로드 확장 | **결정: B)** `preference_source: "group"\|"speaker"` + `preference_toggle_enabled: bool`, vote_card·place 양쪽 |
| Q7-b | 토글 동작 범위 | §6 (재발행 흐름), §9 (라우트) | **결정: 방 전체 갱신** (broadcast) — `POST /meetings/{id}/recommendations/refresh` 신설 |
| Q7-c | `preference_toggle_enabled=false` 트리거 조건 (게스트? 그룹·발화자 일치? 발화자 정보 부재?) | §3 페이로드 보강 | **결정: C1 + C3 + C4** (게스트 C2 제외 — 게스트도 채팅방 입장 후 선호 설정 가능). **C1**: 발화자 `share_*_data == False` (PII 동의 안 함). **C3**: 그룹 다수결과 발화자 선호 결과 동일 (의미 없음). **C4**: 발화자 본인 정보(home_base/preferences)가 비어있음 |
| Q8 | F1 fallback 정렬 (멤버 수 동률 시) | §4.4 F1 명세 | **결정: A) 시간 빠른 순** (후보는 이미 선호·거부 반영된 상태 가정) |
| Q9 | partial maedeup(time_only) 발행 후 장소 채워졌을 때 시간 번복 가능? | §5.1.6 ↔ 해결점 K | **결정: A) 번복 불가** (확정 후 잠김, 재추천은 별도 경로) |
| Q10 | 한국 휴일/주말이 장소 추천에도 영향? | §4.3 T·§5.1.4 | **결정: C) Gemini prompt 안내** (Kakao 영업시간 미제공 → 옵션 B 단독 불가, v2 후보) |
| Q11 | 기존 사용자 `calendar_consent` 마이그레이션 전략 (default False → True) | PR-X (별도 마이그레이션) | 미결 — PR-X 진행 시 결정 |
| Q12 | `headcount` 방 멤버 수 fallback에 게스트 포함 여부 | §5.1.5 headcount | **결정: A) 게스트 포함** (게스트도 매듭 캘린더 불가능 토글로 거부일 입력 가능) |
| Q13 | `recommendations/refresh` 라우트 권한 | §9 API | **결정: B) 발화자 + 방장만** (트리거 최소 권한) |
| Q14 | refresh 호출 제한 | §9 API | **결정: C) Redis idempotency 캐시 + 일일 100회** (같은 source/scope 조합은 캐시 hit) |
| Q15 | 토글 재발행 narrator 문구 | §3 narrator | **결정: A) "OOO님 선호 기준으로 다시 추천했어요"** (실명 명시 — PII 노출 트레이드오프, 사용자 토글 행동의 투명성 우선) |
| Q16 | F1 `blocker_notification_payload` UI 멤버 식별 | §3 페이로드, UI | **결정: C) 기본 익명 + 더보기 실명** (기본 "1명 불참", 사용자 의도로 클릭 시 실명 — 점진 공개) |

---

## 변경 이력
- 2026-05-14: 초안 작성 (§1~§4, §11), §5~§10 scaffolding
- 2026-05-14 — PR-2: §1~§4 시간+장소 보강 (헤더·§1.1~1.3·§2 S11~S14·§3 페이로드 4종(vote_card / place_recommendation / maedeup_card 확정·partial) + narrator 통합·§4 R/P/T/F 매트릭스 R7~R9·P4~P6·T6~T8·F5~F6 신설). Q7-c 결정 (C1 + C3 + C4, 게스트 C2 제외).
- 2026-05-14 — PR-3.2: §7 권한·접근 조건 본문 작성 (§7.1 역할 정의·§7.2 권한 매트릭스 15행·§7.3 멤버십 검증·§7.4 viewer_user_id privacy·§7.5 refresh 권한 Q13=B·§7.6 토글 차단 Q7-c·§7.7 게스트 정책·§7.8 WS 채널·§7.9 §8 위임 요약). Q12=A·Q13=B·Q14=C·Q15=A·Q16=C 반영.
