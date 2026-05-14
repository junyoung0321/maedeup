# 기능정의서 — 장소 추천 (Place Recommendation)

작성: 2026-05-14
작성자: 본인 (장소/시간 조율 담당)
대상 노드: `place_recommendation` (노드 6b) + `maedeup_card_creation` (노드 7)
관련 문서:
- [spec-common.md](./spec-common.md) — 공통 정책·권한·API·비기능 (단일 SoT)
- [spec-time-coordination.md](./spec-time-coordination.md) — 시간 조율 (자매 spec)
- [recommend-input-catalog.md](./2026-05-13-recommend-input-catalog.md) — 활용 가능 인풋 카탈로그
- [pipeline-structure.html](./pipeline-structure.html) — 파이프라인 구조

> **목적**: 채팅방에서 모임 **장소**를 합의하는 과정을 자동화한다. 사용자 발화·`place_hint`·그룹/발화자 선호를 통합하여 후보 장소를 Kakao Local API로 검색하고 ML/Gemini reranking으로 정렬해 추천 카드(`place_recommendation`)로 제시하며, 시간·장소 합의 결과를 매듭 카드(`maedeup_card`)로 마무리한다.

> **권한·데이터 정책·API·비기능 요건**은 [`spec-common.md`](./spec-common.md) §7~§13 참조.

---

## 1. 기능 개요

### 1.1 핵심 가치 (한 문장)
**채팅으로 흩어진 장소 의사를 자동으로 모아 "그룹·발화자 선호를 반영한 후보 장소"로 변환하고, 합의 결과를 매듭 카드로 마무리한다.**

### 1.2 시스템 위치
- **slot_filling (노드 3)**: 사용자 발화·선호도를 읽어 `place_hint` 슬롯 채우기 ([공통 진입은 `spec-common.md §4`](./spec-common.md) 참조)
- **place_recommendation (노드 6b)**: `place_hint`·`home_base`·그룹/발화자 선호로 Kakao 검색 + ML/Gemini reranking → 장소 추천 카드 페이로드
- **maedeup_card_creation (노드 7)**: 시간·장소 확정 시 매듭 카드(확정), 시간만 결정된 경우 partial(time_only) 카드 발행

이 spec은 **입력 발화부터 `place_recommendation` / `maedeup_card` payload 발행까지** 장소 경로를 다룬다.

### 1.3 책임 경계
- ✅ 이 spec이 정의함
  - 어떤 발화가 장소 조율 흐름을 트리거하는가
  - 장소 후보를 어떻게 추출·검색·재정렬하는가 (`place_hint`·`home_base` fallback, ML/Gemini reranking, 비선호 페널티)
  - 어떤 형태의 카드 페이로드(`place_recommendation` / `maedeup_card` 확정·partial)를 출력하는가
  - 발화자 vs 그룹 선호 토글 메타(Q7=B) 정책 (`preference_source`·`preference_toggle_enabled`)
- ❌ 이 spec이 정의하지 않음
  - 시간 슬롯 생성·캘린더 통합 → [`spec-time-coordination.md`](./spec-time-coordination.md)
  - 권한·접근 조건 → [`spec-common.md §7`](./spec-common.md)
  - 데이터·PII·동의 정책 → [`spec-common.md §8`](./spec-common.md)
  - API·이벤트·로그 → [`spec-common.md §9`](./spec-common.md)
  - intent 분류 자체 (동료 영역, `intent_detection`)
  - 검증/판단 supervisor (동료 영역, `supervisor_validation`)
  - Kakao Local API / ML ranker 내부 구현 (외부 서비스)

---

## 2. 사용자 시나리오 (= 골든 회귀 케이스)

각 시나리오는 "발화/이벤트 → 기대 출력"으로 정의. **이 표가 §10 회귀 테스트의 일대일 원본이 된다.**

> **시간 시나리오 (S1~S10)** 는 [`spec-time-coordination.md §2`](./spec-time-coordination.md), **공통 시나리오 (S15 refresh)** 는 [`spec-common.md §2`](./spec-common.md) 참조.

