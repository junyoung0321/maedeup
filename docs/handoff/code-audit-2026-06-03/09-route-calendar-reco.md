# 코드 감사: API: calendar.py(free-slots·busy·GCal)·recommendations·places route

> 영역키 `route-calendar-reco` · 워크플로 자동 감사 (2026-06-03) · P0/P1은 적대적 검증 거침.

## 검토 파일
- `backend/app/api/routes/calendar.py`
- `backend/app/api/routes/recommendations.py`
- `backend/app/api/routes/places.py`
- `backend/app/services/google_calendar.py`
- `backend/app/services/kakao_maps.py`
- `backend/app/services/scheduling_round.py (load_room_unavailability)`
- `backend/app/api/routes/users.py (update_consent)`
- `backend/app/api/routes/rooms.py (cache invalidation call sites)`
- `frontend/src/lib/datetime.ts`
- `frontend/src/components/home/AiRecommendCard.tsx`
- `frontend/src/components/home/QuickMatchPopup.tsx`
- `backend/app/models/user.py`

## 감사 노트
검토 완료. 확인한 핵심 불변식: (1) IDOR 방어는 견고 — free-slots는 캐시 GET '이전'에 RoomMember 멤버십 검증(calendar.py:414-423)을 수행해 비멤버 캐시 HIT 차단(주석에 free-use audit 2026-06-01 명시). available-friends/nearby-places/my-events는 모두 current_user 본인 데이터(친구·home_base·본인 캘린더)만 노출, 타 유저/타 방 누수 없음. (2) datetime aware/naive 처리: _classify_friend의 _to_naive는 모든 값을 일관된 naive UTC로 정규화 후 비교(reco.py:60-71) — 비교 자체는 정확. _has_event_on_day/_compute_free_slots의 aware-aware 비교(KST·UTC 혼재)는 Python이 오프셋 고려해 올바르게 비교. 종일 이벤트(Google end.date 배타적)는 KST 자정~다음날 자정으로 파싱(calendar.py:153-154)되어 work-hour(09-22) 전체를 덮어 busy 판정 — 정확. (3) Google 토큰 401 재시도·force_refresh 경로 일관(google_calendar.py 전반), refresh 시 새 refresh_token 있으면 갱신·commit. (4) sync/delete_events_for_meeting_members는 best-effort로 per-member 실패를 잡고 매핑 정리 — 고아 이벤트는 주석상 수용된 trade-off. (5) Kakao 5xx/timeout은 KakaoApiError로 raise해 narrator 분기(의도된 설계), 그 외 빈 결과는 [] — places/nearby의 except가 적절히 [] 처리. (6) 캐시 직렬화: FreeSlotsResponse는 전부 str/int 필드라 model_dump→JSON 왕복 안전, 캐시 HIT raw dict도 response_model로 재검증됨. 주요 발견은 reco-1(available_at UTC/KST 규약 불일치, 프론트 9h 스큐)가 사용자 체감 가장 큼. 발견된 4건 모두 Codex 진행 중 5버그와 무관(겹침 없음).

## 발견 (활성)

### [P2] reco-1 — available-friends의 available_at은 UTC-naive인데 프론트는 KST-naive로 해석 → '곧 가능' 시간 9시간 오류
`correctness` · conf 8/10 · ⤵ 강등됨(원래 P1)

