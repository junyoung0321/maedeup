# 시간+장소 기능정의서 작성 — 진행 상태 핸드오프 (v2)

작성: 2026-05-14
최종 갱신: 2026-05-14 (PR-1.8 후)
작성자: 본인 + Claude Opus 4.7 (PM 모드)
브랜치: `docs/spec-time-coordination` (origin 푸시 = 89571d4 시점까지, 그 후 로컬 a362a44 까지 진행)
대상 문서: `docs/handoff/spec-time-and-place.md` (기능정의서, 412줄)

> **다음 세션 빠른 컨텍스트 복구**: `cat docs/handoff/2026-05-14-spec-progress.md` 한 줄로 본 문서를 먼저 읽으세요.

---

## 1. 현재 상태 (한눈에)

- **스코프 확정**: 시간 + 장소 조율을 **한 문서**로 통합
- **파일**: `docs/handoff/spec-time-and-place.md` (rename·재구조·결정 반영 완료)
- **작성 진행**: §1~§5 + §11 완성, §6~§10 / §12 / §13 미작성
- **결정 누적**: **22건 확정 + 2건 미결** (Q7-c, Q11)
- **운영 모드**: PM 모드 — 리더는 분배·통합·결정 제안, 깊은 분석은 3담당 에이전트에 위임 (메모리 영구 저장)

## 2. 이번 세션 변경 (커밋 5건)

| SHA | 메시지 | 변경 |
|---|---|---|
| `a362a44` | Q13~Q16 결정 4건 추가 (refresh 권한·rate limit·narrator·blocker UI) | +6 / -2 |
| `715650f` | spec 잔존 불일치 4건 정리 + Gemini 휴일 라벨 한계 명시 | +8 / -4 |
| `d53e0ed` | spec 미결 결정 6건 반영 (Q7·Q7-b·Q8·Q9·Q10·Q12) | +16 / -12 |
| `89571d4` | spec §5 재구조 (기능별 7 서브섹션) + 결정 안건 갱신 | +182 / -10 |
| `494807e` | spec 파일 rename + audit-findings 해결점 N 추가 | +29 / 0 |
| `1de2024` | (이전 커밋) 시간 조율 기능정의서 초안 (§1~§4, §11) | (출발점) |

**푸시 상태**: `origin/docs/spec-time-coordination`은 `89571d4`까지 (PR-1.6 / PR-1.7 / PR-1.8은 로컬만, 푸시 대기).

## 3. 수정한 파일

- `docs/handoff/spec-time-and-place.md` — rename + §5 재구조 + 결정 22건 반영
- `docs/handoff/audit-findings.md` — 해결점 N(다음주 자동 확장) 정식 헤더 추가 (line 942~)

## 4. 확정된 결정 (22건)

### 4.1 핵심 정책 (6건)
| # | 항목 | 결정 |
|---|---|---|
| 스코프 | 기능정의서 범위 | **시간 + 장소 통합** (한 문서) |
| 파일명 | spec 파일 | **`spec-time-and-place.md`** |
| 동의 | 공유 동의 모델 | **opt-out 유지** (단, models/user.py:35 default=False 모순 → PR-X에서 정정, Q11) |
| 게스트 | 게스트 식별 정책 | **방별 이름 기반 pseudo_id** (room_id × name) |
| 비기능 | 절 위치 | **§12 비기능** / **§13 부록** 분리 |
| 백로그 | 시연 후 보완 (P·O·ACT 4·5) | **별도 v2 spec 예고** |

### 4.2 Q-시리즈 결정 (15건)
| # | 결정 |
|---|---|
| **Q1** | B) 단일 슬롯도 vote_card 발행 (날짜범위 확정 상태 전제) |
| **Q2** | 선호 장소 다수결 → 동률 시 발화자 → 선호 없으면 방장 위치 |
| **Q3** | A) 방 멤버 수 사용 (headcount=None fallback) |
| **Q5** | hybrid: 그룹 다수결 기본 + 발화자 토글 |
| **Q6** | A) F1 fallback v1.0 구현 포함 |
| **Q7** | B) `preference_source: "group"\|"speaker"` + `preference_toggle_enabled: bool`, vote_card·place 양쪽 |
| **Q7-b** | 방 전체 갱신 (broadcast) — `POST /meetings/{id}/recommendations/refresh` 신설 |
| **Q8** | A) F1 fallback 정렬 = 시간 빠른 순 |
| **Q9** | A) partial maedeup 후 시간 번복 불가 (재추천은 별도 경로) |
| **Q10** | C) Gemini prompt에 휴일·요일 라벨 안내 (helpers/dates.py 헬퍼 import) |
| **Q12** | A) headcount fallback에 게스트 포함 |
| **Q13** | B) refresh 라우트 권한 = 발화자 + 방장만 |
| **Q14** | C) Redis idempotency 캐시 + 일일 100회 상한 |
| **Q15** | A) 토글 narrator = "OOO님 선호 기준" 실명 (PII 트레이드오프 인지) |
| **Q16** | C) blocker_notification UI = 기본 익명 + 더보기 실명 |

