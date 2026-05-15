# DECISIONS — 매듭 프로젝트 결정 사항

**최종 갱신**: 2026-05-16
**기준**: spec v1.0 + PR-X·Y·Z·V·V1.5·V1.5.1·V1.5.2 + 자동 루프 run12 GREEN + Option C R8 GREEN + 시연 D-6 (2026-05-22 금)

---

## 1. 핵심 정책 결정 (6건)

| # | 항목 | 결정 | 근거 |
|---|---|---|---|
| **스코프** | 기능정의서 범위 | 시간 + 장소 통합 (3 파일 분할) | 시간만으론 ACT 5 미커버 |
| **파일명** | spec 파일 | spec-common + spec-time-coordination + spec-place-recommendation | 단일 SoT 원칙 |
| **동의 모델** | 공유 동의 | opt-out 유지 (default=True, PR-X 마이그) | 시연·졸업 발표 우선 |
| **게스트 정책** | 식별 | 방별 이름 기반 pseudo_id (room_id × name) | 동명이인 분리 |
| **비기능 위치** | 구조 | §12 비기능 / §13 부록 분리 | 가독성 |
| **백로그 정책** | 시연 후 보완 | v2 spec 예고 (해결점 P·O·ACT 4·5) | v1.0 출하 우선 |

---

## 2. Spec Q-시리즈 결정 (16건)

| # | 결정 | 적용 |
|---|---|---|
| **Q1** | B) 단일 슬롯도 vote_card 발행 | spec §5.1.5·§4.4 F3 |
| **Q2** | 선호 장소 다수결 → 동률 시 발화자 → 없으면 방장 위치 | F5 4-step (_resolve_place_hint) |
| **Q3** | A) 방 멤버 수 사용 (headcount=None fallback) | spec §4.4 F2 |
| **Q5** | hybrid — 그룹 다수결 기본 + 발화자 토글 | Q7=B 메타 키로 노출 |
| **Q6** | A) F1 fallback v1.0 포함 | PR-Y1 |
| **Q7** | B) preference_source + toggle_enabled, vote_card·place 양쪽 | PR-Z1·Z2 |
| **Q7-b** | 방 전체 broadcast — refresh 라우트 신설 | POST /meetings/{id}/recommendations/refresh |
| **Q7-c** | C1∨C3∨C4 (게스트 C2 제외) | spec §6.13 |
| **Q8** | A) F1 정렬 = 시간 빠른 순 | spec §4.4 F1 |
| **Q9** | A) partial maedeup 후 시간 번복 불가 | spec §6.9 |
| **Q10** | C) Gemini prompt에 휴일·요일 라벨 안내 | spec §6.16 |
| **Q11** | A) 일괄 True 자동 마이그레이션 | PR-X |
| **Q12** | A) headcount fallback에 게스트 포함 | 일관성 |
| **Q13** | B) refresh 라우트 권한 = 발화자 + 방장만 | 최소 권한 |
| **Q14** | C) Redis idempotency 캐시 + 일일 100회 상한 | Gemini quota 보호 |
| **Q15** | A) 토글 narrator = "OOO님 선호 기준" 실명 | 액션 가능성·투명성 |
| **Q16** | C) blocker_notification = 기본 익명 + 더보기 실명 | k-anonymity |
| **Q17** | A) F4 narrator = 실명 | Q15=A 일관 (코드 미구현 → LIMIT-9) |

**Q4 점수 공식**: `0.4 * ML + 0.3 * Gemini + 0.3 * 거리` (`_compute_final_score` in place.py)

---

## 3. 자동 루프 결정 (이번 세션, run12 GREEN 기준)

### 옵션 A — InfoPane VoteCardSection 제거 (run3/라운드5)
- **결정**: InfoPane에서 VoteCardSection mount 제거. AI 어시스턴트 패널에서만 vote_card 렌더
- **근거**: InfoPane + AI 패널 중복 노출 시 무한 루프 발생 (setInfoPanePhase 트리거 중복)
- **구현**: `AiAssistantPane.tsx:531` hideConfirmAction prop 제거, `InfoPane.tsx:341` !scheduleConsensus 조건

### 옵션 B — PREFERENCE_TOGGLE_ENABLED=false (run12)
- **결정**: `.env`에 `PREFERENCE_TOGGLE_ENABLED=false` → preference_toggle 파이프라인 진입 차단
- **근거**: ACT 2.5 ScheduleRecommendationCard 슬롯 클릭이 host availability prefill echo back → TimeBar 즉시 unmount race 유발. 근본 원인 추적 전 시연 환경 dormant 처리
- **구현**: `preference_toggle.py:72-99` 환경변수 조기 반환

