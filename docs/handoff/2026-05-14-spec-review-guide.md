# 기능정의서 v1.0 — 외부 리뷰 가이드

작성: 2026-05-14
대상: 졸업 심사위원·협업자 (외부 리뷰자)
본문 (PR-V로 3분할):
- [`docs/handoff/spec-common.md`](./spec-common.md) — 공통 정책·권한·API·비기능·부록 (단일 SoT, 결정 안건·변경 이력 포함)
- [`docs/handoff/spec-time-coordination.md`](./spec-time-coordination.md) — 시간 조율 본문 (§1~§6 시간·§10 회귀)
- [`docs/handoff/spec-place-recommendation.md`](./spec-place-recommendation.md) — 장소 추천 본문 (§1~§6 장소·§10 회귀)
진행 핸드오프: [`docs/handoff/2026-05-14-spec-progress.md`](./2026-05-14-spec-progress.md)

> 본 문서는 본문 1523줄을 직접 읽지 않아도 핵심을 파악할 수 있도록 작성한 self-contained 안내서다. 심사위원은 §1~§5만 읽으면 5~10분 안에 전체 그림을 잡을 수 있다. 협업자는 §6~§9에서 필요한 절·테스트·SoT로 빠르게 점프하면 된다.

---

## 1. 한 줄 요약

**매듭(Maedeup)** = AI 모임 조율 플랫폼. 채팅방의 시간·장소 교착을 자동 감지해 투표 카드·장소 추천 카드를 생성한다. **본 spec(spec-common·spec-time-coordination·spec-place-recommendation 3-파일, v1.0)은 그 핵심 흐름 — 시간·장소 조율 기능 — 의 단일 SoT(Source of Truth) 기능정의서**다 (PR-V로 분할).

---

## 2. 1분 개요 (Executive Summary)

### 2.1 매듭이 푸는 문제
- 카톡·디스코드 같은 그룹 채팅에서 시간/장소 조율이 무한 핑퐁("언제 모일까?" → "다 안 돼")으로 빠지는 현상.
- 사용자 발화·캘린더·선호도를 통합해 **합의 가능한 후보 슬롯·장소 카드**로 변환.
- 결과를 "매듭 카드"(확정/partial)로 마무리해 모임 의사결정을 종결.

### 2.2 5가지 차별점 (시연 SoT)
1. **자동 트리거** — 사용자가 봇 호출 안 해도 채팅 교착·합의 신호 자동 감지 (`stalemate_judged` / `conclusion_detected` / `all_members_selected` / `direct_request` 4종).
2. **그룹/발화자 선호 hybrid 토글** — 그룹 다수결 기본 + 발화자 선호로 토글 가능 (Q5/Q7 결정).
3. **부분 카드(partial maedeup)** — 시간만 결정돼도 카드 발행, 장소는 추후 자동 갱신 (Q9 시간 잠금).
4. **fallback narrator 매트릭스** — 전원 불가/캘린더 권한 없음/단일 슬롯 등 6종 fallback 모두 사용자 인지 명문화 (F1~F6).
5. **PII 보호 점진 공개** — k-anonymity·익명+더보기·실명 narrator를 결정 안건 17건으로 명세 (Q15·Q16·Q17).

### 2.3 본 spec이 다루는 노드
- `slot_filling` (노드 3) — 발화·캘린더·선호 통합
- `function_calling` 캘린더 path (노드 4) — `get_free_slots`
- `vote_card_creation` (노드 6a) — 시간 투표 카드
- `place_recommendation` (노드 6b) — 장소 추천 카드 (ML/Gemini reranking)
- `maedeup_card_creation` (노드 7) — 확정/partial 카드

### 2.4 spec 분량
1523줄 / 13개 절 / 결정 31건 + 신규 미결 1건(Q17) / 회귀 시나리오 19건(S1~S14 + S15.1~5).

---

## 3. spec §1~§13 절 요약

