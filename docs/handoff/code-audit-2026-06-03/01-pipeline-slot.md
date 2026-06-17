# 코드 감사: 파이프라인: 슬롯 필링·시간 산출·랭킹

> 영역키 `pipeline-slot` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/services/pipeline/nodes/slot.py`
- `backend/app/services/pipeline/helpers/slots.py`
- `backend/app/services/pipeline/helpers/slot_state.py`
- `backend/app/services/slot_ranker.py`
- `backend/app/services/pipeline/constants.py`
- `backend/app/services/pipeline/helpers/dates.py`
- `backend/app/services/pipeline/nodes/function_call.py`
- `backend/app/services/pipeline/nodes/vote_card.py`
- `backend/app/api/routes/rooms.py`
- `backend/app/services/scheduling_round.py`
- `backend/app/services/pipeline/helpers/preferences.py`

## 감사 노트
검토 범위: slot.py(10 분기 헬퍼 전체), helpers/slots.py(get_free_slots 225줄 + _find_free_slots + _build_majority_fallback_slots + _build_multi_date_slots + _build_preference_time_slots + _is_busy_during), helpers/slot_state.py(_update_slot_state, _build_flexible_time_options, _preference_score_for_start), slot_ranker.py 전체. 호출부(function_call.py, vote_card.py, rooms.py schedule-confirm, scheduling_round.slot_idx_to_time, preferences._load_meeting_preferences)까지 교차 확인.

확인한 핵심 불변식(문제 없음):
- _is_busy_during(slots.py:730-754): naive busy period를 UTC로 보정 후 aware 비교, overlap 조건 `ps < end_at and pe > start_at` 정확. _find_free_slots/_build_multi_date_slots의 start_at은 모두 aware ISO(전자는 UTC-aware current.isoformat(), 후자는 KST-aware)라 slot_ranker._to_kst의 naive→KST 가정과 충돌하는 naive 슬롯은 발생하지 않음.
- get_free_slots date_hint UTC 파싱(slots.py:513-516) + KST work-hour 필터: 06-08 1일창(UTC)이 KST로는 06-08 09:00~06-09 09:00이지만 work_hour 9~22 필터로 06-08 종일(09~21시)이 정상 커버됨 — 요청일 슬롯 손실 없음(extended 전략 별건은 slot-2로 분리).
- _update_slot_state(slot_state.py:44-82): date_hint 변경 시 time_options 리셋, headcount _coerce_headcount로 0/음수 None 처리 정상. SLOT_KEYS 4개 missing 계산 정확.
- _normalize_preferred_times는 PREFERRED_TIME_RANGES 6개 canonical 키만 통과시켜 stalemate의 '평일'/'주말' prefix 검사 및 _preference_score_for_start가 안전. common_times도 동일 정규화 거침(preferences.py:505).
- manual pick 정상 경로(rooms.py)는 end_idx<26 검증 → slot_idx_to_time(26)=22:00 상한 안전.
- _slot_filling_all_members 구역 A~D는 각 try가 (NameError/AttributeError/ImportError) re-raise + 나머지 swallow로 silent-fail 의도적 처리됨(주석 명시). DB 세션도 async with로 정상 정리.

Codex 5버그와의 겹침: 없음(별개 슬롯/랭킹 로직 결함). slot-1/slot-3은 BUG-26-D(카운터 분모) 인접 영역이나 다른 결함(fallback 경로 분모 불일치 / 분자 과대계상)이라 신규.

리더 후속 제안: slot-1(F1 fallback 분모 불일치)과 slot-3(분자 과대계상)은 vote_card 카운터 표시 일관성 이슈 — UI/리뷰 담당이 실제 게스트 혼합 룸에서 vote_card 카운터 표기를 qa로 재현 확인 권고. slot-2(date_hint extended 날짜 누출)는 finalization/confirmed_date 소비 경로 담당이 단일슬롯 확정 흐름에서 날짜 일관성 검증 필요.

## 발견 (활성)

### [P2] slot-1 — F1 다수결 fallback 슬롯의 total_count 분모가 정상 경로(BUG-26-D)와 불일치 — 캘린더 미동의 멤버가 누락된 비율 표시
`data-integrity` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/helpers/slots.py:264, backend/app/services/pipeline/nodes/function_call.py:236-246`
- **메커니즘**: 정상 경로의 _find_free_slots는 headcount_total(=전체 룸 멤버 수 len(members))를 total 분모로 사용한다(slots.py:183, get_free_slots가 headcount_total=len(members) 전달, line 539/556/583/600 — BUG-26-D 수정). 그러나 전원 가능 슬롯 0개일 때 진입하는 F1 fallback 경로의 _build_majority_fallback_slots는 headcount_total 인자를 받지 않고 total = len(busy_by_user)(=캘린더 동의 멤버 수)만 사용한다(slots.py:264, 291 total_count=total). function_call.py:236도 total_members = len(busy_by_user)로 잡아 missing_count/total_count를 계산한다. 게스트나 캘린더 미동의 멤버가 있으면(예: 룸 4명 중 2명만 동의) 정상 vote_card는 '2/4'로 보여주지만 F1 fallback vote_card는 '1/2'처럼 다른 분모로 표시되어 같은 룸에서 전략에 따라 카운터 의미가 달라진다.
- **근거**: slots.py:183 `total = headcount_total if headcount_total else len(busy_by_user)` (정상). slots.py:264 `total = len(busy_by_user)` (fallback, headcount_total 미수용). _build_majority_fallback_slots 시그니처(slots.py:241-248)에 headcount_total 파라미터 없음. function_call.py:236 `total_members = len(busy_by_user)`.
- **영향**: 전원 가능 슬롯이 없는 모임(F1 다수결 추천)에서 vote_card의 'N명 가능' 카운터 분모가 전체 인원이 아니라 캘린더 동의 인원으로 표시 → BUG-26-D가 막으려던 '1/1명 가능' 류의 오해를 fallback 경로에서 재현. 시연 중 캘린더 미동의 멤버 존재 시 가능 인원 비율이 과대표시될 수 있음.
- **제안 수정**: _build_majority_fallback_slots에 headcount_total 파라미터 추가(기본 None), total = headcount_total or len(busy_by_user)로 통일. function_call.py:236의 total_members도 len(members)(전체 룸 멤버)로 산출하도록 변경하여 BUG-26-D와 동일 분모 사용.

