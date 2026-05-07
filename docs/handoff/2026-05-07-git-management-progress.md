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
| **A3-1** | TimeBar 합의 narration "19:00~21:00이 겹쳐요" 동적 | `22b235b` | ✅ |
| **A4-1** | confirm 후속 안내 박스 emit | `5d709f2` | ⏳ 미검증 |
| **A5-1** | quick_classify 정규식 + 즉시 약속 슬롯 | `13110cb` | ✅ 부분 (단축 경로 발동, 18s) |
| **D** | TimeBar 추천 범위 선호도 동기화 | `6877461` + `b1dfd14` | ⏳ 미검증 |
| **A3-2 backend** | 자동 발동 차단 + 호스트 확정 endpoint | `4478608` | ⏳ frontend 짝 대기 |
| **A0-1** | PersonalData D-1 시드 스크립트 | `91cb4ef` | (도구) |
| **시나리오 docs** | v3 통합본 + 시드 안내 한 줄 | `acd38a0` | (docs) |

---

## 진행 중 / Pending (다른 터미널)

| ID | 우선 | 작업 | 작업자 | 상태 |
|---|---|---|---|---|
| **A3-2 frontend** | 🔥 P0 | useSocialWebSocket schedule_consensus_ready 핸들러 + "확정하기" 버튼 + POST /schedule-confirm 호출 | frontend | 미시작 (D commit 인지 후 가능 — **이미 main에 있음**) |
| **A4-3** | 🔥 P0 | all_members_selected → place 직행 막고 Partial maedeup 카드 강제 발행 | langgraph | 미시작 |
| **A6-1** | ⚠️ P1 | memory_extractor 카테고리 misclassification (거부 발화 → time_preference) | langgraph | 미시작 |
| **A5-2** | ⚠️ P1 | reasoning ✨ 이름 인용 검증 (시드 후 재테스트 필요) | (검증) | 시드 스크립트 사용 후 이쪽 재검증 |

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