### 4.3 운영 결정 (1건)
- **해결점 N** = audit-findings에 정식 추가 (PR-0 완료)

## 5. 미결 결정 (2건만)

| # | 결정 | 단서 | 처리 시점 |
|---|---|---|---|
| **Q7-c** | `preference_toggle_enabled=false` 트리거 조건 (게스트? 그룹·발화자 일치? 발화자 정보 부재?) | §3 페이로드 보강 | PR-2 §3 작업 시 |
| **Q11** | 기존 사용자 `calendar_consent` 마이그레이션 전략 (default False → True) | PR-X (별도 마이그레이션) | PR-X 진행 시 |

## 6. 남은 TODO

### PR-Y — F1 fallback 우선 구현 (사용자 결정, 시연 영향)
- [ ] F1 fallback 로직 (전원 가능 슬롯 0개 → 가능 멤버 max인 슬롯 3개)
- [ ] `blocker_notification_payload` 생성 → UI 연결
- [ ] 정렬: 시간 빠른 순 (Q8=A)
- [ ] 멤버 식별: 기본 익명 + 클릭 시 실명 (Q16=C)
- 시연 시나리오 S8 활성화에 필수

### PR-X — 운영 영향 큼, 별도 진행
- [ ] **`backend/app/models/user.py:35`** `calendar_consent: bool = Field(default=False)` → `default=True`
- [ ] **Alembic 마이그레이션** 신규 작성 (기존 사용자의 `calendar_consent=False/NULL` 처리 전략 — Q11 결정 필요)
- [ ] 동의 화면 UI 영향 검토 (`/m/consent`)

### PR-2 — §1~§4 동반 확장 (문서 일관성 에이전트가 식별한 12 위치)
- [ ] 헤더 라인1: "시간 조율 (Time Coordination)" → "시간·장소 조율"
- [ ] 헤더 라인5: 대상 노드에 `place_recommendation`, `maedeup_card_creation` 추가
- [ ] 헤더 line10 목적문: 장소 합의 보강
- [ ] §1.1 핵심 가치 — 장소 가치 보강 1줄
- [ ] §1.2 시스템 위치 — 노드 5/7 추가
- [ ] §1.3 책임 경계 — 장소 추천·확정 책임 추가
- [ ] §2 시나리오 — **S11~S14 장소 시나리오 4건 신설**
- [ ] §3 페이로드 — §3.3 `place_recommendation_payload`, §3.4·§3.5 `maedeup_card_payload` 확정/partial + **§3에 `preference_source`/`preference_toggle_enabled` 키 추가**
- [ ] §3.1 narrator — 4종 통합 + 토글 narrator 추가 (Q15=A)
- [ ] §4.1 R 매트릭스 — R7 `place_hint`, R8 `place_coord`, R9 `cuisine`
- [ ] §4.2 P 매트릭스 — P4 음식 비선호, P5 areas, P6 transport_mode
- [ ] §4.3 T 매트릭스 — T6 Kakao, T7 ML, T8 Gemini
- [ ] §4.4 F 매트릭스 — F5 place_hint fallback(Q2 반영), F6 cuisine 미감지
- [ ] **Q7-c 결정** (이 시점에 필요)
- [ ] 변경 이력 갱신

### PR-3 — §6~§10 본격 신규 작성 (절 단위)
- [ ] **§6 상태 및 예외 처리** — slot turns, awaiting/timeout, F1·F4 fallback narrator, 동시성 race, 해결점 P 번복, O 정규식 사각지대, 토큰 만료/revoke, **단일 슬롯 거부 흐름** (충돌 C3), **partial 시 time_options 잠금** (충돌 C2)
- [ ] **§7 권한·접근 조건** — 멤버/방장/게스트 권한 매트릭스, viewer_user_id 멤버십 검증
- [ ] **§8 데이터 정책** — opt-out 모델, `is_ai_filled` UI, k-anonymity 가드(소규모 방 N≤3), Redis 캐시 PII·만료, 동의 철회/삭제 SLA, **Q15 PII 트레이드오프 명시**
- [ ] **§9 API·이벤트·로그** — 시간+장소 엔드포인트 표, **`POST /meetings/{id}/recommendations/refresh` 명세** (Q13 권한 + Q14 rate limit 반영), 구조화 로그 필드
- [ ] **§10 회귀 테스트** — S1~S14 → pytest 매핑, fixture 패턴

