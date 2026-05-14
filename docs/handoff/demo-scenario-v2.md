# 통합 시연 시나리오 v2 — "오랜만의 동아리 회식, 매듭이 다 해줌"

**컨셉**: 평범한 회식 잡기 한 번에 매듭의 핵심 기능(Personal Data 추출·F1 다수결·자연어 거부·hybrid 토글·rejected_places 재추천·실명 narrator)이 모두 자연스럽게 노출.

**예상 시간**: 4분 30초 ~ 5분 (budget 목표)

**룸 수**: 1개 (집중도 ↑, 시연 부담 ↓)

**v1 대비 추가 ACT**: ACT 0.5(Personal Data 모달) · ACT 2.5(F1 다수결) · ACT 5.5(hybrid 토글 + F4 narrator)

---

## 참여자

| 멤버 | 역할 | Personal Data 시드 (사전 ✨) |
|---|---|---|
| 지민 | 방장 ✅ | 한식·강남·저녁형 ✨ |
| 수현 | 멤버 ✅ | 채식·홍대 비선호 ✨ |
| 민수 | 멤버 ✅ | 지하철 ✨ |
| 예린 | **게스트** (앱 없음, 카톡 링크) | — |

> **사전 시드 (D-1)**: `docker exec maedeup-api python -m scripts.seed_demo_personal_data --room <id>` — ACT 0.5 ✨ 노출 + ACT 5 reasoning 이름 인용 + ACT 5.5 hybrid 토글 활성 조건 충족용.

---

## 흐름 한눈에

```
ACT 0.5  Personal Data 모달 사전 투어     40s   [6 카테고리 ✨ 추출 모달]
ACT 1    모임 생성 + 초대 + 게스트        25s   [플로팅바 + InviteModal + 카톡 링크]
ACT 2    채팅 교착 → 자연어 거부 → 확장   40s   [stalemate + 강한 거부 패턴 + N + P]
ACT 2.5  F1 다수결 fallback 발동         30s   [전원 가능 0 → majority_fallback vote_card]
ACT 4    Partial 카드 발행               10s   [선호 장소 비어있음 → I]
ACT 5    AI 패널 단축 + 장소 확정         30s   [direct_request + reasoning ✨ + E + J]
ACT 5.5  hybrid 토글 + F4 실명 narrator  25s   [Q5 토글 → OOO님 선호 기준 + calendar F4]
마무리                                   10s   [카드 라이프사이클 클로징]
총합                                    ~4:50
```

---

## ACT 0.5. Personal Data 모달 사전 투어 (40초)

### 시나리오 흐름

발표 시작 전 이미 로그인된 지민 계정으로 메인화면에 진입. 상단 PersonalData 위젯에 ✨ 3개 항목(한식·강남·저녁형)이 표시되어 있다. 해당 위젯을 클릭해 6 카테고리 상세 모달을 펼친다.

> **목적**: "AI가 이전 모임 채팅에서 자동 학습한 데이터"임을 청중에게 먼저 각인. ACT 5 장소 추천 reasoning이 왜 수현님 이름을 언급하는지 복선 역할.

### 자동화 step

수동 액션 (시연자 마우스 클릭). `.gstack-demo.py`는 ACT 0.5를 포함하지 않음 — 시연자가 직접 메인 ✨ 위젯 클릭 → 모달 열기.

### 백엔드 호출 흐름

해당 없음 (프론트 렌더만). 시드 데이터는 D-1에 `seed_demo_personal_data` 스크립트로 미리 주입 완료. `GET /api/v1/users/me/personal-data` 호출로 6 카테고리 JSON 반환.

### 발표자 narration

> *"화면 보시면 ✨ 아이콘이 있어요. 이건 매듭이 이전 모임 채팅에서 자동으로 추출한 개인 선호 데이터입니다. 지민이 경우 한식 선호, 강남 지역, 저녁 모임형 — 전부 예전 채팅에서 뽑아온 거예요. 총 6개 카테고리가 있는데 식습관·이동수단·선호 지역 같은 것들입니다."*

### 시청자가 보는 화면

- `ExplorePage` → PersonalData 위젯 ✨ 배지 3개
- 클릭 시 6 카테고리(food_preferences / food_restrictions / liked_areas / disliked_areas / transport_mode / preferred_time_slots) 상세 모달
- 각 항목 옆 `is_ai_filled=True` 표시 (✨ 아이콘)

---

