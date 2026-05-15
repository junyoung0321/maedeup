# 2026-05-15 — Round 4 GREEN: ACT 3 confirm 자동화 복구 + ACT 5.5 토글 enable

- **최종 갱신**: 2026-05-15
- **브랜치**: `docs/spec-time-coordination`
- **HEAD**: `a2e9b16`
- **TL;DR**: 자동 루프 5라운드(A1~A5+C) 완주 → ACT 3 "일정 확정하기" fallback 해소 + ACT 5.5 preference_toggle GREEN. QA run3 2m13s, 백엔드 ERROR 0건.

---

## §1 배경

QA run1(2026-05-15, 3m04s)에서 두 가지 문제 발견:

1. **ACT 3 step 4** — "일정 확정하기" 버튼 30s timeout 후 ACT 4 fallback 진행. `POST /meetings/confirm` 미도달.
2. **ACT 5.5 토글** — `preference_toggle_enabled: false` 로 SKIP. narrator 미출력.

두 문제 모두 시연 자동화 본번 가치를 절반 이상 손실시키는 P0 항목.

진행 방식: **자동 루프** (qa → 분석 → 수정 → 코덱스 리뷰 → qa) 반복. `feedback-demo-iteration-loop` 메모리 규칙 준수.

---

## §2 루프 라운드 진화

### A 트랙 (ACT 3 confirm 복구)

| 라운드 | fix 요약 | 코덱스 평가 | qa 결과 |
|---|---|---|---|
| A1 | `meetings.py:636` — `vote_update` 에 `user_votes` 배열 추가 | APPROVE WITH NITS | ACT 3 여전히 fallback |
| A2 | `meetings.py:323-334` pending-vote `current_user_vote` + `VoteCardSection.tsx:100-119` hydration + `useAgentWebSocket.ts:57-64` | APPROVE WITH NITS (P0 해결 인정) | run2: ACT 3 여전히 fallback (dead code 발견) |
| 라운드 2 분석 | code-analyst opus — root cause 확인: **VoteCardSection JSX 마운트 누락** | — | `grep -rn "<VoteCardSection" frontend/src` → 0건 |
| A3 | `InfoPane.tsx:354-362` — VoteCardSection mount 추가 (`mode="vote-only"`, `infoPanePhase !== "placeConfirmed/done"`) | REQUEST CHANGES (이중 제어면 우려) | — |
| A4 | `ScheduleRecommendationCard.tsx:47,525,553` `hideConfirmAction` prop + `AiAssistantPane.tsx:531` 주입 | REQUEST CHANGES (demo selector 깨짐 우려) | — |
| A5 | `.gstack-demo.py:732-741,820-834` selector 새 흐름 적응 ("로 확정" → "투표하기" gate, ACT 4 fallback "일정 확정하기" wait + 팝업) | 빈 응답 — PM 직접 위험 평가 | — |
| **qa run3** | — | — | **GREEN** 2m13s, ACT 3 PASS, ACT 5.5 PASS, 백엔드 0 ERROR |

### C 트랙 (ACT 5.5 토글 seed 보강, A 트랙과 병렬)

- `backend/scripts/seed_demo_personal_data.py` — 방장 `home_base` "강남"→"신촌", `food` ["일식·양식·디저트"], `share_*_data True` 명시
- 코덱스: APPROVE WITH NITS (P1 — 주석을 MeetingPreference 기준으로 정확화 권고)
- run2 검증 GREEN: `preference_toggle_enabled: true`, narrator "김창윤님 선호 기준으로 다시 추천했어요" 출력

---

## §3 Root Cause 분석 (라운드 2 핵심)

- **표면 증상**: ACT 3 step 4 "일정 확정하기" 버튼 30s timeout
- **A1·A2 코드 자체는 옳음**: backend payload 정상, frontend hydration 정상
- **진짜 원인**: `VoteCardSection` 컴포넌트가 `InfoPane.tsx` 에 `import` 만 존재하고 JSX 트리에 마운트 안 됨

  ```
  grep -rn "<VoteCardSection" frontend/src
  (출력 0건)
  ```

  누군가 mount PR을 빠뜨린 회귀. useEffect/state 모두 정상 정의됐으나 렌더 트리에 안 붙어 UI 영향 0.

- **코덱스 한계**: 두 라운드가 코드 로직만 검토하고 렌더 트리 마운트 여부를 확인하지 못함. code-analyst opus 직접 분석으로 보완.

---

## §4 Commit 흐름

