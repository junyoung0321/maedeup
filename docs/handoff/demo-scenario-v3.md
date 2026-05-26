# 통합 시연 시나리오 v3 — "오랜만의 동아리 회식, 매듭이 다 해줌"

**컨셉**: 평범한 회식 잡기 한 번에 매듭의 핵심 기능(Personal Data 추출·F1 다수결·시간대 변경 투표·hybrid 토글·rejected_places 재추천·실명 narrator)이 모두 자연스럽게 노출.

**예상 시간**: 약 5분 25초 (budget 약간 넘음 — 발표자 트림 여지)

**룸 수**: 1개 (집중도 ↑, 시연 부담 ↓)

**v2 대비 추가 ACT**: ACT 3 신설 (시간대 변경 → 시간 투표 → 결과 합의 → 시간 확정)

**변경 이력**:
- 2026-05-15 ACT 3 update: vote 직접 호출 → TimeBar 합의 흐름으로 변경. `.gstack-demo.py` ACT 3 동기 적용 완료.
- 2026-05-16 Option C 반영: ACT 3 확정 버튼 → "이 시간으로 확정" (TimeBar 내 호스트 전용); 캘린더 셀 빨간 배지 제거; 시연 D-Day 갱신 (2026-05-22).
- 2026-05-16 ACT 2 자연 표현 + 5/18 기준 갱신: 발화를 날짜 나열 → 자연 한국어 표현으로 교체; 5/18(월) 촬영일 기준 날짜 환산 및 vote_card 슬롯 후보 추가.
- 2026-05-16 정합성 7건 fix (D-1~D-7): ACT 0.5·5.5 자동화 표기; ROOM_NAME "이번 주 저녁 약속"; 선호 장소 강남 입력·Partial 분기 설명 갱신; guest-join API 경로; ACT 3 슬롯 분산값 (수현 0~5·민수 20~23·예린 21~25·호스트 20~24); TimeBar selector -mine-20/-mine-24.

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
ACT 3    시간대 변경 → TimeBar 합의 → 확정  35s   [★신설] ["시간대 변경" 클릭 → TimeBarSelector → WS time_selection → 슬롯 클릭 → consensus → 확정]
ACT 4    Partial 카드 발행               10s   [시간 확정 후 Partial maedeup]
ACT 5    AI 패널 짧은 입력 → 장소 확정    30s   ["강남 한식 추천해줘" 입력 → carousel → 확정]
ACT 5.5  hybrid 토글 + F4 실명 narrator  25s   [Q5 토글 → OOO님 선호 기준 + calendar F4]
마무리                                   10s   [카드 라이프사이클 클로징]
총합                                  ~5분 25초
```

---

## ACT 0.5. Personal Data 모달 사전 투어 (40초)

### 시나리오 흐름

발표 시작 전 이미 로그인된 지민 계정으로 메인화면에 진입. 상단 PersonalData 위젯에 ✨ 3개 항목(한식·강남·저녁형)이 표시되어 있다. 해당 위젯을 클릭해 6 카테고리 상세 모달을 펼친다.

> **목적**: "AI가 이전 모임 채팅에서 자동 학습한 데이터"임을 청중에게 먼저 각인. ACT 5 장소 추천 reasoning이 왜 수현님 이름을 언급하는지 복선 역할.

### 자동화 step

자동화 포함 (`--skip-act-0-5` 플래그로 수동 전환 가능). 시연자가 직접 메인 ✨ 위젯 클릭 → 모달 열기.

### 백엔드 호출 흐름

해당 없음 (프론트 렌더만). 시드 데이터는 D-1에 `seed_demo_personal_data` 스크립트로 미리 주입 완료. `GET /api/v1/users/me/personal-data` 호출로 6 카테고리 JSON 반환.

### 발표자 narration

> *"화면 보시면 ✨ 아이콘이 있어요. 이건 매듭이 이전 모임 채팅에서 자동으로 추출한 개인 선호 데이터입니다. 지민이 경우 한식 선호, 강남 지역, 저녁 모임형 — 전부 예전 채팅에서 뽑아온 거예요. 총 6개 카테고리가 있는데 식습관·이동수단·선호 지역 같은 것들입니다."*

### 시청자가 보는 화면

- `ExplorePage` → PersonalData 위젯 ✨ 배지 3개
- 클릭 시 6 카테고리(food_preferences / food_restrictions / liked_areas / disliked_areas / transport_mode / time_preference) 상세 모달
- 각 항목 옆 `is_ai_filled=True` 표시 (✨ 아이콘)

---

## ACT 1. 모임 생성 + 친구 초대 + 게스트 (25초)

### 시나리오 흐름

지민이 플로팅 바에서 모임을 생성하고, 수현·민수는 앱 알림으로 입장, 예린은 카톡 링크로 게스트 입장한다. 선호도 팝업에서 지민은 **선호 장소 `강남` 입력**, 수현·민수는 장소 공란으로 제출한다. ACT 4 Partial 카드는 선호 장소 유무와 무관하게 `partial_mode="time_only"` (시간 확정 후 장소 미확정 상태) 분기로 발행된다.

### 자동화 step

`.gstack-demo.py` ACT 1 블록 실행:
- 플로팅 바 "모임 생성" 클릭
- 모임명 `이번 주 저녁 약속` / 카테고리 식사 / 친구 체크 (수현·민수)
- 선호도 팝업: 가능 시간 `평일 저녁`, **선호 장소 `강남` 입력** (지민 preferred_location="강남")
- InviteModal → 카톡 게스트 링크 복사 (예린용)
- 수현·민수: 알림 클릭 → 입장 + 선호도 (장소 공란 — best_location 미등록)
- 예린: 카톡 링크 → 닉네임 `예린` → 게스트 입장 (`rooms.py:202~244`, synthetic email `guest-{uuid12}@maedeup.local`, `is_guest=True`)

### 백엔드 호출 흐름

1. `POST /api/v1/rooms` → room 생성, `RoomMember.role=owner`
2. 수현·민수: `POST /api/v1/rooms/{id}/members`
3. 예린: `POST /api/v1/rooms/{id}/guest-join` (`rooms.py:176~298`) → JWT 발급
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

4명이 차례로 채팅을 보낸다. 수현·민수·예린이 자연 한국어 표현("내일", "이번주", "다음주")으로 거부해 후보 슬롯 대부분이 소진된다. 교착 감지 후 AI가 자동 개입하고, 거부된 날짜들이 캘린더에 동기화된다. 남은 후보가 전원 소진되면 **다음주 자동 확장(해결점 N)**으로 이어진다.

> **5/18(월) 촬영 기준 발화**: "내일" = 5/19(화), "이번주 수·목·금" = 5/20·21·22, "다음주 월·화" = 5/25·26, "다음주 수요일" = 5/27, "다음주 화요일" = 5/26, "다음주 토요일" = 5/31.
> **자연 표현 포인트**: 날짜 직접 열거 대신 "내일", "이번주", "다음주" 같은 구어체를 사용. Gemini가 상대 시간 표현(relative date)을 절대 날짜로 해석하는 능력을 보여줌.

### 자동화 step

`.gstack-demo.py` ACT 2 블록 — 채팅 4메시지 순차 전송:

```
지민: "다들 시험 끝나고 한번 보자!"
수현: "내일은 동아리 MT라 안 되고, 이번주 수·목·금도 시험 기간이라 다 안 돼. 다음주 월·화도 발표 준비 때문에 일정 잡혀있어"
민수: "다음주 수요일은 본가 내려가야 해서 패스"
예린: "다음주 화요일은 좀 쉬고 싶다… 다음주 토요일 빼고 다 바빠"
```

> **5/18 기준 날짜 환산**:
> - 수현 거부: 5/19(화) MT, 5/20·21·22(수·목·금) 시험기간, 5/25·26(다음주 월·화) 발표 준비
> - 민수 거부: 5/27(다음주 수) 본가
> - 예린 거부: 5/26(다음주 화) 쉬고싶음, "다음주 토요일 빼고 다 바빠" → 5/31 외 전부 거부

→ 4번째 메시지 전송 후 `after_trigger=14.0`초 대기 → vote_card 또는 자동 확장 응답 수신.

### vote_card 슬롯 후보 (예상, 5/18 실행 기준)

| 날짜 | 불가 멤버 | 가용 인원 |
|---|---|---|
| 5/25 (다음주 월) | 수현 거부 | 3/4 |
| 5/26 (다음주 화) | 수현·예린 거부 | 2/4 |
| 5/27 (다음주 수) | 민수 거부 | 3/4 |
| 5/28 (다음주 목) | 거부 없음 | **4/4** (best slot 후보) |
| 5/29 (다음주 금) | 거부 없음 | **4/4** |
| 5/31 (다음주 토) | 예린 가능 ("토요일 빼고") + 나머지 | 4/4 |

> `majority_fallback` 발동 시: 전원 가능 슬롯이 없으면 가장 많은 멤버 가능 순으로 top 3 선출.
> 5/28·5/29·5/31이 4/4 → 정상 vote_card(전원 가능) 또는 4/4 베스트 슬롯 직접 발행 가능성 있음.

### 백엔드 호출 흐름

1. 메시지 4건 WebSocket `social` 채널 전송 → `social.py` stalemate 카운터 누적 (임계값 4, 해결점 A)
2. 임계값 도달 → `judge_stalemate` LLM 호출 → `stalemate_judged` trigger_reason 주입
3. `run_pipeline` 진입:
   - `entity_extraction` 노드: Gemini가 "내일(MT)·이번주 수·목·금(시험)·다음주 월·화(발표)·다음주 수(본가)·다음주 화(쉬고 싶다)·다음주 토요일 빼고 다 바빠" → 상대 날짜를 절대 날짜로 변환 후 `rejected_dates` 배열 추출
   - `slot_filling` 노드: `trigger_reason="stalemate_judged"` 분기 → 후보 슬롯 필터링
   - 후보 소진 → 해결점 N: 다음 주(5/25~5/31)로 범위 자동 확장
4. 해결점 P: rejected_dates → calendar WebSocket broadcast → 캘린더 패널 셀에 X/Y 가용 인원 배지 갱신 (빨간 카운트 배지 제거, commit `bc315f1` — `_compute_day_avail` blocked_today 중복 표시였음)

**AI narrator (vote_card_creation 노드 출력)**:
```python
# vote_card.py:335 — stalemate + 다수결 아닌 정상 확장 케이스
narrator = f"캘린더 확인 결과, {best_label}을(를) 추천드려요. 📅 아래에서 확인해주세요."
```
best_label 예시: `"5월 28일 (목) 19:00"` — 다음주 첫 전원 가용 슬롯.

### 발표자 narration

> 1. *"4번째 메시지에서 자동 개입. 카톡이라면 흐지부지 됐을 거예요."*
> 2. *"'내일', '이번주 수·목·금', '다음주 월·화' — 자연스러운 말로 해도 거부 날짜를 정확히 이해해서 후보에서 제외하고 캘린더에 동기화합니다."*
> 3. *"이번 주가 다 안 되니까 매듭이 알아서 다음주로 후보를 확장합니다."*

### 시청자가 보는 화면

- AI 패널: `"캘린더 확인 결과, 5월 28일 (목) 19:00을(를) 추천드려요. 📅 아래에서 확인해주세요."` (또는 다음주 날짜)
- 채팅 스크롤 끝에 assistant 메시지 말풍선
- 캘린더: 5/19·5/20·5/21·5/22·5/25·5/26·5/27 셀에 `X/Y` 가용 인원 배지 표시 (해결점 P)
  - 4/4 = 초록, 3/4 이하 = 노란색(#eab308). **빨간 "1" 카운트 배지는 제거됨** (commit `bc315f1`)
  - "X일 안돼" 발언자는 셀 클릭 → detail panel "🚫 불가능 표시" 섹션에서 확인
- vote_card 또는 ACT 2.5로 자연스럽게 전환

---

## ACT 2.5. F1 다수결 fallback 발동 (30초)

### 시나리오 흐름

ACT 2의 강한 거부 패턴 결과 **전원 가능 슬롯 = 0개** 상황이 발생한다. 28일 확장 후에도 전원 가능 슬롯이 없으면 **F1 다수결 fallback**이 발동하여 가장 많은 멤버가 가능한 3개 슬롯을 담은 vote_card가 발행된다. 각 슬롯에 배지와 불참자 토글이 표시된다.

> **별도 room 셋업 없음**: ACT 2의 채팅 거부 패턴이 충분히 강하므로 자연스럽게 유도. 시드 데이터·추가 방 불필요.

### 자동화 step

ACT 2에서 이어지는 자동 흐름 — 추가 step 없음. `.gstack-demo.py` `after_trigger` 대기 완료 후 vote_card WebSocket 이벤트 수신 → `ScheduleRecommendationCard` 자동 렌더.

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
- 방장(지민) 화면: **"○월 ○일로 확정"** 버튼 + **"시간대 변경"** 버튼 두 개 표시

---

## ACT 3. ★신설 — 시간대 변경 → TimeBar 합의 → 호스트 확정 (35초)

> **2026-05-15 update**: vote 직접 호출 → TimeBar 합의 흐름으로 변경. `.gstack-demo.py` ACT 3 동기 적용 완료.
> **2026-05-16 update (Option C)**: 확정 버튼 위치·텍스트 변경 — InfoPane A3-2 "추천 시간 그대로 확정" → TimeBar 카드 내 호스트 전용 "이 시간으로 확정" 버튼으로 교체. TimeBar unmount 시점도 확정 후로 변경.
> **코드 근거**: `ScheduleRecommendationCard.tsx:511~546` — `isHost` 조건 시 두 버튼 렌더. `InfoPane.tsx:406` — `scheduleConsensus + isHost` 조건 (fallback 용). TimeBar 카드 내 보라색 "이 시간으로 확정" 버튼 (commit `ffd4e1f`, `aac6303`).

### 시나리오 흐름

방장 지민이 vote_card 추천 슬롯(예: 오후 6시)을 확인하고 **"시간대 변경"** 버튼을 클릭한다. InfoPane에 TimeBarSelector 카드가 마운트되어 각 멤버의 가능 시간대를 시각화한다. 게스트 3명이 가능 시간을 WS로 전송하면 TimeBar "다른 분들" row가 파란색으로 채워진다. 방장이 TimeBar 슬롯을 클릭하면 "전원" row가 초록색으로 활성화(consensus)되고, TimeBar 카드 내 보라색 안내 박스 "✅ 모두 시간대를 골랐어요" 와 호스트 전용 **"이 시간으로 확정"** 버튼이 노출된다. 방장이 버튼을 눌러 시간을 확정한다.

> **게스트 화면**: TimeBar 그대로 유지. 회색 안내 박스 "⏳ 방장 확정 대기 중 — 시간은 자유롭게 변경 가능합니다" 표시. "이 시간으로 확정" 버튼 미노출.
> **호스트 재선택**: 잘못 골랐으면 시작 슬롯 재클릭 → range 재선택 가능 (TimeBar unmount 안 됨).

### 자동화 step (`.gstack-demo.py` ACT 3 블록)

**step 0**: ScheduleRecommendationCard의 추천 슬롯(예: 오후 6시) 재확인. 화면 5초 시청 (TimeBar 등장 전 렌더 확인).

**step 1**: 호스트가 "시간대 변경" 버튼 클릭
- `InfoPane`의 `voteAwaitingTimeMeetingId` 세팅 → 캘린더 패널에 TimeBarSelector 카드 마운트
- 클릭 후 5초 시청 (TimeBar 렌더 확인)

**step 2**: 게스트 3명이 각자 WS로 `time_selection` 송신 (자동화 시뮬레이션)
- WS URI: `ws://localhost:8000/ws/social/{room_id}?token={게스트_token}`
- 수현: `{"type":"time_selection","date":"YYYY-MM-DD","start":0,"end":5}` (오전 9:00~11:30)
- 민수: `{"type":"time_selection","date":"YYYY-MM-DD","start":20,"end":23}` (오후 7:00~8:30)
- 예린: `{"type":"time_selection","date":"YYYY-MM-DD","start":21,"end":25}` (오후 7:30~9:30)
- 효과: TimeBar "다른 분들" row가 차례로 파란색으로 채워짐 (`peer_time_selection` broadcast)
- 게스트 사이 2.5초 간격, 3명 완료 후 4초 시청