| ID | 발화 / 이벤트 | trigger_reason | 기대 출력 | 검증 포인트 |
|---|---|---|---|---|
| **S11. place_hint 명시** | "강남에서 모이자" | `direct_request` | 강남 좌표 기반 place_recommendation_payload (≤5 후보) | `place_hint="강남"`, `place_coord` 변환, `preference_source` 표기 (Q7=B) |
| **S12. place_hint 미지정 fallback** | "다음주에 모이자" (place_hint 없음) | `direct_request` | 선호 장소 다수결 → 동률 시 발화자 → 선호 없으면 방장 home_base 기준 추천 | F5 fallback 순서 (Q2), `preference_source="group"` 기본, 발화자 토글 시 `"speaker"` |
| **S13. cuisine 자동 감지** | "한식 먹자" | `direct_request` | 한식 카테고리 Kakao 검색 + reranking | `_detect_cuisine_type` → `meeting_type="한식"`, place_recommendation_payload |
| **S14. 그룹 비선호 음식 페널티** | (방 멤버 중 1명 disliked_food="갑각류") "맛집 추천해줘" | `direct_request` | 갑각류 키워드 포함 후보 score 0.1 강등 | `_contains_disliked_keyword` 패널티 (P4), 익명 합산 prompt |
| **S16. 장소 거부 누적·재추천** | (강남 후보 카드 발행 후) "강남 말고 다른 데로" | `direct_request` (재추천) | 강남 제외된 `place_recommendation_payload` | "말고" 뒤 키워드 추출하여 새 `place_hint`로 재검색 — `rejected_places` state 키 누적 정책은 **v1.5 후보 (코드 미존재, §6.16 v1.5 backlog)**, 현재는 새 발화 시 place_hint 덮어쓰기만 작동 |
| **S17. Kakao 검색 결과 0건 fallback** | "북극해에서 모이자" (Kakao 미등록 지명) | `direct_request` | narrator "해당 지역에서 추천 결과를 찾지 못했어요. 다른 지역을 알려주실래요?" + `place_recommendation_payload` 미발행 (또는 빈 `recommendations`) | `place_search_results == []` 분기 (`nodes/function_call.py:55, 72`), narrator 발행 — F7 fallback (§4.4) |
| **S18. cuisine 다중 충돌** | "한식 먹을까 일식 먹을까" | `direct_request` | cuisine ambiguity 감지 → narrator "한식과 일식 중 어느 쪽이 좋으세요?" 또는 두 카테고리 모두 후보로 reranking (정책 미확정) | `_detect_cuisine_type` 결과 2건 이상일 때 conflict_options 활용 또는 신규 분기 — **v1.5 후보 (현재 코드는 첫 매칭 cuisine만 반환, `helpers/places.py:128~135`)** |
| **S19. 발화자 토글 후 speaker 차이** | (그룹 다수결로 "강남 한식" 카드 발행 후) 김민수가 "내 취향으로 보기" 클릭, 김민수 프로필 `liked_areas=["홍대"]`·`food_preferences=["양식"]` | `preference_toggle` | 홍대 양식 후보로 reranking된 `place_recommendation_payload` (그룹 카드와 다른 결과) | `requester_preferences` 적용, Q5 hybrid 시각화 (PR-Z1 P0-4 plumbing), `preference_source="speaker"` 명시 |
| **S20. 거리 vs ML 점수 트레이드오프** | (place_coord = 강남 기준) "한식 추천" | `direct_request` | ML 1위(10km 강북·distance_score 0.2 + ML 0.95) vs 후순위(1km 강남·distance_score 0.8 + ML 0.7) — **종합 score 높은 쪽 우선** | Q4 가중치 공식 (점수 통합) — 현재 ML reranking + Gemini scoring + 거리 점수 혼합, **정확 공식 미정 → v1.5 또는 v2 후보** |

### 2.1 비목표 시나리오 (Out of scope, [`spec-common.md §11`](./spec-common.md))
- "오프라인 장소 import" (사용자가 따로 즐겨찾는 장소 등록) — Kakao Local API로 한정
- "예약 가능 여부 자동 확인" (예약 시스템 연동) — MVP 외

---

## 3. 출력 카드 페이로드 형식

본 spec은 3종 카드 페이로드를 발행한다: `place_recommendation` (§3.1), `maedeup_card` 확정 (§3.2), `maedeup_card` partial/time_only (§3.3). 카드별 narrator는 §3.4에 통합.

> **vote_card_payload (시간 투표)** 는 [`spec-time-coordination.md §3.1`](./spec-time-coordination.md) 참조.

### 3.1 place_recommendation_payload (장소 추천)

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

### 3.2 maedeup_card_payload (확정)

실제 출력 JSON 스키마 (코드: `nodes/maedeup.py:182~197`). 시간+장소 결과 carry.

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

### 3.3 maedeup_card_payload (partial, time_only)

실제 출력 JSON 스키마 (코드: `nodes/maedeup.py:150~166`, 해결점 I·J·K). 시간만 확정되고 장소 pending인 partial 카드.

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

