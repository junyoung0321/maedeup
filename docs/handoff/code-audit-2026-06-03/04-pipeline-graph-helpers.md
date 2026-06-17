# 코드 감사: 파이프라인: 그래프 라우팅·헬퍼

> 영역키 `pipeline-graph-helpers` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/services/pipeline/graph.py`
- `backend/app/services/pipeline/helpers/dates.py`
- `backend/app/services/pipeline/helpers/formatting.py`
- `backend/app/services/pipeline/helpers/json_extract.py`
- `backend/app/services/pipeline/helpers/messaging.py`
- `backend/app/services/pipeline/helpers/preferences.py`
- `backend/app/services/pipeline/helpers/preference_toggle.py`
- `backend/app/services/pipeline/helpers/slot_state.py`
- `backend/app/services/pipeline/constants.py`
- `backend/app/services/pipeline/state.py`
- `backend/app/services/pipeline/nodes/entity.py`
- `backend/app/services/pipeline/nodes/validation.py`
- `backend/app/services/pipeline/nodes/vote_card.py`
- `backend/app/services/pipeline/nodes/slot.py`
- `backend/app/services/pipeline/nodes/maedeup.py`
- `backend/app/models/meeting_preference.py`

## 감사 노트
담당 영역(graph.py + helpers/dates,formatting,json_extract,messaging,preferences,preference_toggle)을 직접 읽고 인접 노드(entity/validation/vote_card/slot/maedeup)와 모델(meeting_preference)로 데이터 흐름을 교차 검증했다.\n\n[확인한 핵심 불변식 — 깨끗한 부분]\n1. 동시성/자원: _load_social_context(preferences.py:86-167)는 P0 fix(2026-05-16)로 r=None try/finally 패턴이 정확히 적용돼 redis connection leak 없음. Redis socket_connect_timeout/socket_timeout=1로 장애 시 fail-open. 캐시 boundary_id>=oldest_recent_id 비교(line 111-117) 정확.\n2. 프라이버시: _emit_assistant_message(messaging.py:133-148) visibility 로직은 shared 플래그/viewer_user_id 기준 일관. social context 로드는 social pane(방 전체 공개)이라 IDOR 아님. MeetingPreference는 (room_id,user_id) UNIQUE(meeting_preference.py:13-15)라 중복 제출 방어됨 → all_submitted: len(prefs)>=total_members(preferences.py:544) 카운트 신뢰 가능.\n3. tz: _format_confirmed_time/_format_slot_label에 들어가는 start_at은 slots.py:78(.replace(tzinfo=KST))로 KST-aware 생성 → isoformat +09:00 보존 → _parse_iso_datetime(dates.py:405-406 naive면 UTC 부여)이 보존 → astimezone(KST) 정확. naive/aware 혼선 없음(정상 경로 한정).\n4. 무한루프: needs_next_week_expansion은 function_call.py:87 state.pop으로 즉시 소거 → validation↔function_call 재진입 차단(주석 명시).\n5. preference_toggle.py 토글 차단조건(C1/C3/C4)과 share_*_data None→True opt-out 처리(preferences.py:266-268,344-358) 일관.\n6. json_extract.py loose 파싱은 빈입력/None/비-dict/JSONDecodeError 모두 안전하게 {} 반환.\n\n[발견 요약] 중대(P0) 결함 없음. 가장 주목할 것은 dates-1/dates-2(거부 날짜·요일 경계 해석 — 자유체험존에서 거부 신뢰성에 영향, confidence 6-7). graph-2는 Codex place 흐름과 인접해 overlaps_codex=true로 표시. 나머지(graph-1, dates-3, formatting-1)는 현재 정상 경로에서 마스킹된 잠복 결함이라 P2-P3.\n\n[PM 후속 제안]\n- dates-1/dates-2: 거부 날짜 파싱 정책은 스펙(audit-findings.md 해결점 O/P, backlog #1-#2 '번복 처리')과 연결되므로 리스크 담당 또는 PM이 '거부=미래롤 금지' 정책 확정 후 dates.py 분기 결정.\n- graph-2: Codex가 수정 중인 4/5번 place 흐름 담당과 합쳐서 all_members_selected 라우터 가드 일관성 점검 권장(중복 작업 회피 위해 Codex 영역과 조율).\n- date_classify.py(이번 범위 외, 21KB)와 slots.py(36KB)는 rejected_dates 여집합·free-slot 계산의 본체라 별도 담당 위임 시 더 깊은 correctness 감사 가능.

## 발견 (활성)

### [P2] dates-2 — 요일 경로와 일(日) 경로의 '오늘' 처리 불일치 (요일은 +7 미룸, 일은 당일 허용)
`correctness` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/helpers/dates.py:230-260,158-162`
- **메커니즘**: _fallback_parse_natural_date의 요일 단독 입력(line 232-237)은 days_ahead<=0이면 +7해 '오늘=해당 요일'을 다음 주로 보낸다. 반면 'D일' 입력(line 239-260)은 day==now_kst.day면 롤하지 않아 오늘로 처리. 또 헬퍼 _next_weekday(line 158-162)는 include_current_week 플래그로 이 경계를 제어 가능하나 요일 인라인 경로는 이 헬퍼를 쓰지 않아 항상 오늘을 배제한다. 같은 '오늘'을 가리키는 두 표현이 서로 다른 날짜로 파싱됨.
- **근거**: line 234-237 인라인 요일 처리는 days_ahead<=0 → +7. line 244 `if day < now_kst.day`(== 제외). _next_weekday는 별도로 존재하나 미사용.
- **재현**: 오늘이 금요일일 때 '금요일에 볼까' 입력 → 다음 주 금요일. 오늘이 6일일 때 '6일 어때' 입력 → 오늘.
- **영향**: '금요일 보자'를 금요일 당일에 입력하면 다음 주 금요일로, '6일 보자'를 6일에 입력하면 당일로 — 같은 의도의 표현이 일관되지 않게 미래로 점프. 당일 모임 후보가 사라지는 엣지.
- **제안 수정**: 요일/일 경로 모두 동일한 '오늘 포함' 정책으로 통일하거나 _next_weekday(include_current_week=...)로 일원화. 정책은 PM/스펙 확인 필요.

