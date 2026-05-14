# 시간+장소 기능정의서 작성 — 진행 상태 핸드오프 (v3)

작성: 2026-05-14
최종 갱신: 2026-05-15 (QA 시연 dry-run 후 — **백엔드 OK, 시연 환경 셋업 진행 중**)
작성자: 본인 + Claude Opus 4.7 (PM 모드 + QA + Playwright MCP)
브랜치: `docs/spec-time-coordination` (origin 푸시 = `e996bba` 시점까지, 그 후 로컬 `0ffdfbe`까지 진행)
대상 문서 (PR-V로 3분할):
- `docs/handoff/spec-common.md` — 공통 정책·권한·API·비기능·결정 안건·변경 이력 SoT (~700줄)
- `docs/handoff/spec-time-coordination.md` — 시간 조율 본문 (~700줄, git mv로 history 보존)
- `docs/handoff/spec-place-recommendation.md` — 장소 추천 본문 (~500줄, 신규)
- (구) `docs/handoff/spec-time-and-place.md` 1633줄 → 3-파일 분할 완료
추가 문서:
- `docs/handoff/2026-05-14-spec-review-guide.md` (외부 리뷰 가이드, 212줄, c)
- `docs/handoff/2026-05-14-spec-v2-plan.md` (v2 spec 계획, 304줄, e)
신규 코드 PR (Q5 hybrid 인프라):
- PR-Z1 백엔드 (`66110e9`): refresh 라우트 + P0-2·3·4 + 메타 키 + Q7-c, 9 files +946
- PR-Z2 프론트 (`ea759d1`): 토글 UI + refresh API 호출, 3 files +255/-1

> **다음 세션 빠른 컨텍스트 복구**: `cat docs/handoff/2026-05-14-spec-progress.md` 한 줄로 본 문서를 먼저 읽으세요.

---

## 1. 현재 상태 (한눈에)

- **스코프 확정**: 시간 + 장소 조율을 **한 문서**로 통합
- **파일**: 구 `docs/handoff/spec-time-and-place.md` (헤더·§1~§5·§11 시간+장소 통합 완료) → PR-V로 3분할 (`spec-common.md`·`spec-time-coordination.md`·`spec-place-recommendation.md`)
- **작성 진행**: **§1~§13 모두 완성 ✅** (spec v1.0)
- **코드 구현**: spec v1.0의 **핵심 미구현 항목(Q5 hybrid 인프라) 완성 ✅** (PR-Z1·Z2)
- **결정 누적**: **31건 확정 + 1건 신규 미결** (Q17 F4 narrator 실명/익명)
- **코드 작업**: PR-X·PR-Y1·PR-Y2 로컬 커밋 완료, **푸시 안 함**
- **운영 모드**: PM 모드 — 리더는 분배·통합·결정 제안, 깊은 분석은 3담당 에이전트에 위임 (메모리 영구 저장)

## 2. 이번 세션 변경 (커밋 39건)

