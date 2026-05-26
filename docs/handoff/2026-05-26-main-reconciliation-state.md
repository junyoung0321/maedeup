# Main 정리 — 현재 상태와 결정 대기 항목 (2026-05-26)

## 컨텍스트
- 시연(D-4)은 완료. 다음 마일스톤은 **2026-06-04 전시** (9일 남음).
- main이 깨진 상태로 인지됨 (정확한 증상·원인 미파악).
- `docs/spec-time-coordination` 가 작동하는 작업 브랜치.
- 이번 세션에서 main 정리 절차를 시작하려다 정확한 진단을 위해 보류.

## 브랜치 상태 (2026-05-26 작성 시점)
- 현재 체크아웃: `docs/spec-time-coordination`
- origin 동기화: 완료 (방금 push)
- main 대비: **101 commit ahead, 39 commit behind**

## 이번 세션 push 내역
- `524bf86 fix(demo): 캘린더 X/N 동기화 + AI 요약 결론 표현 제거`
  - `frontend/src/components/meeting/ChatPane.tsx` — `peer_unavailable_update` 수신 시 `refreshCalendar()` 호출 추가. `/free-slots` 카운트 stale 버그 fix.
  - `backend/app/services/pipeline/nodes/conversation_analyzer.py` — prompt 의 `card.date` 예시·가이드에 결론 표현("유일한 후보", "~만 가능") forbidden phrase 명시.

## 미커밋 / 미정 항목
| 항목 | 상태 | 메모 |
|---|---|---|
| `docs/handoff/tech-flow.html` (42KB, 5/22) | untracked | 의도 불명 |
| `docs/handoff/tech-flow-by-scenario.html` (60KB, 5/22) | untracked | 의도 불명 |
| stash@{0} `.gstack-browser-launch.py` viewport fix | feat/intent-classifier-gpt5-nano 소속 | 별도 처리 |
| stash@{1} intent-classifier WIP 3 파일 | feat/intent-classifier-gpt5-nano 소속 | 별도 처리 |
| stash@{2} feat/option-c-on-main 4 파일 | feat/option-c-on-main 소속 | 별도 처리 |

## main에만 있는 39개 커밋 — 카테고리 분류

**A. perf / 안정성 (7건) — 거의 필수**
- `723eadc` perf: `_parse_natural_date` 메모이즈 (-1.5s)
- `bb70331` perf: entity multi-date 병렬화
- `f1e847b` perf: call_gemini 15s timeout
- `708b289` perf: meeting_preferences 캐싱
- `217f749` gemini: call_gemini 결정성 강화 (top_p=0.1, top_k=1)
- `faaf71e` stability: PAID Gemini fallback + 헬스체크 (config.Settings 변경 포함)
- `0f6d1d7` fix: vote_card 호스트 캘린더 의존 버그 (5/20 hotfix)

**B. 기능 fix (12건) — 필수**
- `041b1d7` slot: direct_request 부분 정보 카드 생성
- `15c1ea2` places: 미등록 지명 처리
- `0b8efe2` dates: `_fallback_parse_natural_date` 정수 시간 추출
- `a93da94` slot+vote: 명시 시간 단일 슬롯 카드 발행
- `7b8037e` quick_classify: 자연어 시간/식사 키워드 (regex 보강)
- `4d6fbfd` mobile: 페이지 높이 844px 통일 + 백엔드 보강
- `71763c2` fix: 사람 명사가 `place_hint`/`headcount` 망치는 버그
- `100f656` demo: ACT 6 학습 모먼트 host 매칭
- `9ecfc03` timezone: AI 확정/완료 KST 변환 누락
- `944b6a8` trigger: 잡담→모임 전환 자동 개입 미발화 (NOTIFIABLE-only 카운터)
- `72de03f` validation: 과거 슬롯이 errors 채우면서 vote_card 생성 실패
- `3c2b349` alembic: missing `e2a3b4c5d6f7` migration 복원

