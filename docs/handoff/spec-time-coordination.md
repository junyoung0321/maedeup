# 기능정의서 — 시간 조율 (Time Coordination)

작성: 2026-05-14
작성자: 본인 (장소/시간 조율 담당)
대상 노드: `slot_filling` (노드 3) + `function_calling` (노드 4) + `vote_card_creation` (노드 6a)
관련 문서:
- [spec-common.md](./spec-common.md) — 공통 정책·권한·API·비기능 (단일 SoT)
- [spec-place-recommendation.md](./spec-place-recommendation.md) — 장소 추천 (자매 spec)
- [recommend-input-catalog.md](./2026-05-13-recommend-input-catalog.md) — 활용 가능 인풋 카탈로그
- [pipeline-structure.html](./pipeline-structure.html) — 파이프라인 구조

> **목적**: 채팅방에서 모임 **시간**을 합의하는 과정을 자동화한다. 사용자 발화·캘린더·선호도를 통합하여 합의 가능한 후보 시간을 투표 카드(`vote_card`)로 제시한다. 시간만 결정되고 장소가 pending인 경우 partial 매듭 카드(`maedeup_card`, time_only)로 직행한다.

> **권한·데이터 정책·API·비기능 요건**은 [`spec-common.md`](./spec-common.md) §7~§13 참조.

---

## 1. 기능 개요

### 1.1 핵심 가치 (한 문장)
**채팅으로 흩어진 시간 의사를 자동으로 모아 "투표 가능한 후보 슬롯"으로 변환하고, 합의 결과를 매듭 카드로 마무리한다.**

### 1.2 시스템 위치
- **slot_filling (노드 3)**: 사용자 발화·캘린더·선호도를 읽어 슬롯 상태 채우기 (시간·장소 공통 진입은 [`spec-common.md §4`](./spec-common.md) 참조)
- **function_calling (노드 4)**: 캘린더 API 호출 (`get_free_slots`), 빈 슬롯 계산
- **vote_card_creation (노드 6a)**: 후보 슬롯을 투표 카드 페이로드로 직렬화 + meeting pending 생성
- **maedeup_card_creation (노드 7)**: 시간만 결정된 경우 partial(time_only) 카드 발행 → 페이로드는 [`spec-place-recommendation.md §3.3`](./spec-place-recommendation.md)

이 spec은 **입력 발화부터 `vote_card` payload 발행까지** 시간 경로를 다룬다.

### 1.3 책임 경계
- ✅ 이 spec이 정의함
  - 어떤 발화가 시간 조율 흐름을 트리거하는가
  - 시간 슬롯을 어떻게 만들고 거르는가 (선호/거부/캘린더 통합)
  - 어떤 형태의 카드 페이로드(`vote_card` / `maedeup_card` partial)를 출력하는가
  - 시간 잠금 정책 (Q9=A partial maedeup 시간 immutable)
- ❌ 이 spec이 정의하지 않음
  - 장소 추출·검색·추천 → [`spec-place-recommendation.md`](./spec-place-recommendation.md)
  - 권한·접근 조건 → [`spec-common.md §7`](./spec-common.md)
  - 데이터·PII·동의 정책 → [`spec-common.md §8`](./spec-common.md)
  - API·이벤트·로그 → [`spec-common.md §9`](./spec-common.md)
  - intent 분류 자체 (동료 영역, `intent_detection`)
  - 검증/판단 supervisor (동료 영역, `supervisor_validation`)
  - 캘린더 API 자체 (외부, `google_calendar.py`)

---

## 2. 사용자 시나리오 (= 골든 회귀 케이스)

각 시나리오는 "발화/이벤트 → 기대 출력"으로 정의. **이 표가 §10 회귀 테스트의 일대일 원본이 된다.**

> **장소 시나리오 (S11~S14, S16~S20)** 는 [`spec-place-recommendation.md §2`](./spec-place-recommendation.md), **공통 시나리오 (S15 refresh)** 는 [`spec-common.md §2`](./spec-common.md) 참조.

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