## ACT 1. 모임 생성 + 친구 초대 + 게스트 (25초)

### 시나리오 흐름

지민이 플로팅 바에서 모임을 생성하고, 수현·민수는 앱 알림으로 입장, 예린은 카톡 링크로 게스트 입장한다. 선호도 팝업에서 **선호 장소를 비워둔다** — ACT 4 Partial 카드 분기를 유발하는 핵심 조건.

### 자동화 step

`.gstack-demo.py` ACT 1 블록 실행:
- 플로팅 바 "모임 생성" 클릭
- 모임명 `동아리 종강 회식` / 카테고리 식사 / 친구 체크 (수현·민수)
- 선호도 팝업: 가능 시간 `평일 저녁`, **선호 장소 공란**
- InviteModal → 카톡 게스트 링크 복사 (예린용)
- 수현·민수: 알림 클릭 → 입장 + 선호도 (장소 공란)
- 예린: 카톡 링크 → 닉네임 `예린` → 게스트 입장 (`rooms.py:202~244`, synthetic email `guest-{uuid12}@maedeup.local`, `is_guest=True`)

### 백엔드 호출 흐름

1. `POST /api/v1/rooms` → room 생성, `RoomMember.role=owner`
2. 수현·민수: `POST /api/v1/rooms/{id}/members`
3. 예린: `POST /api/v1/rooms/{id}/guests/join` (`rooms.py:178~298`) → JWT 발급
4. 각 멤버: `POST /api/v1/meetings/preferences` → `MeetingPreference` upsert (장소 공란 상태)

### 발표자 narration

> *"모임 만들고 친구 초대. 수현·민수는 앱 알림으로, 예린이는 앱 없어서 카톡 링크로 게스트 참여합니다."*

### 시청자가 보는 화면

- 채팅방 생성 + 멤버 4명 입장
- 예린 옆 "게스트" 배지
- 캘린더 패널 초기 상태

---

## ACT 2. 채팅 교착 → 강한 자연어 거부 → 다음주 자동 확장 (40초)

### 시나리오 흐름

4명이 차례로 채팅을 보낸다. 수현과 예린이 5/13~5/16을 모두 강하게 거부하는 메시지를 보내 후보 슬롯 대부분이 소진된다. 교착 감지 후 AI가 자동 개입하고, 거부된 날짜들이 캘린더에 빨간 카운트로 동기화된다. 남은 후보(5/11~5/16)가 전원 소진되면 **다음주 자동 확장(해결점 N)**으로 이어진다.

> **#4 자연어 거부 강화 포인트**: "동아리 MT", "본가", "쉬고 싶다"에 더해 수현이 "5/13·5/14·5/15·5/16 다 안 됨"처럼 날짜를 직접 열거하는 강한 거부 패턴을 추가. Gemini가 rejected_dates로 추출하는 깊이를 청중에게 시각적으로 보여줌.

### 자동화 step

`.gstack-demo.py` ACT 2 블록 — 채팅 4메시지 순차 전송:

```
지민: "다들 시험 끝나고 한번 보자!"
수현: "5/8 금요일은 동아리 MT라 안 되고, 5/13·5/14·5/15·5/16도 시험 기간이라 다 안 돼"
민수: "9일은 본가 내려가야 해서 패스"
예린: "10일 토요일은 좀 쉬고 싶다… 다음주도 사실 5/11 빼고 다 바빠"
```

→ 4번째 메시지 전송 후 `after_trigger=14.0`초 대기 → vote_card 또는 자동 확장 응답 수신.

### 백엔드 호출 흐름

1. 메시지 4건 WebSocket `social` 채널 전송 → `social.py` stalemate 카운터 누적 (임계값 4, 해결점 A)
2. 임계값 도달 → `judge_stalemate` LLM 호출 → `stalemate_judged` trigger_reason 주입
3. `run_pipeline` 진입:
   - `entity_extraction` 노드: Gemini가 "동아리 MT·본가·쉬고 싶다·5/13·5/14·5/15·5/16 다 안 됨·5/11 빼고 다 바빠" → `rejected_dates` 배열 추출
   - `slot_filling` 노드: `trigger_reason="stalemate_judged"` 분기 → 후보 슬롯 필터링
   - 후보 소진 → 해결점 N: 다음 주(5/19~5/23)로 범위 자동 확장
4. 해결점 P: rejected_dates → calendar WebSocket broadcast → 캘린더 패널 5/8·5/9·5/10·5/13~5/16 빨간 카운트 표시

