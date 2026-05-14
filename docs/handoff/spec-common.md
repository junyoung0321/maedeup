# 기능정의서 — 공통 (Common: 공통 결정·권한·API·비기능)

작성: 2026-05-14
작성자: 본인 (장소/시간 조율 담당)
대상 노드: 매듭 시간·장소 조율 전반 — 공통 결정·권한·데이터·API·비기능·부록
관련 문서:
- [spec-time-coordination.md](./spec-time-coordination.md) — 시간 조율 본문 (§1~§6 시간·§10 시간 회귀)
- [spec-place-recommendation.md](./spec-place-recommendation.md) — 장소 추천 본문 (§1~§6 장소·§10 장소 회귀)
- [recommend-input-catalog.md](./2026-05-13-recommend-input-catalog.md) — 활용 가능 인풋 카탈로그
- [pipeline-structure.html](./pipeline-structure.html) — 파이프라인 구조

> **목적**: 시간·장소 두 spec이 공유하는 정책·권한·데이터·API·비기능 요건을 **단일 SoT(Source of Truth)** 로 모은다. 결정 안건(Open Questions) 표와 변경 이력 또한 본 문서에만 둔다.

---

## 1. 공통 개요

매듭(Maedeup)은 채팅방에서 모임 **시간과 장소**를 합의하는 과정을 자동화한다. 사용자 발화·캘린더·선호도를 통합하여 **vote_card**(시간 투표), **place_recommendation**(장소 추천), **maedeup_card**(확정/partial) 페이로드를 발행한다.

- **시간 조율** (`slot_filling` + `function_calling`/캘린더 + `vote_card_creation`): 사용자 발화·캘린더·선호도를 읽어 합의 가능한 후보 슬롯을 vote_card로 발행 → [`spec-time-coordination.md`](./spec-time-coordination.md)
- **장소 추천** (`place_recommendation`): place_hint·home_base·그룹/발화자 선호로 Kakao 검색 + ML/Gemini reranking → place_recommendation 카드 발행 → [`spec-place-recommendation.md`](./spec-place-recommendation.md)
- **매듭 카드** (`maedeup_card_creation`): 시간·장소 확정 시 확정 카드, 시간만 결정된 경우 partial(time_only) 카드 발행 — 시간/장소 양쪽 결과 carry (장소 spec §3.3·§3.4에서 정의)

**책임 경계 (공통)**
- ✅ 본 SoT가 정의: 권한·접근 조건, 데이터·PII 정책, API·이벤트·로그, 비기능 요구사항, 결정 안건, 부록(다이어그램·마이그레이션·환경변수·용어집·변경 이력)
- ❌ 외부 spec: intent 분류 자체(`intent_detection`), 검증/판단 supervisor(`supervisor_validation`), 캘린더 API 자체(`google_calendar.py`), Kakao Local API / ML ranker 내부 구현

---

## 2. 공통 시나리오 (S15 — refresh 토글)

> **시간 시나리오 (S1~S10)** 는 [`spec-time-coordination.md §2`](./spec-time-coordination.md) 참조.
> **장소 시나리오 (S11~S14, S16~S20)** 는 [`spec-place-recommendation.md §2`](./spec-place-recommendation.md) 참조.
> 본 절은 **시간·장소 양쪽 카드를 모두 재발행** 하는 S15만 다룬다.

| ID | 발화 / 이벤트 | trigger_reason | 기대 출력 | 검증 포인트 |
|---|---|---|---|---|
| **S15. Q5 hybrid 토글 (refresh)** | (vote/place 카드 발행 후) "내 취향으로 보기" 버튼 클릭 → `POST /meetings/{id}/recommendations/refresh` | `preference_toggle` (PR-Z1 신설, §9.2와 1:1) | 새 `vote_card_payload`·`place_recommendation_payload` 방 전체 broadcast (Q7-b) + narrator "OOO님 선호 기준으로 다시 추천했어요" (Q15=A 실명) | 권한 Q13=B (발화자+방장만), rate limit Q14=C (Redis idempotency + 일일 100회), Q7-c 토글 차단 조건 (C1∨C3∨C4) 422 분기, 신규 페이로드 `preference_source="speaker"` 또는 `"group"` 일관 표기 |

---

## 3. 페이로드 공통 정책

### 3.1 narrator 메시지 (refresh 통합 문구)

vote_card·place_recommendation·maedeup_card narrator 본문은 자매 spec(§3.5)에 정의. 본 절은 **refresh 시 양쪽 카드 공통 narrator**만 명세.

- **refresh 토글 (Q15=A)**: `"OOO님 선호 기준으로 다시 추천했어요"` — 발화자 실명 명시 (PII 노출 트레이드오프 인지). vote_card·place 양쪽 refresh 시 동일 문구.

### 3.2 페이로드 변경 시 영향 범위

- 프론트 `MeetingChatRoom.tsx` 카드 3종(vote/place/maedeup) 렌더 (mock 컨트랙트)
- `confirm` 엔드포인트가 `meeting_id` + `slot_id`/`place_id`로 확정 호출
- `maedeup_card_creation`이 vote/place payload carry → `selected_time`/`selected_place` 추출
- `POST /meetings/{id}/recommendations/refresh` (§9 신설) 시 카드 모두 재발행 가능 (Q7-b 방 전체 broadcast)

---

## 4. 공통 진입·상태 키 (§5.1.7)

본 절은 시간·장소 양쪽 노드가 함께 읽는 진입 컨텍스트·상태 키를 모은다. 시간·장소 spec은 본 절을 인용한다.

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

## 5. P0 plumbing 요구 (공통 요약)

자매 spec §5.3에서 시간·장소 각 P0 항목을 인용한다. 본 절은 전체 6 항목의 한눈 요약.

| # | 재료 | 영향 spec | 현재 상태 | 의존 결정 |
|---|---|---|---|---|
| 1 | `state["intent"]` 명시 세팅 | 시간·장소 공통 | quick_classify가 `direct_request_kind`만 채우고 `state["intent"]`는 dead | — |
| 2 | `requester_user_id` 노출 | 시간·장소 공통 | `viewer_user_id`는 state에 있으나 추천 노드에서 미사용 | — |
| 3 | `requester_home_base` | 장소 (F5 fallback) | `User.home_base` 컬럼 있음, state까지 안 옴 | Q2 |
| 4 | `requester_preferences` 묶음 | 장소 (P4·P5·P6) | `User.food_*`/`*_areas`/`transport_mode` 미전달 | Q5 hybrid |
| 5 | `time_window` (ISO range) | 시간 (Q1) | `parsed_time_hint` 텍스트 그대로, 정규화 안 됨 | Q1 |
| 6 | `cuisine` state 명시 | 장소 (T6) | place_recommendation 내부에서만 감지 (`_detect_cuisine_type`) | — |

**의존 관계**:
- P0-1·2·6 — 단순 plumbing, 결정 의존 없음
- P0-3 — Q2 (place_hint fallback 순서) 결정 필요
- P0-4 — Q5 hybrid 정책 반영 (UI 토글 메타 §3·§9에 명세)
- P0-5 — Q1 단일 슬롯 = vote_card 반영

**v2 예고** (별도 spec 문서): P1 5항목 (`room_member_home_bases`, `previous_recommendations`, `urgency_signal`, `group_constraints_summary` 양 노드 공유, `notes` 활용)은 본 v1 범위 밖.

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