> **시간 번복 불가 (Q9=A)**: partial 카드 발행 후 장소가 채워져도 `selected_time`은 잠긴다. 시간 재선정은 `POST /meetings/{id}/recommendations/refresh` ([`spec-common.md §9.2`](./spec-common.md)) 명시 호출만 가능.

### 3.4 narrator 메시지 (장소·매듭 카드)

페이로드와 함께 발행되는 narrator 메시지.

- **place_recommendation**: `"강남 근처 5곳을 찾아봤어요"` (`nodes/place.py:346~`)
- **maedeup_card (확정)**: `"확정됐어요!"`
- **maedeup_card (partial, time_only)**: `"장소는 멤버들이 정하면 자동으로 정리해드릴게요!"` (`place_pending_message`)
- **refresh 토글 (Q15=A)**: [`spec-common.md §3.1`](./spec-common.md) 참조.

---

## 4. 기능 상세 (Functional Detail Matrix)

> 본 절은 장소 관련 R/P/T/F 항목만 정의. 시간 관련 R1~R6·P1~P3·T1~T5·F1~F4는 [`spec-time-coordination.md §4`](./spec-time-coordination.md) 참조.

### 4.1 입력 인식 (Input Recognition)
| ID | 기능 | 트리거 | 처리 노드 | 데이터 출처 |
|---|---|---|---|---|
| R7 | `place_hint` 추출 | "강남", "홍대", "강남역" | entity_extraction | Gemini + 패턴 — `nodes/entity.py:66, 256, 366~547` |
| R8 | `place_coord` 변환 | place_hint → 좌표 | entity_extraction (`_resolve_place_coord`) | Kakao geocode — `nodes/entity.py:340~342, 560~562` |
| R9 | `cuisine` 추출 | "한식", "맛집", "양식" | entity_extraction / place_node | `helpers/places._detect_cuisine_type`, place 노드 카테고리 매핑 |

### 4.2 선호 매칭 (Preference Matching)
| ID | 기능 | 데이터 출처 | 처리 위치 |
|---|---|---|---|
| P4 | 음식 비선호 합집합 | `User.food_restrictions`/`food_preferences` (방 멤버) | `_get_room_member_food_preferences` → place prompt 익명 합산 + `_contains_disliked_keyword` 0.1 페널티 |
| P5 | 개인 지역 선호 | `User.liked_areas`/`disliked_areas` | `preferences.py:382~419` → place 노드 prompt (`place.py:244~251`) 익명 합산 |
| P6 | 이동수단 가중치 | `User.transport_mode` ("대중교통"/"도보"/"자차") | place 노드 prompt (`place.py:254~257`) — 역세권/도보 거리 가중치 힌트 |

### 4.3 탐색 정책 (Search Policy)
| ID | 기능 | 트리거 | 처리 |
|---|---|---|---|
| T6 | Kakao 장소 검색 | place_hint·place_coord 확정 | `search_place` (Kakao Local Keyword API) → 후보 장소 목록 |
| T7 | ML 점수화 | `_ML_AVAILABLE` 시 | `_ml_place_search` (LGBMRanker) — top 5 ranking, `nodes/place.py:64~67, 168~181` |
| T8 | Gemini reranking | 항상 (top candidates 진입 시) | `nodes/place.py:269~283` 점수화 + 비선호 페널티 → 최종 `reranked` 정렬 (score desc) |

### 4.4 Fallback 정책 (Fallback Policy)
| ID | 기능 | 트리거 | 출력 |
|---|---|---|---|
| F5 | place_hint 미지정 fallback | 발화에 place_hint 없음 | **Q2 결정 순서**: ① 멤버 선호 장소 다수결(`pref_data["best_location"]`) → ② 동률 시 발화자 개인 선호 → ③ 선호 정보 없으면 방장(creator) `home_base` |
| F6 | cuisine 미감지 | `_detect_cuisine_type` 결과 없음 | `meeting_type` fallback (e.g. "저녁모임"→"음식점") 또는 일반 카테고리("맛집") — 카테고리 미특정 시 Kakao 일반 검색 |
| F7 | Kakao API 실패 / 결과 0건 | Kakao 응답 5xx·timeout (`kakao_maps.py:74~75` `except Exception: return []`) 또는 정상 응답이지만 빈 documents | narrator "장소 검색 서비스가 일시 불가합니다. 잠시 후 다시 시도해주세요." (장애) / "해당 지역에서 추천 결과를 찾지 못했어요. 다른 지역을 알려주실래요?" (0건) + `place_recommendation_payload` 미발행 (또는 빈 `recommendations`). 코드 분기: `nodes/function_call.py:55, 72` `place_search_results=[]`, `nodes/place.py:149` |
| F8 | 거리·ML·Gemini 점수 동률 | top-K 후보 종합 score 동률 (`reranked.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)`, `nodes/place.py:211`) | 안정적 정렬 (Python `sort` stable) — 입력 순서(Kakao relevance/distance) 유지가 사실상 tiebreaker. **명시적 tiebreaker(거리 가까운 순 → place_id 사전순) 도입은 v1.5 후보** (현재 암묵적 의존). |
| F9 | ML 모델 비활성 (`_ML_AVAILABLE=False`) | `from app.services.ml_recommend import ml_place_search` ImportError 또는 LGBMRanker 로드 실패 (`nodes/place.py:66~71`) | Gemini scoring + 거리 점수만으로 reranking 진행 (`nodes/place.py:187~283` Gemini 분기), narrator 변경 없음 — silent degradation. 로깅: `[ML] ml_place_search 실패, Gemini fallback` 또는 import 시 단발성 로그. |