### 2.1 비목표 시나리오 (Out of scope, [`spec-common.md §11`](./spec-common.md))
- "매주 모이는 정기 모임" (recurring) — MVP에선 단일 약속만
- "오프라인 일정 import" (사용자가 따로 캘린더 등록) — Google Calendar로 한정
- "다른 모임과 시간 겹침 경고" — 다중 모임은 P2 이후

---

## 3. 출력 카드 페이로드 형식

본 spec은 시간 투표 카드 페이로드를 발행한다: `vote_card` (§3.1). narrator는 §3.2.

> **place_recommendation·maedeup_card 확정·partial** 페이로드는 [`spec-place-recommendation.md §3`](./spec-place-recommendation.md) 참조.

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

### 3.2 narrator 메시지 (시간 카드)

페이로드와 함께 발행되는 narrator 메시지.

- **vote_card**:
  ```
  "캘린더 확인 결과, 5/19 (월) 18:00~20:00을(를) 추천드려요. 📅 아래에서 확인해주세요."
  ```
  - `date_conflict=true`면: `"날짜가 엇갈리네요 (5/19: 3명, 5/20: 2명). 가장 많이 선택된 날짜 기준으로..."`
- **refresh 토글 (Q15=A)**: [`spec-common.md §3.1`](./spec-common.md) 참조.

> maedeup_card 확정·partial narrator는 [`spec-place-recommendation.md §3.4`](./spec-place-recommendation.md) 참조.

---

## 4. 기능 상세 (Functional Detail Matrix)

> 본 절은 시간 관련 R/P/T/F 항목만 정의. 장소 관련 R7~R9·P4~P6·T6~T8·F5~F9는 [`spec-place-recommendation.md §4`](./spec-place-recommendation.md) 참조.

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
| F2 | headcount=None | entity가 인원 추출 못함 | 방 멤버 수 fallback (**Q3=A**, 게스트 포함 — Q12=A) |
| F3 | 단일 슬롯도 vote_card | 슬롯 1개만 남음 | 단일 옵션 vote_card 발행 (**Q1=B**, 날짜범위 확정 전제) — skip 폐기 |
| F4 | 캘린더 권한 없음 | OAuth 미동의 멤버 | 해당 멤버 캘린더 무시 + narrator에 명시 |

---

## 5. 입력값 / 출력값

본 spec 노드(`slot_filling` · `function_calling`/캘린더 · `vote_card_creation`)가 **소비**·**생성**하는 데이터를 정리한다. 전체 카탈로그(약 40개, 6 카테고리)는 [`2026-05-13-recommend-input-catalog.md`](./2026-05-13-recommend-input-catalog.md) 참조 — 본 절은 그중 본 spec이 실제로 읽거나 쓰는 항목만 추려 file:line을 표기한다.

마크: ✅ 활용 중 / ⚠️ state에 있으나 미활용 / 🔧 plumbing 필요 (§5.3에서 P0로 별도 다룸)

### 5.1 입력 (소비) — 기능별 데이터 카탈로그

시간 관련 항목만 정리. 장소 관련 5.1.4는 [`spec-place-recommendation.md §5.1.4`](./spec-place-recommendation.md), 공통 진입·상태 5.1.7은 [`spec-common.md §4`](./spec-common.md) 참조.

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

#### 5.1.3 선호 매칭 (시간 한정)

