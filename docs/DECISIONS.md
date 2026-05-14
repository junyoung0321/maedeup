# DECISIONS — 매듭 프로젝트 결정 사항

**최종 갱신**: 2026-05-15
**기준**: spec v1.0 + 코드 PR-X·Y·Z·V·V1.5·V1.5.1·V1.5.2

---

## 1. 핵심 정책 결정 (6건)

| # | 항목 | 결정 | 근거 |
|---|---|---|---|
| **스코프** | 기능정의서 범위 | **시간 + 장소 통합** (한 spec 트리, 3 파일 분할) | 시간만으론 시연 시나리오 ACT 5 미커버. 분리는 결정 중복 위험 |
| **파일명** | spec 파일 | `spec-common.md` + `spec-time-coordination.md` + `spec-place-recommendation.md` (PR-V 3분할) | 단일 SoT 원칙. common이 결정·권한·API·비기능 |
| **동의 모델** | 공유 동의 | **opt-out 유지** (모델 default=True, PR-X 일괄 마이그) | 시연·졸업 발표 우선, PIPA 한계 §8.1에 명시 |
| **게스트 정책** | 식별 | **방별 이름 기반 pseudo_id** (room_id × name) | 동명이인 분리, 카톡 링크 가입 단순화 |
| **비기능 위치** | 구조 | **§12 비기능 / §13 부록** 분리 | 가독성·표준 spec 구조 |
| **백로그 정책** | 시연 후 보완 | **별도 v2 spec 예고** (해결점 P·O·ACT 4·5) | v1.0 출하 우선, v2는 시연 후 |

---

## 2. Spec Q-시리즈 결정 (16건)

| # | 결정 | 근거 / 적용 |
|---|---|---|
| **Q1** | B) 단일 슬롯도 vote_card 발행 | 날짜범위 확정 상태 전제, 명시 동의 의식 부여 (spec §5.1.5·§4.4 F3) |
| **Q2** | 선호 장소 다수결 → 동률 시 발화자 → 선호 없으면 방장 위치 | F5 4-step (spec §6.17, helpers/places.py `_resolve_place_hint`) |
| **Q3** | A) 방 멤버 수 사용 (headcount=None fallback) | 단순·일관 (spec §4.4 F2) |
| **Q5** | hybrid — 그룹 다수결 기본 + 발화자 토글 | Q7=B 메타 키로 노출 (spec §4.2 P3) |
| **Q6** | A) F1 fallback v1.0 구현 포함 | 시연 S8 차단 해소 (PR-Y1) |
| **Q7** | B) `preference_source: "group"\|"speaker"` + `preference_toggle_enabled: bool`, vote_card·place 양쪽 | 평면 키, 기존 컨벤션 일관 (PR-Z1·Z2) |
| **Q7-b** | 방 전체 broadcast — refresh 라우트 신설 | `POST /meetings/{id}/recommendations/refresh` (PR-Z1) |
| **Q7-c** | C1∨C3∨C4 (게스트 C2 제외) | 게스트도 채팅방 입장 후 선호 설정 가능 (spec §6.13) |
| **Q8** | A) F1 정렬 = 시간 빠른 순 | 후보는 이미 필터된 상태 가정 (spec §4.4 F1) |
| **Q9** | A) partial maedeup 후 시간 번복 불가 | 재추천은 별도 경로 (spec §6.9, refresh 라우트 잠금) |
| **Q10** | C) Gemini prompt에 휴일·요일 라벨 안내 | Kakao Local API는 영업시간 미제공 (spec §6.16, helpers/dates.py 헬퍼 활용) |
| **Q11** | A) 일괄 True 자동 마이그레이션 | 명시 거부자 포함 (Q-X1) PR-X 적용 |
| **Q12** | A) headcount fallback에 게스트 포함 | 게스트도 매듭 캘린더 불가능 토글로 거부일 입력 가능 |
| **Q13** | B) refresh 라우트 권한 = 발화자 + 방장만 | 최소 권한 원칙 (meetings.py refresh route) |
| **Q14** | C) Redis idempotency 캐시 + 일일 100회 상한 | Gemini quota 보호 (meetings.py rate limit) |
| **Q15** | A) 토글 narrator = "OOO님 선호 기준" 실명 | 액션 가능성·투명성 (PR-Z narrator 발행) |
| **Q16** | C) blocker_notification UI = 기본 익명 + 더보기 실명 | 점진 공개·k-anonymity 결합 (PR-Y2 UI) |
| **Q17** | A) F4 narrator = 실명 (권고 적용) | Q15=A 일관 + 액션 가능성 (spec §9.7) |

### 구현 세부 결정 (Q-X·Q-Y, 7건)

| # | 결정 |
|---|---|
| **Q-X1** | 명시 False 거부자 포함 일괄 True 마이그 (Q11=A 엄격 적용) |
| **Q-X2** | `/m/consent` JWT consent=True면 redirect 유지 (기본 권고) |
| **Q-X3** | `assistant.py:99` "캘린더 연동: 예/아니오" 토큰 체크 보강 (PR-V1.5에서 구현) |
| **Q-Y1** | F1 페이로드 형식 = 슬롯별 `unavailable_users`/`available_count`/`total_count` |
| **Q-Y2** | Q16=C 토글 = 슬롯별 single-expand (`expandedUnavailableSlotId`) |
| **Q-Y3** | PR-Y는 F1 (케이스 A)만 — 권한 0%·모든 blocked 등은 별도 PR (PR-V1.5에서 추가) |
| **Q-Y4** | 28일 확장 후에도 0이면 F1 fallback (기본 권고) |

