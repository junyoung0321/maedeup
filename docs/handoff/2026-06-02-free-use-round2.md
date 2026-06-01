# 2026-06-02 — 자유 사용 감사 라운드 2 (Docker 검증 + safe 패치 9건)

> 선행: `2026-06-01-free-use-audit-checkpoint.md` (라운드 1, 8건 수정 commit d1ddba0).
> 본 라운드: d1ddba0 부팅 검증 GREEN + 잔여 ~64건 재검증 → demo-safe 패치 9건 적용.
> 전시 D-2(2026-06-04 수). 모든 변경은 additive·해피패스 불변·해결점 O 비재개방.

## 1. Docker 부팅 검증 (라운드 1, GREEN)
commit d1ddba0의 8건이 런타임 컨테이너에 라이브 확인:
- 5개 수정 모듈 컨테이너 import ALL OK
- 날짜 롤·kakao_api_error 플래그·_safe_resolve_place_coord·place_hint 50자 캡·meetings 409 가드 전부 present
- `/health` db+redis ok, 50 routes 정상

## 2. 라운드 2 방법
멀티 에이전트 워크플로우(`wf_939ff9a6-4d8`): 8개 차원별 에이전트가 현재 코드 기준 잔여 finding 재검증 → 분류(already-fixed / safe-additive-fix / product-decision / defer-frontend / low-value-skip) → 각 safe 패치를 적대적으로 데모-안전성 검증. 게이트: 데모 happy path(ACT 0.5~5.5) 불변 + 함수 시그니처 불변 + 해결점 O 비재개방.
분류 결과: confirmedSafe 11, product-decision 21, defer-frontend 6, low-value 15, verify-rejected 10.
상세 데이터: `docs/handoff/2026-06-02-free-use-round2-findings.json`.

## 3. 적용한 패치 (9건, 검증 완료)
| # | 심각도 | 파일 | 내용 |
|---|---|---|---|
| #14 | P1 | `services/intent_classifier.py` | Gemini 확정 non-general 의도의 confidence를 `max(sim,0.7)`로 — RAG 경계(0.60~0.69)에서 0.7 게이트에 폐기되던 사각 해소. general은 raw 유지(동작 불변) |
| #09 | P1 | `pipeline/nodes/entity.py` | 단일 date_hint 경로 과거날짜 필터 추가(multi-date 경로와 동일 규칙) — 과거날짜 입력 시 빈슬롯+에러 대신 graceful |
| #25 | P2 | `api/routes/assistant.py` | 홈 비서 프롬프트 인젝션 완화 — 사용자 메시지를 `<user_input>` 델리미터로 래핑 + SYSTEM_PROMPT rule 7 추가 |
| #52 | P2 | `api/ws/social.py` | conclusion 자동개입 idempotency NX 키 — 같은 trigger_message_id 재평가 시 ai_auto_trigger 중복 발행 차단(첫 발행만 통과) |
| #43 | P2 | `pipeline/nodes/entity.py` | fast-skip(short cmd) 가드에 사람·인원 명사 정규식 추가 — '우리 셋이 추천해줘'에서 headcount 소실 방지 |
| #33 | P2 | `pipeline/helpers/dates.py` | 주말/평일/월말/다음달(담달) 카테고리 표현 결정적 처리 — Gemini 장애 시에도 안정 |
| #50 | P2 | `api/ws/social.py` | _maybe_emit_proposal explicit_count를 현 멤버 집합과 교집합 — 탈퇴/스테일 user_id 잔재 제외(합의 오판 차단) |
| #27 | P2 | `api/ws/social.py` | 솔로 방(member_count<2) schedule_consensus_ready 발화 차단 — '전원 합의' 솔로 모임 방지 |
| #48 | P2 | `pipeline/nodes/vote_card.py` | 거부/평일 필터 후 후보 0개면 빈 time_options vote_card·빈 pending 모임 차단(early skip) |

검증: py_compile 6/6 OK · 컨테이너 restart 후 healthy · 6개 모듈 import OK · 스모크(카테고리 날짜 신규해결+데모표현 불변, 헤드카운트 정규식 6/6, 프롬프트 template.format KeyError 없음) PASS.

## 4. 전시 후로 보류 (2건)
- **#22** pending vote_card 복구 집계(aggregated_votes/total_voters): 백엔드 단독은 체감 0, 완결엔 VoteCardSection.tsx + 프론트 리빌드 동반 → 전시 후 백+프론트 함께.
- **#44** 'D일' 단독 ISO 정규화: 이미 하류 `_parse_natural_date` + past 필터로 해소되는 near-zero 가치(검증자도 보류 권고).

## 5. 제품 결정 필요 (21건 — 사용자 판단, 미적용)
권한·소유권·정책류라 행동 변경이 생겨 자율 수정 보류. 핵심:
- **P1 권한/인증**: #07(confirm proposal없는 경로 호스트검증 부재), #10(guest-join 무인증 무한생성), #11(호스트 leave 시 모임 전멸+소유권 미이전), #02(rate_limit 호출처 0건→LLM 무제한)
- **P2 권한**: #24(PATCH place 누구나 변경), #45(무제한 덮어쓰기 투표), #51(refresh owner 판정 약함), #20(호스트 퇴장 후 확정 트리거 불가), #57(다른이름 반복 guest-join으로 member_count 부풀림)
- **정책**: #31(동점·번복 정책 부재=해결점 P), #19(eligible_voters 생성시점 고정), #58(1인 모임 자동확정), #30(confirm NX lock room단위)
- **분류/파싱 튜닝(회귀 위험)**: #21·#49(완곡거부/다중의도 정규식 사각=해결점 O 인접), #47(slot_filling 중 잡담 오염), #32(근무시간 밖 시각 silent drop), #29(rejected_places 같은지역 거부루프), #33-인접
- **상태/만료**: #39(부분매듭 영구 미완), #41(confirmed 방 재트리거 중복 pending), #56(maedeup phase idle 고착)
전체 목록·근거는 findings JSON `productDecisions` 참조.

## 6. defer-frontend (6건, 프론트+백 동반 → 전시 후)
#13(새로고침 InfoPane phase 복원), #15(부분매듭 '장소 정하기' 복구), #46(WS 재연결 vote_update 상태복구), #28(0건 추천 빈 카드), #37(JWT 만료 게스트 세션 소멸), #61(비선호 0% 노출).

## 7. verify-rejected (10건 — 데모 파손 위험으로 제외)
적대적 검증이 데모-크리티컬 경로 접촉을 잡아냄: #08(snapshot_hash 전제 불일치+확정 트리거), #34(카드 라이프사이클 해결점 J), #64(refresh 409 데모 ACT5.5 경로), #68(stalemate judge 게이트 의미변경), #16/#26/#60/#59/#40/#66.

## 8. 다음 액션
1. §5 제품 결정 항목을 사용자와 합의 → 합의분만 추가 라운드로 적용.
2. 전시 후 §4·§6 프론트 동반 항목 처리.
3. 미커밋 산출물: 본 문서 + findings JSON은 commit 포함. (코드 9건은 별도 commit)