| 항목 | 의미 | 출처 | 사용처 | 예시 데이터 형태 | 마크 |
|---|---|---|---|---|:---:|
| `_load_meeting_preferences()` | `MeetingPreference` row 집계 (방 전체) | `helpers/preferences.py:447~541` | `_enrich_with_preferences` 진입점 | `{"has_preferences":true,"all_submitted":true,"best_location":"홍대","common_times":["주말 오후"],"total_members":4}` | ✅ |
| `preference_common_times` | 멤버 공통 가능 시간대 교차 | `helpers/preferences.py:493~509` → `nodes/slot.py:87,98` | `function_call` preference_based 슬롯 생성 (`helpers/slots.py:331~349`) | `["평일 저녁","주말 오후"]` | ⚠️ |
| `User.time_preference` | 개인 lifestyle 시간 (단일 str) | `personal_data_extractor.py:85~90`·`preferences.py:218` | personal_data 익명 합산 (점수화 미연결) | `"평일 저녁 7시 이후"` | ⚠️ |
| 발화자 토글 (Q5 hybrid) | 동률 시 트리거 사용자 선호 우선 토글 | (Q5 결정, 미구현) | place_hint fallback 순위·UI 토글 | — | 🔧 |

> `preference_common_times` ⚠️ 사유: 교차 set 비면 top-3 fallback. 시연 시나리오 한정 검증.
> **Q5 hybrid 토글 (Q7=B 결정)**: 카드 페이로드에 `preference_source: "group"|"speaker"` + `preference_toggle_enabled: bool` 두 키 (vote_card·place 양쪽). **Q7-b: 방 전체 갱신** — 토글 시 새 페이로드 broadcast (`POST /meetings/{id}/recommendations/refresh` 신설, [`spec-common.md §9.2`](./spec-common.md)). **권한 (Q13=B)**: 발화자 + 방장만 호출 가능. **Rate limit (Q14=C)**: Redis idempotency 캐시(같은 source/scope 조합 hit) + 일일 100회 상한. **Narrator (Q15=A)**: 재발행 시 "OOO님 선호 기준으로 다시 추천했어요" 실명 명시 — PII 노출 트레이드오프 인지 필요. **Q7-c (`preference_toggle_enabled=false` 트리거 조건)**: C1(발화자 `share_*_data == False`) ∨ C3(그룹 다수결과 발화자 선호 결과 동일) ∨ C4(발화자 본인 정보 비어있음). 게스트(C2 후보)는 채팅방 입장 후 선호 설정 가능하므로 토글 허용.

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

#### 5.1.6 확정·부분 카드 발행 (시간 한정)

> 장소 결과 carry·`maedeup_card_payload` 발행은 [`spec-place-recommendation.md §5.1.6`](./spec-place-recommendation.md) 참조.

| 항목 | 의미 | 출처 | 사용처 | 예시 데이터 형태 | 마크 |
|---|---|---|---|---|:---:|
| `partial_mode` | 부분 카드 모드 (해결점 I·J·K) | `state.py:49`·`nodes/slot.py:254,280` | `maedeup.py:74` time-only 분기 | `"time_only"` | ✅ |
| `confirmed_date`/`confirmed_time` | manual host pick 시각 (HH:MM~HH:MM) | `nodes/slot.py:250~251` | `maedeup.py:79~90` explicit_start/end 파싱 | `"2026-05-15"` / `"19:00~21:00"` | ✅ |
| `selected_time` (payload key) | maedeup 카드 시간 필드 (※ state 키 아님 — 로컬 변수 → payload) | `maedeup.py:108~120, 163, 192` | 프론트 카드 표시 | `{"label":"2026-05-15 19:00~21:00","start_at":"...","end_at":"..."}` | ✅ |

> **시간 확정 후 번복 불가 (Q9=A)**: time_only maedeup 발행 후 사용자가 장소를 채워도 **시간은 잠김 (immutable)**. 시간 재선정은 명시적 재추천 요청(`POST /meetings/{id}/recommendations/refresh`, [`spec-common.md §9.2`](./spec-common.md))으로만 가능 — `partial_mode` 분기와 별개의 경로.

---

### 5.2 출력 (생성)

#### 5.2.1 카드 페이로드 (시간 한정)

| 카드 | set 노드 | 핵심 키 | 출처 |
|---|---|---|---|
| `vote_card_payload` | vote_card_creation | `type`/`title`/`room_id`/`meeting_id`/`time_options[]`/`headcount`/`blocker_notification`/`calendar_strategy` | §3 참조 (`nodes/vote_card.py:259~279`) |