**AI narrator (vote_card_creation 노드 출력)**:
```python
# vote_card.py:335 — stalemate + 다수결 아닌 정상 확장 케이스
narrator = f"캘린더 확인 결과, {best_label}을(를) 추천드려요. 📅 아래에서 확인해주세요."
```
best_label 예시: `"5월 19일 (월) 19:00"` — 다음주 첫 가용 슬롯.

### 발표자 narration

> 1. *"4번째 메시지에서 자동 개입. 카톡이라면 흐지부지 됐을 거예요."*
> 2. *"'동아리 MT', '본가', '쉬고 싶다' — 거부 발언을 정확히 이해해서 후보에서 제외하고 캘린더에 빨간 카운트로 동기화됩니다. 수현이는 날짜까지 직접 열거했는데 그것도 다 잡아냅니다."*
> 3. *"이번 주가 다 안 되니까 매듭이 알아서 다음주로 후보를 확장합니다."*

### 시청자가 보는 화면

- AI 패널: `"캘린더 확인 결과, 5월 19일 (월) 19:00을(를) 추천드려요. 📅 아래에서 확인해주세요."` (또는 다음주 날짜)
- 채팅 스크롤 끝에 assistant 메시지 말풍선
- 캘린더: 5/8·5/9·5/10·5/13~5/16 빨간 카운트 뱃지 (해결점 P)
- vote_card 또는 ACT 2.5로 자연스럽게 전환

---

## ACT 2.5. F1 다수결 fallback 발동 (30초)

### 시나리오 흐름

ACT 2의 강한 거부 패턴 결과 **전원 가능 슬롯 = 0개** 상황이 발생한다. 28일 확장 후에도 전원 가능 슬롯이 없으면 (Q-Y4 결정) **F1 다수결 fallback**이 발동하여 가장 많은 멤버가 가능한 3개 슬롯을 담은 vote_card가 발행된다. 각 슬롯에 배지와 불참자 토글이 표시된다.

> **별도 room 셋업 없음**: ACT 2의 채팅 거부 패턴이 충분히 강하므로 자연스럽게 유도. 시드 데이터·추가 방 불필요.

### 자동화 step

ACT 2에서 이어지는 자동 흐름 — 추가 step 없음. 단, 시연자는 vote_card의 `calendar_strategy` 값을 확인해 `"majority_fallback"` 임을 청중에게 구두로 설명.

`.gstack-demo.py` `after_trigger` 대기 완료 후 vote_card WebSocket 이벤트 수신 → `ScheduleRecommendationCard` 자동 렌더.

### 백엔드 호출 흐름

1. `slot_filling` → 28일 전체 확장 후에도 `len(calendar_free_slots) == 0`
2. `state["calendar_strategy"] = "majority_fallback"` 세팅 → `vote_card_creation` 진입
3. `vote_card_creation` 노드 (`vote_card.py:229~231`):
   ```python
   is_majority_fallback = state.get("calendar_strategy") == "majority_fallback"
   # majority_fallback이면 슬롯 수와 무관하게 항상 투표 카드 발행
   ```
4. F1 narrator (`vote_card.py:329`):
   ```python
   if state.get("calendar_strategy") == "majority_fallback":
       narrator = "전원 가능한 시간이 없어 다수결로 추천드려요. 가장 많은 멤버가 가능한 3개 시간 중 골라주세요. 📅"
   ```
5. vote_card 페이로드 (`vote_card.py:294~321`):
   ```python
   state["vote_card_payload"] = {
       "type": "vote_card",
       "title": "모임 시간 투표",
       "calendar_strategy": "majority_fallback",
       "time_options": [
           {
               "slot_id": ...,
               "label": ...,
               "available_count": 3,   # Q-Y1: 가능 멤버 수
               "total_count": 4,
               "unavailable_users": ["예린"],  # Q-Y1: 불참자 실명
           },
           ...
       ],
       "preference_source": compute_preference_source(state),   # "group"
       "preference_toggle_enabled": compute_preference_toggle_enabled(state),
   }
   ```
6. Redis publish → WebSocket broadcast → 프론트 `ScheduleRecommendationCard` 수신

