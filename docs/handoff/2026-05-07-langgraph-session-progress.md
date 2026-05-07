# 2026-05-07 — Langgraph 세션 진행분 (다른 터미널 작업 범위 체크용)

이 세션에서 변경한 모든 항목 + 상태 + 다른 터미널 충돌 여부 체크리스트.
"여기서 커밋 안 함" 정책 적용 중 — 모든 commit/push는 git 관리 터미널에서.

**대응 핸드오프**: `2026-05-07-frontend-session-progress.md` (다른 터미널 — frontend/UX 세션, A3-2 담당).
**작업 시작 전 두 핸드오프 모두 확인**.

## 현재 git 상태

- 브랜치: `main` (로컬), origin/main 5 ahead / 1 behind 추정 (in-progress merge로 인해 정확치 변동 가능)
- in-progress merge: `origin/main` ← `docs/handoff/demo-scenario.md` 충돌 미해결 — **이 세션이 만든 게 아님**, 다른 터미널이 시작
- 마지막 자체 커밋: `dcc4e20` "fix(langgraph): 해결점 O — review checkpoint v2" (메시지만 임시, 내용은 검증 통과)

## 변경된 파일 — 카테고리별

### A. 이미 커밋된 작업 (`dcc4e20` 단일 commit)

**파일**: `backend/app/services/langgraph_pipeline.py` 단일

**내용** (Codex review 2회 통과):
- 해결점 O — `_REJECT_SIGNAL_PATTERN` 추가 + `_extract_entities_from_context` shortcut에 거부/불가능 키워드 게이트
  - rejected_dates / conflict_detected가 정규식 단축에서 누락되는 사각지대 차단
- Codex P2 반영 — `_PLACE_INTENT_PATTERN` 기반 fast-path를 `pref_keywords_loose`보다 앞으로 이동
  - "강남 한식 추천해줘" 등이 `meeting_schedule`로 오분류되던 이슈
- Codex P2 반영 — `_place_fast_path_this_run` sentinel 추가
  - 이전 턴 잔존 `place_hint` + Gemini 분류 place_suggestion 조합에서 entity_extraction fast-skip 발동 방지 (multi-turn에서 새 메시지의 headcount 등 손실 방지)
- Codex P1 — `place_recommendation_payload`에 named summary가 broadcast되는 privacy trade-off 코드 주석 + 시연 후 정교화 TODO

**커밋 메시지 정리 필요** (선택): `dcc4e20` 메시지 → `fix(langgraph): 해결점 O — entity_extraction 거부 키워드 게이트 + Codex P1·P2 반영` 권장. 현재 "review checkpoint v2"는 review iteration 도중 임시.

### B. 미커밋 — Today bump 로직 (langgraph_pipeline.py)

**상태**: 파일에는 적용, 미커밋, Docker 미반영 (재시작 시 활성화)

**위치**:
- `_build_multi_date_slots` (line 3294 부근)
- `_build_preference_time_slots` (line 3343 부근, `range(1, 29)` → `range(0, 29)`)

**내용**:
- 오늘 + 현재 시각이 선호 시간대 시작 이후인 경우 `start_at = now + 1h`로 bump
- `now+1h + SLOT_MINUTES > end_of_pref` 이면 오늘 후보 스킵
- `_build_preference_time_slots`은 `day_offset` range를 0부터로 변경 (오늘 포함)

**예시** (평일저녁 18-21):
| now | 결과 |
|---|---|
| 14:00 | 오늘 18:00 슬롯 (기존 동작) |
| 18:30 | 오늘 19:30 슬롯 (신규 bump) |
| 20:00 | 오늘 21:00 → +60min=22:00 > 21:00 → 오늘 스킵 |

**남은 사이드 사각지대**:
- `_build_preference_time_slots` 끝부분 fallback (line 3413 부근)은 `range(1, 29)` 유지 — 메인 루프 보강용이라 today 영향 작음. 필요시 동일 처리 가능.
- `get_free_slots` (line 1762)의 `time_min = now.replace(hour=0) + timedelta(days=1)` — Google calendar consent 멤버 있는 경로에서 today 자체가 freebusy query에서 제외. **사용자 테스트 시 today 미포함 보고된 가능 원인 1순위.** 수정 안 한 상태.

