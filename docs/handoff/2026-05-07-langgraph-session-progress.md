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

### E. 종결 — A4-3 Partial maedeup 카드 분기 (코드 수정 없음)

**상태**: ✅ 해결 — **시연 입력 패턴 정정으로 종결**. 코드 변경 X.

**최종 결론** (2026-05-07): 사용자 테스트 시 선호도 팝업에 "강남" 입력 → `pref_data.best_location = "강남"` → `_slot_filling_all_members`의 2차 elif 분기 fire → place_recommendation 직행. 시나리오 doc은 명시적으로 "선호 장소 비워둠"이라 적혀있어서 **시연 시 공란 입력**이 정답. 코드 회귀 위험 없이 종결.

**참고용 분석** (코드 변경했을 경우 발생 가능 문제 — 향후 일반 사용성 검토 시 재참조):


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

**조사 결과 (코드 분석 완료)**:

**근본 원인 — `_slot_filling_all_members` (langgraph_pipeline.py:3105-3128)의 3-way 분기**:
```python
if state.get("place_hint"):
    state["status"] = "location_first_ready"  # → place_recommendation
elif best_location:                             # pref_data.best_location
    state["place_hint"] = best_location
    state["status"] = "location_first_ready"  # → place_recommendation
else:
    state["partial_mode"] = "time_only"
    state["status"] = "time_only_ready"        # → maedeup partial 카드 ✓
```

`_route_after_validation` (line 4427)에서 `time_only_ready` status를 우선 체크해 maedeup_card_creation으로 라우팅하므로, **time_only_ready 분기에 진입하기만 하면 partial 카드 정상 발행**됨. 문제는 진입 못 함.

**진입 못 하는 이유 (가능성 순)**:
1. **`pre_extracted_signals.place_hint`가 set됨** — `_analyze_conversation` (langgraph_pipeline.py:4644)이 Gemini로 social chat 분석 시 `place_hint` 추출. 데모 ACT 2 채팅엔 장소 명시 없지만, 이전 turn 또는 시드 메시지에 "강남" 등이 있으면 잡힘. entity_extraction 노드가 pre_extracted를 그대로 state["place_hint"]로 주입 (line 2371).
2. **`slot_context.place_hint` 잔존** — `agent.py:794-796`이 매 메시지마다 result.place_hint를 slot_context에 보존. ACT 2 trigger 결과가 place_hint를 채웠다면 ACT 3·4까지 잔존.
3. **`_enrich_with_preferences` (line 2947-2950)** — pref_data.best_location이 set이면 (멤버가 preferred_location 입력) state.place_hint 자동 채움. 시나리오상 모두 빈 칸이라 발동 안 해야 정상.

**수정 방향 (추천)**:
`_slot_filling_all_members`를 **trigger_reason 기반으로 단순화** — `all_members_selected` 진입 시 place_hint 무관하게 **항상 time_only_ready**.

Why: 시나리오 ACT 4-5 핵심은 카드 라이프사이클 (partial → place 확정 → maedeup 갱신). place_hint가 우연히 set 됐다고 해서 partial 단계 건너뛰면 시연 임팩트 (`"같은 카드가 partial → 완성으로 진화"`) 손실.

```python
async def _slot_filling_all_members(state, pref_data):
    # 해결점 A4-3: TimeBar 전원 합의 → 항상 Partial maedeup 카드 (시간만).
    # 장소는 ACT 5에서 사용자가 별도 요청 → place_recommendation 카드 → confirm → 같은
    # meeting_id의 maedeup 카드 갱신 (partial → 완성). 시나리오 ACT 4-5 카드 라이프사이클.
    state["partial_mode"] = "time_only"
    state["status"] = "time_only_ready"
    logger.info("[TRIGGER] all_members_selected → time-only partial card (always)")
    # ... headcount/meeting_type defaults 등 기존 로직 유지
```