**프론트 렌더 (ScheduleRecommendationCard.tsx:225~291)**:
- `isMajorityFallback = voteCard.calendar_strategy === "majority_fallback"` → 배너 모드 활성
- `renderAvailabilityBadge`: 슬롯별 `available_count/total_count` 배지 (초록 3/4·앰버 2/4·레드 1/4)
- `renderUnavailableToggle`: 불참자 수 표시 → 클릭 시 실명 펼침 (Q16=C, `expandedUnavailableSlotId`)

### 발표자 narration

> *"이번엔 전원이 다 안 되는 최악의 케이스입니다. 매듭은 포기하지 않고 '가장 많은 멤버가 가능한 시간' 다수결로 투표 카드를 발행합니다. 각 슬롯에 몇 명이 가능한지 배지로 보이고, '2명 불참' 클릭하면 누가 못 오는지도 볼 수 있어요."*

### 시청자가 보는 화면

- AI 패널 메시지: `"전원 가능한 시간이 없어 다수결로 추천드려요. 가장 많은 멤버가 가능한 3개 시간 중 골라주세요. 📅"`
- vote_card 상단 배너 (majority_fallback 모드)
- 슬롯 3개 + 각 슬롯에 `3/4명 가능` (초록) · `2/4명 가능` (앰버) 배지
- 불참자 토글 버튼 `👤 1명 불참` → 클릭 시 `불참: 예린` 펼침

---

## ACT 4. Partial 카드 발행 (10초)

### 시나리오 흐름

ACT 2/2.5에서 일정이 합의되면(vote_card 확정 또는 all_members_selected trigger) 선호 장소가 비어있으므로 **Partial 매듭 카드**가 발행된다. 시간은 확정됐지만 장소 정보가 없는 상태임을 보여준다.

### 자동화 step

`.gstack-demo.py` ACT 4 블록: vote_card 확정 버튼 클릭 (`POST /api/v1/meetings/confirm`) → maedeup_card(partial) WebSocket 이벤트 수신.

### 백엔드 호출 흐름

1. `POST /api/v1/meetings/confirm` → `MeetingSchedule.status = "pending"` 갱신
2. `all_members_selected` 또는 confirm 후 `trigger_reason="conclusion_detected"` 발동
3. `maedeup_card_creation` 노드 (`maedeup.py:74`):
   ```python
   if state.get("partial_mode") == "time_only":
       payload = {
           "type": "maedeup_card",
           "place_pending": True,
           "place_pending_message": "멤버들이 장소를 정하면 자동으로 정리해드릴게요!",
           ...
       }
   ```
4. DB `scheduled_at` / `end_at` 동기화 (`maedeup.py:125~148`, P0 fix)

### 발표자 narration

> *"선호 장소를 안 정했어도 일단 시간만 카드로 발행합니다. 장소는 AI 추천으로 채울 수 있어요."*

### 시청자가 보는 화면

- maedeup_card: `"5/19 (월) 19:00 ✅"` + `"멤버들이 장소를 정하면 자동으로 정리해드릴게요!"` (place_pending 배너)

---

## ACT 5. AI 패널 단축 경로 → Personal Data 활용 → 장소 확정 (30초)

### 시나리오 흐름

지민이 AI 패널에 "강남에서 다 같이 갈만한 한식집"이라고 직접 입력한다. `direct_request` 단축 경로로 빠르게 장소 카드가 발행되고, reasoning에 수현님 채식·홍대 비선호 ✨가 인용된다. 지민이 장소를 선택해 확정하면 같은 meeting_id의 maedeup_card가 partial → 완성으로 진화한다.

### 자동화 step

`.gstack-demo.py` ACT 5 블록:
- AI 패널 입력: `"강남에서 다 같이 갈만한 한식집"`
- `after_place_query=16.0`초 대기
- place_recommendation 카드 수신 → view_pause=3s
- 첫 번째 장소명 클릭 → PlaceDetailPane
- "이 장소로 확정" 버튼 클릭 (`PATCH /api/v1/meetings/{id}/place`)
- `after_place_confirm=8.0`초 대기

### 백엔드 호출 흐름