**step 3**: 호스트가 Playwright로 TimeBar 슬롯 클릭 (시연 핵심 시각화)
- selector: `[id$="-mine-20"]` (start), `[id$="-mine-24"]` (end)
- aria-label fallback: `"내 시간 19:00"`, `"내 시간 21:00"`
- 호스트 WS 송신: `{"type":"time_selection","date":"YYYY-MM-DD","start":20,"end":24}` (오후 7:00~9:00)
- start 클릭 후 0.8초 (시연 페이스), end 클릭
- 효과: "내 시간" row + "전원" row 초록색 활성 (consensus 도달)
- 클릭 후 5초 시청

**step 4**: TimeBar 카드 내 "이 시간으로 확정" 버튼 5초 대기 → 호스트 클릭
- consensus 달성 후 TimeBar 카드 내 보라색 안내 박스 + 호스트 전용 보라색 **"이 시간으로 확정"** 버튼 노출 (commit `ffd4e1f`, `aac6303`)
- 5초 대기 후 클릭 (시연 시각 인지용)
- 클릭 → `POST /api/v1/rooms/{roomId}/schedule-confirm` (mode=auto) → `setInfoPanePhase("timeConfirmed")` → TimeBar unmount → `maedeup_card (partial)` 발행
- **fallback** (TimeBar 버튼 미활성 시): A3-2 카드 "추천 시간 그대로 확정" 버튼 (`InfoPane.tsx:406`, `scheduleConsensus + isHost` 조건) 클릭
- 클릭 후 5초 시청 (maedeup_card partial 시청)

