# 시간+장소 기능정의서 작성 — 진행 상태 핸드오프 (v3)

작성: 2026-05-14
최종 갱신: 2026-05-14 (PR-Y2 후)
작성자: 본인 + Claude Opus 4.7 (PM 모드)
브랜치: `docs/spec-time-coordination` (origin 푸시 = `e996bba` 시점까지, 그 후 로컬 `adc444f`까지 진행)
대상 문서: `docs/handoff/spec-time-and-place.md` (기능정의서, 412줄)

> **다음 세션 빠른 컨텍스트 복구**: `cat docs/handoff/2026-05-14-spec-progress.md` 한 줄로 본 문서를 먼저 읽으세요.

---

## 1. 현재 상태 (한눈에)

- **스코프 확정**: 시간 + 장소 조율을 **한 문서**로 통합
- **파일**: `docs/handoff/spec-time-and-place.md` (rename·재구조·결정 반영 완료)
- **작성 진행**: §1~§5 + §11 완성, §6~§10 / §12 / §13 미작성
- **결정 누적**: **30건 확정 + 1건 미결** (Q7-c)
- **코드 작업**: PR-X·PR-Y1·PR-Y2 로컬 커밋 완료, **푸시 안 함**
- **운영 모드**: PM 모드 — 리더는 분배·통합·결정 제안, 깊은 분석은 3담당 에이전트에 위임 (메모리 영구 저장)

## 2. 이번 세션 변경 (커밋 8건)

| # | SHA | 메시지 | 변경 | 상태 |
|---|---|---|---|---|
| 8 | `adc444f` | feat(frontend): F1 fallback vote_card UI (배너·배지·토글) | +132 / -11 | 로컬 |
| 7 | `54e1532` | feat(pipeline): F1 fallback (다수결 vote_card) v1.0 구현 | +522 / -3 | 로컬 |
| 6 | `9609bee` | feat(consent): calendar_consent default True + 일괄 마이그 | +372 / -1 | 로컬 |
| 5 | `e996bba` | docs(handoff): 2026-05-14 진행 상태 v2 | +199 / 0 | origin |
| 4 | `a362a44` | docs(handoff): Q13~Q16 결정 4건 추가 | +6 / -2 | origin |
| 3 | `715650f` | docs(handoff): spec 잔존 불일치 4건 + Gemini 한계 | +8 / -4 | origin |
| 2 | `d53e0ed` | docs(handoff): 미결 결정 6건 반영 (Q7~Q12) | +16 / -12 | origin |
| 1 | `89571d4` | docs(handoff): spec §5 재구조 (7 서브섹션 6 컬럼) | +182 / -10 | origin |
|   | `494807e` | docs(handoff): spec 파일 rename + 해결점 N 추가 | +29 / 0 | origin |
|   | `1de2024` | (출발점) 시간 조율 초안 §1~§4·§11 | (기존) | origin |

**푸시 상태**: `origin/docs/spec-time-coordination`은 `e996bba`까지. 그 이후 로컬 미푸시 3 커밋(`9609bee`, `54e1532`, `adc444f`).

## 3. 수정한 파일

### 스펙·문서
- `docs/handoff/spec-time-and-place.md` — §5 재구조 + 결정 22건 반영
- `docs/handoff/audit-findings.md` — 해결점 N 정식 추가
- `docs/handoff/2026-05-14-spec-progress.md` — v1→v3 진행

### 코드 (이번 세션 PR-X·Y)
- `backend/app/models/user.py:35` — calendar_consent default `False → True`
- `backend/alembic/versions/e2a3b4c5d6f7_set_calendar_consent_default_true.py` — 신규 마이그레이션
- `backend/tests/integration/test_user_consent_default.py` — 신규 테스트 (248줄)
- `backend/app/services/pipeline/helpers/slots.py` — `_build_majority_fallback_slots` 함수 추가
- `backend/app/services/pipeline/nodes/function_call.py` — F1 trigger 분기
- `backend/app/services/pipeline/nodes/vote_card.py` — majority_fallback skip 예외·narrator·payload 필드
- `backend/app/services/pipeline/state.py` — blocker_notification/calendar_strategy 주석
- `backend/tests/unit/test_majority_fallback.py` — 신규 (149줄)
- `backend/tests/integration/test_f1_fallback_pipeline.py` — 신규 (220줄)
- `frontend/src/hooks/useAgentWebSocket.ts` — VoteCardTimeOption/Strategy/Blocker 타입 확장
- `frontend/src/components/meeting/ScheduleRecommendationCard.tsx` — majority_fallback UI

