# 기능정의서 — 시간 조율 (Time Coordination)

작성: 2026-05-14
작성자: 본인 (장소/시간 조율 담당)
대상 노드: `slot_filling` (입력 처리) + `vote_card_creation` (출력 카드) + `function_calling`의 캘린더 path
관련 문서:
- [recommend-input-catalog.md](./2026-05-13-recommend-input-catalog.md) — 활용 가능 인풋 카탈로그
- [pipeline-structure.html](./pipeline-structure.html) — 파이프라인 구조

> **목적**: 채팅방에서 모임 시간을 합의하는 과정을 자동화한다. 사용자가 합의 가능한 후보 시간을 만들어 투표 카드로 제시하는 책임.

---

## 1. 기능 개요

### 1.1 핵심 가치 (한 문장)
**채팅으로 흩어진 시간 의사를 자동으로 모아 "투표 가능한 후보 슬롯"으로 변환한다.**

### 1.2 시스템 위치
- **slot_filling (노드 3)**: 사용자 발화·캘린더·선호도를 읽어 슬롯 상태 채우기
- **function_calling (노드 4)**: 캘린더 API 호출 (`get_free_slots`), 빈 슬롯 계산
- **vote_card_creation (노드 6a)**: 후보 슬롯을 투표 카드 페이로드로 직렬화 + meeting pending 생성

이 spec은 **입력 발화부터 vote_card_payload 발행까지** 전체 경로를 다룬다.

### 1.3 책임 경계
- ✅ 이 spec이 정의함
  - 어떤 발화가 시간 조율 흐름을 트리거하는가
  - 슬롯을 어떻게 만들고 거르는가
  - 어떤 형태의 카드를 출력하는가
- ❌ 이 spec이 정의하지 않음
  - intent 분류 자체 (동료 영역, `intent_detection`)
  - 검증 후 maedeup 카드로 갈지 여부 (동료 영역, `supervisor_validation`)
  - 캘린더 API 자체 (외부, `google_calendar.py`)

---

## 2. 사용자 시나리오 (= 골든 회귀 케이스)

각 시나리오는 "발화/이벤트 → 기대 출력"으로 정의. **이 표가 §10 회귀 테스트의 일대일 원본이 된다.**

| ID | 발화 / 이벤트 | trigger_reason | 기대 출력 | 검증 포인트 |
|---|---|---|---|---|
| **S1. 기본 케이스** | "다음주에 모이자" | `direct_request` | 평일 저녁 시간 3~5개 vote_card | 모든 멤버 가능한 슬롯만 추천 |
| **S2. 거부 누적** | "월요일은 안돼" (이후 새 추천 요청) | `direct_request` | 월요일 제외된 vote_card | `rejected_dates` 누적, 안전망 필터 작동 |
| **S3. 선호 매칭** | (방 설정: 평일 오전 선호) "이번주 모이자" | `direct_request` | 평일 오전 슬롯만 vote_card | `preference_common_times` 적용, 주말 자동 제외 |
| **S4. 다음주 확장** | "이번주 모이자" → 이번주 모두 안됨 | `direct_request` | 다음주로 확장된 vote_card + 사유 narrator | `expanded_to_next_week=true`, 사용자에게 사유 안내 |
| **S5. 명시 단일 시간** | "내일 6시 어때" | `direct_request` | 단일 슬롯 카드 (또는 maedeup 직행) | Q1 결정 필요 (현재 단일이면 skip) |
| **S6. 채팅 기반 충돌 감지** | (TimeBar에서 멤버 전원 선택 완료) | `all_members_selected` | TimeBar 데이터 기반 vote_card | 채팅에서 추출된 거부 시간 반영 |
| **S7. 시간대 충돌 투표** | "A는 토요일, B는 일요일이래" | `direct_request` | conflict_options 분기 vote_card | `conflict_options` 슬롯 생성 |
| **S8. 모두 불가 fallback** | 거부/캘린더로 가능한 슬롯 0개 | any | 가장 많은 멤버 가능한 슬롯 3개 vote_card + "전원 가능 시간 없음" narrator | "다수결 vote_card" 분기 — **v1.0 구현 대상 (Q6=A)**, 정렬 정책 Q8 미결 |
| **S9. 시간만 결정** | "다음주 화요일 6시" | `direct_request` | `time_only_ready` → maedeup 카드 직행 (vote_card 우회) | `partial_mode="time_only"` |
| **S10. 결론 자동 감지** | (멤버들이 채팅에서 "그럼 화요일 7시로 ㄱ") | `conclusion_detected` | maedeup 카드 직행 | vote_card 스킵, 결론 합의로 인식 |

### 2.1 비목표 시나리오 (Out of scope, §11)
- "매주 모이는 정기 모임" (recurring) — MVP에선 단일 약속만
- "오프라인 일정 import" (사용자가 따로 캘린더 등록) — Google Calendar로 한정
- "다른 모임과 시간 겹침 경고" — 다중 모임은 P2 이후

---