### [P2] graph-1 — _route_after_validation 라우터가 state를 in-place mutate (partial_mode) — LangGraph 안티패턴, 현재는 노드 중복 set으로 마스킹
`correctness` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/graph.py:145-147`
- **메커니즘**: conditional edge 함수 _route_after_validation이 status==time_only_ready일 때 라우터 내부에서 `state["partial_mode"]="time_only"`를 set. LangGraph의 라우터(path 함수)는 라우팅 키만 반환하며 state delta를 채널에 병합하지 않는 것이 원칙이라, 이 mutation이 다음 노드 maedeup_card_creation(maedeup.py:82가 partial_mode를 읽음)에 보장 전파되지 않을 수 있다. 현재는 time_only_ready에 도달하는 정상 경로에서 slot.py:304/522가 이미 partial_mode를 박아 마스킹됨 → 라우터 set은 사실상 dead/중복.
- **근거**: graph.py:146 라우터 내 state 쓰기. slot.py:304,522가 같은 값을 노드 안에서 이미 set. maedeup.py:82가 partial_mode 소비.
- **재현**: 직접 재현 불가(현재 정상 경로는 마스킹). 코드 리뷰 수준 결함.
- **영향**: 현 시점 무해(중복). 그러나 향후 time_only_ready를 slot.py 외 경로로 도달시키면 partial_mode가 누락돼 매듭 카드가 full 모드로 잘못 렌더될 수 있는 잠재 결함. 라우터의 부작용은 디버깅을 어렵게 함.
- **제안 수정**: 라우터에서 state mutation 제거. partial_mode set은 supervisor_validation 노드(validation.py) 내부로 이동시켜 노드 반환으로 전파 보장.

### [P2] graph-2 — _route_after_place_recommendation에서 all_members_selected가 confirmed_place 없이 maedeup 직행 → 장소 미확정 매듭 카드 가능
`correctness` · conf 5/10 · 미검증(P2/P3) · ⚠겹침:Codex

- **위치**: `backend/app/services/pipeline/graph.py:206-220, backend/app/services/pipeline/nodes/maedeup.py:64-81`
- **메커니즘**: place_recommendation 후 라우터는 trigger_reason==direct_request만 END로 보내고(line 217), all_members_selected는 어느 분기에도 안 걸려 line 220 else로 maedeup_card_creation 직행. all_members_selected는 TimeBar 시간확정+장소추천 흐름(graph:159-161)인데, place 노드가 confirmed_place를 set하지 않으면 maedeup.py:77이 pending meeting을 만들며 confirmed_place 없는 매듭 카드를 생성. line 214-218 주석은 direct_request에 대해 '자동 진행하면 confirmed_date와 데이터 불일치 가능'이라며 END 처리한 반면 all_members_selected에는 같은 보호가 없음.
- **근거**: graph.py:217은 direct_request만 END. all_members_selected 미언급 → line 220 else. maedeup.py:67-81은 confirmed_place 부재여도 카드 생성 진행.
- **재현**: all_members_selected 트리거 + date_hint 존재 + place_recommendation 정상 종료 경로. place 노드가 confirmed_place 미설정이면 maedeup 진입.
- **영향**: TimeBar 전원 선택 흐름에서 사용자가 장소를 confirm하기 전에 매듭 카드(장소 미확정/추천 첫 후보 자동 채택)가 발행될 수 있어, 장소 확정 UX와 데이터 정합성 불일치 위험. Codex 4/5번(place 흐름)과 인접하나 라우터 분기 누락은 별개.
- **제안 수정**: direct_request와 동일하게 all_members_selected도 confirmed_place 없으면 END 처리하거나, place 노드의 confirmed_place 설정 보장을 라우터 가드에 추가. PM/Codex와 흐름 정합 확인 필요.

### [P3] formatting-1 — _format_slot_label 12시간제 변환에서 0시/12시 표기 부정확 (WORK_HOUR 범위 밖이라 비발현)
`correctness` · conf 8/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/helpers/formatting.py:22-23,35`
- **메커니즘**: line 22 `ampm = "오전" if start_at.hour < 12 else "오후"`, line 23 `hour = start_at.hour if start_at.hour <= 12 else start_at.hour - 12`. 0시는 '오전 0:00'(12시간제 관례는 '오전 12:00'), 12시는 '오후 12:00'으로 표기. 동일 모듈의 _format_confirmed_time(line 43)은 `hour % 12 or 12`로 0시를 12로 정규화 → 두 함수 규칙 불일치.
- **근거**: formatting.py:23 vs line 43. 모임 슬롯은 WORK_HOUR_START=9~WORK_HOUR_END=22(constants.py:12-13) 범위라 0시 슬롯 미생성.
- **재현**: 현재 경로상 재현 불가(슬롯 시간 9~22로 제한).
- **영향**: 정상 운영에서는 9~22시 슬롯만 생성돼 비발현. 자정/정오 슬롯이 생기는 미래 변경 시 라벨 표기 오류.
- **제안 수정**: _format_slot_label도 `hour = start_at.hour % 12 or 12`로 통일.