**C. 큰 기능 (5건) — 결정 필요**
- `6185d43` mobile: M2.3 장소 선택 위자드 + AI 추천 페이지 (sanigod)
- `2142038` feat: 모임 조건 설정에 참여 친구 선택 기능
- `d63cda0` feat: 모바일 캘린더 Google Calendar 연동 (sanigod)
- `a88c409` feat(ml): Two-Tower 파인튜닝 + LGBMRanker 하이브리드 랭킹 (sanigod) — **model_v2_no_sentiment.pkl 파일 의존, 시연 로그에서 매번 fallback 확인됨**
- `abc33eb` feat(vote_card): slot_ranker 통합

**D. 리뷰 fix (2건) — 필수**
- `5c5934e` review P0/P1 7건 — agent.py blocking + Redis leak + places fallback
- `5d7f41f` review /review 3건 — shim 회귀 + fire-and-forget task 누수 + quick_classify 오탐

**E. demo-stab (2건) — 필수**
- `ee55467` demo-stab Phase 1 — 자동 머지 가능한 4 파일 (FE-1/FE-3 + seed)
- `2cc4164` demo-stab Phase 2 — 충돌 4 파일 수동 부분 적용 (BE-1+BE-2+FE-2+BE-3)

**F. 정책/문서 (4건)**
- `1055938` docs(handoff): 응답시간 단축 매뉴얼 v1
- `b2a0c8a` docs(handoff): D-4 상태 정리 + agent_v2 비교 자료
- `81468fc`/`4c9ddd9` chore(docs): 비교 자료 제거
- `359088c` docs(claude): **푸시만 사용자 승인 — 커밋은 PM 자율 (정책 변경)**

**G. 머지 커밋 (3건)**
- `fad52b6`, `e7a17a1`, `2810a2d`

**H. 의문 (1건) — 조사 완료**
- `1b90a05` "제코 케이스 추가" — by jjy(정준영). 알고 보니 showcase 스크립트 974줄 추가만, **코드 변경 없음**. 안전.

## 의심 후보 (main 깨짐 원인 가설)
시연 로그에서 직접 관찰된 단서:
```
[ML] ml_place_search 실패, Gemini fallback:
[Errno 2] No such file or directory: '/data/output/training/models/model_v2_no_sentiment.pkl'
```
→ `a88c409` ML 기능이 모델 파일 의존하는데 로컬 환경에 없어서 매번 fallback path 탐. Fallback이 있어서 완전 실패는 아니지만 timing/품질 영향 가능.

기타 가능성 (미검증):
- `faaf71e`의 config 변경이 다른 호출처와 충돌?
- `2810a2d` PR #10 merge가 누락된 fix를 재도입?

**확정 진단은 안 됨.** main을 실제로 띄워서 증상 재현해야 함.

## 옵션 정리 (시연 후 진행 대상)

1. **진단 우선 (A)**: backup 브랜치 만들고 `git switch origin/main` → docker 재시작 → 데모 돌려서 증상 관찰 → 원인 좁힌 뒤 결정.
2. **merge -X ours (B)**: 충돌은 docs/spec-time-coordination 우선으로 main 39개 흡수 → push. 빠르지만 ML/모바일 신기능이 실제 동작하는지는 별도 검증 필요.
3. **선별 cherry-pick (C)**: 진단 후 안전한 fix만 추려서 cherry-pick. 머지 커밋 안 생김. 시간 소요 큼.
4. **force-replace (D)**: docs/spec-time-coordination을 새 main으로 force-push + 팀원(sanigod) 신기능만 별도 PR. **CLAUDE.md가 명시적으로 금지하는 방식**. 팀 합의 필요.

권장: 1 → (진단 결과에 따라) 2 또는 3.

## 환경 동기화 잔여 (협업자 셋업)
- `.env` (GEMINI_API_KEY, GOOGLE_*, JWT_SECRET, KAKAO_*)
- `.gstack-demo-token` (JWT, 본인 발급)
- `docker compose up -d` (의존성 자동)
- `docker exec maedeup-api python -m scripts.seed_demo` (시연 데이터 1회)
- frontend rebuild: `docker compose up -d --build frontend`

## 다음 세션 시작 절차 제안
1. 이 문서 읽기
2. `git switch docs/spec-time-coordination` 확인
3. `git log --oneline -5` 로 push 상태 확인
4. 사용자에게 옵션 1~4 중 선택 받기