- **위치**: `backend/app/api/routes/recommendations.py:60-63,77,79; frontend/src/lib/datetime.ts:11-14; frontend/src/components/home/AiRecommendCard.tsx:44; frontend/src/components/home/QuickMatchPopup.tsx:24`
- **메커니즘**: 1) _classify_friend의 _to_naive()가 busy period end를 d.astimezone(timezone.utc).replace(tzinfo=None)로 변환 → UTC 벽시계값(오프셋 없음)을 available_at으로 반환(line 77,79). 2) Pydantic이 naive datetime을 오프셋 없는 ISO 문자열로 직렬화(예: '2026-06-03T05:30:00'). 3) 프론트 parseServerDate는 new Date(value)만 호출하며 주석상 'KST naive → 로컬 시간(KST) 해석' 규약(datetime.ts:13). KST 로컬 환경에서 JS가 이 문자열을 KST로 파싱 → 서버 의도(UTC)와 9시간 차이. 4) AiRecommendCard.tsx:44 minutes 계산이 음수가 되어 Math.max(1,...)로 항상 '1분 후'로 표시되거나, QuickMatchPopup.tsx:24는 raw new Date로 큰 음수 분을 그대로 노출.
- **근거**: recommendations.py:60-63 _to_naive는 UTC로 변환 후 tzinfo 제거. 동일 응답의 now 필드(line 120,166)는 aware UTC라 규약이 한 응답 내에서도 불일치. datetime.ts:13 주석이 명시적으로 'KST naive' 가정. free_in은 earliest_end<=until(window<=720분)일 때만 발생하므로 9h 스큐가 거의 항상 오표시 유발.
- **영향**: 홈 화면 'AI 추천/빠른 매칭'에서 '곧 가능' 친구의 가능 시각(예: '15분 후 가능')이 9시간 어긋나 항상 '1분 후' 또는 음수로 표시. 데모 시 눈에 띄는 오동작.
- **제안 수정**: available_at을 aware UTC로 반환(replace(tzinfo=timezone.utc) 유지)하거나, _to_naive 후 출력 시 KST로 변환해 응답. 가장 일관적인 방법은 now와 동일하게 aware UTC datetime을 그대로 직렬화(프론트가 'Z' 오프셋으로 정확히 파싱). 또는 프론트 parseServerDate가 오프셋 없는 값을 UTC로 강제하도록 통일.
- **검증 판단**: 메커니즘 4단계 모두 코드로 확인. (1) recommendations.py:60-63 _to_naive가 aware→UTC-naive 변환, calendar.py:149-154 _get_busy_periods는 항상 aware(시간일정 +00:00, 종일 KST) 반환하므로 line 77/79 available_at=earliest_end는 UTC 벽시계값. (2) AvailableFriend.available_at: Optional[datetime](recommendations.py:43)은 naive라 Pydantic이 오프셋 없는 ISO로 직렬화. (3) datetime.ts:11-13 parseServerDate는 new Date(value)뿐, 주석상 'KST naive→로컬(KST) 해석' 규약 → KST 브라우저가 UTC 문자열을 KST로 파싱해 9h 빠르게 해석. (4) AiRecommendCard.tsx:44는 음수→Math.max(1,..)로 항상 '1분 후', QuickMatchPopup.tsx:24-25는 음수→'곧 가능'. now 필드(recommendations.py:115,165)는 aware UTC라 한 응답 내 직렬화 규약 불일치도 확인. 반증 시도: 프론트 양쪽에 오프셋 보정 가드 없음, free_in window≤720분이라 540분 스큐가 거의 항상 부호 뒤집음 → 결함 실재(confirmed). 다만 P1→P2 하향: ① 영향이 표시 부정확에 국한(AiRecommendCard는 클램프로 '1분 후', QuickMatchPopup은 '곧 가능' graceful fallback — 크래시/데이터손상/음수노출 없음), ② 백엔드 분류 로직(free/free_in/busy_now 판정·정렬·렌더)은 정상, ③ 9h 단정은 브라우저=KST 전제 의존(데모는 성립하나 일반성 약함). available_at만 보조 라벨이라 핵심 기능 결손 아님.

