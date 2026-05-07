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