## 4. 확정된 결정 (30건)

### 4.1 핵심 정책 (6건)
| # | 항목 | 결정 |
|---|---|---|
| 스코프 | 기능정의서 범위 | **시간 + 장소 통합** (한 문서) |
| 파일명 | spec 파일 | **`spec-time-and-place.md`** |
| 동의 | 공유 동의 모델 | **opt-out 유지** (코드도 일치 — PR-X로 해소) |
| 게스트 | 게스트 식별 정책 | **방별 이름 기반 pseudo_id** (room_id × name) |
| 비기능 | 절 위치 | **§12 비기능** / **§13 부록** 분리 |
| 백로그 | 시연 후 보완 (P·O·ACT 4·5) | **별도 v2 spec 예고** |

### 4.2 Spec Q-시리즈 결정 (16건)
| # | 결정 | 적용 |
|---|---|---|
| **Q1** | B) 단일 슬롯도 vote_card 발행 (날짜범위 확정 전제) | spec ✅ |
| **Q2** | 선호 장소 다수결 → 동률 시 발화자 → 선호 없으면 방장 | spec ✅ |
| **Q3** | A) 방 멤버 수 사용 (headcount=None fallback) | spec ✅ |
| **Q5** | hybrid: 그룹 다수결 기본 + 발화자 토글 | spec ✅ |
| **Q6** | A) F1 fallback v1.0 구현 포함 | spec + 코드 (PR-Y1) ✅ |
| **Q7** | B) `preference_source` + `preference_toggle_enabled`, vote/place 양쪽 | spec ✅ |
| **Q7-b** | 방 전체 갱신 (broadcast) — refresh 라우트 신설 | spec ✅ |
| **Q8** | A) F1 fallback 정렬 = 시간 빠른 순 | spec + 코드 (PR-Y1) ✅ |
| **Q9** | A) partial maedeup 후 시간 번복 불가 | spec ✅ |
| **Q10** | C) Gemini prompt에 휴일·요일 라벨 안내 | spec ✅ (코드는 별도) |
| **Q11** | A) 일괄 True 자동 마이그레이션 | 코드 (PR-X) ✅ |
| **Q12** | A) headcount fallback에 게스트 포함 | spec ✅ |
| **Q13** | B) refresh 라우트 권한 = 발화자 + 방장만 | spec ✅ |
| **Q14** | C) Redis idempotency 캐시 + 일일 100회 상한 | spec ✅ |
| **Q15** | A) 토글 narrator = "OOO님 선호 기준" 실명 | spec ✅ |
| **Q16** | C) blocker_notification UI = 기본 익명 + 더보기 실명 | spec + 코드 (PR-Y2) ✅ |

### 4.3 구현 세부 결정 (7건, PR-X·Y에서 적용)
| # | 결정 |
|---|---|
| **Q-X1** | A) 명시적으로 False로 거부한 non-guest user도 포함 일괄 True (Q11=A 엄격 적용) |
| **Q-X2** | /m/consent JWT consent=True면 redirect 유지 (기본 권고) |
| **Q-X3** | `assistant.py:99` "캘린더 연동" 메시지 토큰 체크 보강은 별도 후속 PR |
| **Q-Y1** | payload 형식 = 슬롯별 `unavailable_users`/`available_count`/`total_count` |
| **Q-Y2** | Q16=C 토글 = 슬롯별 single-expand (`expandedUnavailableSlotId`) |
| **Q-Y3** | 이번 PR-Y는 F1 (케이스 A)만 — 권한 0%·모든 blocked 등은 별도 PR |
| **Q-Y4** | 28일 확장 후에도 0이면 F1 fallback (기본 권고) |

### 4.4 운영 결정 (1건)
- **해결점 N** = audit-findings.md에 정식 헤더 추가 (PR-0 완료)

## 5. 미결 결정 (1건)