페이로드의 `preference_toggle_enabled: false` 산출 규칙 (자매 spec §3 페이로드 메타). UI에서 토글 비활성화로 표현되며, 우회 호출 시 422로 거부:

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

본 절은 PII·동의·보존 정책을 정의한다. PIPA(개인정보 보호법) 준수를 1차 기준으로 하고, 미구현 항목은 §8.9에 갭으로 명시한다.

### 8.1 동의 모델 (opt-out)

매듭은 **opt-out 모델**을 채택한다. 사용자가 명시 거부하지 않는 한 데이터 공유에 동의한 것으로 간주한다.

**적용 항목** (`models/user.py:35,40-42`):
- `calendar_consent: bool = Field(default=True, index=True)` — Google Calendar busy 조회 동의 (PR-X `9609bee` 이후 기본 True 적용)
- `share_food_data: bool = Field(default=True)` — 음식 선호/제약 그룹 합산 공유
- `share_location_data: bool = Field(default=True)` — 좋아하는/싫어하는 지역 공유
- `share_schedule_data: bool = Field(default=True)` — 시간 선호 (선호 시간대) 공유

**확정 결정 (Q-X1=A)**: 마이그레이션 시 기존 명시 거부 사용자(`False`)도 일괄 `True`로 재설정한다. 사용자가 다시 토글하기 전까지 동의 의제.

**사용자 거부 흐름**:
- 홈 `/m/consent` 페이지의 QuickPreferences 토글 UI
- `PATCH /users/me/consent` (calendar_consent, `routes/users.py:126~150`)
- `PATCH /users/me/preferences` (share_*_data, `routes/users.py:164~`)
- 토글 즉시 다음 API 호출부터 반영 (캐시 무효화는 §8.4)

**PIPA 한계 명시**: opt-out은 한국 PIPA의 "명시적 동의(opt-in)" 원칙과 긴장 관계에 있다. 매듭은 졸업 프로젝트 MVP로서 UX 우선순위를 적용했으며, 상용화 시 opt-in으로 전환 필요. 현재는 가입 시 약관에 "캘린더 자동 연동" 및 "선호 데이터 그룹 합산" 동의 항목 명시로 갈음.

### 8.2 `is_ai_filled` 정책 (AI 추출 데이터 출처 표시)

AI가 chat 메시지에서 자동 추출한 PII와 사용자가 수동 입력한 PII를 구분한다.

**자료 구조** (`models/user.py:28~31`):
- `is_ai_filled: dict[str, bool]` — 카테고리명(food_restrictions, liked_areas 등) → AI 채움 여부
- 추출 진입점: `services/pipeline/nodes/memory.py:189~228` (`_persist_personal_data`)
- 추출 트리거: 모임 종료 시 chat history에서 Gemini가 카테고리별 추출 (`services/personal_data_extractor.py`)

**UI 정책**:
- 홈 PersonalData 카드에 ✨ 마크로 AI 추출 표시 (`models/user.py:27~28` 주석)
- 사용자가 수동 수정 시 → `is_ai_filled[category] = False` (✨ 사라짐, `routes/users.py:177~183`)
- ✨ 클릭 시 receipts 표시 (`PersonalDataSourceResponse`, `routes/users.py:115~123`): 어느 방/메시지에서 추출됐는지 출처 노출

**거부 흐름**: AI 추출 결과를 사용자가 거부하려면 PersonalData 화면에서 해당 카테고리를 수동 수정(빈 값 또는 다른 값)하면 됨. 이 시점에 `is_ai_filled[cat]=False`로 마크되고 후속 AI 추출이 같은 카테고리를 덮어쓰지 못한다(Case A vs Case B 분기, `memory.py:111~112` 주석).

### 8.3 k-anonymity 가드 (소규모 방 보호)

소규모 방(`total_members <= 3`)에서 그룹 합산 PII는 사실상 개별 식별 가능하다. 예: 3인 방에서 `group_constraints_summary: ["갑각류 제외"]`가 노출되면, 본인이 갑각류 제약을 입력하지 않은 멤버는 나머지 1명을 식별할 수 있다.

**권장 정책 (v1.5 후보, 현재 미구현)**:
- 임계값: `total_members >= 4`일 때만 `group_constraints_summary` 노출
- 미만일 때: 합산을 마스킹("선호 데이터가 충분하지 않아요") 또는 표시 자체 차단
- F1 `blocker_notification` 실명 노출(§8.6 점진 공개)도 동일 임계값 적용

**현재 상태**: `place.py:325~328`의 `group_constraints_summary`는 멤버 수 검증 없이 노출됨. v1.5 backlog.

### 8.4 Redis 캐시 PII · 만료

**캐시 위치**: `room_place_rec:{room_id}` (TTL 24h, `nodes/place.py:332~344`)

**저장 내용**: `place_recommendation_payload` 전체 — `recommendations`(장소 후보) + `group_constraints_summary`(익명 합산 문자열). 개별 멤버 PII는 평문으로 저장되지 않으나, 합산 결과 자체가 소규모 방에서는 식별 가능(§8.3).

**정책**:
- TTL 24h 유지 (새로고침 복구용 UX 우선). 단축 옵션은 v1.5 검토.
- **모임 취소 시 캐시 즉시 삭제** (현재 미구현 — §8.9 갭)
- **사용자 탈퇴 시 해당 user_id가 속한 모든 방의 캐시 무효화** (현재 미구현 — §8.9 갭)
- `share_*_data` 토글 OFF 시 → 다음 추천부터 반영, 기존 24h 캐시는 TTL 만료 대기 (강제 무효화 v1.5)

### 8.5 동의 철회 · 삭제 SLA

**사용자 액션**:
- `PATCH /users/me/consent` (calendar_consent) — 즉시 반영, 새 JWT 발급
- `PATCH /users/me/preferences` (share_*_data) — 즉시 반영
- **계정 삭제**: 현재 미구현 (`DELETE /users/me` 부재 — §8.9 갭)

**SLA 목표**:
- 토글: 즉시 (다음 API 호출부터)
- 탈퇴 후 PII 삭제: 30일 내 (PIPA 권고 기준)
- Redis 캐시 invalidate: 토글/탈퇴 즉시 (현재 미구현)
- Google 토큰 폐기: `calendar_consent=False` 토글 시 `google_*_token` NULL 처리 (현재 토큰 자체는 유지됨 — 갭)

### 8.6 narrator PII 정책 (Q15=A · F4 · F1 통합)

**확정 결정 (Q15=A): 실명 narrator** — 토글 재발행 narrator는 "OOO님 선호 기준으로 다시 추천했어요" 형태로 실명 노출.

- 적용 조건: viewer가 토글한 사용자와 **같은 방 멤버**일 때만 노출 (멤버십 검증은 §7)
- 비멤버는 narrator 자체를 수신하지 않음 (WebSocket 채널 분리)
- 토글 audit: 누가 언제 토글했는지 구조화 로그 또는 `audit_log` 테이블 — §9에 위임

**F4 캘린더 권한 만료 narrator ([`spec-time-coordination.md §6.7`](./spec-time-coordination.md) open 항목 해소)**:
- 옵션 A) 실명: "OOO님 캘린더 권한이 만료됐어요"
- 옵션 B) 익명: "1명 캘린더 권한 만료"
- **권고: 옵션 A 실명** — Q15=A 일관성 + 해당 멤버에게 직접 알림이 액션 가능성을 높임
- **신규 미결 (Q17 후보)**: F4 narrator 실명/익명 — 본 PR에서 권고만 명시, 최종 결정은 §결정 안건으로 이관