### [P2] slot-2 — date_hint 지정 시 extended 전략이 요청 날짜 외 날짜(+7~14일) 슬롯을 반환 — confirmed_date(요청일)와 슬롯 실제 날짜 불일치 가능
`correctness` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/helpers/slots.py:513-519,566-640, backend/app/services/pipeline/nodes/vote_card.py:259-260`
- **메커니즘**: get_free_slots에서 date_hint(예 '2026-06-08')가 있으면 time_min/time_max를 해당 날짜 1일 창으로 잡는다(slots.py:515-516). 그러나 전원/n-1 슬롯이 그 날에 없으면 extended_time_max = time_max + 7~14일로 확장해(slots.py:566) 06-09~06-15의 슬롯까지 후보로 반환한다(extended_full_slots / final_slots). 이 슬롯들이 calendar_free_slots가 되어 vote_card로 흘러간다. 한편 vote_card.py:259-260은 confirmed_date = date_hint(06-08)로 박는다. 따라서 단일슬롯/time_only finalization 경로에서 사용자가 요청한 날짜(06-08)와 실제 추천 슬롯 날짜(예 06-12)가 어긋날 수 있다. (vote_card의 time_options 라벨/start_at 자체는 슬롯값을 그대로 쓰므로 다중 투표 카드에선 사용자에게 실제 날짜가 노출되어 일관되지만, confirmed_date를 권위값으로 쓰는 후속 단계와 충돌.)
- **근거**: slots.py:513 `re.match(r"\d{4}-\d{2}-\d{2}", str(date_hint))` 후 1일 창. slots.py:566 `extended_time_max = time_max + timedelta(days=14 if normalized_preferred_times else 7)`. extended 슬롯은 _filter_out_blocked만 통과(날짜 제한 없음). vote_card.py:260 `state["confirmed_date"] = state.get("date_hint")`. 정상 경로 narrator는 best_label(슬롯값)을 쓰므로(vote_card.py:403,412) 메시지는 슬롯날짜 기준 — confirmed_date(date_hint)와 분리됨.
- **영향**: 특정 날짜를 지정한 모임에서 그 날 전원 가능 슬롯이 없으면 다른 날짜의 슬롯이 추천되는데 confirmed_date는 원래 요청일로 남아, 후속 확정/요약 표시에서 날짜 불일치 가능. 빈번하진 않으나 캘린더가 꽉 찬 멤버가 있을 때 발생.
- **제안 수정**: date_hint가 명시된 단일 날짜 케이스에서는 extended 전략을 적용하지 않거나(요청일 내에서만 n-1까지 탐색), extended 적용 시 confirmed_date를 실제 선택된 슬롯의 날짜로 갱신. 최소한 extended 슬롯을 date_hint 날짜로 _filter 하거나 narrator/confirmed_date 정합 보장.

### [P2] slot-3 — _find_free_slots available_count가 검증되지 않은 비동의 멤버를 '가능'으로 합산 (headcount_total > 동의 인원)
`correctness` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/helpers/slots.py:183,200,202-206`
- **메커니즘**: all_members_available 전략 호출 시 minimum_available=len(busy_by_user)(동의 인원, 예 2), require_exact_absent_count=0(동의자 중 불가 0명)로 호출되지만 total=headcount_total(전체, 예 4)이다(slots.py:183). available_count = total - len(unavailable_names)에서 unavailable은 busy_by_user(동의자) 중에서만 집계되므로(slots.py:195-200), 캘린더 미동의 멤버 2명은 가용성 확인 없이 자동으로 '가능'에 포함된다 → available_count=4, total_count=4 ('전원 가능'). 실제로는 동의자 2명만 비어있음이 검증됨. BUG-26-D 주석(slots.py:181-183)은 분모를 전체로 올리는 의도만 명시하고 분자 과대계상은 의도에 포함되지 않음.
- **근거**: slots.py:183 total=headcount_total(4). slots.py:195-199 unavailable_names는 busy_by_user.items()만 순회(동의자 2명). slots.py:200 available_count = 4 - (0~2). require_exact_absent_count=0이므로 동의자 전원 free일 때만 슬롯 채택 → available_count는 항상 4(=full)로 표기되며 미동의 2명은 미검증.
- **영향**: 캘린더 미동의/게스트 멤버가 있는 룸에서 vote_card가 실제로는 검증 안 된 멤버를 포함해 '4/4 전원 가능'으로 과대표시. 사용자가 전원 확정으로 오인할 수 있음. (주석상 분모 의도는 명시됐으나 분자 신뢰도 표기 부재.)
- **제안 수정**: available_count를 검증된 동의자 기준으로 두 가지로 분리 표기하거나(예 'verified_available' vs 'total'), unavailable 미상(unknown) 멤버 수를 별도 필드로 노출. 최소한 narrator/카드에서 '동의 멤버 기준'임을 표기.