### AUTO_CALENDAR_PUSH=false — 시연 환경 default
- **결정**: Google Calendar 실제 이벤트 생성 비활성화
- **근거**: 시연 반복 실행 시 캘린더 오염 방지
- **구현**: `meetings.py:563+867` 2곳 gate 추가, `config.py` AUTO_CALENDAR_PUSH field

### ACT 3 흐름 = TimeBar 합의 (vote_card 직접 확정 X)
- **결정**: vote_card 슬롯 클릭 → 확정이 아니라 TimeBar 가용 시간 입력 → 방장이 range 선택 → 합의 확정
- **근거**: 실제 모임 조율 UX와 일치. 각 멤버가 가능한 시간대 제출 → 다수결 overlap → 방장 확정
- **구현**: ACT 3 5단계 (게스트 WS 송신 + 호스트 Playwright 클릭 + WS 송신 best-effort + A3-2 확정)
- **SoT**: `docs/handoff/demo-scenario-v3.md`

### demo.py 호스트 = Playwright + WS 송신 병행 패턴
- **결정**: 호스트 TimeBar 조작은 Playwright (시각 증거) + WS 직접 송신 (ground truth) 병행
- **근거**: Playwright slot 24 selector 간헐적 실패 (LIMIT-demo-1) → WS fallback이 실질 결과 보장
- **구현**: `.gstack-demo.py` ACT 3 best-effort WS 송신

### backend majority overlap = compute_majority_slot
- **결정**: 4인 TimeBar 슬롯 중 과반(≥3명) 겹치는 slot → `manual_chosen_time` 주입
- **근거**: vote_card best slot은 개인 선호 기반, TimeBar는 가용시간 기반 → 별도 계산 필요
- **구현**: `agent.py:427-479` compute_majority_slot + manual_chosen_time 주입
- **결과**: slot 21-23 (19:30~20:30) → 확정 시간 19:30

### all_members_selected debounce 예외
- **결정**: NX Redis lock + local debounce 둘 다 all_members_selected 트리거에 예외 처리
- **근거**: debounce가 WS 송신 완료 후 트리거 신호를 묵음 → TimeBar 합의 후 파이프라인 미발동
- **구현**: `agent.py:758-790`

### TimeBarSelector restoredFromServer ref guard + selectionEnd null 보류
- **결정**: 서버 복원 값 주입 시 WS 재송신 차단 (ref guard). selectionEnd null이면 broadcast 보류
- **근거**: 서버 복원 echo back이 다른 멤버의 TimeBar를 덮어쓰는 race 차단
- **구현**: `TimeBarSelector.tsx:105-213` restoredFromServer ref + selectionEnd null 조건

