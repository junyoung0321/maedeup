# TODO — 매듭 프로젝트

**최종 갱신**: 2026-05-15
**기준 시점**: PR-V1.5.2 + handoff v17 후, QA dry-run v2 백그라운드 실행 중

---

## 🔵 진행 중 (immediate)

### QA dry-run v2 — Playwright MCP 시각 검증 ✅ 완료 (2026-05-15)
- **상태**: ✅ PASS (taskId `a9dbbaccb1eb8c374`, duration 8min38s)
- **결과**: ACT 1→2→4→5 풀 자동 재현 통과, room 72 / meeting 88 / 수담한정식 강남점 확정, 백엔드 ERROR/EXCEPTION 0건
- **스크린샷 6장**: `qa-v2-act1-room-created.png`, `qa-v2-act2-vote-card.png`, `qa-v2-act4-time-confirmed.png`, `qa-v2-act5-place-cards.png`, `qa-v2-act5-place-confirmed.png`, `qa-v2-final-success.png`
- **발견**: P0 0건. P2 1건 (free-slots 1095ms), P3 2건 (favicon.ico 404 재확인, QA 가이드 컨테이너 WS 활용 추가) — 모두 BUGS.md 등록
- **BUG-2 (Playwright MCP)** 최종 해소 확인

---

## 🟢 즉시 가능 (사용자 결정 시)

### A. 푸시 — 원격 동기
- 로컬 미푸시 38+ 커밋 → `origin/docs/spec-time-coordination`
- 명령: `git push`
- **현재 정책**: 사용자 명시 승인 후 (메모리 영구 저장 — `feedback_handoff_auto_update.md` 외 `feedback_qa_runtime_role.md`에 명시)

### B. 실제 시연 진행 (Windows에서)
- 환경: **Windows PowerShell + `.venv\Scripts\python.exe`** (WSL 사용 금지, BUG-1 결정)
- 사전: Docker 4 컨테이너 healthy 확인, `.gstack-demo-token` JWT 존재 확인
- 명령:
  ```powershell
  # 터미널 1
  python .gstack-browser-launch.py
  # 터미널 2 (별도 셸)
  python .gstack-demo.py  # 또는 --fast
  ```
- ACT 흐름: 1(방 생성) → 2(채팅 stalemate) → 4(partial) → 5(AI 패널·확정)
- ACT 3 (TimeBar)·ACT 6 (extractor)는 데모 스크립트 스킵 (옵션)
- D-1 사전: `sg docker -c "docker exec maedeup-api python -m scripts.seed_demo_personal_data --room <ID>"` (Personal Data ✨ 시드)

---

## 🟡 v1.6 backlog (Codex·QA 후속 권고)

| # | 항목 | 출처 | 영향 |
|---|---|---|---|
| 1 | Gemini 분기에서도 disliked food final_score=0.0 가드 (defense-in-depth) | Codex P1 보강 | place 추천 품질 |
| 2 | `preference_common_foods` 정의를 union → 70% multi-set 교집합 | Codex P2 보강 | Q7-c C3 정확도 |
| 3 | `_load_group_preference_context`를 `helpers/preferences.py`로 이동 + User.food_preferences fallback | Codex P2 보강 | 모듈 응집도 |
| 4 | alembic versions의 `'{}'::json` 패턴 (이미 3건 정리, 잔존 검토) | QA 후속 | 테스트 인프라 |
| 5 | pytest-asyncio event_loop fixture deprecation 정정 (`conftest.py:19`) | pytest warning | 미래 호환 |
| 6 | rejected_places의 cap 적용 (메모리 leak 방지) | spec §6.15 권고 | 안정성 |
| 7 | F8 명시 tiebreaker 외 `score=0.1` 보조 키 추가 | Codex 후속 | 정렬 일관성 |
| 8 | F1 외 0 슬롯 케이스 추가 정교화 (현재 consent_zero·all_blocked만) | spec §6.x | UX |
| 9 | `[FALLBACK] ml_disabled` 구조화 로그 — Prometheus·Grafana 연동 | spec §12.7 | 관측성 |
| 10 | `/api/v1/calendar/free-slots` 응답 1095ms — Redis 캐싱 또는 월별 prefetch | QA v2 LIMIT-7 | UX 첫 로드 |
| 11 | QA 운영 가이드에 "WSL 게스트 WS = 백엔드 컨테이너 내부 `python /tmp/send_chat.py` 활용" 명시 | QA v2 후속 P3 | QA 자동화 |
| 12 | `frontend/public/favicon.ico` 추가 (console error 0건 / 시연 영상 cleanliness) | QA v2 LIMIT-8 | cosmetic |
| 13 | **F4 narrator 백엔드 구현** (Q17=A) — `meetings.py` 캘린더 sync 분기에 `"{name}님 캘린더 권한이 만료됐어요"` emit 추가 | QA v3 LIMIT-9 | spec/코드 불일치 해소 |
| 14 | `seed_demo_calendar_busy.py` 스크립트 신설 — ACT 2.5 `majority_fallback` 자연 발동 안정성 ↑ | QA v3 D-1 #2 | 시연 안정성 |
| 15 | `.gstack-demo.py` ACT 3 자동화 블록 신설 — 슬롯 클릭→시간대 변경→멤버 vote→방장 확정 팝업 (~30~40 LOC) | QA v3 권고 | 자동화 |