**F1 `blocker_notification` (Q16=C 점진 공개)**:
- 기본 표시: "1명 불참" (익명)
- 슬롯별 `더보기` 클릭 시 실명 공개 ("OOO, ㅁㅁㅁ")
- **k-anonymity 결합 (§8.3)**: `total_members >= 4`인 방에서만 실명 공개 허용 권고. 미만에서는 익명 유지.

### 8.7 게스트 데이터 보관 정책

게스트 (`is_guest=True`, `models/user.py:45`) 는 Google 로그인이 없으므로 `calendar_consent`가 강제 `False` (`routes/rooms.py:221,239,295`). 그러나 다음 데이터는 수집된다 (Q12=A 확정 — 게스트 포함):
- `MeetingPreference` (선호 시간대, 불가 시간)
- `unavailability` (입력 시)
- chat 메시지 (방 단위)

**보관 정책**:
- 모임 종료 후 `MeetingPreference` 30일 보관 (PIPA 권고)
- 게스트 row 자체: 방별 pseudo identity (synthetic email)로 유지
- **부풀림 위험** (`rooms.py:185~191` 주석): 동일 인물이 다른 이름으로 재접속 시 새 row 생성 → 누적 가능
- **권고**: 모임 종료 후 90일 동안 미사용 게스트 row → archive 처리 (현재 미구현, §8.9 갭)

### 8.8 PII 보존 기간 요약 표

| 데이터 | 보존 기간 | 삭제 트리거 |
|---|---|---|
| `User` 본인 정보 (email, name, picture, home_base) | 무기한 | 사용자 탈퇴 (현재 미구현) |
| `User.google_access_token` · `google_refresh_token` | 무기한 | `calendar_consent=False` 토글 또는 Google revoke (현재 자동 NULL 처리 미구현) |
| `User.is_ai_filled` AI 추출 데이터 (food_restrictions 외) | 무기한 | 사용자 수동 수정 (✨ 해제) 또는 탈퇴 |
| `User.share_*_data` 토글 상태 | 무기한 | 사용자 탈퇴 |
| `MeetingPreference` | 모임 종료 후 30일 | 모임 종료 자동 트리거 (현재 미구현) |
| `MeetingParticipant` · `Notification` | 영구 (audit 목적) | — |
| `ChatMessage` (private = 1:1) | 영구 | 사용자 탈퇴 시 익명화 (현재 미구현) |
| `ChatMessage` (shared = 그룹방) | 영구 (방 단위) | 방 삭제 시 cascade |
| Redis `room_place_rec:{room_id}` | 24h TTL | 모임 취소 / TTL 만료 |
| `AIMemory` (meeting_record 등) | 무기한 | 사용자 탈퇴 |
| 게스트 `User` row | 무기한 (방별 pseudo) | 90일 비활성 archive 권고 (미구현) |

### 8.9 알려진 갭 (v1 · v1.5 backlog)

PIPA 의무 또는 정책 일관성을 위해 추가 구현이 필요한 항목:

1. **계정 삭제 엔드포인트 미구현** (`DELETE /users/me`) — PIPA Right to Erasure 의무. v1 또는 별도 PR 우선순위.
2. **Google calendar revoke 엔드포인트 미구현** — `calendar_consent=False` 토글 시 `google_*_token`이 NULL로 자동 처리되지 않음. 사용자가 토큰을 코드 레벨에서 폐기할 수 없음.
3. **k-anonymity 가드 미구현** (§8.3) — 소규모 방 PII 노출 위험. `group_constraints_summary` · F1 blocker 실명 노출 양쪽에 임계값 미적용.
4. **모임 종료 시 자동 보관 트리거 미구현** — `MeetingPreference` 30일 보관 SLA 자동화 부재.
5. **Redis 캐시 즉시 invalidate 미구현** — 모임 취소 / 사용자 탈퇴 / `share_*_data` 토글 시 `room_place_rec:{room_id}` 강제 삭제 부재.
6. **chat 메시지 익명화 미구현** — 사용자 탈퇴 후 그룹방 `ChatMessage`의 sender 익명 처리 부재.
7. **게스트 row archive 미구현** (§8.7) — 90일 비활성 archive 자동화 부재.
8. **audit_log 미구현** (§8.6) — 토글 narrator 누가/언제 audit 로그 부재. §9에서 정의.

---

## 9. API / 이벤트 / 로그

§7 권한 매트릭스·§8 데이터 정책의 외부 인터페이스(REST 라우트·WebSocket 이벤트·구조화 로그·audit) 정의. v1 코드 기준 인벤토리 + Q5 hybrid 토글용 신규 라우트(미구현) 명세.

### 9.1 시간+장소 관련 엔드포인트 인벤토리

라우터별 v1 라우트(`backend/app/api/routes/*.py` 기준). 권한 컬럼은 §7.2 매트릭스 행 번호 참조.

**`/api/v1/chat`** (메시지·share)

| 메서드 | 경로 | 인증 | 요청 | 응답 | 권한 | 비고 |
|---|---|---|---|---|---|---|
| GET | `/messages` | JWT | `room_id`·`pane_type`·`since` | `ChatMessageRead[]` | 방 멤버 | `chat.py:49` — viewer 필터링 (§7.4) |
| POST | `/messages` | JWT | `ChatMessageCreate` | `ChatMessageRead` | 방 멤버 | `chat.py:95~117` — `RoomMember` 검증 |
| POST | `/messages/{id}/share` | JWT | `card_payload?` | `ShareMessageResponse` | 메시지 owner | `chat.py:120` — private→shared 전환 (§7.2 R12) |

**`/api/v1/meetings`** (모임 CRUD·확정·취소)

| 메서드 | 경로 | 인증 | 권한 | 비고 |
|---|---|---|---|---|
| GET | `/` | JWT | 본인 모임 | `meetings.py:112` — 사용자 참여 모임 목록 |
| GET | `/upcoming` | JWT | 본인 모임 | `meetings.py:148` — 다음 예정 모임 |
| GET | `/rooms/{id}/pending-place` | JWT | 방 멤버 | `meetings.py:189` — partial(time_only) 조회 |
| GET | `/rooms/{id}/pending-vote` | JWT | 방 멤버 | `meetings.py:223` — pending vote_card 조회 |
| GET | `/{id}` | JWT | 방 멤버 | `meetings.py:286` — 상세 조회 |
| POST | `/confirm` | JWT | 방 멤버 (`meetings.py:371`) | 시간·장소 확정 (§7.2 R5) |
| POST | `/{id}/vote` | JWT | 방 멤버 | `meetings.py:517` — slot 투표 |
| PATCH | `/{id}/place` | JWT | 방 멤버 | `meetings.py:719` — 장소 수동 입력 (해결점 K, §7.2 R6) |
| POST | `/{id}/cancel` | JWT | 모임 `created_by` 본인 (`meetings.py:869`) | 취소 — 방 broadcast `meeting_cancelled` |
| **POST** | **`/{id}/recommendations/refresh`** | **JWT** | **발화자 + 방장 (Q13=B)** | **신규 — §9.2, 현재 미구현** |

**`/api/v1/rooms`** (방·게스트·선호)