| 절 | 분량 | 핵심 |
|---|---|---|
| **§1 기능 개요** | ~30줄 | 핵심 가치 한 문장 + 시스템 위치(5개 노드) + 책임 경계(✅ 포함 / ❌ 미포함) |
| **§2 사용자 시나리오** | ~25줄 | 골든 회귀 14건 (S1~S14). §10 회귀 테스트의 1:1 원본 |
| **§3 출력 카드 페이로드** | ~150줄 | 4종 JSON 스키마 (vote_card·place_recommendation·maedeup 확정·partial) + narrator 4종 |
| **§4 기능 매트릭스** | ~50줄 | R(인식)/P(선호)/T(탐색)/F(fallback) 4 레이어 × 6~9 항목 |
| **§5 입력·출력 데이터 카탈로그** | ~170줄 | 7 기능 서브섹션에 입력 ~40개 (✅/⚠️/🔧 마크), 출력 카드 3종 4변형, P0 plumbing 6개 |
| **§6 상태·예외 처리** | ~220줄 | 13 하위 절. 노드 예외(`_handle_node_exception`), F1~F4 narrator, race condition, 토큰 만료, 단일 슬롯 거부 흐름, Q9 시간 잠금, conclusion_false_positive, 해결점 P·O backlog |
| **§7 권한·접근 조건** | ~120줄 | 9 하위 절. 역할 4종(방장/멤버/게스트/비멤버), 권한 매트릭스 15행 × 4역할, viewer_user_id privacy boundary, refresh 권한(Q13), 토글 차단 조건(Q7-c), 게스트 정책(Q12) |
| **§8 데이터 정책** | ~140줄 | 9 하위 절. opt-out 동의(Q-X1), is_ai_filled UI(✨), k-anonymity 가드(v1.5 후보), Redis 캐시 TTL, 동의 철회 SLA, narrator PII(Q15·Q16·Q17), PII 보존 표 11행, 알려진 갭 8건 |
| **§9 API·이벤트·로그** | ~220줄 | 8 하위 절. 31 엔드포인트 인벤토리, refresh 라우트 신규 명세(Q13·Q14), WebSocket 채널, 구조화 로그 26 [TIMING] 키, audit log, 에러 응답 형식 6종, Q17 권고 A, 미구현 갭 7건 |
| **§10 회귀 테스트** | ~100줄 | 8 하위 절. S1~S14 pytest 매핑 + S15(refresh) 5건 + negative 5건, 신규 fixture 7종, P0/P1/P2 우선순위, 동시성, v2 backlog |
| **§11 Out of scope** | ~12줄 | 비목표(반복 모임·비-Google 캘린더·시간대 변환) + Known Limitations(Gemini 휴일 힌트 한계) |
| **§12 비기능 요구사항** | ~95줄 | 8 하위 절. 성능 P50/P95 표, 가용성(graceful degradation), 보안, 프라이버시, 접근성 WCAG 2.1 AA 권고, 다국어, 관측성, acceptance gate |
| **§13 부록** | ~110줄 | 6 하위 절. 다이어그램 인덱스 8종, 마이그레이션 표 22 revisions, 환경변수(마스킹), 용어집 19항, 변경 이력, 참고 SoT |

---

## 4. 핵심 결정 요약 (31건 + 신규 미결 1건)

### 4.1 스코프·정책 (6건)
- 시간·장소·공통을 **3-파일로 분할** (PR-V): `spec-common.md` (공통 정책·SoT) + `spec-time-coordination.md` (시간) + `spec-place-recommendation.md` (장소). 결정 안건·변경 이력은 `spec-common.md`에만 단일 SoT로 유지.
- 공유 동의 모델 = **opt-out** (코드와 일치 — PR-X로 해소)
- 게스트 식별 = **방별 이름 기반 pseudo_id** (`room_id` × name)
- §12 비기능 / §13 부록 절 위치 분리
- 시연 후 보완(해결점 P·O·ACT 4·5)은 **별도 v2 spec 예고**