1. AI 패널 메시지 → `quick_classify` → `direct_request_kind="place"` 판정 → `direct_request` trigger_reason
2. `entity_extraction` 노드: `place_hint="강남"`, `meeting_type="식사"`, `headcount=4`
3. `place_recommendation` 노드 (`place.py:151~492`):
   - `_get_room_member_constraints_named` → `per_user_constraints` (수현: 채식, 홍대 비선호)
   - `_build_named_constraints_summary` → `group_constraints_summary`:
     ```
     "수현님 채식·홍대 비선호 ✨ 반영. 강남 한식 중 채식 옵션 있는 곳 위주."
     ```
   - `_ml_place_search` (사용 가능 시) 또는 Gemini scoring
   - `_compute_final_score`: `0.4 * ml_score + 0.3 * gemini_score + 0.3 * distance_score` (Q4=A)
   - narrator (`place.py:477`): `"{hint} 근처 추천 장소 {count}개를 정리했어요. 아래 카드에서 확인해 주세요."` → 예: `"강남 근처 추천 장소 5개를 정리했어요."`
4. 장소 확정: `PATCH /api/v1/meetings/{id}/place` (`meetings.py:788~914`)
   - DB `location_name` / `location_address` / `kakao_place_id` 갱신
   - `_publish_maedeup_place_update` → maedeup_card `place_pending=False` broadcast
   - `_asyncio.create_task(_spawn_personal_data_extraction(room_id))` — ACT 6 학습 fire-and-forget

**단축 경로 latency**: `direct_request` 분기 → entity→place→maedeup 3 노드만 통과, 평균 3~5초 (일반 경로 6~15초).

### 발표자 narration

> 1. *"의도가 명확하니까 단축 경로 — 보통 6~15초에서 3~5초로 줄어듭니다."*
> 2. **(임팩트 ↑↑)** *"reasoning 보세요 — '수현님 채식'. 수현이 한 마디도 안 했는데, 이전 모임에서 학습된 ✨ 데이터로 자동 반영됐어요."*
> 3. *"같은 카드가 partial → 완성으로 진화하는 거 보이시죠. 새 카드 쌓이는 게 아니라 모임의 라이프사이클입니다."*

### 시청자가 보는 화면

- AI 패널 narrator: `"강남 근처 추천 장소 5개를 정리했어요. 아래 카드에서 확인해 주세요."`
- PlaceRecommendationCard:
  - `group_constraints_summary` 박스: `"수현님 채식·홍대 비선호 ✨ 반영. 강남 한식 중 채식 옵션 있는 곳 위주."`
  - 장소 5개 carousel (각 점수 배지 표시)
  - Q5 hybrid 토글 버튼 (preference_toggle_enabled=true 시 노출) → ACT 5.5에서 사용
- 확정 후 maedeup_card: `place_pending=False` → 장소명 표시 완성

---

## ACT 5.5. Q5 Hybrid 토글 + F4 캘린더 narrator (25초)

### 시나리오 흐름

장소 카드가 발행된 후, 지민이 그룹 다수결 추천 대신 **"내 선호 기준"으로 다시 보고 싶어** 토글을 클릭한다. `POST /meetings/{id}/recommendations/refresh`가 발동하고, narrator가 "지민님 선호 기준으로 다시 추천했어요"라고 실명으로 안내한다. 이어서 F4 시나리오(캘린더 만료 안내)를 한 줄로 자연스럽게 언급한다.

> **#1 Q5 hybrid 토글** + **#5 rejected_places 재추천** 포인트.
> **Q17=A**: F4 narrator는 실명 표기 — "OOO님 캘린더 권한이 만료됐어요" (시연에서는 자연스럽게 한 줄 멘트로만 처리).

### 자동화 step

수동 액션 (시연자 클릭). `.gstack-demo.py`에 미포함.

지민이 PlaceRecommendationCard의 `[그룹 다수결] [내 선호]` 토글 중 **"내 선호"** 클릭.

```
POST /api/v1/meetings/{meeting_id}/recommendations/refresh
Body:
{
  "scope": "place_recommendation",
  "preference_source": "speaker",
  "requester_user_id": <지민 user_id>
}
```

### 백엔드 호출 흐름

1. `refresh_recommendations` 라우트 (`meetings.py:1050~1264`):
   - **권한 검증 (Q13=B)**: `is_requester = viewer_user_id == body.requester_user_id` → 지민 본인이므로 통과
   - **Q7-c 차단 검증**: `compute_preference_toggle_enabled(probe_state)` — 지민의 `home_base=강남`, `food_preferences=[한식]` + `share_*_data=True` → C1·C4 미해당, C3 `_lightweight_speaker_matches_group` 비교 후 결과 상이 → `True` (토글 활성)
   - **Rate limit (Q14=C)**: Redis `refresh_count:{user_id}:{date}` INCR, 일일 100회 상한
   - **Idempotency**: Redis `refresh:{user_id}:{meeting_id}:place_recommendation:speaker` 5분 TTL 캐시