| 메서드 | 경로 | 권한 | 비고 |
|---|---|---|---|
| POST | `/` | JWT | `rooms.py:104` — 방 생성 (생성자 = owner) |
| GET | `/` · `/{id}` | JWT, 방 멤버 | 목록·상세 |
| POST | `/{id}/guest-join` | 토큰 | `rooms.py:176` — 게스트 가입 (§7.7) |
| POST | `/{id}/preferences` · GET | JWT, 방 멤버 | `MeetingPreference` 입력/조회 (§7.2 R3·R4) |
| POST | `/{id}/schedule-confirm` | JWT, 방 멤버 | `rooms.py:464` — 스케줄 확정 흐름 |
| POST | `/{id}/leave` | JWT, 방 멤버 | `rooms.py:554` — 방 나가기 |

**`/api/v1/calendar`** (개인 캘린더)

| 메서드 | 경로 | 권한 | 비고 |
|---|---|---|---|
| GET | `/free-slots` | JWT, 본인 | `calendar.py:335` — `calendar_consent=True` 필요 |
| GET | `/my-events` | JWT, 본인 | `calendar.py:478` — `calendar.py:496` consent 가드 |

> 캘린더 불가능 토글(§7.2 R10)은 현재 별도 라우트 없이 `/rooms/{id}/preferences` 페이로드 안에 임베드 — v1.5 별도 라우트 분리 후보.

**`/api/v1/finalization`** · **`/api/v1/places`** · **`/api/v1/notifications`** · **`/api/v1/auth`** (요약)

| 경로 | 권한 | 비고 |
|---|---|---|
| `POST /finalization/{proposal_id}/vote` | JWT, 방 멤버 | `finalization.py:134` — Proposal 별도 흐름 |
| `GET /finalization/room/{room_id}` | JWT, 방 멤버 | `finalization.py:181` |
| `POST /places/search` | JWT | `places.py:30` — Kakao Local proxy |
| `GET /notifications` · `/unread-count` · `POST /{id}/read` · `POST /read-all` | JWT, 본인 | `notifications.py:36~100` |
| `GET /auth/google` · `/auth/google/callback` | (public) | `auth.py:30~56` — OAuth flow |

### 9.2 신규 라우트: `POST /meetings/{id}/recommendations/refresh` (Q7-b)

**목적**: Q5 hybrid 토글 — 그룹 다수결 ↔ 발화자 선호 기준 전환 시 방 전체에 새 vote_card / place_recommendation broadcast (Q7-b: 방 전체 갱신).

**상태**: v1 코드 미구현. v1.5 backlog (§9.8).

**요청 본문**

```jsonc
{
  "scope": "vote_card" | "place_recommendation" | "both",
  "preference_source": "group" | "speaker",
  "requester_user_id": 7  // 발화자 (서버측 viewer_user_id와 교차 검증)
}
```

**권한 (Q13=B)**

- JWT → `viewer_user_id` 추출 → `RoomMember(room_id=meeting.room_id, user_id=viewer_user_id)` 조회.
- 허용 조건 (둘 중 하나):
  1. **발화자**: `requester_user_id == viewer_user_id` AND `RoomMember.user_id == requester_user_id`.
  2. **방장**: `RoomMember.role == "owner"` (또는 `Room.created_by == viewer_user_id` — 코드 일관성은 §7 매트릭스 R5와 동일 기준).
- 거부 시 `403 PERMISSION_DENIED`.

**Rate limit (Q14=C)**

- **Idempotency 캐시 (Redis)**: 키 `refresh:{user_id}:{meeting_id}:{scope}:{preference_source}`, TTL 5분.
  - 같은 조합 재호출 시 캐시 hit 응답 (Gemini 미호출, 비용 절감).
- **일일 호출 제한**: 키 `refresh_count:{user_id}:{YYYY-MM-DD}`, INCR. 100 초과 시 `429 RATE_LIMITED`.

**응답**

- `200 OK`: 새 페이로드 (`vote_card_payload` / `place_recommendation_payload` / both)를 WebSocket으로 방 전체 broadcast (§9.3).
- `403 PERMISSION_DENIED`: 발화자·방장 모두 아님.
- `422 TOGGLE_DISABLED`: `preference_toggle_enabled=false` 조건 (Q7-c C1·C3·C4 중 하나) 위배 — 게스트(C2)는 차단 대상에서 제외.
- `429 RATE_LIMITED`: 일일 100회 초과.
- `404 NOT_FOUND`: meeting 없음 or 취소됨.

**부수 효과**

1. 새 페이로드 발행 (`pane_type=social` 채널, 방 멤버 전체 push — §9.3).
2. narrator 메시지 발행 (Q15=A 실명): `"OOO님 선호 기준으로 다시 추천했어요"`.
3. Audit log 기록 (§9.5).

### 9.3 발행 이벤트 (WebSocket / 시스템)

**WebSocket 채널 — pane_type 분리**

| `pane_type` | 대상 | 사용처 |
|---|---|---|
| `agent` | viewer_user_id별 push (개인 비서 패널) | vote_card private 미리보기, narrator 1:1 |
| `social` | 방 전체 broadcast (방 채팅) | shared vote_card, place_recommendation, maedeup_card, narrator |
| `personal_assistant` | viewer_user_id별 push (홈 비서) | 친구/알림 등 방 외부 |

**이벤트 종류**

- `new_assistant_messages` — `helpers/messaging.py:154~167` publish queue. agent.py가 Redis로 fan-out.
- `vote_card_payload` broadcast — 방 전체 (shared) 또는 viewer별 (private 미리보기).
- `place_recommendation_payload` broadcast — 동일 채널 정책.
- `maedeup_card_payload` broadcast — 확정/partial 카드 (자매 spec §3).
- `meeting_cancelled` broadcast — `meetings.py:893~906` `_publish_finalization_event`.
- `notification` event — `notify.py:68` `notifications:user:{user_id}` 채널 (개인 알림 envelope).

**캐시 invalidate 이벤트 (현재 미구현 — §8.4 / §9.8 갭)**

- `meeting_cancelled` → Redis `room_place_rec:{room_id}` 강제 삭제.
- `user_deleted` → 해당 user 포함 방의 모든 캐시 무효화 (§8.4 위임).
- `share_*_data=False` 토글 → 해당 user PII 포함 캐시 키 무효화.

### 9.4 구조화 로그 필드

**LangGraph 노드 latency**

형식: `[TIMING] {node_name}: {duration_seconds}s`. 모든 노드 일관 형식.

| 노드 | 로그 키 | 위치 |
|---|---|---|
| intent | `[TIMING] intent_detection`·`general_response (template/gemini)` | `nodes/intent.py:130·177·264` |
| entity | `[TIMING] entity_extraction` (+ 5종 fast-skip variant) | `nodes/entity.py:349·400·435·469·571` |
| function_call | `[TIMING] function_calling` (+ false_positive·time_only_ready·place-suggestion·multi-date·preference-based variant) | `nodes/function_call.py:51·56·74·100·122·217` |
| validation | `[TIMING] supervisor_validation` | `nodes/validation.py:118` |
| vote_card | `[TIMING] vote_card_creation` (+ skipped: no date selection / single slot) | `nodes/vote_card.py:186·210·310` |
| place | `[TIMING] place_recommendation` (+ confirmed·skipped 변종) | `nodes/place.py:133·141·360` |
| maedeup | `[TIMING] maedeup_card_creation` | `nodes/maedeup.py:199` |
| memory | `[TIMING] memory_extraction` (+ users affected count) | `nodes/memory.py:242` |

**Fallback 발동 로그 (자매 spec §4.4 F1~F9)**