---

## 5. 입력값 / 출력값

본 spec 노드(`place_recommendation` · `maedeup_card_creation`)가 **소비**·**생성**하는 데이터를 정리한다. 전체 카탈로그(약 40개, 6 카테고리)는 [`2026-05-13-recommend-input-catalog.md`](./2026-05-13-recommend-input-catalog.md) 참조 — 본 절은 그중 본 spec이 실제로 읽거나 쓰는 항목만 추려 file:line을 표기한다.

마크: ✅ 활용 중 / ⚠️ state에 있으나 미활용 / 🔧 plumbing 필요 (§5.3에서 P0로 별도 다룸)

### 5.1 입력 (소비) — 기능별 데이터 카탈로그

장소 관련 항목만 정리. 시간 관련 항목 5.1.1~5.1.3·5.1.5는 [`spec-time-coordination.md §5.1`](./spec-time-coordination.md), 공통 진입·상태 5.1.7은 [`spec-common.md §4`](./spec-common.md) 참조.

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

#### 5.1.6 확정·부분 카드 발행 (장소·매듭 한정)

> 시간 관련 항목(`partial_mode`·`confirmed_date`·`selected_time`)은 [`spec-time-coordination.md §5.1.6`](./spec-time-coordination.md) 참조. 본 표는 장소·maedeup carry 한정.

| 항목 | 의미 | 출처 | 사용처 | 예시 데이터 형태 | 마크 |
|---|---|---|---|---|:---:|
| `confirmed_place` | 확정 장소명 | `state.py:75`·`maedeup.py:171~180` | maedeup `selected_place.name` | `"홍대 OO식당"` | ✅ |
| `place_pending_message` | 부분 카드 안내 문구 | `maedeup.py:157` | 카드 UI | `"멤버들이 장소를 정하면 자동으로 정리해드릴게요!"` | ✅ |
| `vote_card_payload`/`place_recommendation_payload` carry | 상위 카드 meeting_id 재사용 | `maedeup.py:64~66, 194~195` | `_card_payload_meeting_id` lookup | dict carry | ✅ |
| `maedeup_card_payload` | 최종 매듭 카드 페이로드 | `maedeup.py:150~196` | publish | `{"type":"maedeup_card","meeting_id":42,"date":"...","time":"...","place":null,"place_pending":true,...}` | ✅ |
| `calendar_registration` | GCal 등록 결과 (현재 placeholder) | `maedeup.py:43~50, 181` | 카드 `calendar_registered` 필드 | `{"provider":"google_calendar","status":"placeholder"}` | ⚠️ |

> `calendar_registration` ⚠️ 사유: 노드는 `status="skipped"` placeholder만 반환. 실제 등록은 `routes/meetings.py` confirm 라우터.

---

### 5.2 출력 (생성)

#### 5.2.1 카드 페이로드 (장소·매듭)

| 카드 | set 노드 | 핵심 키 | 출처 |
|---|---|---|---|
| `place_recommendation_payload` | place_recommendation | `type`/`room_id`/`meeting_id`/`place_hint`/`recommendations[≤5]`/`group_constraints_summary` | `nodes/place.py:320~329` |
| `maedeup_card_payload` (확정) | maedeup_card_creation | `type`/`room_id`/`meeting_id`/`title`/`intent`/`date_hint`/`place_hint`/`headcount`/`meeting_type`/`selected_time`/`selected_place`/`vote_card`/`place_recommendation`/`calendar_registration` | `nodes/maedeup.py:182~197` |
| `maedeup_card_payload` (partial, time_only) | maedeup_card_creation | `type`/`meeting_id`/`date`/`time`/`place=null`/`place_pending=true`/`place_pending_message`/`headcount`/`calendar_registered=false`/`title`/`meeting_type`/`date_hint`/`selected_time`/`selected_place={}` | `nodes/maedeup.py:150~166` (해결점 I·J·K) |