> `place_recommendation_payload`·`maedeup_card_payload`는 [`spec-place-recommendation.md §5.2.1`](./spec-place-recommendation.md) 참조.

#### 5.2.2 DB 변경 (시간 한정)

**(a) 파이프라인 노드 직접 쓰기**
| 변경 | 노드 | 비고 |
|---|---|---|
| `MeetingSchedule` pending 생성 | vote_card_creation | `_ensure_pending_meeting_id` |
| `MeetingSchedule.vote_options` JSON 채움 | vote_card_creation | slot_id 배열 |

**(b) confirm 라우터 다운스트림 쓰기** (파이프라인 외부 — [`spec-common.md §9`](./spec-common.md))
| 변경 | 위치 |
|---|---|
| `MeetingSchedule.scheduled_at`/`end_at` 확정 | `routes/meetings.py:501` |
| `MeetingSchedule.google_event_ids` (JSON dict `user_id→event_id`) | `routes/meetings.py:501, 797, 915` |
| `MeetingParticipant` 일괄 추가 | `routes/meetings.py:345` |
| `Notification` 발행 | finalization_reason / meetings 라우터 |

#### 5.2.3 외부 효과 (시간 한정)
| 효과 | 위치 | 비고 |
|---|---|---|
| WebSocket publish queue (`new_assistant_messages` append) | `services/pipeline/helpers/messaging.py:155~157` (state 정의 `state.py:65`) | 카드·narrator 발행 queue. 실제 WS 송신은 graph 종료 후 호출자 (`ws/agent.py`) |

#### 5.2.4 narrator 메시지 (시간 한정)
- `vote_card`: "캘린더 확인 결과 ... 추천드려요" — §3.2 참조

---

### 5.3 P0 plumbing 요구 (시간 한정)

카탈로그 P0 6 항목 중 시간 spec에 영향을 주는 항목 — 전체 표는 [`spec-common.md §5`](./spec-common.md).

| # | 재료 | 현재 상태 | 작업 | 본 spec 영향 |
|---|---|---|---|---|
| 1 | `state["intent"]` 명시 세팅 | quick_classify가 `direct_request_kind`만 채우고 `state["intent"]`는 dead | agent.py에서 `kind` → `state["intent"]` 매핑 | direct_request 경로의 intent 분기(슬롯·카드 양쪽) 정상화 |
| 5 | `time_window` (ISO range) | `parsed_time_hint` 텍스트 그대로, 정규화 안 됨 | "내일 6시" → `{start: ISO, end: ISO}` | **Q1 결정 반영** — 단일 슬롯이어도 vote_card 발행 가능하게 |

**의존 관계**:
- P0-1 — 단순 plumbing, 결정 의존 없음
- P0-5 — **Q1 단일 슬롯 = vote_card** 반영

---

## 6. 상태 및 예외 처리 (시간 한정)

본 절은 §1~§5에서 정의된 정상 경로 밖에서 발생하는 모든 분기 — 노드 예외, 사용자 응답 대기, 부분 정보 acknowledgment, fallback narrator, 동시성, v2 backlog로 미뤄둔 갭 — 을 한 곳에 모아 정의한다. **운영 중 한 번이라도 관찰될 수 있는 상태는 모두 본 절에 명세된다**.

> 장소 한정 상태 §6.14~§6.18은 [`spec-place-recommendation.md §6`](./spec-place-recommendation.md) 참조.

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
- **적용 노드 (본 spec 범위)**: `slot_filling` (`slot.py:70`), `entity_extraction` (`entity.py:574`), `supervisor_validation` (`validation.py:121`).
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