| # | SHA | 메시지 | 변경 | 상태 |
|---|---|---|---|---|
| 39 | `aaec29d` | fix(test-infra): P3 — alembic batch + JSON dialect + test seed (PR-V1.5.2) | +208 / -193 | 로컬 |
| 38 | `dcc9c9c` | docs(handoff): v15 — QA + P2 hotfix 완료 반영 | +6 / -4 | 로컬 |
| 37 | `1892b50` | fix(test-infra): QA P2 hotfix (PR-V1.5.1) — alembic·JSON·SENTINEL | +60 / -11 | 로컬 |
| 36 | `625cdac` | docs(handoff): v14 — PR-V1.5 + Codex P1·P2 통합 반영 | +9 / -4 | 로컬 |
| 35 | `90131f2` | feat(pipeline): spec v1.0 미구현 12건 + Codex P1·P2 (PR-V1.5) | +1342 / -54 | 로컬 |
| 34 | `6769400` | docs(handoff): spec 3 분리 (PR-V) — common·time·place | +1943 / -1646 | 로컬 |
| 33 | `76d7949` | docs(handoff): v13 — PR-W 장소 보강 완료 반영 | +7 / -5 | 로컬 |
| 32 | `1921fc7` | docs(handoff): v6 갱신 — PR-3.2 §7 완료 반영 | (보강) | 로컬 |
| 31 | (PR-V·W 커밋 누적) | | | |
| 30 | `698793f` | docs(handoff): spec 장소 보강 (PR-W) — S15~S20·F7~F9·§6.14~6.18 | +115 / -5 | 로컬 |
| 29 | `b7335ef` | docs(handoff): v12 — PR-Z1·Z2 완료 반영 | +22 / -8 | 로컬 |
| 28 | `ea759d1` | feat(frontend): Q5 hybrid 토글 UI + refresh API (PR-Z2) | +255 / -1 | 로컬 |
| 27 | `66110e9` | feat(pipeline): Q5 hybrid refresh 라우트 + P0 plumbing (PR-Z1) | +946 / -4 | 로컬 |
| 26 | `b3d1509` | docs(handoff): v2 spec 계획서 (e) — 38 항목 / 10 카테고리 | +304 / 0 | 로컬 |
| 25 | `90f5bb0` | docs(handoff): 외부 리뷰 가이드 (c) — 심사위원·협업자용 | +212 / 0 | 로컬 |
| 24 | `672f3cd` | docs(handoff): spec d-cleanup — §11 rename + Q11 결정 표 갱신 | +2 / -2 | 로컬 |
| 23 | `b735699` | docs(handoff): v10 final — v1.0 완성 반영 | +34 / -13 | 로컬 |
| 22 | `1a9f1e2` | docs(handoff): spec §12 비기능 + §13 부록 (PR-4) — **v1.0 완성** | +208 / 0 | 로컬 |
| 21 | `e963d86` | docs(handoff): v9 갱신 — PR-3.5 §10 완료 + PR-3 종료 | +9 / -7 | 로컬 |
| 20 | `f287088` | docs(handoff): spec §10 회귀 테스트 (PR-3.5) | +102 / -9 | 로컬 |
| 19 | `14c31de` | docs(handoff): v8 갱신 — PR-3.4 §9 완료 반영 | +9 / -7 | 로컬 |
| 18 | `8955b00` | docs(handoff): spec §9 API·이벤트·로그 (PR-3.4) | +226 / -5 | 로컬 |
| 17 | `54a4fb8` | docs(handoff): v7 갱신 — PR-3.3 §8 완료 반영 | +17 / -14 | 로컬 |
| 16 | `b37b9af` | docs(handoff): spec §8 데이터 정책 (PR-3.3) | +137 / -4 | 로컬 |
| 15 | `1921fc7` | docs(handoff): v6 갱신 — PR-3.2 §7 완료 반영 | +9 / -7 | 로컬 |
| 14 | `2ef873b` | docs(handoff): spec §7 권한·접근 조건 (PR-3.2) | +116 / -3 | 로컬 |
| 13 | `7386035` | docs(handoff): v5 갱신 — PR-3.1 §6 완료 반영 | +16 / -14 | 로컬 |
| 12 | `36eed6c` | docs(handoff): spec §6 상태 및 예외 처리 (PR-3.1) | +216 / -5 | 로컬 |
| 11 | `471128c` | docs(handoff): v4 갱신 — PR-2 완료 반영 | +31 / -32 | 로컬 |
| 10 | `d3b7d89` | docs(handoff): spec §1~§4 시간+장소 보강 (PR-2, 12 위치) | +157 / -25 | 로컬 |
| 9 | `9ce7de4` | docs(handoff): v3 갱신 — PR-X·Y1·Y2 완료 반영 | +119 / -88 | 로컬 |
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

**푸시 상태**: `origin/docs/spec-time-coordination`은 `e996bba`까지. 그 이후 **로컬 미푸시 32 커밋** (PR-X·Y·Z·W·V·V1.5 + 문서 v1.0 + 외부 리뷰·v2 계획·cleanup).

## 3. 수정한 파일

### 스펙·문서
- `docs/handoff/spec-common.md` · `spec-time-coordination.md` · `spec-place-recommendation.md` — PR-V 3분할 (기존 `spec-time-and-place.md` git mv → `spec-time-coordination.md`로 history 보존, 공통/장소 신규 작성)
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
| 파일명 | spec 파일 | **3-파일 분할** (PR-V): `spec-common.md` + `spec-time-coordination.md` + `spec-place-recommendation.md` |
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
| **Q17** | F4 캘린더 권한 만료 narrator 실명/익명 | §8.6 PR-3.3에서 식별 | PR-3.4 §9 작성 시 또는 별도 라운드. 권고: A) 실명 (Q15=A 일관 + 액션 가능성) |

**기타 잠재 결정 (PR-3.4·3.5 작성 시 자연 발생 가능)**:
- §9 API 에러 응답 형식 (rate limit 초과·권한 없음)
- §10 fixture 패턴 (기존 backend/tests/conftest.py 따를지)

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

### ~~PR-2 — §1~§4 동반 확장~~ ✅ 완료 (`d3b7d89`)
~~- 헤더·§1.1~1.3 시간+장소 보강~~
~~- §2 S11~S14 장소 시나리오 4건~~
~~- §3 페이로드 4종 통합 (vote/place/maedeup 확정·partial) + preference_source/toggle_enabled~~
~~- §3.5 narrator 4종 통합 + 토글 narrator (Q15)~~
~~- §4 R/P/T/F 매트릭스 장소 항목 추가 (R7~9·P4~6·T6~8·F5~6)~~
~~- Q7-c 결정 (C1+C3+C4, C2 제외)~~
~~- 변경 이력 갱신~~
- [ ] (선택) §5.2.1 "3종 4변형" 헤더 검토 (place 별도 카드로 명시 후 4종 4변형 갱신 여부)
- [ ] (선택) 노드 번호 (6a/6b/7) 정합 검증 — `pipeline-structure.html`·카탈로그와 일대일

