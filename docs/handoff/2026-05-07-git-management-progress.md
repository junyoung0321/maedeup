# 2026-05-07 — Git 관리 + 라이브 검증 세션 (지속 갱신)

이 터미널은 **git 작업 (커밋·머지·푸시·rebuild) + chromium UI 라이브 검증**만 담당.
코드 수정은 langgraph/frontend 터미널이 하고, 우리는 그 결과를 main에 반영하고 검증.

대응 핸드오프:
- `2026-05-07-langgraph-session-progress.md`
- `2026-05-07-frontend-session-progress.md`

---

## 현재 main HEAD (origin 동기화)

```
b1dfd14 fix(infopane): Map iteration → forEach (TS downlevelIteration 회피)
acd38a0 docs(handoff): 시드 안내 + audit 진행 갱신 + 세션 progress
91cb4ef chore(scripts): A0-1 PersonalData 시연 시드 스크립트
5d709f2 fix(meetings): A4-1 confirm 후속 안내 박스 emit
c43f986 docs(handoff): 2026-05-07 langgraph + frontend 세션 진행분
4478608 fix(schedule): A3-2 자동 발동 차단 + 호스트 확정 endpoint
6877461 feat(timebar): TimeBar 추천 범위 선호도 동기화 (옵션 A)
0b6b341 docs(handoff): 2026-05-07 라이브 검증 결과 + 신규 미해결 항목
13110cb fix(intent): A5-1 place 단축 경로 정규식 보강 + 오늘 즉시 약속 슬롯
22b235b fix(narration): A3-1 합의 시간대 동적 주입
9cf5a2a docs(handoff): 시연 시나리오 v3 vs 코드 검수
3c21ab5 chore(gitignore): .venv-* 패턴 추가
32d039a fix(frontend): vote_card label regex + awaiting state reset
8fe9862 Merge remote-tracking branch 'origin/main'
dcc4e20 fix(langgraph): 해결점 O — review checkpoint v2
cb16aef Merge branch 'feat/langgraph-tweaks'
0d04fe5 feat(frontend): vote_card 시간대 변경 분기
```

Docker 상태: API + Frontend 모두 health 200, 새 코드 반영 완료 (마지막 rebuild: b1dfd14 시점).

---

## 시연 안전선 — 완료된 항목