**Side effect 분석**:
- 기존에 place_hint 있는 케이스가 place_recommendation으로 직행하던 경로가 사라짐.
- 사용자가 ACT 5에서 "강남에서 갈만한 한식집" 같은 별도 메시지를 보내면 다시 place_recommendation 트리거됨 (시나리오 핵심 흐름).
- 단점: 자동 트리거 없이 사용자 의도 파악만으로 place_recommendation을 주는 케이스는 사라짐. 시연 시나리오에선 영향 없음.

**구현 단계**:
1. `_slot_filling_all_members` 단순화 (위 코드)
2. (선택) `_route_after_validation` line 4438의 `if trigger == "all_members_selected": return "place_recommendation"`은 죽은 분기 됨 — time_only_ready가 먼저 잡혀서. 정리 가능하지만 시연 안전을 위해 유지.
3. Codex 리뷰
4. 다른 터미널에서 commit

**충돌 영역**: `langgraph_pipeline.py` 내부. 다른 터미널 A3-2는 `social.py` + 새 endpoint이라 직접 충돌 없음.

### F. 미커밋 — A6-1 personal_data_extractor 거부 발화 차단 (3중 안전망)

**상태**: 파일 적용 완료, 미커밋, Docker 미반영. Codex 리뷰 대기.

**파일**: `backend/app/services/personal_data_extractor.py`

**증상** (audit-findings.md A6-1):
- `memory_extraction`이 채팅 거부 발화를 `time_preference` 카테고리에 잘못 저장
- 예: "5월 8일 동아리 MT라 안 돼" → 수현 `time_preference: "5월 8일 동아리 MT로 인해 불가능"`
- 시연 ACT 6 ✨ 학습 카드 정확도 ↓, ACT 5 reasoning에 헛소리 들어갈 위험

**수정 — 3중 안전망**:
1. **Prompt 강화** (`_PROMPT_TEMPLATE`): time_preference 정의에 "반복적 lifestyle 패턴만, 일회성 이벤트/거부 절대 X" 명시
2. **부정 예시** (Prompt 후반): 5개 부정 예시 추가 ("5월 8일 동아리 MT라 안 돼" 등) — Gemini가 sneak-through 못 하게
3. **Post-process 필터** (`_filter_invalid_time_preference`): 정규식 `_TIME_PREF_INVALID_PATTERN`으로 추출 결과 후처리. value/source_quote에 매칭 시 drop. Gemini + canned 양쪽 경로에 통일 적용 (`extract_personal_data` 반환 직전).

**정규식 패턴**:
```python
r"\d+\s*월\s*\d+\s*일|"  # "5월 8일" 구체 날짜
r"안\s*[돼되]|못\s*가|못\s*해|힘들|어려워|어렵다|어렵겠|"
r"패스|불가능|곤란|선약|MT|시험"
```

**검증** (regex sanity, 9 테스트 케이스 통과):
| 입력 | drop? |
|---|---|
| "주말 오후" | ❌ (pass) |
| "평일 저녁 7시 이후" | ❌ (pass) |
| "저녁형" | ❌ (pass) |
| "5월 8일 동아리 MT라 안 돼" | ✅ drop |
| "9일은 본가 내려가야 해서 패스" | ✅ drop |
| "내일 시험이라 못 가" | ✅ drop |
| "그 날은 어려워" | ✅ drop |
| "주말 위주로 활동" | ❌ (pass) |
| "평일 저녁이 좋아" | ❌ (pass) |

**시연 영향**:
- ACT 6 ✨ 학습 마무리 임팩트 정확도 ↑
- ACT 5 reasoning에 거부 컨텍스트 누설 차단

**Side effect 분석**:
- `MT`/`시험` 키워드는 일반 대화에서 정성적으로 등장할 수도 있음 (예: "MT 가는 것 좋아해"). 이런 정상 케이스도 drop 됨 → false negative 가능. 시연 시나리오에선 발생 안 함.
- 정규식 보수적이라 정상 추출 100% 보장은 아님. 시연 후 false negative 감지되면 패턴 정밀화.