### Q4 점수 통합 공식 (S20 의존)

**결정**: A) `0.4 * ML + 0.3 * Gemini + 0.3 * 거리`
- ML 가중치 ↑ (학습된 ranker 신뢰)
- Gemini·거리 동일 비중
- `_compute_final_score` (place.py)에 구현

---

## 3. 운영 결정 (메모리 영구 저장)

### PM 모드 (4 담당)
**메모리**: `feedback_pm_operating_mode.md`

리더는 **PM 역할만** — 작업 분배·진행 점검·결과 통합·최종 의사결정 제안. 깊은 분석은 4 담당 에이전트에 위임:
1. 코드 분석 (정적)
2. 문서/기획 (정적)
3. 리뷰/리스크 (정적)
4. **QA — 서비스 런타임 검증** (Bash·Playwright MCP·실서버)

리더 직접 read는 얕은 확인만 (디렉토리 ls·git status·헤더 한두 줄). 본문 분석은 항상 위임.

### Handoff 자동 갱신
**메모리**: `feedback_handoff_auto_update.md`

PR 완료마다 `docs/handoff/2026-05-14-spec-progress.md` 자동 갱신:
- §1 결정 누적
- §2 커밋 표
- §4 확정 결정
- §5 미결 결정
- §6 남은 TODO
- §9 잠재 충돌
- §7 다음 명령

별도 사용자 요청 없어도 PR 워크플로 일부.

### QA 운영 규칙
**메모리**: `feedback_qa_runtime_role.md`

- 실제 명령 실행 전 리더가 범위·위험도 사전 검토
- **금지**: 운영 데이터·외부 API 대량 호출·시크릿 출력·docker compose down --volumes·파일 수정·git commit/push
- **시연 환경 운영 규칙 (2026-05-15 신설)**:
  - `.gstack-demo.py` WSL 실행 금지
  - 시연은 Windows PowerShell + `.venv\Scripts\python.exe`
  - QA는 Playwright MCP 또는 CLI로 대체 검증
- 보고 양식: 재현·기대·실제·로그·원인·심각도

### 원격 푸시 정책
- 로컬 커밋은 자유 (CLAUDE.md "승인 없이 커밋/푸시 금지" 적용)
- 푸시는 **사용자 명시 승인 후만** (2026-05-14 사용자 명시 directive)

### Codex 리뷰 활용
- PR 완료 후 `codex review --uncommitted --title "..."` 자동 호출
- Codex 발견 P1·P2 → 별도 hotfix 에이전트로 위임
- 통합 단일 커밋으로 처리

---

## 4. 신규 결정 (이번 세션, 6건)

| # | 결정 | 적용 |
|---|---|---|
| **N (해결점)** | "다음주 자동 확장"을 audit-findings.md에 N 정식 헤더로 추가 | PR-0 (`494807e`) |
| **시연 환경** | WSL `.gstack-demo.py` 실행 금지 — Windows .venv로 (BUG-1 처리 방향) | 메모리 영구 저장, CLAUDE.md 갱신 권고 |
| **PM 4번째 담당 추가** | QA — 서비스 런타임 검증 (Bash·Playwright MCP) | 메모리 영구 저장 |
| **Codex 리뷰 통합** | 큰 PR 완료 시 codex CLI `review --uncommitted` 권장 | 본 세션 PR-V1.5에 적용 |
| **§11 rename** | "비기능 (Out of scope)" → "Out of scope + 알려진 한계" (§12 비기능 요구사항과 구분) | PR-V·V1.5 |
| **3 파일 분할** | `spec-time-and-place.md` 1633줄 → common·time·place 3 파일 | PR-V (`6769400`) |

---

## 5. 잠재 충돌·트레이드오프 (4건, 해소 상태)

| # | 충돌 | 해소 |
|---|---|---|
| **C1** | Q5 hybrid + Q7-b 방 전체 + Q15=A 실명 → 발화자 PII 간접 노출 | spec §3 페이로드에 `toggled_by: user_id` + Q7-c 차단 (구현 완료, v1.6에서 narrator 정밀화 후보) |
| **C2** | Q9 번복 불가 + Q7-b refresh → partial 상태 토글 시 시간 변경 가능성 | **PR-3.1 §6.9로 해소** (refresh가 partial 시 time_options 잠금 명시) |
| **C3** | Q1=B 단일 슬롯 + 거부 흐름 미정의 | **PR-3.1 §6.8로 해소** (단일 거부 → rejected_dates 누적 → F1 또는 N) |
| **~~C4~~** | ~~opt-out 정책 + calendar_consent default=False 모순~~ | **PR-X로 완전 해소** (`9609bee`) |

---

## 6. 결정 안건 단일 SoT

**spec-common.md** §결정 안건 표가 모든 Q 결정의 단일 SoT.

PR-V 3분할 후 `spec-time-coordination.md`·`spec-place-recommendation.md`에는 결정 인라인 인용만 (예: "Q1=B 결정"·"Q7-c=C1+C3+C4").