**step 5**: `act3_completed = True` → ACT 4 (Partial maedeup_card) 자동 진행

### 시연 화면 전환 흐름

```
화면 1: vote_card 추천 슬롯 (6시) 확인
화면 2: "시간대 변경" 클릭 → vote_card "시간대 합의 중..." placeholder
화면 3: TimeBarSelector 카드 마운트 (캘린더 패널)
화면 4: 게스트 "다른 분들" row 파란색 채워짐
화면 5: 호스트 슬롯 클릭 → "내 시간" + "전원" row 초록 (consensus)
화면 6: TimeBar 카드 내 보라색 안내 박스 "✅ 모두 시간대를 골랐어요 — 위 그래프 확인 후 확정해주세요" + "이 시간으로 확정" 버튼 활성 → 클릭
  ↳ 게스트 화면: 회색 박스 "⏳ 방장 확정 대기 중 — 시간은 자유롭게 변경 가능합니다" (버튼 없음)
화면 7: TimeBar unmount → maedeup_card partial 발행 (ACT 4 진입)
```

### 백엔드 호출 흐름

1. **"시간대 변경" 클릭**: 프론트 상태 전환만 (API 호출 없음). `MeetingContext.requestTimeChange` → `voteAwaitingTimeMeetingId = meetingId`
2. **게스트 WS `time_selection` 송신**: `social` 채널 수신 → `peer_time_selection` broadcast → TimeBar "다른 분들" row 갱신
3. **호스트 슬롯 클릭 → TimeBar consensus**: 프론트 상태 내 `scheduleConsensus=true` 세팅 → TimeBar 카드 내 보라색 "이 시간으로 확정" 버튼 노출 (호스트 전용). 게스트 화면엔 회색 안내 박스만 표시.
4. **확정 API** (`POST /api/v1/rooms/{roomId}/schedule-confirm`, mode=auto) → `setInfoPanePhase("timeConfirmed")` → TimeBar unmount → `maedeup_card (partial)` 발행.
   - (기존 fallback) `meetings.py:414`:
   - `meeting.status = MeetingStatus.confirmed`, `meeting.scheduled_at = scheduled_at`
   - AI 패널 안내 (`meetings.py:537~555`): `"✅ 일정이 확정되었어요 — {time_label}"` + `"이제 어디서 만날지 정해볼까요?"`
   - Google Calendar fan-out (동의 멤버 대상, `sync_events_for_meeting_members`)