| # | 결정 | 단서 | 처리 시점 |
|---|---|---|---|
| **Q7-c** | `preference_toggle_enabled=false` 트리거 조건 (게스트? 그룹·발화자 일치? 발화자 정보 부재?) | §3 페이로드 보강 | **PR-2 §3 작업 시** |

## 6. 남은 TODO

### ~~PR-X — calendar_consent 마이그레이션~~ ✅ 완료 (`9609bee`)
~~- backend/app/models/user.py:35 default False→True~~
~~- Alembic 마이그레이션 신규~~
~~- 통합 테스트~~
- [ ] **DB 마이그레이션 실행** (운영/dev 환경에서 `docker exec maedeup-api alembic upgrade head`)

### ~~PR-Y1·Y2 — F1 fallback~~ ✅ 완료 (`54e1532`·`adc444f`)
- [ ] **docker rebuild** (`docker compose up -d --build` for backend/frontend 변경 반영)
- [ ] **pytest 실행** 검증 (`pytest backend/tests/unit/test_majority_fallback.py backend/tests/integration/test_f1_fallback_pipeline.py -v`)
- [ ] **시연 시나리오 S8 수동 검증** (전원 가능 슬롯 0개 → 다수결 카드)

### PR-2 — §1~§4 동반 확장 (다음 작업)
- [ ] 헤더 라인1: "시간 조율 (Time Coordination)" → "시간·장소 조율"
- [ ] 헤더 라인5: 대상 노드에 `place_recommendation`, `maedeup_card_creation` 추가
- [ ] 헤더 line10 목적문: 장소 합의 보강
- [ ] §1.1 핵심 가치 — 장소 가치 보강 1줄
- [ ] §1.2 시스템 위치 — 노드 5/7 추가
- [ ] §1.3 책임 경계 — 장소 추천·확정 책임 추가
- [ ] §2 시나리오 — **S11~S14 장소 시나리오 4건 신설**
- [ ] §3 페이로드 — §3.3 `place_recommendation_payload`, §3.4·§3.5 `maedeup_card_payload` 확정/partial + **`preference_source`/`preference_toggle_enabled` 키 추가** (Q7=B 반영)
- [ ] §3.1 narrator — 4종 통합 + 토글 narrator 추가 (Q15=A "OOO님 선호 기준")
- [ ] §4.1 R 매트릭스 — R7 `place_hint`, R8 `place_coord`, R9 `cuisine`
- [ ] §4.2 P 매트릭스 — P4 음식 비선호, P5 areas, P6 transport_mode
- [ ] §4.3 T 매트릭스 — T6 Kakao, T7 ML, T8 Gemini
- [ ] §4.4 F 매트릭스 — F5 place_hint fallback(Q2 반영), F6 cuisine 미감지
- [ ] **Q7-c 결정 받기** (PR-2 §3 작업 시점)
- [ ] 변경 이력 갱신

### PR-3 — §6~§10 본격 신규 작성
- [ ] **§6 상태 및 예외 처리** — slot turns, awaiting/timeout, F1·F4 fallback narrator, 동시성 race, 해결점 P 번복, O 정규식 사각지대, 토큰 만료/revoke, **단일 슬롯 거부 흐름** (충돌 C3), **partial 시 time_options 잠금** (충돌 C2)
- [ ] **§7 권한·접근 조건** — 멤버/방장/게스트 권한 매트릭스, viewer_user_id 멤버십 검증
- [ ] **§8 데이터 정책** — opt-out 모델, `is_ai_filled` UI, k-anonymity 가드(소규모 방 N≤3), Redis 캐시 PII·만료, 동의 철회/삭제 SLA, **Q15 PII 트레이드오프 명시**
- [ ] **§9 API·이벤트·로그** — 시간+장소 엔드포인트 표, **`POST /meetings/{id}/recommendations/refresh` 명세** (Q13 권한 + Q14 rate limit 반영), 구조화 로그 필드
- [ ] **§10 회귀 테스트** — S1~S14 → pytest 매핑, fixture 패턴

### PR-4 — §12·§13 신설
- [ ] **§12 비기능 요구사항** — 성능(P95 ≤ 10s), 가용성, 보안, 프라이버시, 접근성(WCAG 2.1 AA), 관측성 + 측정 지표
- [ ] **§13 부록** — 다이어그램 인덱스, 마이그레이션 표, 환경변수(마스킹), 용어집