| commit | 파일 수 | 변경 규모 | 내용 |
|---|---|---|---|
| `0f3802b` | 7 파일 | +72/-32 | A1+A2+A3+A4+A5 묶음 (ACT 3 confirm 자동화 복구) |
| `a2e9b16` | 1 파일 | +34/-11 | C (ACT 5.5 seed 보강, 별개 commit) |

### 파일 × 라운드 매핑

| 파일 | 라인 | 라운드 |
|---|---|---|
| `backend/app/api/routes/meetings.py` | 636 | A1 |
| `backend/app/api/routes/meetings.py` | 323-334 | A2 |
| `frontend/src/hooks/useAgentWebSocket.ts` | 57-64 | A2 |
| `frontend/src/components/meeting/VoteCardSection.tsx` | 100-119 | A2 |
| `frontend/src/components/meeting/InfoPane.tsx` | 354-362 | A3 |
| `frontend/src/components/meeting/ScheduleRecommendationCard.tsx` | 47, 525, 553 | A4 |
| `frontend/src/components/meeting/AiAssistantPane.tsx` | 531 | A4 |
| `.gstack-demo.py` | 732-741, 820-834 | A5 |
| `backend/scripts/seed_demo_personal_data.py` | (전체 개편) | C |

---

## §5 검증 결과

### QA run3 (2026-05-15 14:28~14:31, 2m13s, exit 0)

- ACT 0.5 / 1 / 2 / 2.5 / 3 / 4 / 5 / 5.5 전 액트 PASS
- ACT 3 step 4: "일정 확정하기" 버튼 **2초** 만에 활성 (이전: 30s timeout)
- `POST /meetings/101/vote 200 OK × 3건` + `POST /meetings/confirm 201 Created`
- `MeetingStatus.confirmed` DB UPDATE 확인
- `POST /meetings/101/recommendations/refresh 200 OK` — `preference_toggle_enabled: true`, narrator "김창윤님 선호 기준으로 다시 추천했어요"
- 백엔드 ERROR / EXCEPTION / Traceback **0건** (로그 2972 lines 전수 확인)
- 최종 확정 픽스처: room 83 / meeting 101 / 2026년 6월 2일 (화) 오후 6:00 / 수담한정식 강남점 / 참여자 4명

### 회귀 비교

| 메트릭 | run1 | run2 | run3 |
|---|---|---|---|
| 소요 시간 | 3m04s | 2m44s | **2m13s** |
| ACT 3 confirm | fallback | fallback | **PASS** |
| ACT 5.5 토글 | SKIP | PASS | PASS |
| 백엔드 에러 | 0 | 0 | 0 |
| confirm 201 도달 | ✗ | ✗ | **✓** |

---

## §6 남은 Backlog (다음 PR 후보)

코덱스 권고 중 이번 PR 미반영 항목:

1. **vote_update payload 최소화** — `user_votes` 전체 → `current_voter` 만 전달 (개인정보 최소화)
2. **VoteCardSection 회귀 테스트** — pending-vote hydration, partial null 복귀, 이중 마운트 방지
3. **VoteCardSection mount 조건 정밀화** — `timeConfirmed` phase 도 제외 필요 (현재 `placeConfirmed/done` 만 제외)
4. **seed_demo_personal_data 주석 정확화** — User 모델 기준이 아닌 MeetingPreference 기준으로 표기
5. **refresh rerun state 통일** — `default_place_hint` / `preference_common_foods` 주입, route gate vs payload drift 방지

기존 TODOS.md backlog(해결점 O·P·LIMIT-7 등)는 본 PR 영향 없음.

---

## §7 메타

- **자동 루프 운영 모드** 5라운드 완주 검증 — `feedback-demo-iteration-loop` 메모리 규칙 준수
- **코덱스 빈 응답 2회** (A4 첫 시도, A5) — PM 직접 위험 평가로 보완. 코덱스 의존 단일 실패점 확인.
- **demo.py selector 변경** 동반 (A5) — 자동화 SoT 의 작은 진화. 차후 `docs/handoff/demo-scenario-v3.md` 업데이트 검토 필요.
- 코덱스가 렌더 트리 마운트를 정적 분석으로 놓친 패턴 — 향후 "컴포넌트 추가 시 grep으로 마운트 확인" 체크리스트 추가 권고.

---

## §8 다음 세션 진입 순서 (권고)

1. `docs/spec-time-coordination` (origin 동기 확인) — 이번 라운드 결과 반영됨
2. **CLAUDE.md `현재 task` 갱신** — "ACT 3 확정 자동화 GREEN + ACT 5.5 토글 GREEN" 로 업데이트
3. **TODOS.md §1** (v2 spec 작성) — 시연 후 진행
4. **코덱스 권고 P1 백로그 5건** 정리 후 v1.6 backlog 추가