### PR-3 — §6~§10 본격 신규 작성 (절 단위)
- [x] **PR-3.1 §6 상태 및 예외 처리** ✅ `36eed6c` — 13 하위 절, 충돌 C2·C3 해소
- [x] **PR-3.2 §7 권한·접근 조건** ✅ `2ef873b` — 9 하위 절, 권한 매트릭스 15행 × 4역할
- [x] **PR-3.3 §8 데이터 정책** ✅ `b37b9af` — 9 하위 절 + PII 보존 표 11행 + 알려진 갭 8건
- [x] **PR-3.4 §9 API·이벤트·로그** ✅ `8955b00` — 8 하위 절, 31 엔드포인트 + refresh 명세 + 26 [TIMING] 로그
- [x] **PR-3.5 §10 회귀 테스트** ✅ `f287088` — 8 하위 절, S1~S14 매핑 + S15·negative 10건 + 우선순위 P0/P1/P2

### ~~PR-4 — §12·§13 신설~~ ✅ 완료 (`1a9f1e2`) — **spec v1.0 완성**
- ~~§12 비기능 요구사항~~ — 8 하위 절, 성능·가용성·보안·프라이버시·접근성·다국어·관측성·acceptance gate
- ~~§13 부록~~ — 6 하위 절, 다이어그램·마이그레이션 22행·환경변수·용어집 19·변경 이력·SoT

### ~~후속 cleanup~~ ✅ 완료 (`672f3cd`)
- [x] **§11 rename** — "비기능 (Out of scope)" → "Out of scope + 알려진 한계"
- [x] **결정 안건 표 Q11 갱신** — "미결" → "결정: A) 일괄 True 자동 (PR-X 9609bee 적용)"

### 추가 산출물 (c·e)
- [x] **외부 리뷰 가이드** ✅ `90f5bb0` — `2026-05-14-spec-review-guide.md` (212줄, FAQ·심사위원 가이드)
- [x] **v2 spec 계획서** ✅ `b3d1509` — `2026-05-14-spec-v2-plan.md` (304줄, 38 항목·PR-v2 6단계)

### 코드 검증 (b, 사용자 환경 의존)
- [ ] **Docker Desktop WSL 통합 활성화** (Settings → Resources → WSL Integration → Ubuntu-22.04 토글 ON)
- [ ] 통합 후 `docker compose up -d --build` (PR-Y2·PR-Z2 frontend 반영)
- [ ] `docker exec maedeup-api alembic upgrade head` (PR-X 마이그)
- [ ] pytest 실행:
  ```
  docker exec maedeup-api pytest \
    backend/tests/integration/test_user_consent_default.py \
    backend/tests/unit/test_majority_fallback.py \
    backend/tests/integration/test_f1_fallback_pipeline.py \
    backend/tests/unit/test_preference_toggle.py \
    backend/tests/integration/test_refresh_route.py -v
  ```
- [ ] 시연 시나리오 수동 검증 (S1·S2·S4·S8·S11·S12·S15.1·S15.2 = P0 8건)

### 후속 / 별도 PR
- [ ] **assistant.py:99 보강** (Q-X3) — "캘린더 연동: 예/아니오" 토큰 체크 추가
- [ ] **0 슬롯 세분화** (Q-Y3 후속) — 캘린더 권한 0%, 모든 시간 blocked 등 케이스별 narrator

## 7. 다음에 이어서 할 명령

### 새 세션 시작 시 (recommended)
```bash
cat docs/handoff/2026-05-14-spec-progress.md
```

### 다음 작업별 진입 명령

**A. 푸시 (사용자 명시 승인 후)**
```
원격에 푸시 OK — 21 커밋 origin으로
```

**B. 코드 검증 (Docker Desktop WSL 통합 후)**
```
도커 켜졌으니 검증 시작 — pytest + 시연 P0 8건
```

**C. spec v1.0 외부 리뷰 진행**
```
외부 리뷰 가이드(2026-05-14-spec-review-guide.md) 공유
```

**D. v2 spec 작성 시작**
```
PR-v2.0 시작 — Q18~Q25 결정 라운드 후
```

**E. 시연 진행**
```
시연 시작 (PR-X·Y·spec v1.0 적용 후)
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
| ~~C2~~ | ~~Q9 번복 불가 + Q7-b refresh → partial 상태 토글 시 시간 변경 가능성~~ | **PR-3.1 §6.9로 해소** (refresh가 partial 시 time_options 잠금 명시) |
| ~~C3~~ | ~~Q1=B 단일 슬롯 + 거부 흐름 미정의~~ | **PR-3.1 §6.8로 해소** (단일 거부 → rejected_dates 누적 → F1 또는 N) |
| ~~C4~~ | ~~opt-out 정책 + calendar_consent default=False 모순~~ | **PR-X로 해소** (`9609bee`) |

## 10. 참고 SoT

| 파일 | 역할 |
|---|---|
| `docs/handoff/spec-common.md` | 기능정의서 공통 SoT (권한·데이터·API·비기능·결정 안건·변경 이력) |
| `docs/handoff/spec-time-coordination.md` | 기능정의서 시간 조율 본문 |
| `docs/handoff/spec-place-recommendation.md` | 기능정의서 장소 추천 본문 |
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
