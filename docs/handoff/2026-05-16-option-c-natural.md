# 2026-05-16 — Option C 완성 + 자연 표현 + 시나리오 정합성

- **최종 갱신**: 2026-05-16
- **브랜치**: `docs/spec-time-coordination`
- **HEAD**: `4a98d2f`
- **TL;DR**: Option C (TimeBar in-card 호스트 확정) 라운드 1~9 완주 → ACT 3 GREEN. CalendarPane 빨간 배지 제거, ACT 2 자연 표현, 시나리오 정합성 7건 fix. 시연 D-6 (2026-05-22 금 점심) 준비 완료. 영상 촬영 2026-05-18 (월) 예정.

---

## §1 개요

2026-05-15 자동 루프 라운드 4 GREEN 이후, 오늘(2026-05-16) 세션에서 22 커밋을 push하여 시연 D-6 최종 준비를 마쳤다.

주요 성과 4가지:

1. **Option C 라운드 1~9 완성** — TimeBar in-card "이 시간으로 확정" 버튼 호스트 전용 노출 흐름 확정
2. **CalendarPane 빨간 배지 제거** — 중복 표시 해소 (1차 commit 잘못 → 2차 commit 정정)
3. **ACT 2 자연 표현 + backend 보강** — "차주" alias, "그 다음주" +14일 분기, `DEMO_TARGET_DATE` 상수
4. **시나리오 정합성 7건 fix** — D-1~D-7 체크리스트 기반 수정

---

## §2 Option C 라운드 1~9 흐름

### 목표

TimeBar 컴포넌트를 별도 카드 팝업 대신 ScheduleRecommendationCard 안에 inline 포함하고, 호스트에게만 "이 시간으로 확정" 버튼을 노출하는 Option C 구현.

### 라운드별 진화

| 라운드 | commit | 핵심 fix | 결과 |
|---|---|---|---|
| 1 | `ecee744` | Option C — 호스트 in-card "이 시간으로 확정" 버튼 도입 | fake RED (stale image) |
| 2 | `ffd4e1f` | ACT 3 TimeBar in-card 확정 셀렉터 갱신 | fake RED (stale image) |
| 3 | `3528f19` | .pytest_cache dockerignore 추가 | fake RED (stale image) |
| 4 | `8a7c7d5` | ScheduleRecommendationCard isHost 낙관적 렌더 — hostLoading race 해소 | fake RED (stale image) |
| 5 | `cdf727b` | Option C 보존 — maedeup_card auto phase-advance 가드 | fake RED (stale image) |
| 6 | `1fe9b17` | R6 — setVoteCard phaseAlreadyAdvanced에 dateConfirmed 포함 | fake RED (stale image) |
| 7 | `ad22516` | TS build error — InfoPanePhase "placeRecommendation" 비교 제거 | fake RED (stale image) |
| **8** | `cb0acee` | TS union narrowing — card.type maedeup_card guard 추가 | **진짜 GREEN** |
| 9 | `aac6303` | ACT 3 step 4 호스트 버튼 노출 시점 5초 대기 추가 | GREEN 유지 |

### 핵심 발견: TS build error로 stale image 7번 누적

라운드 1~7은 코드 변경 자체가 올바르나 **TypeScript build error** 로 인해 Docker image가 stale 상태로 남아 실제 변경이 반영되지 않았다. 오류 패턴:

- 라운드 7: `InfoPanePhase` 타입에 없는 `"placeRecommendation"` 문자열 비교 → TS2367 에러
- 라운드 8: `card.type` union narrowing 미처리 → TS 컴파일 실패

TS build error 가 없는 8라운드에서 처음으로 실제 변경이 반영되어 GREEN 달성.

**교훈**: 프론트엔드 변경 후 `docker compose up -d --build frontend` 로 rebuild하고, 컨테이너 로그에서 TS compile 에러 여부를 먼저 확인해야 한다.

### 적용 fix 5건 (commit 기준)

| 파일 | 변경 | 라운드 |
|---|---|---|
| `frontend/src/components/meeting/ScheduleRecommendationCard.tsx` | `isHost` 낙관적 렌더 (hostLoading race 해소) | 4 |
| `frontend/src/components/meeting/AiAssistantPane.tsx` (via MeetingContext) | `phaseAlreadyAdvanced` — maedeup_card auto phase-advance 가드 | 5 |
| `frontend/src/components/meeting/InfoPane.tsx` (또는 MeetingContext) | `setVoteCard` phaseAlreadyAdvanced에 `dateConfirmed` 포함 | 6 |
| `frontend/src/components/meeting/InfoPane.tsx` | `InfoPanePhase` 없는 `"placeRecommendation"` 비교 제거 | 7 |
| `frontend/src/hooks/useAgentWebSocket.ts` (또는 InfoPane) | `card.type === "maedeup_card"` union narrowing guard 추가 | 8 |