### backend single-slot 제외 (_is_explicit, start==end)
- **결정**: TimeBar WS 수신 시 start==end인 단일 슬롯은 _is_explicit() false 처리 → majority 계산 제외
- **근거**: ACT 2.5 echo back이 single-slot으로 수신되어 majority 오염
- **주의**: 30분 미팅 단일 슬롯 use case에서 false negative 가능 (TODO #9)
- **구현**: `social.py:81-92`

### Option C — TimeBar in-card 호스트 확정 (라운드 8 GREEN, 2026-05-16)
- **결정**: 호스트 끝 슬롯 클릭 즉시 unmount 대신 TimeBar 유지 + 호스트 전용 "이 시간으로 확정" 버튼 + 호스트 명시 클릭 후 확정
- **근거**: 호스트 실수 방지 (재선택 가능) + UX 안전장치. ACT 3에서 "이 시간으로 확정" 버튼이 핵심 시연 장면
- **구현**: 9 commit (`ecee744`~`cb0acee`):
  - `ecee744` — Option C frontend (InfoPane mount 조건 + TimeBarSelector 호스트 버튼 + onHostFinalize)
  - `ffd4e1f` — demo.py ACT 3 셀렉터 갱신
  - `8a7c7d5` — ScheduleRecommendationCard isHost 낙관적 렌더 (hostLoading race 해소)
  - `cdf727b` — AiAssistantPane maedeup_card auto phase-advance 가드
  - `1fe9b17` — setVoteCard phaseAlreadyAdvanced에 dateConfirmed 추가
  - `ad22516` + `cb0acee` — TS build error 2건 해소
  - `aac6303` — demo.py ACT 3 step 4 5초 대기
- **부수 효과**: A3-2 카드 "추천 시간 그대로 확정" 버튼 유지 (이중 진입점 일시 공존, 시연 후 정리 예정)

### CalendarPane 빨간 배지 제거 (정합성, 2026-05-16)
- **결정**: 캘린더 셀에서 채팅 발화 "X일 안돼" 표시 빨간 배지 제거. 기존 `{count}/{total}` X/Y 표시(`#22c55e`/`#eab308`/`#ef4444`)가 이미 backend `_compute_day_avail`에서 `blocked` 반영
- **근거**: 중복 표시 해소. 정보 손실 없음 — 셀 클릭 시 detail panel "🚫" 섹션에서 채팅 발화자 이름 표시
- **구현**: `bc315f1` — `CalendarPane.tsx` 빨간 배지 블록 제거
- **검증**: qa-runtime DOM 조사 — 빨간 배지 0개, X/Y 카운트 31개 정상. 스크린샷: `calendar-badge-verify-124.png`

### Build cache stale 검증 정책 (2026-05-16)
- **결정**: 시연 D-1 이전 매 commit 후 `docker exec maedeup-frontend ls -la /app/.next/BUILD_ID`로 BUILD_ID 갱신 확인
- **근거**: 오늘 라운드 R1~R7 fake RED — TS build error로 인해 stale image(`7ffb7c4821a9`, `7fd7daa` 시점 SHA) 7번 재사용. BUILD_ID 타임스탬프 갱신 안 됨이 빌드 실패 신호
- **적용**: rebuild 후 항상 BUILD_ID timestamp 검증 → 갱신 안 되면 `docker compose build` 출력에서 `Type error` / `Failed to compile` 검색

---

## 4. 운영 결정 (메모리 영구 저장)

### PM 모드 v2 (4 담당 + 메모리)
- **코드 작성**: code-writer Sonnet
- **분석·검증**: analyst / risk-reviewer Opus
- **QA 런타임**: qa-runtime Sonnet (Playwright MCP, 실서버)
- **문서**: docs-planner Sonnet
- 리더는 PM 역할만 — 분배·점검·통합·결정 제안

### 시연 환경 실행 규칙
- 시연 스크립트: WSL venv `~/.venv-maedeup-demo/bin/python3` (Python 3.12)
- QA agent: Playwright MCP (MCP chromium 별도 인스턴스)
- Windows PowerShell 실행도 가능 (`.venv\Scripts\python.exe`)

### 커밋·푸시 정책
- 커밋: 사용자 명시 승인 후, 단일 commit per 라운드
- 푸시: 사용자 명시 승인 후만

### Handoff 자동 갱신
- PR 완료마다 `docs/handoff/2026-05-15-round4-green.md` 갱신
- 메모리: `feedback_handoff_auto_update.md`

### Codex 리뷰 활용
- 큰 변경 후 `codex review --uncommitted --title "..."` 권장
- P1·P2 발견 → hotfix 에이전트 위임 → 단일 커밋

---

## 5. 잠재 충돌·트레이드오프 (해소 + 잔존)

| # | 충돌 | 상태 |
|---|---|---|
| **C1** | Q5 hybrid + Q15=A 실명 → 발화자 PII 간접 노출 | v1.6 narrator 정밀화 후보 |
| **C2** | Q9 번복 불가 + Q7-b refresh → partial 시 시간 변경 가능성 | §6.9 refresh 잠금으로 해소 |
| **C3** | Q1=B 단일 슬롯 + 거부 흐름 미정의 | §6.8 rejected_dates 누적으로 해소 |
| **C4** | opt-out + calendar_consent default=False 모순 | PR-X로 완전 해소 |
| **C5 (신규)** | PREFERENCE_TOGGLE_ENABLED=false + ACT 2.5 슬롯 클릭 echo back | 옵션 B로 dormant, 근본 원인 미해소 (TODO #8) |
| **C6 (신규)** | single-slot 제외 + 30분 미팅 use case | 잠재 false negative (TODO #9) |

---

## 6. 결정 안건 단일 SoT

- **Q-시리즈**: `docs/handoff/spec-common.md` §결정 안건 표
- **루프 결정**: 본 파일 §3
- **운영 결정**: 본 파일 §4 + 메모리 (`feedback_pm_operating_mode.md` 등)
