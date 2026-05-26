# BUGS — 매듭 프로젝트 발견 버그 인벤토리

**최종 갱신**: 2026-05-16
**기준**: Option C R8 GREEN + CalendarPane 빨간 배지 제거. 시연 D-6 (2026-05-22 금 점심)

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

## 시연 차단 해소됨 (Option C 라운드 1~9, 2026-05-16)

| 버그 | 증상 | 해소 방법 | commit |
|---|---|---|---|
| TS build error 잠재 (`7fd7daa` 시점부터) | `docker compose build` 매번 실패 → stale image(`7ffb7c4821a9`) 재사용 → R1~R7 fake RED | InfoPanePhase 없는 "placeRecommendation" 비교 제거 + maedeup_card union narrowing guard | `ad22516` + `cb0acee` |
| hostLoading API race | ScheduleRecommendationCard에서 isHost=false 낙관적 렌더 실패 → 호스트 버튼 미노출 | isHost state 낙관적 초기화 | `8a7c7d5` |
| AiAssistantPane maedeup_card auto phase-advance | maedeup_card WS 수신 시 phaseAlreadyAdvanced 미체크 → Option C 건너뜀 | maedeup_card type 가드 추가 | `cdf727b` |
| setVoteCard phaseAlreadyAdvanced dateConfirmed 누락 | dateConfirmed 상태에서도 phase reset → TimeBar 재마운트 | phaseAlreadyAdvanced 조건에 dateConfirmed 추가 | `1fe9b17` |
| CalendarPane 빨간 배지 중복 | "안 되는 사람 수" 빨간 배지가 기존 X/Y 카운트와 동일 정보 중복 표시 | 빨간 배지 블록 통째 제거 | `bc315f1` |

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

### LIMIT-10 — 장소 추천 호스트 단독 확정 (v2 spec 후보, 사용자 제안)
- **위치**: ACT 5 `frontend/src/components/meeting/` 장소 카드 클릭 핸들러
- **증상**: 시간 합의(vote_card + TimeBar + Option C)는 투표 기반인데, 장소 확정은 호스트 첫 카드 클릭으로 단독 결정 → 합의 흐름 불일치
- **해소 방법**: 장소 카드에도 vote_card 패턴 적용 (vote_card + WS protocol + frontend + demo.py 변경 필요)
- **우선순위**: 시연 후 P1 (TODO #5 참조)
- **심각도**: P2 (시연 차단 없음, v2 spec PR-v2.1 후보)

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

## 시연 차단 현황 (2026-05-16 기준, 시연 D-6)

- **P0**: 0건 (시연 차단 없음)
- **P1**: 1건 (WSL venv 의존 — 현재 해소 상태, 재발 주의)
- **P2**: 9건 (모두 시연 영향 미미) — LIMIT-10 추가
- **P3**: 1건 (cosmetic)

---

## main 정리 후 잔여 (2026-05-26)

`docs/handoff/2026-05-26-main-reconciliation-result.md` 참조. 머지 회귀 2건 (Bug-M1/M2) 은 commit `a73b188` + `2391b38` 으로 해소 + push 완료.

| # | 증상 | 우선순위 | 의심 코드 | 메모 |
|---|---|---|---|---|
| BUG-26-1 | `/free-slots` API 가 특정 날짜에 1슬롯 (오전 9-10시) 만 반환 — 시간대 다양성 누락 | **P1** | `backend/app/api/routes/calendar.py` 의 free_slots 빌더. `detail_date` 인자 시 시간대별 슬롯 생성 로직 | 공통 회귀 (working/main 양쪽 재현). 머지와 무관. |
| BUG-26-2 | `/free-slots` 라벨 `오전 11:00 ~ 10:00` (시작 11시 → 종료 10시) — 시각 normalize 버그 | P2 | label 포맷 helper (`pipeline/helpers/formatting` 또는 calendar route) | working-only. |
| BUG-26-3 | Gemini 2회 timeout(15s × 2) 시 vote_card fallback 메시지 본문 시각이 TimeBar 합의 최종값과 다름 (`5/27 18:00` 추천 vs `5/27 19:30` 합의) | P2 | `gemini.py` timeout 15s + retry, vote_card fallback message builder | 채팅 본문 클로즈업 안 하면 시연 영상 영향 X. |
| BUG-26-4 | `_detect_and_notify_intent` 외층 `except Exception: logger.debug(...)` — silent fail 패턴. trigger NameError 가 1차 진단에서 무음 통과 | **P1** | `backend/app/api/ws/social.py` `_detect_and_notify_intent` 외층 except | 회귀 방지 위해 `logger.warning` 으로 승격 권장. 같은 패턴 다른 영역도 감사 필요. |
| BUG-26-5 | `_PEOPLE_NOUN_RE` (slot.py) + `call_gemini` cfg/timeout (gemini.py) 같은 정의 누락이 `-X theirs` 머지에서 발생. AST 정적 분석으로는 못 잡음 (사용은 있고 정의가 사라진 패턴) | P2 | merge strategy + lint | 향후 큰 머지 시 정의/사용 짝 + 함수 본문 hunk 충돌을 사람이 review 권고. |

**우선순위 합계** (2026-05-26 추가분):
- P1: 2건 (BUG-26-1, BUG-26-4)
- P2: 3건 (BUG-26-2, BUG-26-3, BUG-26-5)