---

## §3 CalendarPane 빨간 배지 제거

### 문제

CalendarPane 셀에 "안 되는 사람 수" 빨간 배지가 표시되어 시연 시각적으로 혼란. 채팅 blocked 정보가 `avail.count` 에 이미 반영돼 있음 → 빨간 배지가 중복.

### 수정 흐름

| commit | 내용 | 판단 |
|---|---|---|
| `8ce6b46` | 셀 배지를 "안 되는 사람 수" → "가능한 사람/전체" (X/Y) 형식으로 변경 | 1차 — 형식 변경, 배지 유지 |
| `bc315f1` | 빨간 배지 완전 제거 — avail.count 이미 반영 (중복 해소) | 2차 — 최종 정정 |

결과: 캘린더 페인 X/Y 숫자 표시만 남고 빨간 배지 0개. 시연 스크린샷 확인 완료.

---

## §4 ACT 2 자연 표현 + backend 보강

### 문제

시연 ACT 2에서 수현 발화가 "5월 xx일"처럼 절대 날짜 하드코딩이라 촬영일에 따라 의미가 어색해짐. "차주 주말" 같은 자연어 표현이 backend에서 미처리.

### 적용 fix

**backend** (`backend/app/services/pipeline/helpers/dates.py`, commit `2e8ee9f`):
- `"차주"` alias 추가 — "차주 토요일" → 다음주 토요일 처리
- `"그 다음주"` / `"다다음주"` +14일 분기 추가

**frontend/demo** (commit `8b03c04`):
- `DEMO_TARGET_DATE` 상수 신설 — 촬영일(5/18) 기준 날짜 계산
- ACT 2 수현·예린 발화 자연 표현 하드코딩 (5/18 기준: "이번 주 금요일", "차주 월요일" 등)
- dry-run guard: 상수 기반이라 날짜 계산 오류 시 즉시 감지 가능

**demo-scenario-v3.md** (commit `58eb58e`):
- ACT 2 발화 5/18 기준 날짜 환산 갱신

---

## §5 시나리오 정합성 7건 fix

**commit `4a98d2f`** — 시연 D-1~D-7 체크리스트 기반 정합성 점검 결과 7건 수정.

| 번호 | 항목 | fix 내용 |
|---|---|---|
| D-1 | ACT 2 발화 날짜 자연어 표현 | 5/18 기준 "차주" 표현으로 교체 |
| D-2 | ACT 3 TimeBar 셀렉터 | Option C in-card 버튼 경로로 갱신 |
| D-3 | 검증 결과 A | 실제 dry-run GREEN 확인 |
| D-4 | 캘린더 배지 표기 | 빨간 배지 제거 후 X/Y 표기 반영 |
| D-5 | ACT 3 step 4 페이스 | 5초 대기 추가 후 시나리오 대기 시간 표기 갱신 |
| D-6 | 시연 일정 | 5/19·5/20 → 5/22 금 점심 수정 |
| D-7 | HEAD SHA | `a2e9b16` → `4a98d2f` 갱신 |

---

## §6 시연 페이스 5초 대기 (ACT 3 step 4)

**commit `aac6303`**

Option C 확정 버튼("이 시간으로 확정")이 노출되는 순간 관중이 시각적으로 인지할 시간이 필요. ACT 3 step 4에서 버튼 활성화 후 5초 대기 후 클릭하도록 수정.

- `frontend` UI 변경 없음 — demo.py 자동화 타이밍만 조정
- 시연 영상 편집 시 이 5초가 "AI가 자동으로 최적 시간을 찾아줬어요" 설명 타이밍으로 활용 가능

---

## §7 검증 결과

### dry-run 결과 (2026-05-16, 라운드 9 완성 후)

- **ACT 3 primary 경로 GREEN** — TimeBar in-card "이 시간으로 확정" 버튼 호스트 전용 노출 확인
- **캘린더 X/Y 표시** — 빨간 배지 0개 확인
- **TimeBar 유지** + 버튼 노출 타이밍 5초 대기 적용 확인
- 스크린샷 5건 저장 (`.gitignore` 패턴 `option-c-*.png` 추가로 미추적)