**Codex 리뷰 결과**: ✅ 통과 (3 iteration 후 clean):
1. v1 — Codex P2: month-less day-only ("10일") + 휴식 마커 누락 → 정규식 강화로 수정
2. v2 — Codex P2: source_quote 검사로 인한 false negative (혼합 발화) → value-only 검사로 변경
3. v3 — Codex P2: prompt가 거부 키워드 발화 전체 무시 지시 → 혼합 발화 lifestyle만 추출하도록 prompt 미세 조정 + 긍정 예시 3개 추가
4. v4 — 내 A6-1 변경 finding 0건. A3-2 관련 frontend 2건 (다른 터미널 영역)

**충돌 영역**: `personal_data_extractor.py` — 다른 터미널 작업 영역 아님. 충돌 없음.





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

### J. 미커밋 — Codex P2 보강: `_ensure_pending_meeting_id` 재사용 로직 정밀화

**상태**: 코드 적용 완료, Codex 4 iteration 통과, 미커밋.

**파일**: `backend/app/services/langgraph_pipeline.py:3735~`

**원인**: 다른 터미널 F-1 fix가 "룸의 최신 pending"을 무조건 재사용 → 무관한 stale pending에 새 카드가 잘못 붙는 cross-flow 누설.

**최종 가드** (Codex 4-pass 후):
1. `date_hint` 있으면 → 룸 최근 pending 10건 fetch → Python 측 매칭
   - 1차: `scheduled_at` primary date 매칭
   - 2차: `vote_options` 슬롯 중 어느 하나라도 같은 ISO 날짜면 매칭 (multi-date vote)
   - 시간 제한 X (장시간 합의 흐름 보호)
2. 매칭 실패 → 최근 30분 내 pending fallback (stale 차단)
3. 둘 다 실패 → 새로 생성

**충돌 영역**: `langgraph_pipeline.py` 내부, F-1 fix 영역과 같은 함수 — F-1 commit 후 이 변경이 위에 올라가야 함.

---

### I. 미커밋 — F-4 `_analyze_conversation` 프롬프트 보강 (meeting_summary 풍부화)

**상태**: 코드 적용 완료, 미커밋, Docker 미반영.

**파일**: `backend/app/services/langgraph_pipeline.py` (`_analyze_conversation`, line 4750~)

**증상** (audit-findings.md F-4):
- 결과 `notes: ["시험 끝나고 모임"]` 수준의 한 줄. 시연 카드 임팩트 ↓
- 멤버별 거부 사유, 합의 흐름 누락

**수정**:
1. **card.date 가이드 강화** — 자연어 한 줄 요약 X → 거부/합의 흐름 묘사 ("이번 주 금/토/일 모두 막힘, 다음 주 평일 후보")
2. **card.notes 구조화** — 멤버별 사정과 합의 흐름을 별도 bullet:
   - 거부 1건당 "{이름}: {날짜} {사유}" 형식
   - 마지막 1 bullet에 합의 흐름 요약
   - 3~5개 bullet 권장
3. **End-to-end 예시 추가** — 시연 ACT 2 채팅 4줄 → 기대 card 출력 명시. Gemini few-shot 학습.

**예상 효과** (시연 ACT 2):
```
이전: notes: ["시험 끝나고 모임"]
이후: notes: [
  "수현: 5/8 동아리 MT로 불가",
  "민수: 5/9 본가 일정",
  "예린: 5/10 휴식 원함, 다음 주 제안",
  "이번 주 금/토/일 막힘 → 다음 주가 후보"
]
```

**Side effect 가능성**:
- Gemini few-shot이 강해서 다른 시나리오에서도 비슷한 형식 강제 가능. 시나리오가 다양하면 약간 부자연스러울 수 있음. 시연 시나리오엔 정확히 들어맞음.
- 일관성을 위해 다른 발화 컨텍스트에서도 멤버별 사유 형식 따름. "회식 어디서 할까" 같이 거부 없는 대화는 notes가 다르게 채워짐 (자연스러움).

**충돌 영역**: `langgraph_pipeline.py` 내부, 다른 터미널 작업과 충돌 없음.

---

### H. 미커밋 — F-3 entity_extraction direct_request fast-skip 추가