- **시간 immutable**: `selected_time`은 partial 카드([`spec-place-recommendation.md §3.3`](./spec-place-recommendation.md)) 발행 시점에 잠긴다. 후속 장소 발화가 들어와도 새 vote_card 발행 X.
- **장소 갱신**: 같은 `meeting_id`의 partial 카드를 update (해결점 J, `maedeup.py:150~166`). 별도 vote_card 미발행.
- **명시적 시간 재선정**: `POST /meetings/{id}/recommendations/refresh` ([`spec-common.md §9.2`](./spec-common.md), 권한 Q13=B 발화자+방장만, rate limit Q14=C Redis idempotency + 일일 100회) 호출 시에만.
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
> - C2(게스트)는 채팅방 입장 후 선호 설정 가능하므로 토글 허용 ([`spec-common.md §7.6`](./spec-common.md) 참조).

---

## 10. 회귀 테스트 케이스 (시간 한정)

[`spec-common.md §10`](./spec-common.md) — wait, common에는 회귀 절이 없습니다. 본 절은 시간 시나리오 한정. 공통 전략·fixture·negative test 등은 본 §10에 둔다 (양쪽 spec이 인용).

### 10.1 테스트 전략 개요

- **골든 회귀**: §2의 시나리오 S1~S10 (10개) + [`spec-place-recommendation.md §2`](./spec-place-recommendation.md) S11~S14·S16~S20 (9개) + [`spec-common.md §2`](./spec-common.md) S15 (refresh) → 1 시나리오 = 1 pytest 모듈 또는 ≥1 함수.
- **단위 vs 통합**:
  - **단위**: 노드 단위 헬퍼·함수 (`nodes/entity.py`, `nodes/slot.py`, `nodes/vote_card.py`, `nodes/place.py`, `nodes/maedeup.py`, `helpers/slots.py`)를 직접 호출 — 외부 의존 monkeypatch (`backend/tests/unit/`).
  - **통합**: `run_pipeline()` 전체 흐름 + WebSocket publish 검증 — Google Calendar·Kakao·DB pending meeting은 monkeypatch로 격리 (`backend/tests/integration/`).
- **추가 영역**:
  - [`spec-common.md §9.2`](./spec-common.md) 신규 라우트 `POST /meetings/{id}/recommendations/refresh` (Q7-b·Q13=B·Q14=C·Q7-c) → S15 신규 시나리오.
  - [`spec-common.md §9.6`](./spec-common.md) 에러 응답 코드 negative test (401·403·404·409·422·429).
- **Async**: `pytest-asyncio` (기존 `conftest.py:42` `db_session` 패턴 일관).

### 10.2 Fixture 패턴

기존 `backend/tests/conftest.py` 의 fixture를 그대로 활용:

- `event_loop` (session scope, `conftest.py:19~23`)
- `db_engine` / `db_session` — sqlite+aiosqlite in-memory + SQLModel create_all (`conftest.py:26~46`)
- `fake_redis` — `fakeredis.aioredis.FakeRedis` (`conftest.py:49~56`)

신규 권고 fixture (`conftest.py` 또는 모듈별 fixture 파일에 추가):

| 이름 | 목적 | 사용 시나리오 |
|---|---|---|
| `room_with_n_members(n)` | n명 멤버 방 + RoomMembership seed | S1·S2·S3·S4 |
| `room_with_guest` | 게스트 1명(`is_guest=True`) 포함 방 — Q12=A 검증 | S15.5 (C2 제외 토글), [`spec-common.md §7.7`](./spec-common.md) |
| `busy_by_user_full_conflict` | 전원 가능 슬롯 0개 (F1 fallback trigger용) | S8 |
| `meeting_with_partial_card` | `partial_mode="time_only"` `MeetingSchedule` 사전 발행 | S9, Q9 (번복 불가) |
| `mock_gemini` | Gemini API stub (rate-limit 시 패턴 fallback 분기 검증) | S5·S11·S13 |
| `mock_kakao` | Kakao Local 검색 결과 stub | S11·S12·S13·S14 |
| `mock_google_calendar` | free/busy + Calendar create/delete stub | S1~S8·F4 만료 |

### 10.3 골든 시나리오 pytest 매핑 (S1~S10, 시간 한정)