2. `run_pipeline` 재호출: `trigger_reason="preference_toggle"`, `preference_source="speaker"`, `partial_mode="place_only"`
3. `place_recommendation` 노드: `requester_home_base="강남"`, `requester_preferences.food_preferences=["한식"]` → 지민 기준 필터링 + ranking
4. **narrator 발행 (Q15=A, `meetings.py:1202~1205`)**:
   ```python
   if body.preference_source == "speaker":
       narrator = f"{requester_name}님 선호 기준으로 다시 추천했어요"
       # 실제 출력: "지민님 선호 기준으로 다시 추천했어요"
   ```
5. **방 전체 broadcast (Q7-b)**: Redis `agent:{room_id}` 채널에 새 place_recommendation payload 및 narrator 발행
6. **rejected_places 처리 (spec §6.15)**: 지민이 "나 비린 거 별로야. 회집은 빼자" 채팅을 이미 보낸 경우 `rejected_places` 누적 → `_filter_out_rejected_places` (`place.py:406~408`) 호출로 회(海鮮) 카테고리 제거 후 재추천 carousel 갱신

**F4 narrator (Q17=A)**: 캘린더 consent 만료 시 (`meetings.py` 캘린더 sync 분기):
```
"지민님 캘린더 권한이 만료됐어요"
```
시연에서는 토글 시연 직후 한 줄 멘트로 자연스럽게 언급.

### 발표자 narration

> 1. *"'내 선호' 토글로 나한테 맞는 추천으로 바꿔볼 수도 있어요. 클릭하면 지민 기준으로 다시 계산해서 '지민님 선호 기준으로 다시 추천했어요'라고 안내합니다."*
> 2. *"'회집은 빼자'처럼 거절 발언을 하면 해당 장소가 제외되고 새 carousel이 올라옵니다."*
> 3. (F4 한 줄) *"만약 캘린더 연동 권한이 만료됐다면 '지민님 캘린더 권한이 만료됐어요'처럼 실명으로 안내합니다."*

### 시청자가 보는 화면

- PlaceRecommendationCard 토글: `[그룹 다수결] [내 선호]` → "내 선호" 활성(인디고 배경)
- `preference_source="speaker"` 갱신된 새 carousel 렌더 (top 순위 변경 가능)
- AI 패널 narrator 말풍선: `"지민님 선호 기준으로 다시 추천했어요"`
- (rejected_places 있는 경우) 회집 제거된 refreshed carousel

---

## 마무리 (10초)

### 발표자 narration

> *"같은 카드가 partial → 완성으로 진화했고, ✨ 데이터는 다음 모임 때 또 쓰입니다. 카톡과 다른 점 셋 — 자동 개입, 자연어 이해, AI 학습/활용. 이게 매듭입니다."*

### 시청자가 보는 화면

- maedeup_card 완성 상태 (날짜 + 장소명 + 캘린더 등록 여부)
- 메인화면 복귀 시 MeetingList 누적 + MiniCalendar 점 표시

---

## 노출되는 기능 매트릭스

| 카테고리 | 노출 | ACT |
|---|---|---|
| **Personal Data 6 카테고리** | 추출 모달 시연 (✨ 배지) | 0.5 |
| **메인 위젯** | PersonalData ✨ · MeetingList · MiniCalendar · 플로팅 바 | 0.5 · 1 |
| **게스트 흐름** | 카톡 링크 → 닉네임 → JWT (`rooms.py:202~244`) | 1 |
| **트리거 3종** | `stalemate_judged` · `all_members_selected` · `direct_request` | 2 · (3) · 5 |
| **자연어 거부** | Gemini rejected_dates 추출 + 캘린더 동기화 (해결점 P) | 2 |
| **후보 확장 (N)** | rejected 소진 → 다음주 자동 확장 | 2 |
| **F1 다수결 fallback** | 전원 가능 0 → `majority_fallback` vote_card + 배지 + 불참자 토글 (Q6=A·Q-Y1·Q16=C) | 2.5 |
| **카드 라이프사이클** | partial → place 확정 → maedeup 갱신 (같은 meeting_id, 해결점 J) | 4 · 5 |
| **단축 경로** | `direct_request` → 3~5초 (해결점 E) | 5 |
| **Personal Data 활용** | reasoning 실명 인용 `group_constraints_summary` | 5 |
| **Q5 hybrid 토글** | `preference_source` 토글 → refresh → 실명 narrator (Q5·Q7=B·Q13=B·Q14=C·Q15=A) | 5.5 |
| **rejected_places 재추천** | 거절 누적 → `_filter_out_rejected_places` → 새 carousel | 5.5 |
| **F4 실명 narrator (Q17=A)** | 캘린더 만료 → "OOO님 캘린더 권한이 만료됐어요" | 5.5 |