### [P3] dates-3 — _parse_natural_date_sync(@lru_cache)가 mutable dict를 반환 — 캐시 공유 객체 오염 가능성 (현 호출부는 read-only)
`correctness` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/helpers/dates.py:341-357,360-371`
- **메커니즘**: @lru_cache(maxsize=256)가 캐싱하는 _parse_natural_date_sync는 dict를 반환. _parse_natural_date(line 368-371)는 캐시 hit 시 동일 dict 객체를 그대로 반환한다. 호출자가 이 dict를 mutate하면 캐시된 객체가 오염돼 동일 (text, today_iso) 키의 후속 호출이 변형된 값을 받게 된다. 현재 entity.py:771-781은 .get()으로 읽기만 하므로 미발현.
- **근거**: dates.py:356-357 fallback dict 반환, line 371 `return cached`(복사 없음). entity.py 호출부는 read-only.
- **재현**: 현재 재현 불가. 미래 코드 변경 시 노출.
- **영향**: 현재 무해. 향후 누군가 _parse_natural_date 결과를 in-place 수정하면 cross-request 데이터 오염 → 날짜 파싱 비결정성. 잠복 취약.
- **제안 수정**: _parse_natural_date에서 캐시 결과를 dict(cached)로 복사 반환, 또는 캐시 함수가 불변 형태(frozen) 반환.

### [P3] dates-1 — _resolve_rejected_date가 거부 날짜를 미래 의미로 롤 → 잘못된 날짜를 거부 목록에 삽입
`correctness` · conf 6/10 · ⤵ 강등됨(원래 P1)

- **위치**: `backend/app/services/pipeline/helpers/dates.py:72-103,239-260`
- **메커니즘**: entity.py:803/529가 LLM rejected_dates의 자연어 date("5월 9일","금요일")를 _resolve_rejected_date로 ISO 정규화 → _fallback_parse_natural_date 호출. 거부 표현은 보통 '협의 중인 가까운 후보'를 가리키나, 이 함수는 미래 파서라 day<now_kst.day면 다음 달로(line 244-248), 요일이 days_ahead<=0이면 다음 주로(line 234-237) 롤한다. 결과 ISO가 실제 거부 대상이 아닌 미래 날짜가 됨. 이후 function_call.py:160의 _filter_out_rejected가 엉뚱한 날짜를 후보에서 제거하거나, 정작 거부된 날짜는 살아남는다.
- **근거**: dates.py:244 `if day < now_kst.day: month += 1` 그리고 line 235 `if days_ahead <= 0: days_ahead += 7`. _resolve_rejected_date는 이 결과를 그대로 ISO로 채택(line 100-103). 거부 컨텍스트 전용 로직 없음.
- **재현**: 현재 날짜가 그 달 10일 이상인 상태에서 '5일은 빼고'처럼 일(日) 거부, 또는 오늘과 같은 요일을 거부 발화. _resolve_rejected_date 결과가 다음 달/다음 주 ISO로 나옴.
- **영향**: 멤버가 '9일은 안 돼'라고 거부했는데 오늘이 10일 이후면 9일이 '다음달 9일'로 정규화 → 실제 9일 후보가 vote 카드에 남아 거부 의도 무시. 거부 신뢰성 저하(시연/자유체험 모두 영향).
- **제안 수정**: 거부 날짜 해석은 미래 롤을 하지 말고, now 기준 동일 달/주 우선으로 해석하거나 rejected 전용 파서 분기. 최소한 '오늘 같은 요일'을 +7 미루지 않도록 거부 컨텍스트에서 include_current_week=True 적용 검토.
- **검증 판단**: 주장의 핵심 전제(entity.py:803/529가 LLM rejected_dates의 자연어를 _resolve_rejected_date로 받아 미래 파서가 롤한다)는 정상 거부 경로에서 깨진다. 세 진입 경로 모두 거부 발화에 대해 _DATE_SIGNAL_RE 게이트로 classify_availability→to_rejected_dates를 호출해 rejected_dates를 ISO로 덮어쓴다: ① conversation_analyzer.py:248-257(pre_extracted로 흐름), ② entity.py:484-491(pre 분기), ③ entity.py:265-272(_extract_entities_from_context). to_rejected_dates(date_classify.py:346-360)는 _resolve가 캘린더 윈도우(date_classify.py:199)에서 만들고 line 188 `>= today_iso`로 과거 컷한 ISO set만 반환한다. _resolve_rejected_date(dates.py:72)는 ISO를 받으면 line 87-88 `_is_specific_iso_date`에서 즉시 반환 → 문제의 _fallback_parse_natural_date 미래 롤(dates.py:234-260)에 도달하지 않는다. 주장이 제시한 바로 그 repro("5일은 빼고"→`빼고` 매치, "오늘 같은 요일 거부"→요일 토큰 매치)는 모두 _DATE_SIGNAL_RE(entity.py:220-226)를 통과해 ISO override가 발동되므로 자연어가 파서에 안 닿는다. 잔존 경로: _DATE_SIGNAL_RE는 매치하나 classify_availability가 빈 rejected를 반환(LLM 실패+detector 미매치)하면 entity.py:491/272 `if _av.get("rejected")`가 False라 override 미발동 → LLM 자연어 rejected_dates가 남아 line 803/529가 "금요일"을 받아 미래 롤 가능. 그러나 (a) LLM 프롬프트(entity.py:364)가 "요일은 오늘 이후 가장 가까운 미래로 변환, date는 반드시 YYYY-MM-DD"를 명시해 보통 ISO 반환, (b) 잘못된 미래 ISO가 생겨도 _filter_out_rejected(slots.py:359-364)는 정확 ISO 동등 비교라 가까운 미래 후보 슬롯과 매치 안 돼 "엉뚱한 날짜 제거" 임팩트는 거의 없고 드문 recall 손실만 발생. P1(시연 신뢰성 심각)이 아니라 fallback-of-fallback의 드문 recall 저하 → P3. memory project_pattern_skip_rejected_blindspot.md와 동일 영역이나 이 메커니즘은 ISO override로 대부분 차단됨.