### [P2] cal-1 — free-slots: Google 이벤트가 dateTime/date 둘 다 없으면 _get_busy_periods가 KeyError로 500 (my-events는 가드, free-slots는 미가드)
`edge-case` · conf 8/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/calendar.py:143-156,466`
- **메커니즘**: _get_busy_periods의 for item 루프(143-156)는 'if "dateTime" in start_raw: ... else: start = ...start_raw["date"]'로, start_raw에 dateTime도 date도 없으면(빈 {} 또는 비정상 항목) start_raw['date']에서 KeyError 발생. 이 함수는 try/except로 감싸지지 않았고, 호출부(line 466 busy_by_user[...] = await _get_busy_periods(...))도 가드 없음 → 예외가 get_free_slots 전체로 전파되어 500.
- **근거**: 동일 모듈 my-events(line 620,627,634)는 'if dateTime ... elif date in start_raw ... else: continue'로 방어하지만 _get_busy_periods(148,151)는 'else'에서 무조건 date 키 접근. recommendations.py:127-133의 _safe_busy는 try/except로 보호되어 reco는 안전하나 free-slots는 무방비.
- **영향**: 특정 멤버 캘린더에 비정상 항목이 하나라도 있으면 방 전체 free-slots 조회가 500. 흔치 않으나 발생 시 캘린더 X/N 패널 전체 마비.
- **제안 수정**: _get_busy_periods 루프에서 my-events와 동일하게 'elif "date" in start_raw: ... else: continue' 가드 추가, 또는 항목 파싱을 try/except로 감싸 skip.

### [P3] cal-2 — consent 토글이 free-slots 캐시를 무효화하지 않아 최대 30초 stale 분자/분모
`data-integrity` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/users.py:126-150; backend/app/api/routes/calendar.py:341-361,535-553`
- **메커니즘**: update_consent(users.py:138)가 calendar_consent를 변경하지만 해당 유저가 속한 방들의 invalidate_free_slots_cache를 호출하지 않음. free-slots는 TTL 30s 캐시(calendar.py:546 ex=30)를 사용하므로, 멤버 가입/탈퇴(rooms.py:275,778)는 무효화되지만 consent on/off는 무효화 누락 → 해당 방 캘린더 가용 현황(available/busy/unconnected 분류)이 최대 30초 옛 상태 유지.
- **근거**: invalidate_free_slots_cache 호출처는 rooms.py:275(가입)·778(탈퇴) 2곳뿐(grep 확인). users.py update_consent에는 호출 없음. consenting 필터(calendar.py:451-454)가 calendar_consent에 직접 의존.
- **영향**: 유저가 캘린더 동의를 끄거나 켜도 같은 방의 다른 멤버 화면에서 최대 30초간 옛 가용/미연동 분류가 보임. TTL로 자가 치유되는 경미한 열화.
- **제안 수정**: update_consent에서 해당 유저의 RoomMember 방 목록을 조회해 각 room_id로 invalidate_free_slots_cache 호출(graceful).

### [P3] reco-2 — nearby-places는 x/y 없이 search_keyword 호출 → distance_label이 항상 없음
`correctness` · conf 7/10 · 미검증(P2/P3)

- **위치**: `backend/app/api/routes/recommendations.py:223-242; backend/app/services/kakao_maps.py:85-90`
- **메커니즘**: nearby-places는 query=f"{home} {category}"만 전달하고 좌표(x,y)를 넘기지 않음(line 225). kakao_maps.search_keyword는 x,y가 둘 다 있을 때만 params에 좌표를 넣고(85-88), Kakao는 좌표 없이 keyword 검색하면 documents의 distance 필드를 반환하지 않음. 따라서 doc.get("distance")는 항상 None → distance_label 항상 None(line 235).
- **근거**: recommendations.py:225 search_keyword(query) 좌표 인자 없음. kakao_maps.py:86-88 if x and y일 때만 좌표 세팅. RecommendedPlace.distance_label(line 177) Optional이고 235에서 doc.get('distance') or None.
- **영향**: 홈 화면 '근처 장소' 추천 카드에서 거리 라벨이 노출되지 않음(기능 누락/열화). 크래시 아님.
- **제안 수정**: home_base를 search_address로 좌표 변환 후 x/y를 search_keyword에 전달, 또는 거리 미표시를 의도된 동작으로 문서화.