### 4.2 Q-시리즈 spec 결정 (17건, Q1~Q17)
| Q# | 결정 | 영향 |
|---|---|---|
| Q1=B | 단일 슬롯도 vote_card 발행 | S5/S9, §6.5 F3 |
| Q2 | place_hint fallback = 다수결→발화자→방장 home_base | §4.4 F5 |
| Q3=A | headcount=None → 방 멤버 수 | F2 |
| Q5 | 그룹 다수결 기본 + 발화자 토글 hybrid | UI 메타 §3·§9 |
| Q6=A | F1 fallback v1.0 구현 포함 | S8 |
| Q7=B | `preference_source` + `preference_toggle_enabled` 2 키 | §3 페이로드 |
| Q7-b | refresh = 방 전체 broadcast | §9.2 신규 라우트 |
| Q7-c | 토글 차단 = C1∨C3∨C4 (C2 게스트 제외) | §7.6 |
| Q8=A | F1 정렬 = 시간 빠른 순 | §4.4 F1 |
| Q9=A | partial maedeup 후 시간 번복 불가 | §6.9 (C2 해소) |
| Q10=C | Gemini prompt에 휴일/요일 힌트 | §4·§11 한계 |
| Q11 | 일괄 True 자동 마이그 (PR-X 적용) | 코드 |
| Q12=A | headcount fallback에 게스트 포함 | §5.1.5 |
| Q13=B | refresh 권한 = 발화자 + 방장만 | §7.5 |
| Q14=C | Redis idempotency + 일일 100회 상한 | §9.2 |
| Q15=A | 토글 narrator 실명("OOO님 선호 기준") | §3.5·§8.6 |
| Q16=C | F1 blocker UI = 익명 + 더보기 실명 | §3·§8.6 |
| **Q17** | F4 캘린더 권한 만료 narrator 실명/익명 | **미결**, 권고 A(실명) §9.7 적용 |

### 4.3 구현 세부 (7건, PR-X·Y에서 적용)
- **Q-X1=A** — `calendar_consent=False`로 명시 거부한 user도 일괄 True 재설정
- **Q-X2** — `/m/consent` JWT consent=True면 redirect 유지
- **Q-X3** — `assistant.py:99` "캘린더 연동" 토큰 체크 보강은 후속 PR
- **Q-Y1** — F1 payload = 슬롯별 `unavailable_users`/`available_count`/`total_count`
- **Q-Y2** — Q16=C 토글 = 슬롯별 single-expand (`expandedUnavailableSlotId`)
- **Q-Y3** — PR-Y는 F1 케이스 A(0 슬롯)만; 권한 0%·모든 blocked는 별도 PR
- **Q-Y4** — 28일 확장 후에도 0이면 F1 fallback (기본 권고)

### 4.4 운영 (1건)
- 해결점 N = `audit-findings.md`에 정식 헤더 추가 (PR-0 완료)

---

## 5. 리뷰 포인트 (심사위원 관점)

### 5.1 가장 검토 가치 있는 절
- **§2 시나리오** — 5분 안에 매듭이 무엇을 해결하는지 그림이 잡힌다. 시연 시나리오와 1:1 매핑.
- **§3 페이로드 4종** — 실제 출력 JSON. 프론트/백엔드 컨트랙트의 SoT.
- **§6 상태·예외** — 정상 경로 밖 모든 분기. 학술 spec 관점에서 가장 검토 가치 큰 절.
- **§8 데이터 정책** — PIPA·opt-out·k-anonymity·narrator PII 통합. 윤리·법적 검토 가치 큰 절.
- **§12 비기능** — 성능·보안·접근성·관측성 + acceptance gate. 졸업 심사 기준에서 자주 묻는 부분.

### 5.2 핵심 트레이드오프 4건
1. **PII vs UX** (Q15=A 실명 narrator) — 토글 투명성 우선, 실명 노출. PIPA 한계 §8.1에 명시.
2. **Q7-b 방 전체 갱신** — 토글 시 모든 멤버 화면이 새 카드로 교체. Q15(narrator)·Q16(점진 공개)으로 공격적 UX 완화.
3. **Q9 시간 번복 불가** — partial maedeup 발행 후 시간 잠금. 자유도 vs 합의 안정성 트레이드오프.
4. **opt-out 동의** — PIPA "명시적 동의" 원칙과 긴장. MVP UX 우선, 상용화 시 opt-in 전환 필요 (§8.1).