### ACT 5 장소 확정 변동성

- 일부 라운드에서 장소 확정 round selector fail 보고
- 이전 라운드 기준 GREEN 확인됨
- 원인: 장소 추천 결과가 Gemini 비결정성에 영향받음 (LIMIT-5 계열)
- **시연 대응**: ACT 5 실패 시 manual confirm fallback 시나리오 숙지 필요

---

## §8 남은 backlog

### P0 시연 직전 (2026-05-18~21)

- [ ] **시연 영상 촬영** (2026-05-18 월) — dry-run 최종 확인 후 진행
- [ ] **시연 D-1 리허설** (2026-05-21 목) — `TODOS.md §0` 체크리스트
- [ ] ACT 5 장소 확정 변동성 확인 — selector 실패 패턴 분석 + manual fallback 시나리오 준비

### P1 시연 후 즉시

- [ ] **장소 추천 vote 시스템** (v2 spec PR-v2.1 후보) — 멤버 선호도 투표 집계 흐름 설계
- [ ] **코덱스 P1 backlog 5건** (`TODOS.md §10`) — Option C 완성으로 일부 검토 필요
- [ ] **ACT 5 장소 확정 안정화** — round selector 패턴 보강

### P2 backlog

- v2 spec 본문 작성 (38항목, `2026-05-14-spec-v2-plan.md`)
- 해결점 O·P 구현 (정규식 단축 사각지대, 번복 처리)

---

## §9 오늘 세션 22 commit 목록

| commit | 메시지 요약 |
|---|---|
| `ecee744` | feat(timebar): Option C — 호스트 in-card "이 시간으로 확정" 버튼 도입 |
| `ffd4e1f` | feat(demo): ACT 3 TimeBar in-card 확정 셀렉터 갱신 |
| `3528f19` | chore(docker): .pytest_cache dockerignore 추가 |
| `8a7c7d5` | fix(frontend): ScheduleRecommendationCard isHost 낙관적 렌더 |
| `cdf727b` | fix(frontend): Option C 보존 — maedeup_card auto phase-advance 가드 |
| `1fe9b17` | fix(frontend): R6 — setVoteCard phaseAlreadyAdvanced에 dateConfirmed 포함 |
| `ad22516` | fix(frontend): TS build error — InfoPanePhase 없는 비교 제거 |
| `cb0acee` | fix(frontend): TS union narrowing — maedeup_card guard 추가 |
| `8ce6b46` | feat(calendar): 셀 배지 X/Y 형식으로 변경 |
| `bc315f1` | fix(calendar): 빨간 배지 제거 (avail.count 중복 해소) |
| `0df31ae` | chore(gitignore): qa-runtime 스크린샷 패턴 추가 |
| `aac6303` | feat(demo): ACT 3 step 4 호스트 버튼 노출 5초 대기 |
| `e8a10c4` | chore(gitignore): option-c-*.png 스크린샷 패턴 추가 |
| `646d252` | docs(session-state): Option C + CalendarPane + 시연 D-6 반영 |
| `8119c75` | docs(demo-scenario): 2026-05-16 Option C 패치 반영 |
| `2e8ee9f` | feat(dates): "차주" alias + "그 다음주" +14일 분기 추가 |
| `8b03c04` | feat(demo): ACT 2 발화 자연 표현 하드코딩 (5/18 기준) |
| `58eb58e` | docs(demo-scenario): ACT 2 자연 표현 + 5/18 날짜 환산 갱신 |
| `4a98d2f` | docs(scenario): 정합성 7건 fix D-1~D-7 |

(총 19개 명시, 전체 22 commit 포함 — `cfaaf68`, `558c57c`, `39fd8f9` 등 라운드 4 후속 포함)

---

## §10 메타

- **자동 루프 운영 모드** 9라운드 완주 — TS build error 패턴 신규 발견, 향후 "프론트 변경 시 TS compile 에러 먼저 확인" 체크리스트 추가 권고
- **CalendarPane 2-step fix** (배지 형식 변경 → 배지 제거) — 1차 commit이 시각적으로 혼란을 줄 경우 즉시 2차 commit으로 정정하는 패턴 확립
- **demo.py 자연 표현 패치** — `DEMO_TARGET_DATE` 상수 도입으로 촬영일 변경 시 단일 상수만 수정하면 전 발화 날짜 자동 환산
- **시연 D-6 확인**: 발표일 5/22 금 점심, 영상 촬영 5/18 월 (D-4)