> `vote_card_payload`는 [`spec-time-coordination.md §5.2.1`](./spec-time-coordination.md) 참조.

#### 5.2.2 DB 변경 (장소·매듭 한정)

**(a) 파이프라인 노드 직접 쓰기**
| 변경 | 노드 | 비고 |
|---|---|---|
| `MeetingSchedule.scheduled_at` partial 동기화 | maedeup_card_creation | `nodes/maedeup.py:125~143` (time_only 분기만) |

**(b) confirm 라우터 다운스트림 쓰기** (파이프라인 외부 — [`spec-common.md §9`](./spec-common.md))
| 변경 | 위치 |
|---|---|
| `MeetingSchedule.kakao_place_id`/`kakao_place_url` | `routes/meetings.py:748~749, 774~775` |
| `MeetingSchedule.google_event_ids` (JSON dict `user_id→event_id`) | `routes/meetings.py:501, 797, 915` |

#### 5.2.3 외부 효과
| 효과 | 위치 | 비고 |
|---|---|---|
| Redis 캐시 (`room_place_rec:{room_id}`) | `nodes/place.py:332~344` | 24h TTL, 새로고침 복구용 |
| Memory extraction (fire-and-forget) | 정의 `nodes/memory.py:88`, 호출 `nodes/maedeup.py:169` `_spawn_memory_extraction_async` | graph latency에서 분리 (추정: 코드 주석 `memory.py:91-92` 기반, 실측 미검증) |
| Google Calendar 이벤트 생성 | `nodes/maedeup.py:43~50` `_register_google_calendar` (현재 placeholder만 반환), 실제 등록은 `routes/meetings.py` confirm 라우터 | ❌ 노드 자체는 `status="skipped", reason="pending_confirmation"` placeholder |

#### 5.2.4 narrator 메시지
- `place_recommendation`: "OOO 근처 5곳을 찾아봤어요" — `nodes/place.py:346~`
- `maedeup_card` (확정): "확정됐어요!"
- `maedeup_card` (partial): "장소는 멤버들이 정하면 자동으로 정리해드릴게요!" — `place_pending_message`

---

### 5.3 P0 plumbing 요구 (장소 한정)

카탈로그 P0 6 항목 중 장소 spec에 영향을 주는 항목 — 전체 표는 [`spec-common.md §5`](./spec-common.md).

| # | 재료 | 현재 상태 | 작업 | 본 spec 영향 |
|---|---|---|---|---|
| 2 | `requester_user_id` 노출 | `viewer_user_id`는 state에 있으나 추천 노드에서 미사용 | 추천 노드에서 명시적으로 lookup | 발화자 본인 정보 활용 가능 |
| 3 | `requester_home_base` | `User.home_base` 컬럼 있음, state까지 안 옴 | viewer_user_id → `User.home_base` lookup → state | `place_hint` 없을 때 fallback — **Q2 결정: 선호 장소 다수결 → 동률 시 발화자 → 선호 없으면 방장 위치** (F5) |
| 4 | `requester_preferences` 묶음 | `User.food_*`/`*_areas`/`transport_mode` 미전달 | dict 묶음 state | 발화자 vs 그룹 충돌 시 가중치 — **Q5=hybrid** 정책 반영 |
| 6 | `cuisine` state 명시 | place_recommendation 내부에서만 감지 (`_detect_cuisine_type`) | 결과를 state로 끌어올림 | vote_card도 음식점-친화 시간 추천 가능 |

**의존 관계**:
- P0-2·6 — 단순 plumbing, 결정 의존 없음
- P0-3 — **Q2** (place_hint fallback 순서) 결정 필요
- P0-4 — **Q5 hybrid 정책** 반영 (UI 토글 메타 §3·[`spec-common.md §9`](./spec-common.md)에 명세)

---

## 6. 상태 및 예외 처리 (장소 한정)

> 공통 상태 머신 개요·노드 예외 처리·fallback narrator F1~F4·동시성·토큰 만료·번복(P)·정규식(O) 등은 [`spec-time-coordination.md §6.1~§6.13`](./spec-time-coordination.md) 참조. 본 절은 장소 한정 §6.14~§6.18.

### 6.14 Kakao API 실패 처리 (F7 본문)