### 5.3 알려진 한계 (§11 + §8.9 갭)
- Gemini 휴일 라벨은 힌트 수준 — 실제 매장 영업시간 보장 X (Kakao Local API 미제공).
- 계정 삭제 엔드포인트(`DELETE /users/me`) 미구현 — PIPA Right to Erasure 갭.
- k-anonymity 가드 미구현 — 소규모 방 PII 노출 위험, v1.5 backlog.
- Google OAuth 토큰 평문 저장 — v2 Fernet/KMS 암호화 후보.
- audit_log 테이블 미구현 — 토글·권한 변경 audit, §9.5·§9.8.

---

## 6. 협업자 가이드 (개발자 관점)

### 6.1 이번 PR 사이클 코드 변경 요약
- **PR-X** (`9609bee`) — `calendar_consent` default False→True + 일괄 마이그(Q11·Q-X1=A). Alembic `e2a3b4c5d6f7`.
- **PR-Y1** (`54e1532`) — F1 fallback 다수결 vote_card 구현(Q6=A·Q8=A). 백엔드: `pipeline/helpers/slots.py`·`nodes/function_call.py`·`nodes/vote_card.py`.
- **PR-Y2** (`adc444f`) — F1 fallback 프론트(배너·배지·토글). `frontend/src/components/meeting/ScheduleRecommendationCard.tsx`.

### 6.2 회귀 테스트 위치
- 단위: `backend/tests/unit/test_majority_fallback.py` (PR-Y1 신규, 149줄)
- 통합: `backend/tests/integration/test_f1_fallback_pipeline.py` (PR-Y1 신규, 220줄)
- 통합: `backend/tests/integration/test_user_consent_default.py` (PR-X 신규, 248줄)
- §10.3에 S1~S14 매핑된 pytest 파일 14개 + S15 5건 정의 (일부는 코드 부재 — v1.5 추가 권고)

### 6.3 신규 라우트 명세 위치
- **`POST /meetings/{id}/recommendations/refresh`** — §9.2 (현재 코드 미구현, v1.5 backlog)
- 권한: 발화자 + 방장 (Q13=B) / Rate limit: Redis idempotency + 일일 100회 (Q14=C)
- 응답 코드: 200·403·404·422·429 정의 (§9.6)

### 6.4 v1.0 미구현 항목
- **§13.2 마이그레이션 22 revisions** 표 참조 — PR-X 마이그 `e2a3b4c5d6f7` 포함.
- **§8.9 데이터 정책 갭 8건**: 계정 삭제·Google revoke·k-anonymity·MeetingPreference 30일 자동 보관·Redis invalidate·chat 익명화·게스트 archive·audit_log.
- **§9.8 API/이벤트 갭 7건**: refresh 라우트·audit_log·계정 삭제·Google revoke·캐시 invalidate·캘린더 토글 라우트 분리·rate limit.

---

## 7. v2 후보 (예고)

본 v1.0 범위를 넘어 별도 spec으로 분리 예정인 항목:

- **해결점 P** — 자연어 거부 번복 처리 ("월요일 안돼" → "아 8일 되네" 자동 clear).
- **해결점 O** — 정규식 단축 경로 사각지대 (`rejected_dates` 누락 hotfix).
- **ACT 4·5 보강** — confirm 후속 메시지·quick_classify 강화.
- **k-anonymity 가드 구현** — `total_members >= 4` 임계값 적용 (§8.3).
- **계정 삭제 엔드포인트** (`DELETE /users/me`) — PIPA Right to Erasure (§8.5·§8.9).
- **Google Places 전환** — 영업시간 데이터 plumbing (§11 Known Limitations 해소).
- **OAuth 토큰 암호화** — Fernet/KMS 적용 (§12.3 보안 갭).
- **관측성 대시보드** — Grafana/Datadog (§12.7).

---

## 8. 자주 묻는 질문 (FAQ)

### Q1. "왜 opt-out인가? PIPA 위반 아닌가?"
- §8.1에서 PIPA "명시적 동의(opt-in)" 원칙과의 긴장 관계를 **명시적으로 기술**. 졸업 프로젝트 MVP로서 UX 우선순위를 적용했으며, 상용화 시 opt-in 전환 필요로 명문화.
- 현재는 가입 시 약관에 "캘린더 자동 연동" 및 "선호 데이터 그룹 합산" 동의 항목 명시로 갈음.
- 사용자는 `/m/consent` 페이지에서 언제든 토글 가능 (`PATCH /users/me/consent`·`PATCH /users/me/preferences`).