---

## 시간 배분표

| ACT | 내용 | 예상 시간 |
|---|---|---|
| 0.5 | Personal Data 모달 투어 | 40초 |
| 1 | 모임 생성 + 초대 + 게스트 | 25초 |
| 2 | 채팅 교착 → 자연어 거부 → 다음주 확장 | 40초 |
| 2.5 | F1 다수결 fallback 발동 | 30초 |
| 4 | Partial 카드 발행 | 10초 |
| 5 | AI 패널 단축 + Personal Data + 장소 확정 | 30초 |
| 5.5 | hybrid 토글 + F4 narrator + 마무리 | 25초 + 10초 |
| **합계** | | **~4분 50초** |

---

## 백업 시나리오 (장애 대응)

### B-1. Gemini rate limit

- **증상**: place_recommendation 응답 지연 30초+, 또는 `ServiceUnavailable`
- **대응**: `DEMO_FALLBACK_ENABLED=true` 환경변수 확인 → Gemini 호출 없이 패턴 기반 scoring만 사용
- **시연자 멘트**: *"지금 AI 엔진 부하가 걸려서 패턴 기반으로 바로 보여드릴게요."*
- **ACT 5.5 추가 백업**: refresh 호출 시 Gemini rate limit → 캐시된 place payload 반환 (Idempotency TTL 5분 내 동일 요청은 cached=true)

### B-2. Kakao Map empty

- **증상**: 장소 카드 `"강남 근처 추천 장소 0개"` 메시지
- **원인**: Kakao Local API 네트워크 문제 또는 `KAKAO_REST_API_KEY` 미설정
- **대응**: `.env`의 `KAKAO_REST_API_KEY` 확인 후 `docker restart maedeup-api`
- **시연자 멘트**: *"지금 지도 API 연결이 잠깐 끊겼어요. 재시도하면 됩니다."*

### B-3. WebSocket disconnect

- **증상**: 채팅 메시지 전송 후 AI 응답 없음
- **대응**: 브라우저 새로고침 → WS 재연결. `GET /api/v1/meetings/rooms/{room_id}/pending-vote` 및 `/pending-place`로 카드 복구 (Redis 캐시)
- **시연자 멘트**: *"네트워크가 잠깐 끊겼는데 새로고침하면 카드가 복원됩니다."*

### B-4. F1 fallback 미발동 (vote_card 정상 발행)

- **증상**: 강한 거부 패턴에도 전원 가능 슬롯이 존재 → 정상 vote_card 발행
- **대응**: ACT 2.5 대신 정상 vote_card를 그대로 사용 → ACT 4로 바로 진행
- **시연자 멘트**: *"이번엔 전원이 가능한 슬롯이 있어서 다수결 없이 바로 추천해드렸어요."*
- **준비**: D-1에 게스트 2명의 rejected_dates를 더 촘촘히 시드해두면 F1 발동 확률 ↑

### B-5. hybrid 토글 비활성 (ACT 5.5)

- **증상**: `preference_toggle_enabled=false` → 토글 버튼 미노출
- **원인**: Q7-c 차단 조건 C1(share_data=False), C3(그룹=발화자), C4(발화자 prefs 없음) 중 하나
- **대응**: ACT 5.5 토글 부분 스킵 → F4 narrator 한 줄 멘트만 진행
- **예방**: D-1 시드에 지민 `share_food_data=true`, `home_base="강남"`, `food_preferences=["한식"]` 포함 확인

### B-6. rejected_places carousel 미갱신

- **증상**: "회집은 빼자" 발화 후 carousel에 회(海鮮) 매장이 여전히 노출
- **원인**: `state["rejected_places"]` 미주입 또는 `_filter_out_rejected_places` 조건 불일치
- **대응**: ACT 5.5에서 rejected_places 데모 생략 → hybrid 토글 시연만 진행

### B-7. LIMIT-7 free-slots 1095ms 지연