| S# | 시나리오 (§2 인용) | pytest 파일·함수 | 핵심 assertion |
|---|---|---|---|
| S1 | 기본 케이스 "다음주에 모이자" (`direct_request`) | `integration/test_vote_card_basic.py::test_default_weekday_evening` | `payload["type"]=="vote_card"`, `3 <= len(time_options) <= 5`, `calendar_strategy=="natural_language_time_options"` |
| S2 | 거부 누적 "월요일은 안돼" | `unit/test_rejected_dates.py::test_monday_excluded` | `state["rejected_dates"]`에 "월요일" 포함, 후속 vote_card `time_options`에 월요일 슬롯 0 |
| S3 | 선호 매칭 (방 설정: 평일 오전) | `integration/test_preference_matching.py::test_weekday_morning_only` | `calendar_strategy=="preference_based"`, 모든 슬롯이 평일·09~12 KST |
| S4 | 다음주 자동 확장 (해결점 N) | `integration/test_expanded_next_week.py::test_auto_expand` | `expanded_to_next_week is True`, narrator 메시지에 "다음주" 단어 포함 |
| S5 | 명시 단일 시간 "내일 6시 어때" (Q1=B) | `integration/test_single_slot.py::test_single_time_vote_card` | `len(time_options)==1`, vote_card skip 안 함 (Q1=B 단일도 발행) |
| S6 | TimeBar 전원 선택 완료 | `integration/test_all_members_selected.py::test_trigger` | `trigger_reason=="all_members_selected"`, slot_filling 노드 진입 로그 |
| S7 | conflict_options "A는 토요일·B는 일요일" | `unit/test_conflict_options.py::test_a_vs_b_date` | `conflict_options==["토요일","일요일"]`, `calendar_strategy=="multi_date_vote"` |
| S8 | F1 fallback (Q6=A·Q8=A) | `unit/test_majority_fallback.py` + `integration/test_f1_fallback_pipeline.py` (PR-Y1 기존) | `calendar_strategy=="majority_fallback"`, 슬롯 3개, `available_count desc` 정렬, `blocker_notification_payload` 발행 |
| S9 | time_only partial maedeup | `integration/test_partial_maedeup.py::test_time_only_skip_vote` | `partial_mode=="time_only"`, vote_card 우회, maedeup_card payload 직행 |
| S10 | conclusion 자동 감지 | `integration/test_conclusion.py::test_auto_detect` | `trigger_reason=="conclusion_detected"`, vote_card skip, maedeup 발행 |

> 장소 시나리오 S11~S20 매핑은 [`spec-place-recommendation.md §10`](./spec-place-recommendation.md), refresh S15 세부는 §10.4 참조.

### 10.4 추가 시나리오 (refresh·negative test)

**S15 세부 — refresh 토글 (PR-3.4 [`spec-common.md §9.2`](./spec-common.md), Q7-b·Q13=B·Q14=C·Q7-c)**:

| 케이스 | pytest 파일·함수 | 핵심 assertion |
|---|---|---|
| S15.1 | `integration/test_refresh_toggle.py::test_speaker_broadcast` | 발화자가 토글 → 방 전체 broadcast (Q7-b), `preference_source=="speaker"` |
| S15.2 | `integration/test_refresh_toggle.py::test_non_speaker_403` | 비발화자·비방장 호출 → HTTP 403 (Q13=B) |
| S15.3 | `integration/test_refresh_toggle.py::test_idempotency_cache_hit` | 같은 source/scope 연속 호출 → Redis 캐시 hit, 재발행 1회 (Q14=C) |
| S15.4 | `integration/test_refresh_toggle.py::test_daily_limit_429` | 일일 100회 초과 → HTTP 429 (Q14=C) |
| S15.5 | `integration/test_refresh_toggle.py::test_q7c_blocked_422` | Q7-c C1·C3·C4 위배 (`share_*_data=False`·결과 동일·발화자 정보 부재) → HTTP 422 |

**Negative test ([`spec-common.md §9.6`](./spec-common.md) 에러 코드 + 시간 fallback 검증)**:

