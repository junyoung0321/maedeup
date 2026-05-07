# 2026-05-07 — Frontend/UX 세션 진행분 (다른 터미널 충돌 방지용)

이 세션의 작업 범위 + 진행 상태 + 다른 터미널 충돌 가능 영역.
"여기서 커밋 안 함" 정책 — 모든 commit/push는 git 관리 터미널에서.

대응 핸드오프: `2026-05-07-langgraph-session-progress.md` (다른 터미널)

## 이미 커밋된 작업 (참고)

| Commit | 내용 |
|---|---|
| `0d04fe5` | feat(frontend): vote_card 시간대 변경 분기 — #9 B 흐름 (MeetingContext + CalendarPane + ScheduleRecommendationCard) |
| `32d039a` | fix(frontend): vote_card label regex + awaiting state reset — #9 P1·P2 fix + regex 정교화 |
| `22b235b` | fix(narration): A3-1 합의 시간대 동적 주입 — `_build_entities_from_timebar`에 `consensus_label` + greeting 동적화 |

## 진행 중 작업 (미커밋)

### A3-2 — TimeBar 자동 발동 차단 (backend 완료, frontend 대기)
### A4-1 — confirm 후 AI 패널 확정 안내 박스 (backend 완료)

신규 모듈 `backend/app/services/agent_messaging.py`:
- `emit_agent_message(redis, room_id, content)` — DB ChatMessage commit + agent 채널 publish (silent fail). 호출처 다양 (A4-1 + 미래 사용)
- `format_korean_meeting_time(dt)` — "5월 8일 (금) 오후 6:00" 포맷

`backend/app/api/routes/meetings.py:confirm_meeting` (line 446 부근):
- DB confirm 직후, GCal 등록 전에 두 메시지 emit:
  1. `"✅ 일정이 확정되었어요 — {Korean time}"`
  2. `"이제 어디서 만날지 정해볼까요? 장소를 추천해드릴게요."`
- silent fail (DB commit unwind 없음)

검증: docker restart 후 `/health` OK. 시연 검증은 chromium 보유 터미널에서 vote_card → 확정 → AI 패널 두 줄 떠야.

### #8 — PersonalData D-1 시드 스크립트 (완료)
신규 파일: `backend/scripts/seed_demo_personal_data.py`
- `SEED_MAP` (지민 한식·강남·저녁형 / 수현 채식·홍대 비선호 / 민수 지하철)
- `--room <id>` + `--dry-run` 인자
- User.name 매칭으로 user_id 자동 찾기, `is_ai_filled[cat]=True`
- Idempotent (이미 시드된 user는 skip)
- dry-run 검증 통과

시연 D-1 사용:
```bash
docker exec maedeup-api python -m scripts.seed_demo_personal_data --room <id>
```

### A3-2 (이전) — 분석 완료, 코드 작성 시작.
**시연 영향**: 🔥 P0 — 사용자 의도 없이 AI 자동 발동되어 "AI 마음대로" 인상.

### 기대 동작
1. TimeBar 합의 → 시각화만 (전원 row 색칠)
2. 호스트가 "확정하기" 버튼 클릭
3. 그제서야 narration + `ai_auto_trigger` 파이프라인 발동

### 변경 영역

#### Backend
- **`backend/app/api/ws/social.py:_maybe_emit_proposal:94-105`** — `ai_auto_trigger` 자동 publish 제거
- 대신 새 payload `schedule_consensus_ready` (호스트한테만 노출용) publish — 같은 social 채널 또는 별도
- **신규 endpoint** `POST /api/v1/rooms/{room_id}/schedule-confirm` (또는 WS msg) — 호스트 클릭 시 호출 → 그 때 `ai_auto_trigger` publish
- 호스트 권한 체크 (room.created_by)
- Idempotent: 같은 snapshot_hash 두 번 호출 시 한 번만 발동

#### Frontend
- WS msg type `schedule_consensus_ready` 수신 핸들러 (`useSocialWebSocket.ts`)
- 호스트일 때만 "일정 확정하기" 버튼 노출 — **`TimeBarSelector.tsx` 또는 `InfoPane.tsx`** 에 UI 추가
- 버튼 클릭 → `POST /schedule-confirm` 호출

### 충돌 가능 영역 (다른 터미널과)

| 영역 | 충돌 가능성 | 비고 |
|---|---|---|
| `backend/app/api/ws/social.py` | 中 | langgraph 핸드오프엔 social.py 변경 없음 → 안전 |
| `backend/app/api/routes/rooms.py` 또는 신규 router 추가 | 低 | 새 endpoint |
| **`frontend/src/components/meeting/InfoPane.tsx`** | **🔥 高** | 다른 터미널 D 카테고리(TimeBar AI 추천 선호도)가 working tree에 미커밋. 같은 파일 수정 예정 — **D 커밋 후 작업 시작 필요** |
| **`frontend/src/components/meeting/TimeBarSelector.tsx`** | **🔥 高** | 다른 터미널 D 카테고리 미커밋. 같은 파일 — **D 커밋 후 작업** |
| `frontend/src/hooks/useSocialWebSocket.ts` | 中 | 새 msg type 추가. 다른 터미널 변경 없는 듯 |

### 작업 순서 (충돌 회피)
1. **Backend 변경 먼저** — social.py + 신규 endpoint. 다른 터미널 영향 0.
2. **다른 터미널이 D 카테고리(InfoPane + TimeBarSelector) commit** 대기.
3. **Frontend 변경** — 새 WS handler + 호스트 "확정하기" 버튼 UI. D 커밋 위에서 추가.

## 다른 신규 P0 (audit 결과)

| # | 우선 | 항목 | 작업 영역 |
|---|---|---|---|
| **A4-3** | 🔥 P0 | `all_members_selected` → 시나리오 ACT 4 = Partial maedeup 카드 기대인데 실제 place_recommendation 직행 | `langgraph_pipeline.py` trigger 분기 — 다른 터미널 영역 |
| **A6-1** | ⚠️ P1 | memory_extraction이 거부 발화를 `time_preference`에 잘못 분류 | `personal_data_extractor.py` — 다른 터미널 영역 |

본 세션은 **A3-2** 한 건만 잡음. A4-3·A6-1은 langgraph 작업 영역이라 다른 터미널 또는 후속 세션.

## Docs 정정 필요 (시연 시나리오)

`demo-scenario-audit.md`에 명시된 단순 정정. 누가 처리할지 미정:
- **D-A2-1**: 추천 카드 5/12 → 5/11 (또는 시나리오에 5번째 메시지 "11일도 시험" 추가)
- **D-A2-3**: "5/12 (월)" → "5/12 (화)" (요일 오류)
- **D-A3-1**: "19:00~20:30" → "19:00~21:00" (산수 정정)

## 미커밋 working tree (이 세션 시작 시점)
- `frontend/src/components/meeting/InfoPane.tsx` (M) — **다른 터미널 D 카테고리**, 본 세션 변경 아님
- `frontend/src/components/meeting/TimeBarSelector.tsx` (M) — **다른 터미널 D 카테고리**, 본 세션 변경 아님
- `docs/handoff/2026-05-07-langgraph-session-progress.md` (untracked) — 다른 터미널 핸드오프

## 메모
- 본 세션은 "여기서 커밋/푸시 안 한다" 정책 (사용자 명시).
- 시연 D-day까지 1주.
- D 카테고리 commit 전엔 frontend 영역 손대지 마. backend만 진행.