### C. 커밋됨 (`13110cb`) — `quick_classify` / `_PLACE_INTENT_PATTERN` 정규식 보강

**상태**: ⚠️ 갱신 (2026-05-07): commit `13110cb`로 이미 처리됨. demo-scenario-audit.md 113-115줄 참조. 본 세션에서 working tree에 적용 후 git 터미널에서 commit한 듯.

**파일**:
- `backend/app/services/quick_classify.py:15` — `_PLACE_RE` 3-OR로 재작성
- `backend/app/services/langgraph_pipeline.py` `_PLACE_INTENT_PATTERN` — 동일 키워드 추가

**원인 (확정)**: "강남에서 다 같이 갈만한 한식집" 같은 자연어가 quick_classify에서 `general` 분류 → 챗팟 응답 → 파이프라인 자체가 안 돌아감. `_PLACE_INTENT_PATTERN`은 quick_classify 이후 단계라 영향 못 미침.

**보강 후 매칭** (테스트 통과):
| 입력 | quick_classify |
|---|---|
| 강남에서 다 같이 갈만한 한식집 | place ✓ |
| 강남역 근처 한식 맛집 추천해줘 | place ✓ |
| 강남 좋은 카페 알려줘 | place ✓ |
| 한식 어디서 먹지 | place ✓ |
| 오늘 일정 추천해줘 | schedule ✓ (보존) |

**알려진 false positive** (시연 수준 OK):
- "한식 좋아하지 않아" → place. cuisine 단독 매칭의 trade-off. 파이프라인 downstream에서 place_hint 없으면 자연스럽게 미발동.
- 시연 후 권장: cuisine + 명령형 어미 AND-매칭으로 좁히기.

### D. 미커밋 — TimeBar AI 추천 선호도 동기화 (옵션 A, 적용 완료)

⚠️ **다른 터미널 A3-2와 frontend 파일 겹침 — D 커밋 후 A3-2 시작 가능**.

**파일**:
- `frontend/src/components/meeting/InfoPane.tsx`
- `frontend/src/components/meeting/TimeBarSelector.tsx`

**원인**: 기존 `recommendedRange`는 순수 프론트 휴리스틱 — 멤버들이 불가능 시간을 안 찍으면 전 슬롯 available → 첫 8슬롯(09:00-13:00) 픽. 백엔드 `preference_common_times` / `/preferences` API 미사용.

**구현**:
1. `InfoPane`이 mount 시 `/api/v1/rooms/{roomId}/preferences` fetch → `roomPreferences` 상태 저장
2. `computePreferredTimeRange(date, preferences)`로 weekend/weekday 필터 후 가장 흔한 `preferred_times` → `{start, end}` hour range 변환
3. `TimeBarSelector`에 `preferredTimeRange` prop 신규 추가
4. `recommendedRange` 알고리즘 2-pass:
   - 1차: 선호 범위 내 longest-streak (≥2슬롯)
   - 2차: 1차 실패 시 전체 longest-streak fallback (기존 동작)
5. 백엔드 `PREFERRED_TIME_RANGES` (langgraph_pipeline.py:49-56)을 프론트에 미러링한 상수 추가 — 변경 시 양쪽 동기화 필요

**검증** (논리):
| 선호 | 결과 |
|---|---|
| 평일저녁 (18-21) | 슬롯 18-23 streak → "오후 6:00 ~ 오후 9:00" ✓ |
| 평일오후 (13-17) | 슬롯 8-15 streak → "오후 1:00 ~ 5:00" ✓ |
| 평일오전 (9-12) | 슬롯 0-5 streak → "오전 9:00 ~ 12:00" ✓ |
| pref 없음 / fetch 실패 | fallback → 기존 동작 (9시-13시) ✓ |