- **F1** (`majority_fallback`): 횟수·정렬 정책(Q8=A 시간 빠른 순)·`unavailable_users` 평균 수.
- **F2** (`headcount=None` fallback): RoomMember 수 fallback 적용 횟수 (Q3=A·Q12=A 게스트 포함).
- **F3** (`single_slot_vote_card`): 단일 슬롯 발행 횟수 (Q1=B).
- **F4** (`calendar_consent=False` 멤버 제외): 제외 횟수·user_id (구조화 로그 마스킹).
- **F5** (place_hint fallback): 선호 다수결 → 발화자 → 방장 위치 (Q2) 단계별 발동 카운트.

**Gemini API 호출**

- 모델 (`gemini-2.5-flash`)·input/output token·latency·실패율.
- `quota_exceeded` 시 fallback 발동 카운트 (정규식 fast-skip 경로 — `nodes/entity.py` fast-skip 변종).

**해결점 발동 로그**

- 해결점 N (`expanded_to_next_week=true`): 발동 횟수.
- 해결점 O (정규식 단축 경로): rejected_dates 누락 케이스 카운트.
- 해결점 P (자연어 거부 → 캘린더 동기화 갭): 발동 카운트.

### 9.5 Audit log

**Q5 hybrid 토글 audit (Q15=A 실명 narrator와 연동)**

- 키: `{requester_user_id, meeting_id, scope, preference_source, timestamp}`.
- 저장 위치 (v1 미구현 — backlog §9.8): `audit_log` 테이블 또는 구조화 로그 stream.
- 보존: PIPA 권고 3년 (legal hold 가능).
- 사용자 탈퇴 시 익명화 (`requester_user_id` → `"anonymized"`, §8.6과 일관).

**권한 변경 audit**

- 방장 변경 (현재 미구현).
- 모임 취소 (`meetings.py:869` `created_by` 본인) — 호출 이력 audit log 후보.
- 게스트 강제 퇴장 (현재 미구현).
- `calendar_consent` 토글 변화 — F4 narrator 노출과 연계, audit 권장.

### 9.6 API 에러 응답 형식

표준 형식:

```jsonc
{
  "error": "권한 없음",
  "code": "PERMISSION_DENIED",
  "details": { /* 선택, 디버그용 */ }
}
```

주요 에러 코드:

| HTTP | code | 발생 조건 |
|---|---|---|
| 401 | `UNAUTHENTICATED` | JWT 부재·만료 |
| 403 | `PERMISSION_DENIED` | 방 비멤버, 방장 아님, 발화자 아님 (refresh) |
| 404 | `NOT_FOUND` | meeting/room/proposal 없음 또는 cancelled |
| 422 | `TOGGLE_DISABLED` | Q7-c C1·C3·C4 위배 (게스트 C2 제외) |
| 429 | `RATE_LIMITED` | Q14 일일 100회 초과 |
| 409 | `SUPERSEDED` / `BELOW_MAJORITY` | finalization proposal 상태 위배 (`meetings.py:387~389`) |

### 9.7 F4 narrator 결정 (Q17 권고 A 적용)

[`spec-time-coordination.md §6.7`](./spec-time-coordination.md)·§8.6에서 미결로 남은 Q17 (F4 캘린더 권한 만료 narrator 실명/익명)에 대한 권고:

**Q17 = A) 실명** 적용 (Q15=A 일관 + 액션 가능성 우선):

- 형식: `"OOO님 캘린더 권한이 만료됐어요. 다시 동의해주세요."`
- 조건: viewer가 방 멤버일 때만 노출 (§7.3 멤버십 검증). 비멤버는 narrator 자체를 받지 않음.
- 트레이드오프: Q16=C (F1 blocker 익명+더보기 실명)와 일관성은 다소 어긋나지만, F4는 사용자 액션(재동의)이 필수라 실명 우선.
- Q17 최종 결정 변경 시 본 절·spec-time-coordination §6.7·§8.6 동기 갱신.

### 9.8 미구현·갭 (v1.5·v2 backlog)

§8.9와 별도로 §9 범위에서 식별된 갭:

1. **`POST /meetings/{id}/recommendations/refresh` 라우트 미구현** — 현재 코드 미존재. v1.5 신규 라우터 추가 필요 (§9.2).
2. **`audit_log` 테이블 또는 구조화 로그 통합 미구현** — Q5 토글·권한 변경 audit (§9.5) 보존 부재.
3. **`DELETE /users/me` 계정 삭제 엔드포인트 미구현** — §8.5·§8.9-1과 일관 (PIPA Right to Erasure).
4. **Google Calendar revoke 엔드포인트 미구현** — §8.9-2와 일관 (`calendar_consent=False` 시 token 자동 폐기 부재).
5. **캐시 invalidate 이벤트 미구현** — §9.3 마지막 표 (meeting_cancelled·user_deleted·share toggle).
6. **캘린더 불가능 토글 별도 라우트 부재** — 현재 `/rooms/{id}/preferences`에 임베드, §7.2 R10 명세와 분리 권장.
7. **Rate limit 미구현** — Q14=C 기준 (Redis idempotency + 일일 100회) 코드 미반영, refresh 라우트 신설 시 함께.

---

## 11. Out of scope + 알려진 한계

- 반복 모임 (recurring meeting)
- 비-Google 캘린더 (Outlook, Naver 등)
- 시간대 변환 (KST 외 멤버)
- 다중 모임 시간 겹침 경고
- AI 자동 협상 ("A님 양보해주실 수 있을까요?" 같은 능동 제안)

**알려진 한계 (Known Limitations)**

- **Gemini 휴일 라벨 (Q10=C)**: prompt의 휴일·요일 안내는 힌트 수준 — 실제 매장 영업시간·휴무 회피를 보장하지 않음 (Kakao Local Keyword API 영업시간 미제공). 정확한 휴무 필터는 v2 후보 (Google Places 또는 영업시간 데이터 plumbing).

---

## 12. 비기능 요구사항

### 12.1 성능

사용자 인식 latency = "발화 → vote_card publish" 종단(end-to-end). 노드별 latency는 §9.4 `[TIMING]` 로그에서 집계.

| 지표 | 목표 (P50 / P95) | 측정 방식 |
|---|---|---|
| 사용자 인식 latency (메시지 → `vote_card` 발행) | P50 ≤ 5s / P95 ≤ 10s | §9.4 `[TIMING]` 합산 + WebSocket publish 시각 |
| 단일 LangGraph 노드 평균 latency | 노드별 P95 ≤ 3s | `[TIMING] {node}: {duration}s` (§9.4) |
| Gemini API 응답 P95 | ≤ 4s | `services/gemini.py` 호출 메트릭 |
| Kakao Local Search P95 | ≤ 1s | `services/kakao_maps.py` 메트릭 |
| Google Calendar freeBusy P95 | ≤ 2s | `services/google_calendar.py` 메트릭 |
| Memory extraction (fire-and-forget) | 사용자 인식 latency 무영향 | graph 종료 후 비동기 (`nodes/memory.py` 주석 ~4s 절감) |

성능 측정 위치: §9.4 (구조화 로그) — 모든 노드 entry/exit `[TIMING]` 발행.

### 12.2 가용성

졸업 프로젝트 수준 목표 — **99% (시연 통과 기준)**. 외부 의존성 장애 시 graceful degradation 우선:

| 의존성 | 장애 시 동작 | 근거 |
|---|---|---|
| Gemini API | 정규식 fallback (`_pattern_extract_entities`) | §9.4 fallback 로그 (`gemini_quota_exceeded`) |
| Kakao Local API | F5 narrator ("검색 결과가 없어요") | [`spec-place-recommendation.md §4.4`](./spec-place-recommendation.md) F5 |
| Google Calendar | 캘린더 연동 멤버만 제외 + F4 narrator | [`spec-time-coordination.md §6.7`](./spec-time-coordination.md) F4, §9.7 narrator |
| Redis | 캐시 없이 진행 (silent), 메트릭 alert | §8.4 Redis 캐시 정책 |

§9.8 갭 항목 (외부 의존성 timeout 정책 미명시)은 v2 backlog.

### 12.3 보안

| 영역 | 현황 | 비고 |
|---|---|---|
| JWT | HS256 단일 시크릿, 만료 7일, refresh 미구현 | `JWT_SECRET` dev fallback 위험 — prod 배포 시 강제 변경 (§13.3) |
| Google OAuth 토큰 | `google_access_token` / `google_refresh_token` Text 평문 저장 | `models/user.py` — v2: Fernet 또는 KMS 암호화 |
| API 키 | 환경변수 (`.env.example`), 로그/응답 마스킹 | CLAUDE.md "Never" 규약 |
| Rate limit | Redis idempotency + 일일 100회 (refresh) | §9.2, Q14=C |
| OWASP top 10 | 표준 정책 (CORS·CSRF·XSS·SQLi) | FastAPI/SQLModel 기본 + ORM bind 매개변수 |

알려진 보안 갭: §8.9·§9.8 (RBAC 강제 일관성·OAuth 토큰 암호화) — v2 후보.

### 12.4 프라이버시

§8 데이터 정책에서 본문 명세. 비기능 관점 요약:

- **동의 이력 audit log** (§9.5 위임): `calendar_consent`·`share_*_data` 토글 변경 시 audit row.
- **삭제 SLA** (§8.5 위임): PIPA 준거 30일 보관·삭제. 계정 삭제 엔드포인트는 v1·v2 후보.
- **AI 추출 데이터 검토 UI** (§8.2 위임): `is_ai_filled` 마크(✨), 사용자 거부·수정 가능.
- **PII 노출 정책**:
  - k-anonymity N≥4 (§8.3) — 소규모 방 보호.
  - narrator 실명 (Q15=A) — viewer 멤버일 때만 공개 (§7.4·§8.6).
  - blocker 익명 + 더보기 실명 (Q16=C) — 점진 공개.

### 12.5 접근성 (WCAG 2.1 AA 권고)

| 항목 | 권고 |
|---|---|
| 키보드 네비게이션 | 모든 `vote_card` / `place_card` / `maedeup_card` 클릭 영역 Tab 이동 가능 |
| 색 대비 | 텍스트 ≥ 4.5:1, UI 컴포넌트 ≥ 3:1 |
| 스크린리더 라벨 | 카드·배지·토글에 `aria-label` |
| 포커스 표시 | 토글·버튼 포커스 outline 명시 |
| 검증 도구 | Lighthouse Accessibility 점수 ≥ 90 권고 |

현재 spec은 권고 수준 — 실제 axe-core·Lighthouse 검증은 v2 후보.

### 12.6 다국어

- **현재**: 한국어 only.
- **거부 발언 한국어 가정**: ko_KR 정규식·키워드 매칭 (`maedeup_keywords.py`) — 영어 거부 발언 fallback narrator는 v2.
- **시각자료**: 한국 한정 (`_get_korean_holiday` — Q10=C, 휴일 안내).
- **다국어 전환**: v2 후보.

### 12.7 관측성

§9.4 구조화 로그를 비기능 관점에서 재정렬:

| 카테고리 | 측정 |
|---|---|
| latency | `[TIMING] {node}: {duration}s` — 노드별·종단·P50/P95 집계 |
| Fallback 발동 카운트 | F1·F2·F3·F4 (시간) / F5·F6 (장소) |
| 해결점 발동 카운트 | N·O·P (시연 사후 보완 추적) |
| Gemini 메트릭 | quota·실패율·rate-limit hit |
| Refresh 메트릭 | idempotency hit·daily quota (§9.2) |

**Alert 임계 (권고)**:
- Gemini 실패율 > 5% → alert (정규식 fallback 폭증 신호)
- 사용자 인식 latency P95 > 15s → alert
- F1 fallback 빈도 > 시연 시나리오 임계 → 시나리오 점검

대시보드(Grafana/Datadog): v2 후보 — 현재 미구현.

### 12.8 비기능 acceptance gate (시연 직전 통과 기준)

- 자매 spec §10.7 **P0 테스트 8건** 통과 (S1·S2·S4·S8·S11·S12·S15.1·S15.2).
- 사용자 인식 latency **P95 < 10s** (메시지 → `vote_card`).
- 메모리 누수 없음 (시연 30분 부하 후 RSS 안정).
- Critical 보안 갭 없음 (`JWT_SECRET` prod 변경 완료, 시크릿 평문 노출 없음).

---

## 13. 부록

### 13.1 다이어그램 인덱스

다이어그램 SoT는 `docs/handoff/diagrams/*.mmd` (Mermaid). FigJam은 build artifact — `.mmd` 편집 → diff 승인 → `generate_diagram` MCP 렌더 (CLAUDE.md "다이어그램 작업 규칙").

| 파일 | 다루는 내용 |
|---|---|
| `00-overview.mmd` | 전체 시퀀스 (User → SocialWS → Redis → AgentWS → Gemini → LangGraph → DB) |
| `01-trigger-rules.mmd` | 트리거 규칙 + 4게이트 |
| `02-langgraph-flow.mmd` | 9노드 체인 상세 + `trigger_reason` 분기 (해결점 C·D·E·F·G·I·J) |
| `02-langgraph-flow-annotations.md` | 02 노드별 주석 |
| `03-intent-classifier.mmd` | `classify_intent` 내부 (RAG embed → Gemini → 패턴 3분기) |
| `04-option-c-routing.mmd` | 트리거별 라우팅 통합 |
| `05-full-overview.mmd` | 전체 시스템 한 장 (해결점 A~M 통합) |
| `06-card-update-flow.mmd` | partial 카드 → 수동 입력 → `meeting_id` 갱신 (해결점 J·K) |

### 13.2 마이그레이션 표

`backend/alembic/versions/` (총 22 revisions — PR-X 포함). 모든 마이그레이션 idempotent (`inspector.has_table` / `has_column` 가드, CLAUDE.md "Conventions").