5. **ACT 4로 전환**: 확정 직후 `maedeup_card (partial)` 자동 발행 (선호 장소 공란 → `place_pending=True`)

### 발표자 narration

> 1. *"'시간대 변경' 버튼을 누르면 타임바가 뜹니다. 멤버들이 각자 가능한 시간대를 선택하면 파란색으로 차오르거든요."*
> 2. *"게스트 3명이 가능 시간을 보내니까 '다른 분들' 줄이 파랗게 채워지죠. 실시간이에요."*
> 3. *"방장이 슬롯을 클릭하면 전원 줄이 초록색으로 바뀝니다 — 합의가 된 거예요."*
> 4. *"전원 줄이 초록이 되면 '이 시간으로 확정' 버튼이 나타납니다. 클릭하면 확정되고, 캘린더 연동된 멤버 캘린더에도 자동 등록돼요."*

### 시청자가 보는 화면

- vote_card → `"시간대 합의 중..."` placeholder (지민 화면)
- TimeBarSelector 카드: "다른 분들" row (파랑), "내 시간" row (회색 → 초록), "전원" row (초록)
- 호스트 슬롯 클릭 후 consensus 달성: 전원 row 초록 활성
- **호스트 화면**: TimeBar 카드 유지 (unmount 안 됨) + 보라색 안내 박스 "✅ 모두 시간대를 골랐어요 — 위 그래프 확인 후 확정해주세요" + 보라색 "이 시간으로 확정" 버튼 등장
- **게스트 화면**: TimeBar 유지 + 회색 안내 박스 "⏳ 방장 확정 대기 중 — 시간은 자유롭게 변경 가능합니다" (버튼 없음)
- 확정 클릭 후 TimeBar unmount → 확정 후 AI 패널: `"✅ 일정이 확정되었어요 — 5월 22일 (금) 오후 12:00"` (시연 날짜 기준) + `"이제 어디서 만날지 정해볼까요? 장소를 추천해드릴게요."`

