# 2026-05-06 — 시연 루프 진행 + 다음 스텝

## 이번 세션 요약

아키텍처 감사(A~M) 코드 적용 + 브라우저 시연 루프(ACT 1~5) 검증.
Codex 하청 + 검수 루프 패턴으로 E·I·J·K 적용 완료.

### 커밋된 작업
- `c41bd43` phase 1 — A·D·F·G·H·L·M
- `e46b756` phase 2 — B·C
- `e280c60` phase 3-E — quick_classify direct_request 단축
- `94768f5` phase 3-I — slot_filling 트리거별 분기
- `8883059` phase 3-J — meeting_id Map upsert
- `2f20e85` phase 3-K — partial 카드 + PATCH 엔드포인트

### 미커밋 변경 (이번 세션 후반)
시연 루프 중 발견 + 즉석 수정:

1. **자동 추천 로직 제거** (`backend/app/api/routes/rooms.py`)
   - 방 생성 시 `_trigger_auto_recommendation` 호출 삭제
   - 이유: 사용자 발언 없는 상태에서 AI가 먼저 카드 띄우는 동작 불필요

2. **알고리즘 보강 — 다음주 확장** (`langgraph_pipeline.py` entity_extraction + _slot_filling_stalemate)
   - 모든 후보 거부 시 `expanded_to_next_week` 플래그
   - stalemate 노드에서 today 기준 21일 스캔, 사용자 평일/주말 선호 반영, rejected 제외, 최대 5개

3. **자동 메시지 합성 hack 제거**
   - backend `confirm_time` 핸들러: synthetic user 메시지 INSERT 제거 → run_pipeline 직접 호출
   - frontend `ScheduleRecommendationCard`: `sendMessageToAi("일정이 확정...장소 추천")` 제거

4. **라우팅 수정**
   - `_route_after_validation`: `direct_request_kind == "place"` → place_recommendation
   - `_route_after_place_recommendation`: confirmed_place 없고 direct_request 트리거면 END (자동 maedeup 진입 차단)
   - `_route_after_vote_card_creation`: confirmed_place 없으면 항상 END (Option A — 사용자 투표 대기)

5. **장소 카드 UI 분리** (`AiAssistantPane.tsx`, `InfoPane.tsx`)
   - 장소 추천 카드는 AI 패널에만 렌더
   - 장소명 클릭 → InfoPane(캘린더 패널)에 PlaceDetailPane 표시
   - InfoPane에서 timeConfirmed phase + isPlaceOnlyFlow 카드 중복 렌더 제거

## 다음 스텝

### 1. ACT 3 재확인
시연 루프에서 ACT 3(시간/날짜 확정 흐름)을 빠르게 지나갔음. 다시 처음부터 검증 필요:
- vote_card 발행 → 사용자 슬롯 클릭 → confirm_time → maedeup 자동 직진 안 함 (Option A 확인)
- 5/8(금) 자동 표시 이슈 재발 여부
- meeting_id 카드 Map upsert가 실제로 갱신되는지 (해결점 J)

### 2. ⚠️ 채팅방 "안되는 날짜" 미적용 버그
**증상**: 채팅방에서 "5/8은 안 돼" 같은 거부 발언을 해도 추천 후보에서 제외 안 됨.
**의심 지점**:
- `entity_extraction` 노드의 rejected_dates 추출이 채팅 히스토리 기반으로 안 도는 듯
- 또는 추출은 되는데 후보 필터링 단계까지 흘러가지 않음
- `project_pattern_skip_rejected_blindspot.md` 메모리 — entity_extraction 정규식 통과 시 rejected_dates 누락 가능성 (보류)
**검증 시작점**:
- `_resolve_rejected_date` 헬퍼가 채팅 메시지 텍스트를 받는지
- `_slot_filling_stalemate`의 candidates 필터에 rejected_set이 실제로 채워지는지 로깅
- 채팅방 메시지 → entity_extraction 진입까지 trace

### 3. ACT 5 마무리 + ACT 6 (해결점 K)
- ACT 5: "이 장소로 확정" → maedeup_card 발행 + meeting_id 갱신 검증
- ACT 6: 별도 룸으로 partial 카드 + PlaceInputModal 시연

### 4. PlaceDetailPane meetingId prop 누락
"일정을 먼저 확정해주세요" 버튼 비활성화 이슈 — meetingId 흘러들어가지 않음. 별도 이슈.

## 참고
- 이전 진행 문서: `docs/handoff/2026-05-05-architecture-audit-progress.md`
- 감사 결론: `docs/handoff/audit-findings.md`
- 다이어그램: `docs/handoff/diagrams/`