| 케이스 | 라우터·노드 | 기대 응답·동작 |
|---|---|---|
| 비멤버 호출 | 모든 `/rooms/{id}/*` | 403 ([`spec-common.md §7.3`](./spec-common.md) 멤버십 검증) |
| JWT 부재 | 모든 보호 라우터 | 401 |
| 존재하지 않는 `meeting_id` | `/meetings/{id}/*` | 404 |
| 이미 finalized된 모임 confirm 재시도 | `/meetings/{id}/confirm` | 409 SUPERSEDED ([`spec-common.md §9.6`](./spec-common.md)) |
| 요청 body 검증 실패 | 모든 POST | 422 |

> 장소 negative test (F7 Kakao 5xx, F9 ML disabled, F6 cuisine None)는 [`spec-place-recommendation.md §10.4`](./spec-place-recommendation.md) 참조.

### 10.5 로그·메트릭 assert

- `[TIMING] {node}: {duration}s` 로그 형식 ([`spec-common.md §9.4`](./spec-common.md)) — caplog 으로 노드별 latency 라인 1회 이상 발견.
- F1·F2·F3·F4 fallback 발동 카운트 — 각 분기 진입 시 구조화 로그 키 (`calendar_strategy`, `fallback_reason`) 존재 검증.
- 해결점 N (`expanded_to_next_week`) / O (정규식 단축 사각지대) / P (번복·게스트 정책) 발동 로그 — 진입 시 식별자 키 발견 검증 (P·O는 v2, §10.8 참조).

### 10.6 동시성 테스트 (§6.6 race condition)

- 같은 슬롯에 2명 사용자 동시 투표 (`asyncio.gather`) — `Vote` 테이블 UNIQUE 제약 + 멱등성 검증.
- partial maedeup(`time_only`) 발행 직후 동시 confirm 시도 → 1건만 성공·나머지 409 (Q9=A 번복 불가).
- refresh 라우트 동시 호출 (같은 source·scope) → 1건만 실제 재발행 (Q14=C 캐시 hit).
- 도구 권고: `pytest-asyncio` + `asyncio.gather` (외부 라이브러리 추가 불필요, 기존 stack 재사용).

### 10.7 회귀 우선순위 (시연 직전 필수 케이스)

| 우선순위 | 목적 | 케이스 |
|---|---|---|
| **P0** (시연 영향 큼) | 핵심 흐름 — 골든 데모 | S1, S2, S4, S8, S11, S12, S15.1, S15.2 |
| **P1** (시연 통과 권고) | 분기·partial·도메인 | S3, S5, S7, S9, S13, S14, S17 (F7 Kakao 0건), S19 (speaker 토글 차이) |
| **P2** (운영 단계) | edge·내부·동시성 | S6, S10, S15.3, S15.4, S15.5, §10.6 동시성, §10.4 negative test, F7·F9 fallback 검증 |
| **v1.5 후보** | 후속 정교화 | S16 (rejected_places 누적), S18 (cuisine 다중), S20 (Q4 점수 공식) |

### 10.8 미구현 / v2 backlog

- 신규 fixture (`room_with_guest`, `busy_by_user_full_conflict`, `meeting_with_partial_card`) — 코드 미존재, S15.5·S8·S9 작성 시 함께 도입.
- §6.11·§6.12 해결점 P (번복 처리·게스트 정책 정교화) 회귀 테스트 — v2 spec과 함께.
- 해결점 O (정규식 단축 사각지대) 회귀 — v2.
- 부하 테스트 (rate limit 일일 100회·broadcast 다중 사용자 fan-out) — v2 (외부 도구 locust 등 도입 검토).
- Q17 F4 narrator 실명/익명 결정 후 회귀 케이스 추가 — 권고 A 적용 가정 (Q15=A 일관, [`spec-common.md §9.7`](./spec-common.md) 반영).

> 장소 v1.5 backlog (S16·S18·S20·F7·F8)는 [`spec-place-recommendation.md §10.8`](./spec-place-recommendation.md) 참조.