---

## ACT 4. Partial 카드 발행 (10초)

### 시나리오 흐름

ACT 3에서 시간이 확정되면 선호 장소가 비어있으므로 **Partial 매듭 카드**가 발행된다. 시간은 확정됐지만 장소 정보가 없는 상태임을 보여준다. AI 패널 안내 메시지("장소를 추천해드릴게요")가 ACT 5 진입을 자연스럽게 유도한다.

### 자동화 step

ACT 3 확정에서 자동 이어짐 — 별도 자동화 step 없음. 확정 직후 `maedeup_card (partial)` WebSocket 이벤트 자동 수신.

### 백엔드 호출 흐름

1. `POST /api/v1/meetings/confirm` 응답 후 프론트 `refreshCalendar()` 호출
2. `all_members_selected` 또는 `conclusion_detected` trigger로 pipeline 재진입 → `maedeup_card_creation` 노드
3. `maedeup.py:74`:
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

> *"선호 장소를 안 정했어도 일단 시간만 카드로 발행합니다. AI가 '장소를 추천해드릴게요'라고 하네요 — 바로 물어볼게요."*

### 시청자가 보는 화면

- maedeup_card: `"5/19 (월) 19:00 ✅"` + `"멤버들이 장소를 정하면 자동으로 정리해드릴게요!"` (place_pending 배너)

---

## ACT 5. AI 패널 짧은 입력 → Personal Data 활용 → 장소 확정 (30초)

### 시나리오 흐름

지민이 AI 패널에 **"강남 한식 추천해줘"**라고 짧게 입력한다. `direct_request` 단축 경로로 빠르게 장소 카드가 발행되고, reasoning에 수현님 채식·홍대 비선호 ✨가 인용된다. 지민이 장소를 선택해 확정하면 같은 meeting_id의 maedeup_card가 partial → 완성으로 진화한다.

> **v2 대비 변경**: 입력 텍스트 단순화 — "강남에서 다 같이 갈만한 한식집" → **"강남 한식 추천해줘"**.
> 짧은 한 마디로도 AI가 컨텍스트(방 선호 데이터·이전 채팅)를 읽어 장소를 추천한다는 인상 강조.
>
> **D-1 보강 (QA v3 권고)**: `"추천해줘"` 단독 입력은 `quick_classify` regex(`backend/app/services/pipeline/nodes/quick_classify.py:14~22`) 사각지대로 cuisine·장소 키워드 매치 실패 → Gemini fallback 1.5s + general 분류 진입 → latency 6초+. 반드시 `"강남 한식 추천해줘"`로 입력. 단독 `"추천해줘"`는 백업 B-9로 우회.