**상태**: 코드 적용 완료, 미커밋, Docker 미반영. 사용자 테스트 필요.

**파일**: `backend/app/services/langgraph_pipeline.py`

**근본 원인**:
- `_route_from_start` (line 4395)이 `direct_request` 트리거에 대해 **intent_detection 노드 스킵**
- AI 패널 → quick_classify → place → trigger_reason="direct_request" 흐름은 entity_extraction부터 시작
- 내가 만든 langgraph A5-1 fast-path는 `intent_detection` 안에 있어서 **direct_request에서 절대 발동 안 함**
- 결과: entity_extraction Gemini 호출 그대로 ~15s, 시연 시 멘트 "3-5초"와 불일치

**수정**:
entity_extraction 노드 진입 시점, pre_extracted_signals 분기 다음, sentinel 기반 fast-skip **이전**에 새 fast-skip 추가:
- 조건: `trigger_reason == "direct_request"` AND `direct_request_kind == "place"`
- 추가 검증: 메시지에 cuisine 또는 place 의도 키워드 + 한국 지명 + 날짜/인원 등 다른 entity 신호 없음
- 만족 시: place_hint, meeting_type 직접 set + extracted_entities 빌드 + place_coord 해석 + return → Gemini 호출 스킵

**예상 효과**: AI 패널 "강남에서 다 같이 갈만한 한식집" → entity_extraction ~0.5s (Kakao address API만) — 이전 15.89s에서 ~30배 단축.

**남은 병목**: place_recommendation 52s — Kakao 검색 + Gemini 점수화. 이건 별도 작업 (시나리오 "3-5초"엔 아직 못 미침).

**충돌 영역**: `langgraph_pipeline.py` 내부, 다른 터미널 작업과 충돌 없음.

---

### G. 미커밋 — F-2 진단 로깅 추가 (TimeBar 추천 D 작동 검증)

**상태**: 진단 로깅 적용, 미커밋. 사용자 테스트 + 브라우저 콘솔 확인 필요.

**문제**: D 카테고리 (commit `6877461` + `b1dfd14`) 배포됐으나 TimeBar 추천이 여전히 9-13. 코드 자체엔 버그 없어 보임 — runtime 데이터 흐름 디버깅용 진단 로깅 추가.

**파일**:
- `frontend/src/components/meeting/InfoPane.tsx` — fetch + computePreferredTimeRange에 `console.info` 3개 + silent catch → `console.warn`
- `frontend/src/components/meeting/TimeBarSelector.tsx` — preferredTimeRange prop 도착 추적 `console.info` 1개

**진단 포인트** (브라우저 콘솔):
1. `[InfoPane] room preferences fetched:` — API fetch 성공 + 응답 데이터
2. `[InfoPane] preferredTimeRange computed:` — 계산된 hour range
3. `[TimeBar] preferredTimeRange prop:` — TimeBar 도착 확인

**예상 시나리오 분기**:
| 로그 패턴 | 원인 | 다음 fix |
|---|---|---|
| `fetched` 로그 안 뜸, warn 뜸 | fetch 자체 실패 | API 경로 / 인증 확인 |
| `count: 0` | popup 미입력 / DB 비어있음 | 시드 스크립트 또는 popup flow 검증 |
| `range: null`인데 prefs 있음 | 포맷 불일치 (e.g. "평일 저녁" vs "평일저녁") | computePreferredTimeRange 로직 보강 |
| `range: {18, 21}`인데 9-13 노출 | TimeBar 내부 계산 실패 | longestStreakInRange + aggregateAvailability 추가 진단 |

**시연 후 제거**: `// F-2 진단:` 코멘트가 marker. 시연 안전선 확보 후 일괄 제거.

## 메모

- 본 세션은 "여기서 커밋/푸시 안 한다" 정책으로 작업 중 (사용자 명시).
- 모든 커밋/push/Docker 재시작은 git 관리 터미널에서.
- 본 문서 자체는 미커밋 상태로 둠 (다른 터미널이 git 추적/커밋).