| Revision | 파일명 | 목적 |
|---|---|---|
| `5c2d88f8a524` | `add_users_table` | 초기 users 테이블 |
| `04a69892075f` | `add_sender_to_chat_messages` | 채팅 메시지 sender 필드 |
| `d1e2f3a4b5c6` | `add_rooms_social_meeting_vote_tables` | 방·소셜·meeting·vote 테이블 |
| `d2e3f4a5b6c7` | `add_notifications_table` | 알림 테이블 |
| `d9e0f1a2b3c4` | `add_users_is_guest` | 게스트 사용자 플래그 |
| `9a8b7c6d5e4f` | `add_unique_constraints_for_memberships` | 멤버십 유니크 제약 |
| `9a8b7c6d5e50` | `add_friendship_uniqueness_and_event_starts_at_index` | 친구·이벤트 인덱스 |
| `9a8b7c6d5e51` | `add_meeting_participant_uniqueness_and_schedule_index` | meeting 참가자 유니크·스케줄 인덱스 |
| `a1b2c3d4e5f6` | `add_meeting_reminder_sent` | 모임 알림 발송 플래그 |
| `a2b3c4d5e6f7` | `add_vote_reminder_sent` | 투표 알림 발송 플래그 |
| `b1c2d3e4f5a6` | `add_meeting_vote_fields` | 모임 투표 필드 |
| `b2c3d4e5f6a7` | `add_meeting_preferences` | 모임 선호 (preference_source 등) |
| `b3c4d5e6f7a8` | `add_google_tokens_and_consent` | OAuth 토큰 + `calendar_consent` (default=False) |
| `c1d2e3f4a5b6` | `add_kakao_fields_to_events` | Kakao place_id·place_name |
| `c4d5e6f7a8b9` | `add_intent_examples_table` | RAG intent examples |
| `c5d6e7f8a9b0` | `add_chat_visibility_and_sharing` | 채팅 공개·공유 메타 |
| `e1f2a3b4c5d6` | `add_meeting_google_event_ids` | Google 캘린더 event_id |
| `e5f6a7b8c9d0` | `add_personal_data_columns` | `home_base`·`share_*_data` |
| `e7f8a9b0c1d2` | `add_home_base_and_meeting_end_at` | home_base 좌표·meeting end_at |
| `f4b1c2d3e4f5` | `add_user_food_preferences` | 사용자 음식 선호 |
| `f6a7b8c9d0e1` | `add_share_consent_columns` | share consent 컬럼 분리 |
| `e2a3b4c5d6f7` | `set_calendar_consent_default_true` | **PR-X 신규** — default=True + 일괄 UPDATE (Q11·Q-X1=A) |

### 13.3 환경변수 (마스킹)

`.env.example` 기준 — **값은 노출 X, 키 이름만**. CLAUDE.md "Never": API 키/시크릿 전체 출력 금지.

| 변수 | 용도 | 비고 |
|---|---|---|
| `APP_ENV` | 환경 분기 (`development` / `production`) | prod에서 시크릿 검증 강제 권고 |
| `JWT_SECRET` | JWT 서명 키 | dev fallback 값 prod 배포 금지 (§12.3) |
| `DATABASE_URL` | Postgres 접속 | docker-compose 하드코딩 (CLAUDE.md) |
| `REDIS_URL` | Redis 접속 | docker-compose 하드코딩 |
| `GEMINI_API_KEY` | Gemini 2.5 Flash API | rate limit 시 정규식 fallback (§12.2) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | OAuth 인증 | 테스트 사용자 등록 필요 (CLAUDE.md) |
| `KAKAO_API_KEY` / `KAKAO_REST_API_KEY` / `NEXT_PUBLIC_KAKAO_MAP_KEY` | Kakao Local·Map API | OPEN_MAP_AND_LOCAL 서비스 활성화 필요 |
| `FRONTEND_URL` / `BACKEND_URL` | 서비스 간 URL | docker network 명 의존 |
| `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL` | 프론트 → 백엔드 endpoint | Next.js 빌드 타임 주입 |

### 13.4 용어집

| 용어 | 정의 |
|---|---|
| 매듭 (Maedeup) | 모임 시간·장소 합의 종료 후 발행되는 확정 카드 (도메인 핵심) |
| 매듭 카드 (`maedeup_card`) | `nodes/maedeup.py` 발행 페이로드 (확정 / partial=time_only) |
| 슬롯 (slot) | 후보 시간 구간 (예: 5/19 18:00~20:00) |
| 슬롯 진행 차수 (`slot_filling_turns`) | 같은 정보 재발화 시 acknowledgment 1회 한정 |
| `trigger_reason` | 자동 트리거 분기 키 (`stalemate` / `conclusion_detected` / `all_members_selected` / `direct_request`) |
| direct_request | 사용자 명시 요청 (AI 패널 발화) — `quick_classify` fast path |
| stalemate | 채팅 교착 감지 (`stalemate_judge.py`) |
| conclusion_detected | 합의 발화 감지 ("그럼 ㄱㄱ" 등 — `maedeup_keywords.py`) |
| all_members_selected | TimeBar 멤버 전원 시간 선택 완료 |
| F1~F4 | 시간 fallback (전원 불가 / headcount=None / 단일 슬롯 / 캘린더 권한 없음) |
| F5~F6 | 장소 fallback (`place_hint` 없음 Q2 / cuisine 미감지) |
| 해결점 A~P | `audit-findings.md` 누적 이슈 해결 기록 |
| partial 카드 | `time_only` maedeup (시간만 확정, 장소 pending) |
| `preference_source` | "group" (다수결) vs "speaker" (발화자) — Q5·Q7 |
| Q7-c | `preference_toggle_enabled=false` 트리거 조건 (C1+C3+C4) |
| ACT 0~6 | 시연 시나리오 단계 (`demo-scenario.md`) |
| viewer_user_id | narrator·payload 렌더 컨텍스트 — PII 노출 게이트 (§7.4·§8.6) |

### 13.5 참고 SoT

- `docs/handoff/audit-findings.md` — 해결점 A~P
- `docs/handoff/demo-scenario.md` — 시연 SoT
- `docs/handoff/2026-05-13-recommend-input-catalog.md` — 입력 카탈로그
- `docs/handoff/2026-05-13-pipeline-split-plan.md` — 9노드 분할 계획
- `docs/handoff/2026-05-14-spec-progress.md` — 본 진행 핸드오프
- `CLAUDE.md` — 프로젝트 운영 규칙

---

## 결정 안건 (Open Questions)

> **공통 SoT**: 시간·장소 spec은 모두 본 표를 인용한다. 결정 변경 시 본 표만 수정.