### 자동화 step

`.gstack-demo.py` ACT 5 블록:
- AI 패널 입력: `"강남 한식 추천해줘"` (cuisine "한식" 매치 → place 0.9 정상 분류)
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

> 1. *"'강남 한식 추천해줘' — 짧은 한 마디로도 AI가 알아서 찾아줍니다. 이전에 확정된 모임 컨텍스트를 이미 알고 있거든요."*
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
> **Q17=A**: F4 narrator는 실명 표기 — "OOO님 캘린더 권한이 만료됐어요".

### 자동화 step

자동화 포함 (`--skip-act-5-5` 플래그로 수동 전환 가능). 단 `PREFERENCE_TOGGLE_ENABLED=false` 환경에서는 토글 미노출로 자동 BACKUP 스킵.

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
   - **Q7-c 차단 검증**: `compute_preference_toggle_enabled(probe_state)` — 지민의 `home_base=강남`, `food_preferences=[한식]` + `share_*_data=True` → `True` (토글 활성)
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
6. **rejected_places 처리 (spec §6.15)**: 지민이 "나 비린 거 별로야. 회집은 빼자" 채팅을 이미 보낸 경우 `rejected_places` 누적 → `_filter_out_rejected_places` 호출로 회(海鮮) 카테고리 제거 후 재추천 carousel 갱신

**F4 narrator (Q17=A)**: 캘린더 consent 만료 시 (`meetings.py` 캘린더 sync 분기):
```
"지민님 캘린더 권한이 만료됐어요"
```

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
- AI 패널 마지막 멘트: "✨ 매듭 완성! [확정 시간] [확정 장소]에서 만나요"
- 메인화면 복귀 시 MeetingList 누적 + MiniCalendar 점 표시

---

## 노출되는 기능 매트릭스

| 카테고리 | 노출 | ACT |
|---|---|---|
| **Personal Data 6 카테고리** | 추출 모달 시연 (✨ 배지) | 0.5 |
| **메인 위젯** | PersonalData ✨ · MeetingList · MiniCalendar · 플로팅 바 | 0.5 · 1 |
| **게스트 흐름** | 카톡 링크 → 닉네임 → JWT (`rooms.py:202~244`) | 1 |
| **트리거 3종** | `stalemate_judged` · `all_members_selected` · `direct_request` | 2 · 3 · 5 |
| **자연어 거부** | Gemini rejected_dates 추출 + 캘린더 동기화 (해결점 P) | 2 |
| **후보 확장 (N)** | rejected 소진 → 다음주 자동 확장 | 2 |
| **F1 다수결 fallback** | 전원 가능 0 → `majority_fallback` vote_card + 배지 + 불참자 토글 | 2.5 |
| **★시간대 변경 → TimeBar 합의** | "시간대 변경" 클릭 → TimeBarSelector 마운트 → 게스트 WS time_selection → 호스트 슬롯 클릭 → consensus → "추천 시간 그대로 확정" | **3 (신설)** |
| **카드 라이프사이클** | partial → place 확정 → maedeup 갱신 (같은 meeting_id, 해결점 J) | 4 · 5 |
| **단축 경로** | `direct_request` → 3~5초 (해결점 E) | 5 |
| **Personal Data 활용** | reasoning 실명 인용 `group_constraints_summary` | 5 |
| **Q5 hybrid 토글** | `preference_source` 토글 → refresh → 실명 narrator | 5.5 |
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
| **3** | **★시간대 변경 → TimeBar 합의 → 호스트 확정** | **35초** |
| 4 | Partial 카드 발행 | 10초 |
| 5 | AI 패널 단축 입력 + Personal Data + 장소 확정 | 30초 |
| 5.5 | hybrid 토글 + F4 narrator + 마무리 | 25초 + 10초 |
| **합계** | | **~5분 25초** |

> **발표자 트림 포인트**: ACT 3의 WS time_selection 단계(게스트 3명)를 1명으로 줄이거나 step 2를 스킵하면 약 10~15초 절감 → 5분 10초.

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
- **대응**: ACT 2.5 대신 정상 vote_card를 그대로 사용 → ACT 3으로 바로 진행 (정상 vote_card에서도 "시간대 변경" 버튼 노출됨)
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
- **대응**: 필요 시 D-1에 `docker exec maedeup-api`에서 free-slots warm 호출로 Redis 캐시 준비

### B-8. ★ACT 3 TimeBar 합의 미작동 (신설)

- **증상 유형 1**: "시간대 변경" 버튼 클릭 후 `voteAwaitingTimeMeetingId` 설정은 됐으나 TimeBarSelector가 마운트되지 않음
  - **원인**: `InfoPane`의 `schedule` 컨텍스트 모드 미전환 (MeetingContext `setContextMode("schedule")` 미호출)
  - **대응**: 브라우저 새로고침 후 vote_card 상태 복구(`GET /api/v1/meetings/rooms/{id}/pending-vote`) → 다시 "시간대 변경" 클릭
