# 2026-06-01 — 자유 사용 감사(free-use audit) 체크포인트

> **목적**: 토큰/usage 한도로 세션이 끊겨도 이 작업을 정확히 이어가기 위한 복구 SoT.
> 세션 재개 시 이 문서를 먼저 읽고 "재개 절차"부터 실행하세요.

## 목표 (활성 /goal)
**"일반 사용자가 자유롭게 사용할 때 생길만한 문제가 뭐가 있을지 분석하고 문제 해결해봐"**
- 시연(ACT 0.5~5.5)은 스크립트가 통제 → 항상 동작. 자유 사용은 통제 없음 → 예상 못한 입력·동시성·권한·빈 상태·복구에서 깨짐.
- 분석만이 아니라 **실제 버그 수정**까지가 목표. (Stop hook 활성: 조건 충족까지 종료 차단)

## 진행 상태 (2026-06-01 기준)
- **Phase A — 발견/검증 워크플로우: 1차 실행 후 critic 단계서 실패 → 수정 후 resume 중**
  - 1차 Task `wuir9u6ci` 실패(완전성 비평 에이전트가 StructuredOutput 미호출 → top-level throw). finder·verifier 82개는 완료·저널 캐시됨.
  - fix: 비평 블록을 try/catch + StructuredOutput 강제 지시로 교체. 재개 Task: `wfdcauufc`.
  - Run ID: `wf_f21f67bd-219` (resumeFromRunId 로 재개 — 82개 캐시 반환, critic 만 재실행)
  - Script: `C:\Users\cyun0\.claude\projects\C--Users-cyun0-git-maedeup\b738120f-9f4a-45c0-946b-da679af2365a\workflows\scripts\maedeup-free-use-audit-wf_f21f67bd-219.js`
  - 구조: 8개 자유사용 차원 finder(병렬) → 각 finding 적대적 검증(도달성·기존방어·심각도) → 완전성 비평. 구조화 JSON 반환(confirmed/refuted/missedScenarios).
  - 8개 차원: intent-classification / date-time-parsing / voting-scheduling / place-recommendation / auth-permission-guest / concurrency-ws-recovery / empty-boundary-statemachine / llm-limits-injection
- **Phase B — 수정: 8건 적용 완료** (아래 표). resume가 캐시 미스로 재실행되어 중단 → **저널(journal.jsonl)에서 직접 추출**(74 findings + 104 verdict)해 `2026-06-01-free-use-findings.json` 저장. 모두 py_compile 통과. **Docker 부팅 검증 미완**(Docker Desktop off) → 사용자가 `docker compose up -d` 후 `docker logs maedeup-api --tail 30` P0 에러 확인 필요.

## Phase B — 적용한 수정 (8건, additive·해피패스 불변)
| # | 심각도 | 파일 | 내용 |
|---|---|---|---|
| [01] | P1 보안 | `routes/calendar.py` | free-slots IDOR: 멤버십 검증을 캐시 GET 앞으로 (비멤버가 캐시 HIT로 타 방 멤버이름·가용시간 읽기 차단) |
| [00] | P1 | `routes/meetings.py` | `vote_meeting`: 확정/취소 모임 투표 거부 (409 voting_closed) |
| [05] | P1 | `routes/meetings.py` | `confirm_meeting`: 취소된 모임 부활 차단 (409) |
| [12] | P1 | `services/gemini.py` | `response.text` try 감쌈 — safety 차단 시 ValueError 전파 방지, candidates 폴백 |
| [03] | P1 | `nodes/entity.py` | `_safe_resolve_place_coord` 래퍼 — 지오코딩 KakaoApiError swallow + `kakao_api_error` 플래그 → F7 narrator 발현 (4개 호출부 교체) |
| [06][18] | P1 | `nodes/entity.py` | `M월D일` 항상 올해 묶임→연말 과거날짜 무응답: 과거면 내년 롤 + 비유효날짜 skip |
| [17][35] | P2 | `nodes/entity.py` | place_hint 미추출 시 메시지 전체(2000자) 사용 → 50자 캡 (Kakao 무력화·인젝션·비용 방지) |
| [23] | P2 | `nodes/place.py` | T5 캐시 키에 detected_cuisines 추가 (음식 종류 캐시 충돌 차단) |