---

## 🟠 v2 spec 본격 작성 (38 항목, 별도 문서)

**의존**: 시연 통과 + retrospective 후 권장

`docs/handoff/2026-05-14-spec-v2-plan.md` 참조. 6 sub-PR 권고:

- **PR-v2.0**: 개요·변경 사항·Q18~Q25 등록 (~150줄)
- **PR-v2.1**: 시연 후 보완 (해결점 P·O·ACT 4·5) — `spec-time-and-place-v2.md`로 별도 파일 (~200줄)
- **PR-v2.2**: PIPA·보안 (계정 삭제·Google revoke·k-anonymity·audit_log·OAuth 암호화) — ~300줄
- **PR-v2.3**: 추천 plumbing P1·P2 (room_member_home_bases·previous_recommendations 등) — ~200줄
- **PR-v2.4**: recurring·timezone·다국어 — ~250줄
- **PR-v2.5**: v3 backlog·v1↔v2 매핑 부록 — ~150줄

**신규 Q-시리즈 (8건)**:
- Q18 해결점 P 번복 정책
- Q19 게스트 매핑 실패 시
- Q20 해결점 O 옵션
- Q21 ACT 4 confirm 후속 분류
- Q22 audit_log 스키마
- Q23 OAuth 토큰 암호화 방식
- Q24 recurring 스키마
- Q25 추천 점수 가중치 정밀화

---

## 🔴 P3 (잔존, 별도 PR 후보)

### P3-A: alembic versions 추가 `'{}'::json` 패턴
- PR-V1.5.2에서 d2e3f4·e1f2·e5f6 3 파일은 정리됨
- 단 추가 파일 잔존 가능성 — grep으로 확인 권고:
  ```bash
  grep -rn "'{}'::json" backend/alembic/versions/
  ```
- prod (postgres)는 정상, sqlite 테스트만 영향

### P3-B: assistant.py:99 Q-X3 보강은 PR-V1.5에 통합됨 — 후속 정밀화는 v1.6

### P3-C: `_resolve_place_hint` 4-step 코드 분기 1:1 매핑 정교화 (v1.6 #3과 중복)

---

## ⚪ 사용자 환경 정리 (사용자 영역)

- **WSL playwright 설치 시도 금지** (사용자 결정, 메모리에 영구 저장)
- 시연은 Windows PowerShell + `.venv\Scripts\python.exe`로 진행
- Playwright MCP·CLI는 QA 자동화용 (이미 작동 확인됨)

---

## 후속 PR 패턴 (참고)

새 PR 만들 때 따를 워크플로 (메모리 영구 저장):
1. **계획**: spec·요구사항 확인 → 결정 게이트
2. **에이전트 dispatch**: 4 담당 (코드/문서/리뷰/QA) 중 적합한 담당
3. **검토**: Codex 리뷰 + 내 검토
4. **수정**: Hotfix 에이전트 위임 (필요 시)
5. **커밋**: 단일 PR로 통합
6. **handoff 자동 갱신**: PR 완료마다 `2026-05-14-spec-progress.md`
7. **QA dispatch**: 변경이 사용자 흐름 영향 시 (Playwright MCP)
8. **푸시**: 사용자 명시 승인 후

---

## 다음 세션 진입 우선순위

1. ✅ QA v2 결과 처리 — 완료 (P0 0건, P2/P3는 v1.6 backlog 편입)
2. 🟢 **푸시 결정 (사용자)** — origin 동기화 필요 시 명시 승인 후
3. 🟢 **시연 진행 (Windows, 사용자)** — 사전 준비 완료, 환경 검증 통과
4. v1.6 backlog 12 항목 (시연 후 권장)
5. v2 spec 본격 작성 (38 항목, 시연 후 retrospective 권장)