- **증상 유형 2**: 게스트 WS `time_selection` 송신 후 TimeBar "다른 분들" row가 파랗게 채워지지 않음
  - **원인**: WS 연결 실패 또는 `peer_time_selection` broadcast 누락
  - **대응**: 게스트 토큰 유효성 확인 → WS 재연결 후 재송신
- **증상 유형 3**: 호스트 슬롯 클릭 후 "전원" row 초록 미활성 (consensus 미달성)
  - **원인**: selector `[id$="-mine-18"]` 매칭 실패 (UI 구조 변경) 또는 aria-label 불일치
  - **대응**: Playwright `browser_snapshot` → 실제 slot id 확인 후 selector 수정
- **증상 유형 4**: "이 시간으로 확정" 버튼 미노출 (`scheduleConsensus` 미세팅 또는 TimeBar 카드 Option C 미반영)
  - **원인 A**: `scheduleConsensus=true` 미세팅 → consensus 달성 조건 미충족
  - **원인 B**: 프론트 빌드 stale (BUILD_ID 미갱신) → Option C 코드 미반영
  - **대응 1**: 타임아웃 5초 대기 → TimeBar 내 버튼 미등장 시 InfoPane A3-2 "추천 시간 그대로 확정" 버튼 폴백 (`InfoPane.tsx:406`, `scheduleConsensus + isHost` 조건) 클릭
  - **대응 2**: 버튼 전혀 없으면 ACT 3 생략 → ACT 2.5 vote_card "○월 ○일로 확정" 버튼 직접 클릭 → ACT 4로 진행
  - **시연자 멘트**: *"'시간대 변경' 대신 바로 확정하는 경우엔 이렇게 한 번에 됩니다."*
- **증상 유형 5**: ACT 3 전체 생략 (시간 부족 또는 UI 오류)
  - **대응**: ACT 2.5 vote_card에서 "○월 ○일로 확정" 버튼 직접 클릭 → `POST /api/v1/meetings/confirm` → ACT 4로 바로 진행

### B-9. ★ACT 5 `"추천해줘"` 단독 입력 시 분류 실패 (신설)

- **증상**: ACT 5에서 시연자가 `"추천해줘"`만 입력 → `quick_classify` regex (`backend/app/services/pipeline/nodes/quick_classify.py:14~22`) 의 cuisine·장소 키워드 매치 실패 → Gemini fallback 1.5s → general 분류 진입 → AI 패널 응답 6초+ 또는 `"무엇을 도와드릴까요?"` 같은 generic 메시지 노출
- **원인**: `_PLACE_RE` 정규식이 "추천" 키워드만으로는 place 도메인 식별 불가. cuisine 또는 지역명 동반 필요
- **대응**: 즉시 `"강남 한식 추천해줘"`로 재입력. 1~2초 안에 재분류 완료, 정상 0.9 score로 place 진입
- **시연자 멘트**: *"아, 너무 짧게 입력했네요. '강남 한식 추천해줘'로 다시 한 번."*
- **예방**: D-1 권고대로 시연 입력 텍스트를 `"강남 한식 추천해줘"`로 강제 (시나리오 ACT 5 본문에 명시됨)

---

## 시연 사전 체크리스트

> **시연 일정**: 2026-05-22 (금) 점심. 오늘(2026-05-16) 기준 D-6. D-1 준비일 = 2026-05-21 (목).

### Docker / 서버

- [ ] `docker compose up -d` → 4개 컨테이너(fastapi-app·frontend·postgres-db·redis-broker) `Up` 상태
- [ ] `curl http://localhost:8000/health` → `{"status": "ok"}`
- [ ] `curl http://localhost:3000` → 매듭 메인화면 정상 응답

### JWT / 인증

- [ ] `.gstack-demo-token` 파일에 지민 JWT 저장 (만료 확인 — 보통 30분)
- [ ] **지민·수현·민수 3명 모두 Google OAuth 연동 완료 + `calendar_consent=True` 사전 확인** — `SELECT id, name, calendar_consent FROM users WHERE id IN (지민, 수현, 민수)` 또는 `GET /api/v1/users/{id}` 응답 점검 (QA v3 D-1 권고 — ACT 2.5 `majority_fallback` 발동 안정성 위해 `busy_by_user` non-empty 보장)
- [ ] 예린(게스트)는 OAuth 불필요 — `is_guest=True` 확인
- [ ] 수현·민수 계정 앱 로그인 세션 유효
- [ ] ACT 3 자동화용 수현·민수·예린 JWT 별도 저장 (WS time_selection 송신 시 각자 계정 토큰 필요)

### Personal Data 시드 (D-1)

