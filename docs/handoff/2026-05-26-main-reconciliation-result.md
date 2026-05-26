# Main 정리 — 진행 결과 (2026-05-26)

## 결론
**origin/main 갱신 완료**: `0f6d1d7 → 2391b38` (109 commits push).
working 브랜치의 +101 commits + main 의 ahead 3 fix + 머지 회귀 fix 2건 통합.

## 진행 흐름

| 단계 | 작업 | 결과 |
|---|---|---|
| 옵션 1 | 진단 — P0 instrumentation + working/main 양방향 시연 | `d9e2a8e` instrument commit, snapshot ndjson 추출, working/main Bug 분류 |
| 옵션 2 | merge `-X theirs` (working 우선) | `cee0a9b` merge commit, 109 commits |
| fix 1 | `-X theirs` 가 `_PEOPLE_NOUN_RE` 정의 hunk 누락 → NameError | `a73b188` (slot.py +6줄) |
| fix 2 | `-X theirs` 가 `call_gemini` cfg/timeout/시그니처 정의 누락 → NameError silent swallow → trigger 미발화 | `2391b38` (gemini.py +24/-2) |
| 검증 | 5차 시연 GREEN — ACT 1~5 정상 통과, NameError 0건 | room 210, 3분 11초 |
| push | origin/main 갱신 | `0f6d1d7..2391b38` |

## 발견 Bug 분류 (총 8건 + 2개 회귀)

| Bug | 분류 | 5차 결과 | 비고 |
|---|---|---|---|
| Bug-1 TZ scheduled_at 충돌 | main-only | ✅ 사라짐 | working 의 fix 머지 효과 |
| Bug-4 vote_card 슬롯 라벨 불일치 | main-only | ✅ 사라짐 | working 의 fix 머지 효과 |
| Bug-5 place 메시지 2회 중복 | main-only | ✅ 사라짐 | working 의 fix 머지 효과 |
| Bug-6 partial maedeup 35s 미등장 | 공통 | ✅ 16s 등장 | 머지 + fix 효과 |
| Bug-7 free-slots 시간대 다양성 누락 | 공통 | ⏳ inconclusive | BUG-26-1 backlog |
| Bug-W1 free-slots `11:00~10:00` | working-only | ✅ 사라짐 | merge 흡수 효과 |
| Bug-W2 partial sync 39s 지연 | working-only | ✅ 16s | merge 흡수 효과 |
| Bug-W3 direct_request 22s | working-only | ⚠️ 18.4s (Gemini fallback 경로) | ML 모델 부재 영향 |
| **Bug-M1** NameError `_PEOPLE_NOUN_RE` | 머지 회귀 | ✅ fix `a73b188` | `-X theirs` hunk 충돌 |
| **Bug-M2** NameError `cfg/timeout` (silent) | 머지 회귀 | ✅ fix `2391b38` | `-X theirs` hunk 충돌 + silent swallow |

## 잔여 backlog
`docs/BUGS.md` § "main 정리 후 잔여 (2026-05-26)" 참조 — BUG-26-1 ~ BUG-26-5.

## 학습

### `-X theirs` 한계
working 우선 머지는 정의/사용 짝이 깨질 수 있음. AST 정적 분석으로는 못 잡음 (사용은 있고 정의만 사라진 패턴). Bug-M1 (_PEOPLE_NOUN_RE) 은 1차 점검에서 잡혔지만 Bug-M2 (cfg/timeout) 는 런타임에서만 드러남. 향후 큰 머지 (39 commits 이상) 는 사람이 정의/사용 + 함수 본문 hunk 충돌 review 권고.

### Silent fail 패턴
`_detect_and_notify_intent` 의 외층 `except Exception: logger.debug(...)` 가 NameError 를 DEBUG 로그로 swallow → 무음. 시연 자동화 stdout 만 봤으면 영원히 못 잡았을 함정. 회귀 방지 위해 logger.debug → warning 승격 + 다른 silent except 패턴 감사 (BUG-26-4).

### QA 자동 검증 11항목 (memory `qa-auto-runtime-audit`)
사용자 매번 짚어주던 패턴 (timezone 이중 변환, 캘린더 unavailable 동기화 등) 을 5항목 → 11항목으로 확장. risk-reviewer 가 spec/scenario/audit 문서 훑고 누락 영역 (WS 시퀀스, 카드 라이프사이클, place payload, latency, TZ 5곳 cross-check 등) 통합. 앞으로 qa-runtime 모든 시연에서 default 적용.

### 시연 진행 흐름
- 1차 (working `--fast` 5-ACT): GREEN, 62 lines snapshot
- 2차 (main origin/main detach `--fast`): GREEN
- 3차 (post-merge): RED — Bug-M1 NameError showstopper
- 3차' (post fix1 a73b188): 부분 GREEN — Bug-M2 silent fail 로 ACT 2 trigger 미발화
- 4차 (backup baseline): GREEN — 머지 회귀 확정 baseline
- 5차 (post fix2 2391b38): GREEN — push 가능 판정

## 산출물
- `docs/BUGS.md` — BUG-26-1 ~ BUG-26-5 추가
- `docs/handoff/2026-05-26-main-reconciliation-state.md` — 진행 시작 상태 (이 문서의 입력)
- `~/.claude/projects/-mnt-c-Users-cyun0-git-maedeup/memory/feedback_qa_auto_panel_audit.md` — QA 자동 검증 11항목

## 다음 task (D-9 = 2026-06-04 전시)
1. BUG-26-4 silent fail 감사 + logger.debug → warning 승격 (P1)
2. BUG-26-1 free-slots 시간대 다양성 누락 (P1)
3. BUG-26-3 Gemini timeout 단축 또는 vote_card fallback 메시지 개선 (P2 — 시연 영상 영향 가능)
4. 시연 영상 5/30 (토) 촬영
5. v2 spec 본문 작성