### PR-4 — §12·§13 신설
- [ ] **§12 비기능 요구사항** — 성능(P95 ≤ 10s), 가용성, 보안, 프라이버시, 접근성(WCAG 2.1 AA), 관측성 + 측정 지표
- [ ] **§13 부록** — 다이어그램 인덱스(`docs/handoff/diagrams/*.mmd`), 마이그레이션 표, 환경변수(마스킹), 용어집

## 7. 다음에 이어서 할 명령

### 새 세션 시작 시 (recommended)
```bash
cat docs/handoff/2026-05-14-spec-progress.md
```

### 다음 작업별 진입 명령

**A. 푸시 (PR-1.6 / 1.7 / 1.8 origin으로)**
```
PR-1.6 / 1.7 / 1.8 푸시
```

**B. PR-Y 시작 — F1 fallback 우선 구현 (시연 영향)**
```
PR-Y 시작 — F1 fallback 코드 구현
```

**C. PR-X 시작 — Q11 결정 + calendar_consent 마이그레이션**
```
PR-X 시작 — Q11 결정 받고 마이그레이션
```

**D. PR-2 시작 — §1~§4 보강 + Q7-c 결정**
```
PR-2 시작 — §1~§4 보강. Q7-c 결정 우선
```

**E. PR-3 시작 — §6~§10 본격 작성**
```
PR-3 시작 — §6 상태·예외부터 절 단위 작성
```

**F. PR-4 시작 — §12·§13 신설**
```
PR-4 시작 — §12 비기능 + §13 부록
```

## 8. 운영 모드 (PM 모드, 메모리 영구 저장)

리더(Claude)는 **PM 역할만**:
- 작업 분배·진행 점검·결과 통합·최종 의사결정 제안
- 깊은 분석은 **항상 3담당 에이전트에 위임**:
  1. **코드 분석 담당** — 실제 구현, API/데이터 흐름, 폴더 구조
  2. **문서/기획 담당** — README, docs, 기획 문서, 시나리오, 목차
  3. **리뷰/리스크 담당** — 누락 요구사항, 예외 케이스, 권한·보안·개인정보·운영 리스크, 과장·미확인 표현 점검
- 팀원 보고 없이 혼자 결론 금지. 추정은 반드시 "추정:" 마커.
- 파일 수정은 사용자 명시 승인 후에만.

메모리 위치: `/home/cyun0407/.claude/projects/-mnt-c-Users-cyun0-git-maedeup/memory/feedback_pm_operating_mode.md`

## 9. 알려진 잠재 충돌·트레이드오프 (PR-3 작성 시 반영)

| # | 충돌·트레이드오프 | 해소 방안 |
|---|---|---|
| C1 | Q5 hybrid + Q7-b 방 전체 갱신 + Q15=A 실명 → 발화자 PII 간접 노출 | §3 페이로드에 `toggled_by: user_id` + narrator 실명 + Q7-c 차단 조건에 사용자 share_*_data 동의 여부 반영 |
| C2 | Q9 번복 불가 + Q7-b refresh → partial 상태 토글 시 시간 변경 가능성 | §9 refresh 라우트 명세에 "`partial_mode == "time_only"` 또는 confirmed 상태면 `time_options` 잠금, place만 갱신" 명시 |
| C3 | Q1=B 단일 슬롯 + 거부 흐름 | §6에 "단일 슬롯 거부 → rejected_dates 누적 → 다음 turn에서 F1 또는 N(다음주 확장)" 명시 |
| C4 | opt-out + calendar_consent default=False | Q11 결정 + PR-X 마이그레이션 |

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

`CLAUDE.md` "현재 task" 라인은 시연 직전 시점을 가리키지만, 실제 작업은 기능정의서로 전환됨. 다음 세션 시작 시 사용자 결정으로:
- (a) CLAUDE.md 갱신 (PR-2 또는 별도)
- (b) 본 핸드오프 문서를 우선 SoT로 두고 CLAUDE.md는 그대로