**Edge case**:
- 선호 범위 내 streak ≥ 2가 없는 경우 (e.g. 평일저녁 범위가 캘린더 충돌로 가득) → fallback로 전체 longest 사용 — 사용자 의도 부분 손실되지만 빈 추천보단 나음
- 라벨은 "추천: 오후 6:00 ~ 오후 9:00 (N명 전원 가능)" 그대로 — "선호 시간대 추천" 등으로 명료화 가능 (TODO)

### E. 진행 중 — A4-3 Partial maedeup 카드 분기 (조사 단계)

**상태**: 조사 시작 전 / 코드 미수정.

**시연 영향**: 🔥 P0 — ACT 4 카드 라이프사이클 (partial → place 확정 → maedeup) 핵심.

**증상** (demo-scenario-audit.md A4-3):
- ACT 4 `all_members_selected` 트리거 후 **Partial maedeup 카드 (시간만, 장소 placeholder)** 기대
- 실제로 **place_recommendation 카드 직행**
- 결과: ACT 4-5 카드 진화 흐름이 무너짐. "같은 카드가 partial → 완성으로 진화하는 거 보이시죠"가 안 됨.

**가설**: 호스트 PD(한식·강남·저녁형) 영향으로 trigger_intent가 place로 분기. 검증 필요.

**조사 영역**:
1. `all_members_selected` trigger가 어디서 진입하는지 — `agent.py` / `social.py` / `langgraph_pipeline.py`
2. `trigger_reason` / `direct_request_kind` 등 신호가 어떻게 라우팅 결정하는지
3. `partial_mode = "time_only"` 활성화 조건 — 어디서 set 되고 언제 maedeup_card_creation 노드가 partial 분기 타는지
4. 실제 흐름이 place_recommendation으로 빠지는 분기점 — `function_calling` / `_route_after_*`

**조사 결과 (코드 분석 후 채울 것)**:
- (TBD)

**충돌 영역**: `langgraph_pipeline.py` 내부. 다른 터미널 A3-2는 `social.py` + 새 endpoint이라 직접 충돌 없음.



| 영역 | 충돌 가능성 | 대응 |
|---|---|---|
| `backend/app/services/langgraph_pipeline.py` | 高 — A·B 카테고리 모두 이 파일 | 다른 터미널은 이 파일 동시 수정 자제. 합칠 때 카테고리별 단위로 |
| `backend/app/services/quick_classify.py` | 中 — 카테고리 C | 작은 파일이라 conflict 가능성 낮음 |
| `frontend/src/components/meeting/InfoPane.tsx` | 中 — 카테고리 D (옵션 A) | fetch + prop 전달 + PREFERRED_TIME_RANGES 상수 추가 |
| `frontend/src/components/meeting/TimeBarSelector.tsx` | 中 — 카테고리 D (옵션 A) | prop 추가 + recommendedRange 알고리즘 변경 |
| `docs/handoff/demo-scenario.md` | **현재 in-progress merge로 충돌 상태** | 다른 터미널이 처리 중이라고 인지 |

## 요약 — 다른 터미널이 알아야 할 것

1. **B/C/D 카테고리는 파일 적용됐지만 미커밋** — 합치기 전에 git status로 확인
2. **dcc4e20는 main에 있음** — 메시지 정리(amend) 권장
3. **D 카테고리(TimeBar 옵션 A) 적용 완료** — frontend 2파일 (InfoPane, TimeBarSelector) 변경됨
4. **Docker 재시작은 사용자 타이밍** — 자체 재시작 금지
5. **PREFERRED_TIME_RANGES 동기화 주의** — 백엔드(langgraph_pipeline.py:49)와 프론트(InfoPane.tsx) 두 곳에 동일 정의. 한 쪽 변경 시 다른 쪽도 갱신.

## 메모

- 본 세션은 "여기서 커밋/푸시 안 한다" 정책으로 작업 중 (사용자 명시).
- 모든 커밋/push/Docker 재시작은 git 관리 터미널에서.
- 본 문서 자체는 미커밋 상태로 둠 (다른 터미널이 git 추적/커밋).