| # | 결정 | 영향 시나리오 | 후보 |
|---|---|---|---|
| Q1 | 슬롯 1개만 남으면? | S5, S9 | **결정: B) 단일 슬롯도 vote_card** (날짜범위 확정 상태 전제) |
| Q2 | `place_hint` 없을 때 fallback 순서 | [`spec-place-recommendation.md §4.4`](./spec-place-recommendation.md) F5, P0-3 | **결정**: 선호 장소 다수결 → 동률 시 발화자 → 선호 없으면 방장 위치 (F5 신설은 PR-2) |
| Q3 | headcount=None 시 기본값 | F2 | **결정: A) 방 멤버 수 사용** (게스트 포함 — Q12=A) |
| Q5 | 발화자 선호 vs 그룹 선호 충돌 시 | P3 | **결정: 다수결 기본 + 발화자 토글 hybrid** (UI 메타 = Q7=B) |
| Q6 | F1 fallback (전원 불가능 시 다수결) 구현 우선순위 | S8 | **결정: A) v1.0 구현 포함** (정렬 = Q8=A) |
| Q7 | Q5 hybrid 토글 UI 메타 키 이름·위치 | 자매 spec §3 페이로드 확장 | **결정: B)** `preference_source: "group"\|"speaker"` + `preference_toggle_enabled: bool`, vote_card·place 양쪽 |
| Q7-b | 토글 동작 범위 | 자매 spec §6 (재발행 흐름), §9 (라우트) | **결정: 방 전체 갱신** (broadcast) — `POST /meetings/{id}/recommendations/refresh` 신설 |
| Q7-c | `preference_toggle_enabled=false` 트리거 조건 (게스트? 그룹·발화자 일치? 발화자 정보 부재?) | 자매 spec §3 페이로드 보강 | **결정: C1 + C3 + C4** (게스트 C2 제외 — 게스트도 채팅방 입장 후 선호 설정 가능). **C1**: 발화자 `share_*_data == False` (PII 동의 안 함). **C3**: 그룹 다수결과 발화자 선호 결과 동일 (의미 없음). **C4**: 발화자 본인 정보(home_base/preferences)가 비어있음 |
| Q8 | F1 fallback 정렬 (멤버 수 동률 시) | 자매 spec §4.4 F1 명세 | **결정: A) 시간 빠른 순** (후보는 이미 선호·거부 반영된 상태 가정) |
| Q9 | partial maedeup(time_only) 발행 후 장소 채워졌을 때 시간 번복 가능? | 자매 spec §5.1.6 ↔ 해결점 K | **결정: A) 번복 불가** (확정 후 잠김, 재추천은 별도 경로) |
| Q10 | 한국 휴일/주말이 장소 추천에도 영향? | 자매 spec §4.3 T·§5.1.4 | **결정: C) Gemini prompt 안내** (Kakao 영업시간 미제공 → 옵션 B 단독 불가, v2 후보) |
| Q11 | 기존 사용자 `calendar_consent` 마이그레이션 전략 (default False → True) | PR-X (별도 마이그레이션) | **결정: A) 일괄 True 자동** (PR-X `9609bee` Alembic `e2a3b4c5d6f7` 적용 완료, 게스트 보호 `WHERE is_guest = FALSE`) |
| Q12 | `headcount` 방 멤버 수 fallback에 게스트 포함 여부 | 자매 spec §5.1.5 headcount | **결정: A) 게스트 포함** (게스트도 매듭 캘린더 불가능 토글로 거부일 입력 가능) |
| Q13 | `recommendations/refresh` 라우트 권한 | §9 API | **결정: B) 발화자 + 방장만** (트리거 최소 권한) |
| Q14 | refresh 호출 제한 | §9 API | **결정: C) Redis idempotency 캐시 + 일일 100회** (같은 source/scope 조합은 캐시 hit) |
| Q15 | 토글 재발행 narrator 문구 | 자매 spec §3 narrator | **결정: A) "OOO님 선호 기준으로 다시 추천했어요"** (실명 명시 — PII 노출 트레이드오프, 사용자 토글 행동의 투명성 우선) |
| Q16 | F1 `blocker_notification_payload` UI 멤버 식별 | 자매 spec §3 페이로드, UI | **결정: C) 기본 익명 + 더보기 실명** (기본 "1명 불참", 사용자 의도로 클릭 시 실명 — 점진 공개) |
| Q17 | F4 캘린더 권한 만료 narrator 실명/익명 | [`spec-time-coordination.md §6.7`](./spec-time-coordination.md), §8.6 | **결정: A) 실명** ("OOO님 캘린더 권한이 만료됐어요"). Q15=A 일관 + 액션 가능성 우선. 2026-05-15 사용자 확정 (`docs/DECISIONS.md` SoT와 동기화, §9.7 권고 A 본 적용) |
| Q-X1 | PR-X 마이그레이션 시 기존 명시 거부 사용자(`calendar_consent=False`) 처리 | PR-X | **결정: A) 일괄 True 재설정** (opt-out 모델 일관성, 사용자가 다시 토글 가능) |

---

## 변경 이력

- 2026-05-14 — PR-0: spec rename + 해결점 N (`494807e`)
- 2026-05-14 — PR-1.5: §5 재구조 (`89571d4`)
- 2026-05-14 — PR-1.6~1.8: 결정 안건 갱신
- 2026-05-14 — PR-X: `calendar_consent` 마이그레이션 (`9609bee`, `e2a3b4c5d6f7`)
- 2026-05-14 — PR-Y1·Y2: F1 fallback 백엔드·프론트
- 2026-05-14 — PR-2: §1~§4 시간+장소 보강 (헤더·§1.1~1.3·§2 S11~S14·§3 페이로드 4종(vote_card / place_recommendation / maedeup_card 확정·partial) + narrator 통합·§4 R/P/T/F 매트릭스 R7~R9·P4~P6·T6~T8·F5~F6 신설). Q7-c 결정 (C1 + C3 + C4, 게스트 C2 제외).
- 2026-05-14 — PR-3.2: §7 권한·접근 조건 본문 작성 (§7.1 역할 정의·§7.2 권한 매트릭스 15행·§7.3 멤버십 검증·§7.4 viewer_user_id privacy·§7.5 refresh 권한 Q13=B·§7.6 토글 차단 Q7-c·§7.7 게스트 정책·§7.8 WS 채널·§7.9 §8 위임 요약). Q12=A·Q13=B·Q14=C·Q15=A·Q16=C 반영.
- 2026-05-14 — PR-3.3: §8 데이터 정책 본문 작성 (§8.1 opt-out 동의 모델·§8.2 is_ai_filled UI 정책·§8.3 k-anonymity 가드·§8.4 Redis 캐시 PII·§8.5 동의 철회 SLA·§8.6 narrator PII 통합(Q15=A·F4·F1)·§8.7 게스트 보관·§8.8 PII 보존 표·§8.9 알려진 갭 8건). Q-X1=A 결정 반영, Q17(F4 narrator 실명/익명) 신규 미결 등록.
- 2026-05-14 — PR-3.4: §9 API·이벤트·로그 본문 작성 (§9.1 엔드포인트 인벤토리 7개 라우터·§9.2 신규 refresh 라우트 명세 Q13=B·Q14=C·§9.3 WebSocket 채널·이벤트·§9.4 구조화 로그(노드 latency·F1~F5·해결점)·§9.5 audit log·§9.6 에러 응답 형식·§9.7 F4 narrator 권고 A 적용·§9.8 갭 7건). Q13·Q14·Q15·Q7-b·Q7-c 반영, Q17 권고 A 적용(미결 명시).
- 2026-05-14 — PR-3.5: §10 회귀 테스트 케이스 본문 작성 (§10.1 단위/통합 전략·§10.2 fixture 패턴(신규 fixture 7종)·§10.3 S1~S14 pytest 매핑 표 14행·§10.4 S15 refresh 5종·negative test 5종·§10.5 로그·메트릭 assert·§10.6 동시성·§10.7 P0/P1/P2 우선순위·§10.8 v2 backlog). 모든 결정 사항(Q1·Q2·Q3·Q6·Q7·Q7-b·Q7-c·Q8·Q9·Q12·Q13·Q14·Q15·Q16·Q17 권고 A)을 회귀 검증용으로 명문화.
- 2026-05-14 — PR-4: §12 비기능 요구사항 + §13 부록 신설 (§12.1 성능 P50/P95 표·§12.2 가용성 graceful degradation·§12.3 보안(JWT·OAuth·API 키·rate limit)·§12.4 프라이버시 요약·§12.5 접근성 WCAG 2.1 AA 권고·§12.6 다국어·§12.7 관측성 메트릭/alert·§12.8 acceptance gate·§13.1 다이어그램 인덱스 8종·§13.2 마이그레이션 22 revisions·§13.3 환경변수 마스킹·§13.4 용어집·§13.5 변경 이력·§13.6 참고 SoT). 기능정의서 v1.0 §1~§13 완성.
- 2026-05-14 — PR-V: 기능정의서 3-파일 분할 (`spec-time-and-place.md` → `spec-time-coordination.md` + `spec-place-recommendation.md` + `spec-common.md`). 시간/장소 spec 분리, 공통 정책(권한·데이터·API·비기능·부록·결정 안건·변경 이력)은 본 문서(`spec-common.md`)에 단일 SoT로 통합. cross-reference 헤더 명시.