- **증상**: ACT 2 캘린더 패널 초기 로드 1초+ 대기
- **영향**: 시연 흐름상 큰 영향 없음 (발표자가 설명하는 동안 로드 완료)
- **대응**: 필요 시 D-1에 `docker exec maedeup-api` 에서 free-slots warm 호출로 Redis 캐시 준비

---

## v1 대비 변경 사항

| # | 구분 | v1 | v2 |
|---|---|---|---|
| 1 | **Personal Data 투어** | ACT 0 메인 투어 30초 중 짧은 언급 | **ACT 0.5 신설 (40초)** — 6 카테고리 모달 전개, reasoning 복선 |
| 2 | **F1 다수결 fallback** | 시나리오 없음 | **ACT 2.5 신설 (30초)** — 강한 거부 패턴 → 전원 가능 0 → majority_fallback vote_card + 배지 + 불참자 토글 |
| 3 | **Q5 hybrid 토글** | 미포함 | **ACT 5.5 신설 (25초)** — 토글 클릭 → refresh API → "지민님 선호 기준으로 다시 추천했어요" 실명 narrator + rejected_places 재추천 |
| 4 | **F4 실명 narrator (Q17=A)** | 미포함 | **ACT 5.5 한 줄** — "OOO님 캘린더 권한이 만료됐어요" |
| 5 | **총 시간** | 약 3분 30초 | **약 4분 50초** (목표 4:30~5:00 달성) |

---

## 시연 사전 체크리스트

### Docker / 서버

- [ ] `docker compose up -d` → 4개 컨테이너(fastapi-app·frontend·postgres-db·redis-broker) `Up` 상태
- [ ] `curl http://localhost:8000/health` → `{"status": "ok"}`
- [ ] `curl http://localhost:3000` → 매듭 메인화면 정상 응답

### JWT / 인증

- [ ] `.gstack-demo-token` 파일에 지민 JWT 저장 (만료 확인 — 보통 30분)
- [ ] 지민 계정 Google OAuth 연동 완료 (`calendar_consent=True`)
- [ ] 수현·민수 계정 앱 로그인 세션 유효

### Personal Data 시드 (D-1)

- [ ] `docker exec maedeup-api python -m scripts.seed_demo_personal_data --room <room_id>` 실행 완료
- [ ] 지민: `food_preferences=["한식"]`, `liked_areas=["강남"]`, `preferred_time_slots=["저녁"]`, `share_food_data=True`, `share_location_data=True`, `home_base="강남"`
- [ ] 수현: `food_preferences=["채식"]`, `disliked_areas=["홍대"]`, `share_food_data=True`
- [ ] 민수: `transport_mode=["지하철"]`
- [ ] `GET /api/v1/users/me/personal-data` 응답에 위 데이터 포함 확인

### room / 모임 상태

- [ ] 시연용 방 ID 메모 (`.gstack-demo.py` 실행 전 방 생성 확인)
- [ ] 이전 시연 잔여 `pending` MeetingSchedule 없음 (`GET /api/v1/meetings/rooms/{id}/pending-vote` → null)

### MCP / 자동화

- [ ] Playwright MCP `browser_navigate http://localhost:3000` 정상 응답
- [ ] `.gstack-browser-launch.py` Windows PowerShell `.venv\Scripts\python.exe`로 실행 (BUG-1: WSL에서는 실행 금지)
- [ ] `.gstack-demo.py` dry-run `--fast` 모드로 1회 검증

### 브랜드 / UI

- [ ] 화면 확대 150%~175% (발표 프로젝터 가독성)
- [ ] 다크모드 해제 (Tailwind 기본 라이트)
- [ ] 사이드 패널(AI 어시스턴트) 열려있는 상태로 시작

---

## 시연 후 정리 절차

1. **방 데이터 초기화**: `DELETE /api/v1/rooms/{demo_room_id}` (방장 권한) 또는 DB 직접 삭제
2. **Redis 캐시 정리**: `docker exec maedeup-redis redis-cli FLUSHDB` (시연 rate limit 카운터 포함)
3. **Personal Data 재시드 (다음 시연 준비)**: `seed_demo_personal_data` 스크립트 재실행
4. **JWT 갱신**: `.gstack-demo-token` 파일의 JWT 만료 여부 확인 후 갱신
5. **로그 확인**: `docker logs maedeup-api --tail 100` — P0 에러 없음 확인
6. **snapshot 저장**: Playwright MCP로 주요 화면 스크린샷 6장 이상 `docs/handoff/screenshots/` 보관