### [P3] slot-5 — slot_ranker._lead_time_score 비단조 — days=3(0.9)이 days=4(0.95)보다 낮아 추천 순위 역전 가능
`correctness` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/slot_ranker.py:90-102`
- **메커니즘**: _lead_time_score는 days<=3 분기에서 `0.8 + (days-2)*0.1`을 반환해 days=2→0.8, days=3→0.9. 그러나 days<=7 분기는 `1.0 - (days-3)*0.05`로 days=4→0.95, days=5→0.90. 따라서 day3(0.9) < day4(0.95)로 리드타임이 더 짧은 날이 더 낮은 점수를 받는 비단조 구간이 생긴다. lead_time 가중치 0.20(slot_ranker.py:56)이라 동률 슬롯 간 순위에 영향.
- **근거**: slot_ranker.py:96-99: days==3 → 0.9 (line 96-97 `if days <= 3: return 0.8 + (days - 2) * 0.1`), days==4 → `1.0 - (4-3)*0.05 = 0.95` (line 98-99). 0.9 < 0.95 역전.
- **영향**: vote_slots 재정렬(rank_slots, vote_card.py:313)에서 3일 후 슬롯이 4일 후 슬롯보다 뒤로 밀릴 수 있음 — 추천 품질/순서 미세 왜곡. 데이터 손상·크래시 아님.
- **제안 수정**: days<=3 분기 곡선을 days<=7 분기와 연속이 되도록 보정(예 days==3에서 0.95 또는 days<=7 시작값 정렬). 우선순위 낮음.

### [P3] slot-4 — get_free_slots date_hint에 날짜범위 문자열 유입 시 fromisoformat ValueError 미처리 (re.match prefix 매칭의 사각지대)
`edge-case` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/helpers/slots.py:513-514, backend/app/services/pipeline/nodes/function_call.py:217-218`
- **메커니즘**: date_hint 분기에서 `re.match(r"\d{4}-\d{2}-\d{2}", str(date_hint))`는 fullmatch가 아닌 prefix 매칭이라 '2026-06-08~2026-06-10' 같은 범위 문자열도 통과한다(_is_iso_date_hint는 범위를 허용, dates.py:59-63). 통과 후 `datetime.fromisoformat(str(date_hint))`는 '~'를 파싱 못해 ValueError를 던지며, 이 줄은 try로 감싸여 있지 않아 get_free_slots 전체가 예외 → 상위 node 예외 핸들러로 전파(슬롯 0개·fallback 메시지). function_call.py:217-218도 동일 패턴.
- **근거**: slots.py:513 `re.match(...)` (prefix), slots.py:514 `hint_date = datetime.fromisoformat(str(date_hint))` (try 없음). dates.py:59-63 `_is_iso_date_hint`가 `\d{4}-\d{2}-\d{2}(~\d{4}-\d{2}-\d{2})?` 허용 → date_hint에 범위 유입 경로 존재. _is_specific_iso_date는 fullmatch라 안전하나 여기선 미사용.
- **영향**: date_hint에 단일 날짜 대신 범위가 박히는 경로가 생기면(현재 주 경로는 date_hints 복수로 처리되나 보장 없음) get_free_slots 크래시 → 슬롯 추천 무음 실패. 현재 입력 경로상 빈도 낮음.
- **제안 수정**: slots.py:513의 정규식을 `re.fullmatch` + _is_specific_iso_date로 교체하거나, fromisoformat을 try/except ValueError로 감싸 range/비정상 date_hint를 안전하게 폴백 창으로 처리.