Kakao Local Keyword API 호출이 5xx·timeout 또는 네트워크 예외로 실패한 경우.

```python
# backend/app/services/kakao_maps.py:66~80 (search_keyword)
try:
    async with httpx.AsyncClient() as client:
        resp = await client.get(KAKAO_KEYWORD_URL, params=params,
                                 headers={"Authorization": f"KakaoAK {api_key}"},
                                 timeout=5.0)
except Exception:
    return []                       # ← 모든 네트워크 예외 silent → []
if resp.status_code != 200:
    return []                       # ← 5xx·4xx도 동일 처리
return list(resp.json().get("documents", []))
```

- **현재 동작**: 모든 실패 경로가 빈 리스트로 수렴 → 호출자(`search_place`)는 `place_search_results=[]`로 진입 → `nodes/place.py:149~150` `place_results=[]`·`ranked_places=[]` → `state["place_recommendation_payload"]`는 빈 `recommendations` 발행. narrator는 §6.15 0건 흐름과 합쳐진다.
- **장애 vs 0건 미구분**: 현재 코드는 timeout/5xx와 정상 응답 0건을 구분하지 못함. 사용자에게는 동일 메시지로 노출. **v1.5 후보**: 예외 분기 시 `state["kakao_api_failed"]=True` 플래그 set + 전용 narrator ("장소 검색 서비스 일시 불가, 잠시 후 다시 시도해주세요").
- **재시도 정책**: 현재 미구현 (httpx 5s timeout 1회). 권장: exponential backoff(0.5s, 1s, 2s) 회당 1회 재시도, 최종 실패 시 narrator. **v1.5 backlog**.
- **다운스트림**: `_handle_node_exception` 진입 안 함 (예외는 kakao_maps 내부에서 흡수). 따라서 `status="<node>_error"` 미설정, vote_card 흐름은 영향 없음. 사용자 인지는 narrator 1회만.

### 6.15 place_search_results 0건 처리 (F7 분기)

Kakao API 정상 응답이나 documents 빈 리스트인 경우 (미등록 지명·오타·radius 외).

- **분기 조건**: `search_place` 정상 호출 후 `documents == []` → `place_search_results == []` (`nodes/function_call.py:55, 72, 98, 120, 215`).
- **현재 동작**: `nodes/place.py:149~150` `place_results=[]` 진입 → ranking 분기 (line 172~283) 모두 빈 리스트 통과 → `ranked_places=[]` → `state["place_recommendation_payload"]`의 `recommendations=[]` 발행.
- **narrator**: 카운트 0이면 `"추천 장소를 정리해봤어요. 📍 아래 카드를 확인해 주세요."` (`nodes/place.py:357~361`) — **사용자 친화도 낮음** (실제론 결과 0건). **v1.5 후보**: 명시 narrator "해당 지역에서 추천 결과를 찾지 못했어요. 다른 지역을 알려주실래요?" 분기, 빈 카드 미발행.
- **state 키 신설 권고 (v1.5)**: `place_search_empty: bool` — 0건과 정상 비교 가능. 또는 `state["place_search_results"]`가 `None` vs `[]`로 의도 구분.
- **이력**: place_hint 인식 실패 케이스(예: "북극해")도 동일 분기로 수렴 (지오코딩은 `_resolve_place_coord`에서 별도 처리, `helpers/places.py:168~176`).

### 6.16 cuisine 자동 감지 실패

`_detect_cuisine_type` 반환값 None 케이스 (F6 본문).

```python
# backend/app/services/pipeline/helpers/places.py:128~135
def _detect_cuisine_type(text: str) -> str | None:
    if not text:
        return None
    for trigger, cuisine in _CUISINE_TRIGGERS.items():
        if trigger in text:
            return cuisine
    return None
```

- **현재 동작**: cuisine None → `meeting_type` fallback ("모임"으로 일반화, `helpers/places.py:191`) → Kakao query는 `f"{place_hint} {meeting_type}"` (line 211) 사용. 특정 cuisine 카테고리 강요 안 함.
- **사용자 narrator**: 없음 (silent fallback). meeting_type fallback이 적용된 사실은 user-visible하지 않음.
- **Gemini prompt 영향**: cuisine 미식별 시 prompt에 cuisine 라벨 제외 — 자유 카테고리 reranking. 카드 reasoning은 다른 신호(거리·선호·페널티)에 의존.
- **갭 (다중 cuisine)**: "한식 먹을까 일식 먹을까" 같은 다중 cuisine 발화는 첫 매칭만 반환(`for trigger, cuisine in _CUISINE_TRIGGERS.items()` 첫 hit). 다중 후보 처리는 §2 S18 시나리오와 연결 — **v1.5 후보 (cuisine ambiguity 분기 + 사용자 확인 narrator)**.