## 결정 필요 — 미적용 (행동/제품 변경이라 사용자 판단 필요)
- **[07]** `POST /meetings/confirm`(proposal 없는 경로) 호스트 검증 없음 — 주석에 `"멤버라면 누구나 확정"` 명시. rooms.py `schedule-confirm`은 host-only라 **불일치**. 통일 여부 결정.
- **[10]** `guest-join` 인증 없는 공개 EP — 방번호만 알면 무한 게스트 생성. rate-limit/방어 추가 여부.
- **[02]** `core/rate_limit.py:check_rate_limit` 호출처 0건 → LLM 무제한. 와이어링 시 전시 throttle 위험 → 임계값 신중.
- **[11]** 호스트 leave 시 활성 모임 전부 cancel + 방 고아화 — 소유권 이전 정책 필요.
- **[24]** `PATCH /meetings/{id}/place` 게스트 포함 누구나 확정 장소 변경 가능.
- **[31]** 동점·번복(재투표) 정책 부재 (backlog 해결점 P) — 제품 결정.
- **[14]** RAG confidence<0.7 게이트가 0.60~0.70 정타 분류 폐기 → 튜닝은 K2.2 회귀 위험, 측정 동반.
- **프론트 새로고침 복구** [13][15][22][46]: InfoPane phase·partial maedeup·진행중 투표수 복구 경로 부재 — 프론트+백엔드 EP 필요.
- 전체 P2/P3 목록은 `2026-06-01-free-use-findings.json` 참조.

## 재개 절차
1. 워크플로우가 끝났는지 확인: `TaskOutput(task_id="wuir9u6ci", block=false)` 또는 `/workflows`.
2. **아직 실행 중이면** 완료 대기(자동 재호출됨).
3. **끊겨서 중단됐으면** 같은 세션 재개 시:
   `Workflow({scriptPath: "<위 Script 경로>", resumeFromRunId: "wf_f21f67bd-219"})`
   → 완료된 finder/verifier agent는 캐시 반환(토큰 재소모 없음), 미완료분만 재실행.
4. **완전 새 세션(저널 유실)이면** 워크플로우를 처음부터 재실행하거나, transcript dir의 `agent-*.jsonl`에서 결과를 수동 취합.
5. 결과 받으면 confirmed 목록을 P0→P3 정렬, 사용자 승인 후 수정 착수(또는 자율 모드면 trivial/small 부터 바로 수정).

## 선행 정찰 결과 (직접 확인, 워크플로우 무관하게 유효)
1. **dates.py 날짜 파싱은 KST 기준 일관 처리됨** (`datetime.now(KST)`). 자정 off-by-one 의심 → 이 모듈 한정 방어됨. 단 `_parse_iso_datetime`(dates.py:372)이 naive를 `timezone.utc`로 가정 → 별개 KST/UTC 혼선 의심점으로 남김.
2. **장소 0개 결과는 방어됨** (`place.py:551~572`): `kakao_error`/`place_empty`/`count==0` 별 narrator 분기 존재 → "다른 지역을 알려주실래요?" 안내.
3. **확정 경로 락 커버리지 의심점**: `meetings.py:454` `confirm_meeting`은 Redis NX lock(ex=30)으로 동시 확정 차단. 그러나 시연 TimeBar가 쓰는 **`rooms.py`의 `schedule-confirm`은 별도 경로** → 같은 락 미적용 가능성. 동시성 finder가 확정 예정. (place 확정도 `meetings.py:953` NX lock ex=600 별도 존재)

## 토큰/usage 메모
- 백그라운드 워크플로우는 **같은 quota를 소모** → 한도 임박 시 워크플로우 자체가 멈췄다가 quota 회복 후 재개.
- Claude Code는 대화를 보존 → 한도 리셋 후 같은 대화 이어가면 됨(`claude --continue`/`--resume`). resumeFromRunId는 same-session 기준.
- 이 문서 덕분에 콜드 스타트(새 세션)에서도 복구 가능.

## 관련
- `docs/handoff/2026-05-30-round-summary.md` (전시 안정성 round, HEAD 직전 SoT)
- `docs/handoff/demo-scenario-v3.md` (시연 시나리오 — "통제된" 흐름. 자유 사용은 이걸 벗어남)
- memory `project_pattern_skip_rejected_blindspot.md` (rejected_dates 정규식 사각 — date 차원과 연결)
