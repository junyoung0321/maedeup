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
| **S8. 모두 불가 fallback** | 거부/캘린더로 가능한 슬롯 0개 | any | 가장 많은 멤버 가능한 슬롯 3개 vote_card + "전원 가능 시간 없음" narrator | "다수결 vote_card" 분기 (현재 미구현, P1 후보) |
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
| F1 | 0 슬롯 → 다수결 | 전원 가능 슬롯 0개 | (미구현, P1) 가능 멤버 max인 슬롯 3개 + blocker_notification |
| F2 | headcount=None | entity가 인원 추출 못함 | (현재) supervisor가 에러 — Q3 결정 필요 |
| F3 | single slot skip | 슬롯 1개만 남음 | `vote_card_skipped` 상태 → maedeup 직행 — Q1 결정 필요 |
| F4 | 캘린더 권한 없음 | OAuth 미동의 멤버 | 해당 멤버 캘린더 무시 + narrator에 명시 |

---

## 5. 입력값 / 출력값

(작성 예정 — 카탈로그 6 카테고리 중 시간 조율이 소비하는 항목만 추려서 정리)

### 5.1 입력 (소비) — TODO
### 5.2 출력 (생성) — TODO
### 5.3 P0 plumbing 요구 (intent, time_window 등) — TODO

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
| Q1 | 슬롯 1개만 남으면? | S5, S9 | A) maedeup 직행 / B) 단일 슬롯도 vote_card / C) direct_request만 vote_card |
| Q3 | headcount=None 시 기본값 | F2 | A) 멤버 수 사용 / B) 2 / C) None 허용하고 supervisor 통과 |
| Q5 | 발화자 선호 vs 그룹 선호 충돌 시 | P3 | A) 그룹 우선 / B) 발화자 우선 / C) UI에서 confirm |
| Q6 | F1 fallback (전원 불가능 시 다수결) 구현 우선순위 | S8 | A) 시연 전 P0 / B) 시연 후 P1 / C) 별도 PR |

---

## 변경 이력
- 2026-05-14: 초안 작성 (§1~§4, §11), §5~§10 scaffolding