### 후속 / 별도 PR
- [ ] **assistant.py:99 보강** (Q-X3) — "캘린더 연동: 예/아니오" 토큰 체크 추가
- [ ] **0 슬롯 세분화** (Q-Y3 후속) — 캘린더 권한 0%, 모든 시간 blocked 등 케이스별 narrator

## 7. 다음에 이어서 할 명령

### 새 세션 시작 시 (recommended)
```bash
cat docs/handoff/2026-05-14-spec-progress.md
```

### 다음 작업별 진입 명령

**A. PR-2 시작 — §1~§4 보강 + Q7-c 결정**
```
PR-2 시작 — §1~§4 보강. Q7-c 결정 우선
```

**B. PR-3 시작 — §6~§10 본격 작성**
```
PR-3 시작 — §6 상태·예외부터 절 단위로
```

**C. PR-4 시작 — §12·§13 신설**
```
PR-4 시작 — §12 비기능 + §13 부록
```

**D. 푸시 (사용자 명시 승인 후)**
```
원격에 푸시 OK
```

**E. PR-X/Y 검증 (코드)**
```
docker rebuild + pytest 실행
```

## 8. 운영 모드 (PM 모드 + Handoff 자동 갱신, 메모리 영구 저장)

- 리더(Claude)는 **PM 역할만**: 작업 분배·진행 점검·결과 통합·최종 의사결정 제안
- 깊은 분석은 **항상 3담당 에이전트에 위임**:
  1. 코드 분석 담당
  2. 문서/기획 담당
  3. 리뷰/리스크 담당
- **PR 완료마다 handoff 문서 자동 갱신** — 별도 요청 없이도 진행
- 팀원 보고 없이 혼자 결론 금지. 추정은 반드시 "추정:" 마커.
- 파일 수정은 사용자 명시 승인 후에만.
- **원격 푸시 금지** (이번 세션 directive) — 로컬 커밋만, 푸시는 별도 명시 승인 후

메모리 위치: `/home/cyun0407/.claude/projects/-mnt-c-Users-cyun0-git-maedeup/memory/`

## 9. 알려진 잠재 충돌·트레이드오프

| # | 충돌·트레이드오프 | 상태 |
|---|---|---|
| C1 | Q5 hybrid + Q7-b 방 전체 갱신 + Q15=A 실명 → 발화자 PII 간접 노출 | PR-2 §3에서 `toggled_by: user_id` + Q7-c 차단 조건으로 완화 |
| C2 | Q9 번복 불가 + Q7-b refresh → partial 상태 토글 시 시간 변경 가능성 | PR-3 §9 refresh 라우트 명세에서 "partial/confirmed 시 time_options 잠금" 명시 |
| C3 | Q1=B 단일 슬롯 + 거부 흐름 미정의 | PR-3 §6에 "단일 슬롯 거부 → rejected_dates 누적 → F1 또는 N" 명시 |
| ~~C4~~ | ~~opt-out 정책 + calendar_consent default=False 모순~~ | **PR-X로 해소** (`9609bee`) |

## 10. 참고 SoT

| 파일 | 역할 |
|---|---|
| `docs/handoff/spec-time-and-place.md` | 기능정의서 본문 (작성 중, 412줄) |
| `docs/handoff/audit-findings.md` | 해결점 A~P 누적 (N 추가됨) |
| `docs/handoff/demo-scenario.md` | 시연 시나리오 SoT |
| `docs/handoff/2026-05-13-recommend-input-catalog.md` | 입력 카탈로그 6 카테고리, P0/P1/P2 |
| `docs/handoff/2026-05-13-pipeline-split-plan.md` | 9노드 분할 계획 |
| `docs/handoff/diagrams/*.mmd` | Mermaid 다이어그램 SoT (7개) |
| `CLAUDE.md` | 프로젝트 운영 규칙 (Never·코딩 규칙·시연 후 보완 항목) |

## 11. 메모: CLAUDE.md "현재 task" 갱신 권고

`CLAUDE.md` "현재 task"는 시연 직전 시점을 가리킴. 본 핸드오프 문서가 우선 SoT.
다음 세션 시작 시 사용자 결정으로:
- (a) CLAUDE.md 갱신 (PR-2 또는 별도)
- (b) 본 핸드오프 문서 우선, CLAUDE.md 그대로
