# TODO — 매듭 프로젝트

**최종 갱신**: 2026-05-15 ~ 2026-05-16
**기준 시점**: 자동 루프 run12 GREEN 완료 후. 시연 D-3~4 (5/19~20)

---

## 🔴 시연 전 필수 (D-1 준비)

| # | 항목 | 담당 |
|---|---|---|
| D1 | JWT 유효 확인 (`.gstack-demo-token` 401 여부) | 사용자 |
| D2 | `seed_demo_personal_data --room <ID>` 실행 (방장 신촌 + food) | 사용자 |
| D3 | Docker 4 컨테이너 healthy 확인 | 사용자 |
| D4 | chromium pid 확인 + CDP 9222 응답 확인 | 사용자 |
| D5 | 시연 dry-run 1회 (run12 재현) | 사용자 |

---

## 🟢 즉시 가능 (사용자 결정 시)

### A. 푸시
- 브랜치 `docs/spec-time-coordination` → origin 동기화
- 명령: `git push`
- 현재 정책: 사용자 명시 승인 후

### B. chore/claude-subagents 브랜치 처리
- 옵션 1: main으로 PR (5 sub-agents 공식화)
- 옵션 2: 로컬 보관만 (main 오염 없이 참조)
- 결정 대기

---

## 🟠 시연 후 — P1 (즉시 처리)

### 1. 해결점 O — 정규식 단축 사각지대
- `backend/app/api/ws/social.py` 또는 pipeline 트리거 정규식
- 짧은 발화 (예: "7시", "내일") 미감지 케이스
- 담당: analyst → code-writer

### 2. 해결점 P — 번복 정책 + 게스트 매핑 정교화
- 시간 번복 시나리오 (partial 후 재투표 요청)
- 게스트 pseudo_id 매핑 실패 처리
- `audit-findings.md` 참조
- 담당: analyst → code-writer

### 3. ACT 4 confirm 후속 메시지
- 시간 확정 후 AI 패널 멘트 없음 → narrator 추가
- `meetings.py` confirm 분기에 narrator emit
- 담당: code-writer

### 4. ACT 5 quick_classify 보강
- stalemate 감지 → 장소 추천 진입 간 갭
- `pipeline/graph.py` quick_classify 분기 정교화
- 담당: analyst → code-writer

### 5. LIMIT-9 — F4 narrator 백엔드 미구현 (Q17=A)
- `meetings.py` 캘린더 sync 분기에 `"{name}님 캘린더 권한이 만료됐어요"` emit
- spec-common.md §9.7 / Q17=A 결정과 코드 불일치 해소
- 담당: code-writer

---

## 🟡 자동 루프 12 라운드 후속 — backlog

### 6. watcher.py → .gstack-demo.py hook 통합
- 현재 `.gstack-demo.py`가 WS 수신·fallback을 직접 처리
- 별도 watcher.py 패턴을 hook으로 통합하면 안정성 ↑
- 우선순위: P2

### 7. window.__wsCapture page navigate reset 차단
- `MeetingContext` 마운트 시 `window.__wsCapture = []` 재초기화
- page navigate 후 캡처 배열 stale 문제 차단
- 우선순위: P2

### 8. 옵션 3 — ACT 2.5 ScheduleRecommendationCard 슬롯 클릭 root 추적
- 슬롯 클릭 → host availability prefill 생성 경로 추적·차단
- `PREFERENCE_TOGGLE_ENABLED=false`로 현재 dormant, 근본 원인 미해소
- 우선순위: P2

### 9. backend single-slot guard의 30분 미팅 use case 영향 검토
- `social.py:_is_explicit start==end 제외` 로직
- 실제 30분 단일 슬롯 선택 시나리오에서 false negative 가능성
- 담당: analyst
- 우선순위: P2

---

## 🟠 v1.6 backlog (Codex·QA 후속 권고)

| # | 항목 | 출처 | 우선순위 |
|---|---|---|---|
| 10 | Gemini 분기에서도 disliked food final_score=0.0 가드 (defense-in-depth) | Codex P1 | P2 |
| 11 | preference_common_foods union → 70% multi-set 교집합 | Codex P2 | P2 |
| 12 | _load_group_preference_context → helpers/preferences.py 이동 | Codex P2 | P2 |
| 13 | vote_update 좁히기 (same meeting 조건 + 회귀 테스트) | Codex P1 backlog | P1 |
| 14 | refresh state 통일 (WS race 잠재 재발) | Codex P1 backlog | P1 |
| 15 | LIMIT-7 free-slots 1095ms → Redis 캐싱 또는 월별 prefetch | QA v2 발견 | P2 |
| 16 | LIMIT-8 favicon.ico 404 → `frontend/public/favicon.ico` 추가 | QA v2 발견 | P3 |
| 17 | pytest-asyncio event_loop fixture deprecation 정정 | QA 후속 | P2 |
| 18 | rejected_places cap 적용 (메모리 leak 방지) | spec §6.15 | P2 |
| 19 | F8 tiebreaker score=0.1 보조 키 추가 | Codex 후속 | P2 |

---

## 🔵 v2 spec 본문 작성 (시연 후 권장)

**의존**: 시연 통과 + retrospective 후

`docs/handoff/2026-05-14-spec-v2-plan.md` 참조. 6 sub-PR 예정:

| PR | 범위 | 예상 분량 |
|---|---|---|
| PR-v2.0 | 개요·변경사항·Q18~Q25 등록 | ~150줄 |
| PR-v2.1 | 시연 후 보완 (해결점 P·O·ACT 4·5) — spec-time-and-place-v2.md | ~200줄 |
| PR-v2.2 | PIPA·보안 (계정 삭제·Google revoke·k-anonymity·audit_log·OAuth 암호화) | ~300줄 |
| PR-v2.3 | 추천 plumbing P1·P2 (room_member_home_bases·previous_recommendations 등) | ~200줄 |
| PR-v2.4 | recurring·timezone·다국어 | ~250줄 |
| PR-v2.5 | v3 backlog·v1↔v2 매핑 부록 | ~150줄 |

신규 Q-시리즈 (8건): Q18 번복 정책 / Q19 게스트 매핑 실패 / Q20 해결점 O / Q21 ACT 4 confirm 후속 / Q22 audit_log / Q23 OAuth 암호화 / Q24 recurring / Q25 점수 가중치

---

## ⚪ 메타 / 정리 작업 (시연 후)

- HANDOVER.md → 시연 결과 + 루프 12 성과 반영
- CLAUDE.md → 시연 완료 후 "현재 task" 섹션 갱신
- TODOS.md → 시연 후 v2 roadmap으로 교체
- When2Meet 프라이버시 정책 검토 (시연 영상 공개 시)
- chore/claude-subagents 브랜치 — main PR or 보관 결정

---

## 다음 세션 진입 우선순위

1. **시연 dry-run** — run12 재현 확인 (D-1 또는 D-0)
2. **JWT 갱신 필요 시** — 5/13 생성, 5/19까지 만료 여부 확인
3. 시연 후: 해결점 O·P + ACT 4·5 보강
4. 시연 후: v2 spec PR-v2.0부터 순차 작업
