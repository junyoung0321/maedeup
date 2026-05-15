# BUGS — 매듭 프로젝트 발견 버그 인벤토리

**최종 갱신**: 2026-05-15 ~ 2026-05-16
**기준**: 자동 루프 run12 GREEN 후

---

## 우선순위 정의

- **P0** — 시연 차단·정상 사용 불가
- **P1** — 운영·시연 영향 가능
- **P2** — 테스트 인프라·UX 미세
- **P3** — cosmetic·사소

---

## 시연 차단 해소됨 (run1~run12 해결)

| 버그 | 증상 | 해소 방법 | commit |
|---|---|---|---|
| TimeBar 즉시 unmount (race) | 호스트 1st 클릭 후 TimeBar 사라짐 | frontend restore guard + backend single-slot 제외 + PREFERENCE_TOGGLE_ENABLED=false | `558c57c` |
| 무한 루프 (A3-2 후 재마운트) | timeConfirmed phase 후 TimeBar 다시 뜸 | setInfoPanePhase("timeConfirmed") | `f56271b` |
| vote 카드 InfoPane + AI 패널 중복 노출 | 두 곳에서 동시 렌더 → 클릭 충돌 | 옵션 A — InfoPane VoteCardSection 제거 | `0f3802b` |
| chromium stale cache | selector 실패 재현 | chromium 재시작 (pid 31337 fresh) + act_3_host_click_gap 2.5s | `39fd8f9` |
| all_members_selected debounce 묵음 | 파이프라인 미발동 | NX lock + local debounce 예외 | `7fd7daa` |
| TimeBar availability 무시 | vote_card best slot 사용 (개인 선호 기반) | compute_majority_slot → manual_chosen_time 주입 | `7fd7daa` |
| AUTO_CALENDAR_PUSH 누수 | 시연 반복 시 실제 캘린더 이벤트 생성 | gate 2곳 (confirm + place-confirm) + AUTO_CALENDAR_PUSH=false | `f56271b` |

---

## 이전 세션 해소됨 (PR-V1.5 시리즈)

| 버그 | 해소 commit |
|---|---|
| disliked food 페널티 fast path 회귀 | `90131f2` (PR-V1.5) |
| Q7-c C3 비교 refresh route 미발동 | `90131f2` (PR-V1.5) |
| alembic env.py sqlite 비호환 | `1892b50` (PR-V1.5.1) |
| is_ai_filled JSON server_default postgres-only | `1892b50` (PR-V1.5.1) |
| _make_state factory prefs=None 덮어쓰기 | `1892b50` (PR-V1.5.1) |
| alembic ALTER constraints sqlite 미지원 (7 파일) | `aaec29d` (PR-V1.5.2) |

---

## 잔존 P1

### BUG-WSL — WSL에서 시연 스크립트 실행 시 playwright 미설치
- **발견**: QA dry-run v1 (2026-05-15)
- **증상**: `python3 .gstack-browser-launch.py` → `ModuleNotFoundError: No module named 'playwright'`
- **현재 처리**: WSL venv `~/.venv-maedeup-demo/bin/python3`로 해결됨 (run12 GREEN)
- **잔존 위험**: venv 경로 변경 또는 신규 WSL 인스턴스에서 재현 가능
- **대응**: 시연 전 `~/.venv-maedeup-demo/bin/python3 -c "import playwright"` 확인 권고
- **심각도**: P1 (시연 환경 의존)

---

## 잔존 P2 / 알려진 한계

### LIMIT-demo-1 — demo.py TimeBar slot 24 selector 실패 (간헐적)
- **위치**: `.gstack-demo.py` ACT 3 Playwright selector
- **증상**: `[data-slot="24"]` 요소 not found (간헐적)
- **현재 처리**: WS 송신 fallback이 정상 작동 → run10+ GREEN
- **잔존 위험**: WS 송신도 실패 시 ACT 3 불완전
- **대응**: act_3_host_click_gap 2.5s 충분히 확보. 필요 시 selector 재시도 로직 추가
- **심각도**: P2 (WS fallback 있음)

### LIMIT-7 — free-slots 응답 1095ms
- **위치**: `backend/app/api/routes/calendar.py` free-slots 엔드포인트
- **증상**: Google Calendar 25 events fetch 시 1초+ 응답
- **해소 방법**: Redis 캐싱 또는 월별 prefetch
- **우선순위**: v1.6 backlog
- **심각도**: P2 (시연 영향 적음, UX 한 박자 늦음)

### LIMIT-1 — pytest-asyncio event_loop fixture deprecation
- **위치**: `backend/tests/conftest.py:19`
- **증상**: `DeprecationWarning: event_loop fixture has been redefined`
- **해소 방법**: scope 인자 또는 event_loop_policy fixture
- **우선순위**: v1.6 backlog
- **심각도**: P2 (warning, 동작 정상)

### LIMIT-2 — Q7-c C3 lightweight 비교 (휴리스틱)
- **위치**: `helpers/preference_toggle.py:_lightweight_speaker_matches_group`
- **증상**: home_base + food Jaccard ≥ 70%만 검사. 정확한 결과 비교 X
- **현재**: PREFERENCE_TOGGLE_ENABLED=false로 dormant
- **심각도**: P2

### LIMIT-3 — F1 외 0슬롯 케이스 (2개만)
- **위치**: `nodes/function_call.py`
- **증상**: consent_zero·all_blocked 2 케이스만 분기
- **심각도**: P2

### LIMIT-4 — _resolve_place_hint 4-step 단일 함수 응축
- **위치**: `helpers/places.py`
- **심각도**: P2 (가독성)

### LIMIT-5 — Gemini 분기 disliked food defense-in-depth
- **위치**: `nodes/place.py` Gemini scoring 분기 (>3 후보)
- **심각도**: P2

### LIMIT-9 — F4 narrator 백엔드 미구현 (Q17=A spec only)
- **위치**: `backend/app/api/routes/meetings.py` 캘린더 sync 분기
- **증상**: spec Q17=A "OOO님 캘린더 권한이 만료됐어요" narrator emit 미구현
- **해소 방법**: meetings.py에 narrator emit 추가 (narrator_emit 헬퍼 재사용)
- **우선순위**: v1.6 backlog #5 (시연 후 P1)
- **심각도**: P2 (spec-코드 불일치, 시연 발표자 멘트로 흡수 가능)

---

## P3 (cosmetic)

### LIMIT-8 — favicon.ico 404
- **위치**: `localhost:3000/favicon.ico`
- **해소 방법**: `frontend/public/favicon.ico` 추가
- **우선순위**: v1.7 또는 무시
- **심각도**: P3

---

## Non-bug (의도된 동작)

| # | 현상 | 이유 |
|---|---|---|
| NON-1 | Stalemate 후 agent 응답 미발생 (구독자 없을 때) | Redis pubsub 휘발성. 시연 시 브라우저 항상 구독자 있음 |
| NON-2 | KAKAO_API_KEY 경고 (docker compose ps) | 호스트 환경변수 없음. 컨테이너 내부 .env에 설정됨 |
| NON-3 | ACT 5.5 narrator 자취 [] | PREFERENCE_TOGGLE_ENABLED=false → Idempotency 캐시 미도달. 옵션 B dormant 정상 |

---

## 시연 차단 현황

- **P0**: 0건 (시연 차단 없음)
- **P1**: 1건 (WSL venv 의존 — 현재 해소 상태, 재발 주의)
- **P2**: 8건 (모두 시연 영향 미미)
- **P3**: 1건 (cosmetic)