| ID | 내용 | Commit | 라이브 검증 |
|---|---|---|---|
| **A2** | 자연어 거부 5/8·9·10 ISO 추출 + 캘린더 sync (해결점 F·P) | (기존) | ✅ chromium UI |
| **A2 선호 시간** | 평일 저녁 18:00 정확 반영 | (기존) | ✅ |
| **A3-1** | TimeBar 합의 narration "19:00~21:00이 겹쳐요" 동적 | `22b235b` | ✅ (host TimeBar 두 번째 클릭 정상 시) |
| **A3-2** | 자동 발동 차단 + 호스트 "확정하기" 게이트 | `4478608` + `7b3fce7` | ✅ consensus_ready → host click → trigger 흐름 검증 |
| **A4-1** | confirm 후속 안내 박스 emit | `5d709f2` | ⏳ 미검증 |
| **A4-3** | all_members_selected → time-only Partial 카드 발행 | (자연 정정, A3-2 이후) | ✅ `[TRIGGER] all_members_selected time-only partial card` 로그 |
| **A5-1** | quick_classify 정규식 + 즉시 약속 슬롯 | `13110cb` | ✅ |
| **A6-1** | extractor 카테고리 misclass 차단 | `cd2d7c2` | ✅ `0 users affected` 로그 (거부 발화 학습 거부) |
| **D** | TimeBar 추천 범위 선호도 동기화 | `6877461` + `b1dfd14` | ✅ 평일저녁 18-21 정확 (`42fef84` overflowX 제거 후) |
| **A0-1** | PersonalData D-1 시드 스크립트 | `91cb4ef` | ✅ (스크립트 사용 검증) |
| **시나리오 docs** | v3 통합본 + 시드 안내 한 줄 | `acd38a0` | (docs) |
| **F-1 v2** | pending meeting 재사용 가드 (라이프사이클) | `74779ba` | ✅ vote_card → maedeup 갱신, vote 사라짐 |
| **F-3** | entity_extraction direct_request fast-skip | `4c5ce48` | ✅ 0.09s (이전 15s) |
| **F-4 (1차)** | meeting_summary 풍부화 | `4c5ce48` | ✅ 멤버별 거부 사유 |
| **F-4 (회귀 fix)** | signals ISO 변환 강제 | `b8dd909` | ✅ vote_card 정상 발행 (5/11~5/15) |
| **A4-1** | confirm 후속 안내 박스 | `5d709f2` | ✅ "일정이 확정되었어요 — 5/11 (월) 오후 6:00" + "어디서 만날지" |
| **place top 5** | place_recommendation top 10 → 5 (시연 latency 최적화) | `a0d6136` | ✅ 38.27s → 22.14s first / 53s second variance (Gemini 외부 의존) |
| **P0-2 ACT 4 단축** | function_calling 신규 [TIMING] + memory_extraction 분리 fire-and-forget | `a0d6136` | ✅ TOTAL **0.02s** (이전 4.51s, -99.5%). DetachedInstanceError 0건 |
| **A5-2 reasoning ✨** | place card group_constraints_summary 렌더 | `642f50b` | ✅ "수현님 채식 식단 · 홍대 비선호 ✨ · 김창윤님 한식 선호..." indigo 박스 |
| **G-1 member_joined** | 새 게스트 join → 캘린더 X/N 자동 갱신 | `f2c2cde` | ✅ "4/4" → "5/5" reload 없이 즉시 |
| **AsyncSessionLocal import** | F-1 v2 root cause 수정 | `493f48e` | ✅ silent NameError 차단, 라이프사이클 정상 |
| **A3-3 manual path** | TimeBar 2-버튼 + HostTimeAdjustModal + manual host pick | `ad63b1b`+`333a935`+`3fe6b7e` | ✅ banner 2-버튼 노출 / `[TRIGGER] manual host pick: 2026-05-11 18:00~18:30` / TOTAL 0.02s / partial 영역도 호스트 권한 진행 OK / [확정] auto path 회귀 0건 |

---

## 진행 중 / Pending (다른 터미널)

A3-3 통합 검증 — 핵심 7건 통과. 단 신규 3건 발견:

| ID | 우선 | 작업 | 상태 |
|---|---|---|---|
| **F-5** | ⚠️ P1 | TimeBar individual confirm 버튼 라이프사이클 (그룹 확정 후 hide/disable) | 미시작 |
| **F-6** | ⚠️ P1 | AI 패널 카드/채팅 시간순 정렬 (카드가 항상 상단 누적되는 layout 문제) | 미시작 |
| **A3-3 slider default** | ⚠️ 미세 | HostTimeAdjustModal default가 가장 긴 전원 segment 아닌 partial로 잡힘 | 미시작 |
| **AI 응답 variance** | ⚠️ 외부 | place_recommendation Gemini scoring 22~53s 변동 | 시연 후 |
| **F-2 console.info** | 🟢 cleanup | 진단 로그 제거 | 시연 후 |

---

## Docs 정정 후보 (검증 결과 반영)

| ID | 시나리오 박힌 값 | 실제 |
|---|---|---|
| D-A2-1 | 추천 카드 5/12 (다음주 N-확장 가정) | 5/11 (이번 주 안에서 가능) — 시나리오 5번째 메시지 추가 또는 멘트 정정 |
| D-A2-3 | "5/12 (월)" | 5/12는 화요일 |
| D-A3-1 | "19:00~20:30이 겹쳐요" | 산수상 19:00~21:00 — 백엔드 출력 정상 |

각 항목 단순 docs 수정. 시연 D-day 가까울 때 일괄 정리.

---

## 갱신 정책

이 문서는 **이 터미널이 새 commit/push/rebuild할 때마다 갱신**.
- 새 commit → "현재 main HEAD" 섹션 추가
- 검증 결과 → "완료된 항목" 표 갱신
- 다른 터미널 작업 진행 인지 시 → "Pending" 표 상태 갱신

다른 터미널 commit 들어오면 머지/검증 후 본 문서도 같은 commit에 묶음.