- [ ] `docker exec maedeup-api python -m scripts.seed_demo_personal_data --room <room_id>` 실행 완료
- [ ] 지민: `food_preferences=["한식"]`, `liked_areas=["강남"]`, `time_preference="저녁"`, `share_food_data=True`, `share_location_data=True`, `home_base="강남"`
- [ ] 수현: `food_preferences=["채식"]`, `disliked_areas=["홍대"]`, `share_food_data=True`
- [ ] 민수: `transport_mode=["지하철"]`
- [ ] `GET /api/v1/users/me/personal-data` 응답에 위 데이터 포함 확인 (실제 엔드포인트는 `/api/v1/users/me/profile` 또는 `/api/v1/users/me` — 코드 확인 권고. `is_ai_filled` dict 필드는 `UserProfileResponse:91` 노출)
- [ ] **Calendar busy 시드 (D-1 보강, QA v3 권고)**: ACT 2.5 `majority_fallback` 발동 안정성을 위해 지민·수현·민수 캘린더에 5/13~5/16 + 5/19·5/20 busy 이벤트 사전 시드. 자동 시드 스크립트 없으면 Google Calendar 직접 등록 또는 `docker exec maedeup-api python -m scripts.seed_demo_calendar_busy` 신설 검토.

### room / 모임 상태

- [ ] 시연용 방 ID 메모 (`.gstack-demo.py` 실행 전 방 생성 확인)
- [ ] 이전 시연 잔여 `pending` MeetingSchedule 없음 (`GET /api/v1/meetings/rooms/{id}/pending-vote` → null)
- [ ] ACT 3용 WS time_selection 자동화: 수현·민수·예린 각 JWT로 `ws://localhost:8000/ws/social/{room_id}?token={token}` 연결 + `{"type":"time_selection","date":"YYYY-MM-DD","start":18,"end":23}` 송신 준비

### MCP / 자동화

- [ ] Playwright MCP `browser_navigate http://localhost:3000` 정상 응답
- [ ] `.gstack-browser-launch.py` Windows PowerShell `.venv\Scripts\python.exe`로 실행 (BUG-1: WSL에서는 실행 금지)
- [ ] `.gstack-demo.py` dry-run `--fast` 모드로 1회 검증

### 빌드 검증 (D-1 필수)

- [ ] **프론트엔드 BUILD_ID 갱신 확인**: `docker exec maedeup-frontend ls -la /app/.next/BUILD_ID` — 최신 이미지 기준인지 타임스탬프 확인
  - TS build error 방치 시 stale image 그대로 실행 → 오늘(2026-05-16) 라운드 1~7에서 fake RED 반복된 원인
  - fix 반영이 안 되면 `docker compose up -d --build frontend` 후 BUILD_ID 재확인
- [ ] 백엔드 변경은 `docker restart maedeup-api` 후 `docker logs maedeup-api --tail 20`에서 P0 에러 없음 확인

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

---

## v2 대비 변경 사항

| # | 구분 | v2 | v3 |
|---|---|---|---|
| 1 | **ACT 3 신설 → TimeBar 합의 흐름** | 없음 (v2) / VoteCardSection 직접 투표 (v3 초기) | **"시간대 변경" 클릭 → TimeBarSelector 마운트 → 게스트 WS `time_selection` → 호스트 슬롯 클릭 → consensus → "이 시간으로 확정" 클릭 → `POST /schedule-confirm` (35초)** |
| 2 | **버튼 명칭 정확화** | "다른 시간대" (가정) | **"시간대 변경"** — 실제 코드 텍스트 (`ScheduleRecommendationCard.tsx:545`: `"시간대 변경"`) |
| 3 | **TimeBar 합의 확정 버튼 (Option C)** | InfoPane A3-2 "추천 시간 그대로 확정" | **TimeBar 카드 내 호스트 전용 보라색 "이 시간으로 확정"** 버튼 (commit `ffd4e1f`, `aac6303`). consensus 후 TimeBar 유지 + 안내 박스 표시. fallback: InfoPane "추천 시간 그대로 확정". |
| 4 | **게스트 화면 — TimeBar 대기 상태** | 없음 (미명시) | TimeBar 유지 + 회색 박스 "⏳ 방장 확정 대기 중 — 시간은 자유롭게 변경 가능합니다" (commit `ecee744`, `8a7c7d5`) |
| 5 | **캘린더 셀 빨간 배지 제거** | 안 되는 사람 수 빨간 "1" 배지 + X/Y 배지 이중 표시 | **빨간 배지 삭제**. X/Y 가용 인원 배지만 유지 (4/4=초록, 이하=노란 #eab308). commit `bc315f1` |
| 6 | **ACT 5 입력 단순화** | "강남에서 다 같이 갈만한 한식집" | **"강남 한식 추천해줘"** 또는 **"추천해줘"** — 짧은 입력으로 의도 자동 인식 강조 |
| 7 | **백업 B-8 갱신** | B-8 (VoteCardSection 미작동 4종) | **B-8 (TimeBar 합의 미작동 5종 + TimeBar selector/WS 대응)** |
| 8 | **체크리스트 보강** | v2 | ACT 3 WS time_selection용 게스트 토큰 준비 + 빌드 BUILD_ID 검증 항목 추가 |
| 9 | **시연 D-Day** | (미명시) | **2026-05-22 (금) 점심, D-6 (2026-05-16 기준), D-1=5/21** |
| 10 | **총 시간** | ~4분 50초 | **~5분 25초** (ACT 3 +35초, 발표자 트림 후 ~5분 10초 가능) |