### Q2. "Q7-b 방 전체 갱신은 공격적 UX 아닌가? 토글 한 사람 때문에 모든 멤버 화면이 바뀌는데?"
- 완화 장치 4중: ① Q15 narrator 실명("OOO님 선호 기준")으로 변경 출처 투명화 / ② Q16 점진 공개로 blocker는 익명 표시 / ③ Q13 권한을 발화자+방장만으로 좁힘 / ④ Q14 Redis idempotency + 일일 100회 상한으로 남발 방지.
- 추가로 Q7-c C1·C3·C4(PII 미동의·결과 동일·정보 부재)에서 토글 자체 차단.

### Q3. "F1 fallback 정렬은 왜 시간 빠른 순(Q8=A)인가?"
- 후보 슬롯이 **이미 선호·거부 필터를 통과**한 상태라는 가정. 그 위에서 단순한 정렬 기준이 사용자 예측 가능성 확보에 유리.
- 대안(가능 멤버 수 desc·preference score desc)은 비교 시점에 토글 영향이 커서 deterministic 회귀가 어려움.
- §4.4 F1 / §6.5 F1에 결정 근거 명시.

### Q4. "게스트는 어떻게 식별하나? 같은 사람이 다른 이름으로 들어오면?"
- 게스트 식별 = **방별 이름 기반 pseudo_id** (`room_id` × name). synthetic email `guest-{uuid12}@maedeup.local` (§7.1).
- 동일 방·동일 이름 재가입은 기존 row 재사용 (`rooms.py:202~232`) — `member_count` 분모 안정성 보장.
- **알려진 한계**: 다른 이름으로 재접속 시 새 row 생성 → 누적 가능 (`rooms.py:189` 주석). 90일 비활성 archive는 v1.5 backlog (§8.7·§8.9-7).
- 게스트도 합의 권한 동등 (Q12=A로 headcount 포함, confirm 호출 가능).

---

## 9. 참고 문서

| 파일 | 역할 |
|---|---|
| [`docs/handoff/spec-common.md`](./spec-common.md) | 기능정의서 v1.0 공통 SoT (권한·데이터·API·비기능·결정 안건·변경 이력) |
| [`docs/handoff/spec-time-coordination.md`](./spec-time-coordination.md) | 기능정의서 v1.0 시간 조율 본문 |
| [`docs/handoff/spec-place-recommendation.md`](./spec-place-recommendation.md) | 기능정의서 v1.0 장소 추천 본문 |
| [`docs/handoff/2026-05-14-spec-progress.md`](./2026-05-14-spec-progress.md) | 본 spec 진행 핸드오프 (결정 31건·코드 PR-X/Y·로컬 커밋 17건 정리) |
| [`docs/handoff/audit-findings.md`](./audit-findings.md) | 해결점 A~P 누적 기록 (N·O·P가 v1·v2 backlog) |
| [`docs/handoff/demo-scenario.md`](./demo-scenario.md) | 시연 시나리오 SoT (S1~S14 원본) |
| [`docs/handoff/2026-05-13-recommend-input-catalog.md`](./2026-05-13-recommend-input-catalog.md) | 입력 데이터 카탈로그 6 카테고리 (P0/P1/P2) |
| [`docs/handoff/2026-05-13-pipeline-split-plan.md`](./2026-05-13-pipeline-split-plan.md) | 9노드 파이프라인 분할 계획 |
| [`docs/handoff/diagrams/*.mmd`](./diagrams/) | Mermaid 다이어그램 SoT 8종 (§13.1 인덱스) |
| [`CLAUDE.md`](../../CLAUDE.md) | 프로젝트 운영 규칙 (Never·코딩 규칙·시연 후 보완 항목) |

---

> **문의·피드백**: 본 가이드 또는 spec 본문에 대한 질문은 진행 핸드오프 `2026-05-14-spec-progress.md` §11 "메모: CLAUDE.md 현재 task 갱신 권고"를 우선 참고. spec 본문 수정 제안은 결정 안건(§spec 결정 안건 표)에 새 Q 번호를 받아 추가하는 방식 권장.