### [P3] slot-6 — _slot_filling_all_members manual pick: slot_idx_to_time 상한 미검증 (end_idx+1) — API 검증 우회 시 잘못된 confirmed_time
`edge-case` · conf 6/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/nodes/slot.py:289-301, backend/app/services/scheduling_round.py:582-585`
- **메커니즘**: slot.py:289-295는 start_idx>=0, end_idx>=start_idx만 검증하고 상한을 체크하지 않는다. slot_idx_to_time(scheduling_round.py:582-585)도 idx 상한이 없어 idx>26이면 'HH'가 24 이상('24:30' 등)인 비정상 문자열을 반환한다. confirmed_time은 이 값으로 즉시 세팅된다(slot.py:301). 후속 vote_options patch의 datetime.fromisoformat은 ValueError로 catch되지만(slot.py:380,406) confirmed_time 자체는 이미 비정상값으로 남는다. 단, 주 경로인 rooms.py schedule-confirm은 `ct.end_idx >= sr.TIME_SLOT_MAX(26)`를 검증(rooms.py:561)하므로 정상 입력에서는 end_idx<=25 → slot_idx_to_time(26)=22:00로 안전. compute_majority_slot 경로도 동일 availability 셀 기반이라 통상 안전.
- **근거**: slot.py:291-295 상한 검증 없음. scheduling_round.py:582-585 idx 상한 없음 → 26 초과 시 hh>=24. rooms.py:561 `or ct.end_idx >= sr.TIME_SLOT_MAX or ...` 으로 API에서 차단(완화 요인).
- **영향**: 정상 경로에선 API가 차단하므로 시연 영향 거의 없음. manual_chosen_time이 API 검증을 거치지 않는 다른 경로(예 직접 trigger payload, agent.py:914-916)로 비정상 end_idx가 들어오면 confirmed_time이 '...~24:30' 등으로 깨질 수 있음.
- **제안 수정**: slot.py 검증에 `end_idx < sr.TIME_SLOT_MAX` 상한 추가, 또는 slot_idx_to_time에 0<=idx<=TIME_SLOT_MAX assert/clamp 추가.

### [P3] slot-7 — _enrich_with_preferences: place_hint를 preference best_location으로 주입하면 is_location_first가 True가 되어 사용자가 언급 안 한 장소로 location-first 카드 전환
`edge-case` · conf 5/10 · 미검증(P2/P3)

- **위치**: `backend/app/services/pipeline/nodes/slot.py:120-123,150-154`
- **메커니즘**: has_preferences이고 intent != place_suggestion이며 place_hint가 비어있고 best_location이 있으면 state['place_hint']=best_location으로 채운다(slot.py:121-123). 그 직후 is_location_first = bool(place_hint) and not date_hint and intent != meeting_schedule로 계산된다(slot.py:150-154). 즉 사용자가 장소를 전혀 언급하지 않았어도 선호 데이터의 best_location만으로 is_location_first=True가 되어 시간 조율 대신 장소 추천(location_first_ready) 경로로 분기할 수 있다(_slot_filling_default slot.py:549-554). intent가 meeting_schedule이면 차단되지만 intent가 None/기타면 통과.
- **근거**: slot.py:121-123 place_hint <- best_location. slot.py:150-154 is_location_first 계산이 place_hint 주입 이후. slot.py:549-554 is_location_first True면 status='location_first_ready' 즉시 반환.
- **영향**: 선호에 장소가 등록된 룸에서 사용자가 시간만 논의 중인데(intent 불명확) AI가 갑자기 장소 추천으로 흐를 수 있음 — 흐름 오분기. meeting_schedule 의도 분류가 정확하면 회피됨.
- **제안 수정**: is_location_first 판정 시 '사용자 발화 기반 place_hint'와 '선호 주입 place_hint'를 구분(플래그). 선호로 주입된 경우 is_location_first 트리거에서 제외하거나 date 부재 + 명시적 장소 언급일 때만 location-first 진입.