## 3. 출력 카드 페이로드 형식 (vote_card_payload)

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
    // ... 1~5개
  ],
  "headcount": 4,                         // entity 추출 or 멤버수 fallback
  "blocker_notification": null,           // 시간 외 이유로 불참 멤버 (e.g. "OOO님 일정 충돌")
  "calendar_strategy": "natural_language_time_options"
                                          // multi_date_vote | preference_based | natural_language_time_options
}
```

### 3.1 narrator 메시지 (페이로드와 함께 발행)
```
"캘린더 확인 결과, 5/19 (월) 18:00~20:00을(를) 추천드려요. 📅 아래에서 확인해주세요."
```
- `date_conflict=true`면: `"날짜가 엇갈리네요 (5/19: 3명, 5/20: 2명). 가장 많이 선택된 날짜 기준으로..."`

### 3.2 페이로드 변경 시 영향 범위
- 프론트 `MeetingChatRoom.tsx` voteCard 렌더 (mock 컨트랙트)
- `confirm` 엔드포인트가 `meeting_id` + `slot_id`로 확정 호출
- maedeup_card_creation이 vote_options 중 선택된 슬롯 참조

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

### 4.2 선호 매칭 (Preference Matching)
| ID | 기능 | 데이터 출처 | 처리 위치 |
|---|---|---|---|
| P1 | 방 멤버 공통 선호 시간대 | MeetingPreference 교차 | `_load_meeting_preferences` → `preference_common_times` |
| P2 | 평일/주말 필터 | `preference_common_times`에 "평일~" 포함 | vote_card_creation `weekday_only` 필터 |
| P3 | 발화자 개인 시간 선호 | User.time_preference (🔧 plumbing 필요) | **P0 plumbing 후 추가** |

### 4.3 탐색 정책 (Search Policy)
| ID | 기능 | 트리거 | 처리 |
|---|---|---|---|
| T1 | 이번주 우선 탐색 | date_hint 미지정 | `get_free_slots` default window = 7일 |
| T2 | 다음주 확장 | 이번주 0 슬롯 | `expanded_to_next_week=true`, window +7일 |
| T3 | 멤버 캘린더 합집합 | 항상 | `_load_busy_by_user_for_state` → 모든 멤버 busy 합집합 제외 |
| T4 | 휴일/주말 라벨 | 항상 | `_get_korean_holiday`, `_is_weekend` → 슬롯 메타 |
| T5 | 다중 날짜 빌더 | `date_hints` ≥2개 | `_build_multi_date_slots` |

### 4.4 Fallback 정책 (Fallback Policy)
| ID | 기능 | 트리거 | 출력 |
|---|---|---|---|
| F1 | 0 슬롯 → 다수결 | 전원 가능 슬롯 0개 | (**v1.0 구현 대상**, Q6=A) 가능 멤버 max인 슬롯 3개 + blocker_notification — **정렬: 시간 빠른 순 (Q8=A)**, 후보는 이미 선호·거부 반영된 상태 가정 |
| F2 | headcount=None | entity가 인원 추출 못함 | (현재) supervisor가 에러 — Q3 결정 필요 |
| F3 | single slot skip | 슬롯 1개만 남음 | `vote_card_skipped` 상태 → maedeup 직행 — Q1 결정 필요 |
| F4 | 캘린더 권한 없음 | OAuth 미동의 멤버 | 해당 멤버 캘린더 무시 + narrator에 명시 |

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
> **Q5 hybrid 토글 (Q7=B 결정)**: 카드 페이로드에 `preference_source: "group"|"speaker"` + `preference_toggle_enabled: bool` 두 키 (vote_card·place 양쪽). **Q7-b: 방 전체 갱신** — 토글 시 새 페이로드 broadcast (`POST /meetings/{id}/recommendations/refresh` 신설, §9). Q7-c (`preference_toggle_enabled=false` 트리거 조건)는 PR-2 §3 작업 시 결정.

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
> `blocker_notification_payload` ⚠️ 사유: payload 생성 일부, UI 미연결. Q6=A 결정으로 v1.0 구현 대상.

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

(작성 예정)
- 슬롯 진행 차수 (slot_filling_turns) — 중복 발화 처리
- awaiting_user_reply / wait_timed_out — 대기 상태
- 노드 예외 시 fallback narrator
- conclusion_false_positive 분기

---

## 7. 권한 / 접근 조건

(작성 예정 — 짧음)
- viewer_user_id 기반 privacy boundary (자기 캘린더만 본인 이름으로 표시)
- 방 멤버가 아닌 사용자는 진입 자체 차단 (router 단에서)

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
| Q7-c | `preference_toggle_enabled=false` 트리거 조건 (게스트? 그룹·발화자 일치? 발화자 정보 부재?) | §3 페이로드 보강 | 미결 — PR-2 §3 작업 시 결정 |
| Q8 | F1 fallback 정렬 (멤버 수 동률 시) | §4.4 F1 명세 | **결정: A) 시간 빠른 순** (후보는 이미 선호·거부 반영된 상태 가정) |
| Q9 | partial maedeup(time_only) 발행 후 장소 채워졌을 때 시간 번복 가능? | §5.1.6 ↔ 해결점 K | **결정: A) 번복 불가** (확정 후 잠김, 재추천은 별도 경로) |
| Q10 | 한국 휴일/주말이 장소 추천에도 영향? | §4.3 T·§5.1.4 | **결정: C) Gemini prompt 안내** (Kakao 영업시간 미제공 → 옵션 B 단독 불가, v2 후보) |
| Q11 | 기존 사용자 `calendar_consent` 마이그레이션 전략 (default False → True) | PR-X (별도 마이그레이션) | 미결 — PR-X 진행 시 결정 |
| Q12 | `headcount` 방 멤버 수 fallback에 게스트 포함 여부 | §5.1.5 headcount | **결정: A) 게스트 포함** (게스트도 매듭 캘린더 불가능 토글로 거부일 입력 가능) |

---

## 변경 이력
- 2026-05-14: 초안 작성 (§1~§4, §11), §5~§10 scaffolding