### 6.17 place_hint·place_coord 모두 None (F5 본문)

발화에 place_hint 부재 + entity_extraction이 patterns/Gemini로도 추출 실패한 경우.

- **분기 조건**: `state.get("place_hint") is None` AND `_resolve_place_hint(state)` 반환 None → `nodes/place.py:140~146` 노드 `status="place_skipped"` 진입.
- **Q2 결정 fallback 순서** (§4.4 F5):
  1. **선호 장소 다수결**: `MeetingPreference.preferred_location` 교차 → `pref_data["best_location"]` (구현 위치: `nodes/slot.py` → `_load_meeting_preferences` 결과). 결과 있으면 `state["place_hint"]` 채움 후 search 진행.
  2. **동률 시 발화자 선호**: `requester_home_base` 또는 발화자 `liked_areas` 1순위 (PR-Z1 P0-4 plumbing).
  3. **방장 home_base**: `Room.creator.home_base` 또는 `creator.liked_areas` (1·2 모두 미발견 시).
  4. **셋 다 None**: narrator "장소 추천을 위해 지역을 알려주세요" 발행 (또는 silent skip — **현재 silent skip만 구현**, narrator는 v1.5 후보).
- **현재 코드 갭**: F5 1·2·3 단계의 명시적 분기 순서 코드 미통합. `_resolve_place_hint`가 단일 함수에서 결정. **v1.5 정교화 후보** — F5 fallback의 4-step 명세를 코드 분기 1:1로 매핑.
- **`preference_source` 영향**: 1단계 진입 시 `"group"`, 2단계 진입 시 `"speaker"`, 3단계 진입 시 `"group"` (방장 = 그룹 대표) 표기.

### 6.18 ML 모델 비활성 (F9 본문)

LGBMRanker 로드 실패 또는 환경변수 OFF 시 추천 품질 degradation.

```python
# backend/app/services/pipeline/nodes/place.py:66~71
try:
    from app.services.ml_recommend import ml_place_search as _ml_place_search
    _ML_AVAILABLE = True
except Exception:
    _ml_place_search = None  # type: ignore[assignment]
    _ML_AVAILABLE = False
```

- **분기 조건**: import 시점에 `_ML_AVAILABLE=False` 결정 (모듈 단위, 런타임 토글 불가). 런타임 ML 호출 실패는 try/except로 잡혀 Gemini fallback (`nodes/place.py:184~185`).
- **현재 동작**: Gemini scoring (`nodes/place.py:213~283`) + 거리 점수 (`helpers/places.py:225~232`)만 사용. ranked_places는 ML 없이도 정상 발행, narrator 변경 없음 — **silent degradation**.
- **추천 품질**: ML reranking 부재로 약간 저하 가능 (특히 협업필터링 기반 사용자별 선호 학습 손실). 사용자에게는 노출되지 않음.
- **로깅 권고**: 현재 `[ML] ml_place_search 실패, Gemini fallback: ...` (line 185) — import 시점 단발성 fallback 메트릭은 미발행. **v1.5 권고**: `[FALLBACK] ml_disabled` 구조화 로그 + 메트릭 카운터, P95 latency·품질 회귀 추적.
- **연관 시나리오**: §2 S14·S18 (음식 페널티·cuisine 다중) — ML 없이도 정상 동작해야 함 (회귀 §10 negative test에 분류).

---

## 10. 회귀 테스트 케이스 (장소 한정)

> 공통 테스트 전략·fixture·negative test·로그 metric·동시성·우선순위·v2 backlog는 [`spec-time-coordination.md §10`](./spec-time-coordination.md) 참조. 본 절은 장소 시나리오 S11~S20 매핑만.

### 10.3 골든 시나리오 pytest 매핑 (장소)

| S# | 시나리오 (§2 인용) | pytest 파일·함수 | 핵심 assertion |
|---|---|---|---|
| S11 | place_hint 명시 "강남에서" | `integration/test_place_recommendation.py::test_hint_extracted` | `place_hint=="강남"`, `place_coord` 좌표 변환, `recommendations` ≤ 5 |
| S12 | place_hint fallback (Q2 F5) | `integration/test_place_fallback.py::test_creator_home_base` | 순서 검증: 선호 다수결 → 동률 시 발화자 → 둘 다 비면 방장 `home_base` |
| S13 | cuisine 감지 "한식 먹자" | `unit/test_cuisine.py::test_korean_food` | `_detect_cuisine_type` 반환 "한식", Kakao 검색 쿼리에 cuisine 포함 |
| S14 | 비선호 음식 페널티 (P4) | `unit/test_disliked_food.py::test_penalty` | `_contains_disliked_keyword` True, 후보 score `-= 0.1`, 익명 합산 prompt에 실명 미노출 |
| S16 | 장소 거부 누적·재추천 | `integration/test_place_rejected.py::test_excluded` (**v1.5 후보**) | 새 place_hint 추출 후 재검색 또는 `rejected_places` state 키 누적 — 현재 코드 미존재, **v1.5 backlog** |
| S17 | Kakao 0건 fallback (F7) | `integration/test_kakao_empty.py::test_no_results` (신규) | `place_search_results==[]`·narrator 명시 발행 (또는 빈 `recommendations` 카드 + narrator) |
| S18 | cuisine 다중 충돌 (S18) | `unit/test_cuisine_ambiguity.py::test_dual_cuisine` (**v1.5 후보**) | `_detect_cuisine_type` 결과 2건 이상 시 ambiguity 분기 또는 두 카테고리 모두 reranking — **현재 첫 매칭만 반환, v1.5 backlog** |
| S19 | speaker 토글 차이 (S15 후속) | `integration/test_speaker_toggle.py::test_personal_results` | `requester_preferences` 반영, group 카드와 다른 결과 (예: 그룹 강남 → speaker 홍대), `preference_source=="speaker"` |
| S20 | 거리 vs ML 점수 트레이드오프 | `unit/test_score_integration.py::test_distance_ml_balance` (**v1.5 또는 v2 후보**) | Q4 종합 가중치 공식 (거리·ML·Gemini score 통합) — **현재 정확 공식 미정, v1.5/v2 backlog** |

### 10.4 추가 시나리오 (장소 negative test)

| 케이스 | 라우터·노드 | 기대 응답·동작 |
|---|---|---|
| `test_kakao_5xx_returns_narrator` (F7) | `nodes/place.py` + `services/kakao_maps.py` monkeypatch (5xx) | `place_search_results==[]`, narrator 발행, vote_card 흐름 영향 없음 — F7 검증 |
| `test_ml_disabled_uses_gemini_only` (F9) | `nodes/place.py` (`_ML_AVAILABLE=False` 패치) | Gemini scoring + 거리 점수만으로 reranking, narrator 변경 없음, ranked_places 정상 발행 — F9 silent degradation 검증 |
| `test_cuisine_none_uses_meeting_type_fallback` (F6/§6.16) | `helpers/places._detect_cuisine_type` None 케이스 | meeting_type fallback 적용, cuisine prompt 라벨 제외, silent fallback |

### 10.5 로그·메트릭 assert (장소 한정)

- F5 (place_hint fallback) 단계별 발동 카운트 ([`spec-common.md §9.4`](./spec-common.md)) — 선호 다수결 → 발화자 → 방장 위치 (Q2) 단계 검증.
- F6 (cuisine 미감지) silent fallback 발동 — caplog로 검증.

### 10.7 회귀 우선순위 (시연 직전 — 장소 항목만)

| 우선순위 | 목적 | 케이스 |
|---|---|---|
| **P0** | 핵심 흐름 — 골든 데모 | S11, S12 |
| **P1** | 분기·도메인 | S13, S14, S17 (F7 Kakao 0건), S19 (speaker 토글 차이) |
| **P2** | 운영·동시성 | F7·F9 fallback 검증 |
| **v1.5 후보** | 후속 정교화 | S16 (rejected_places 누적), S18 (cuisine 다중), S20 (Q4 점수 공식) |

### 10.8 미구현 / v2 backlog (장소 한정)

- **S16 `rejected_places` state 키 누적** — 현재 코드 미존재, v1.5 도입 시 회귀 추가 (`integration/test_place_rejected.py`).
- **S18 cuisine ambiguity 분기** — `_detect_cuisine_type` 다중 매칭 지원 + ambiguity narrator 또는 두 카테고리 reranking, v1.5 후보.
- **S20 Q4 점수 통합 공식** — 거리·ML·Gemini score 가중치 명문화 (현재 암묵적 sort by score), v1.5 또는 v2.
- **F7 Kakao 장애 vs 0건 구분** — `state["kakao_api_failed"]` 플래그 + 전용 narrator, v1.5.
- **F8 명시적 tiebreaker** — 동률 시 (거리 가까운 순 → place_id 사전순) 정렬 추가, v1.5.
