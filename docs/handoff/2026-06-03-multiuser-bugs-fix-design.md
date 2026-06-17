# 멀티유저 버그 수정 설계도 (2026-06-03)

대상 버그: `docs/handoff/2026-06-03-multiuser-bugs-report.md` 5건 (근본원인 확정 완료).
브랜치: `fix/speaker-attribution-concurrency`.
원칙: **최소 diff, 근본 원인만, 기존 보호 가드 보존, 회귀 테스트 동반.** 코드 미착수 — 본 문서는 설계만.

업데이트: 실행자가 바로 따라갈 상세 구현 계획은 `docs/superpowers/plans/2026-06-03-multiuser-time-place-fixes.md`에 추가했다. 이 handoff 문서는 요약본으로 유지하고, 구현 시에는 해당 계획 문서의 acceptance criteria와 테스트 명령을 우선한다.

---

## 0. 구현 순서 & 의존성

```
[버그2 단일실행 락]  ──선행──▶  [버그1 확정신호 broadcast]   (버그2가 N중 실행을 막아야
        │                                                   버그1 신호도 1회만 깔끔히 발화)
        ▼
[버그3 지명추출]   (독립, 병행 가능 — places.py 단일 함수)
        ▼
[버그5 location-first 카드 shared]  (독립, 1줄)
        ▼
[버그4 meeting 재사용]  (선택, 별도 검토 — 데모 핵심 동선 아님)
```

- 버그 2 → 1 순서 권장: 버그2를 먼저 고쳐 "확정 1회 실행"을 보장한 뒤 버그1 확정 신호를 얹어야 신호 중복이 없다.
- 버그 3·5는 독립이라 언제 해도 됨.
- 버그 4는 blast radius·회귀 위험이 상대적으로 커 데모 후로 미뤄도 무방(별도 발화 케이스 한정).

권장 커밋 분리: 버그2 / 버그1 / 버그3 / 버그5 각각 1커밋 (bisect 용이). 버그4는 별도 PR 후보.

---

## 버그 2 — 확정 트리거 N중 실행 방지 (per-snapshot 소비락)

### 목표
호스트 확정(`all_members_selected`) 시 연결 인원 수만큼 파이프라인이 도는 것을 **정확히 1회**로. 기존 "확정 묵음 폐기 방지"(NX 우회 도입 사유)는 유지.

### 변경 파일·함수
- `backend/app/api/ws/social.py` — `publish_schedule_auto_trigger`: trigger payload에 `snapshot_hash` 추가.
- `backend/app/api/ws/agent.py` — `_process_auto_triggers`: `is_user_explicit_confirm` 분기를 blanket bypass → **per-snapshot NX 소비락**으로 교체.

### 변경 내용

**social.py** (현재 `publish_schedule_auto_trigger` payload, line ~154):
```python
# before
trigger_payload = json.dumps({
    "type": "ai_auto_trigger",
    "intent": "meeting_schedule",
    "confidence": 1.0,
    "content": "모두 시간대를 선택했어요. 일정을 조율해볼게요!",
    "trigger_reason": "all_members_selected",
    "manual_chosen_time": manual_chosen_time,
}, ensure_ascii=False)
# after — snapshot_hash 추가 (소비측 dedupe 키로 사용)
trigger_payload = json.dumps({
    ...,
    "manual_chosen_time": manual_chosen_time,
    "snapshot_hash": snapshot_hash,   # ← 추가
}, ensure_ascii=False)
```

**agent.py** (`_process_auto_triggers`, 현재 line ~867-891):
```python
# before
nx_key = f"nx_autotrigger:{room_id}"
acquired = False
if is_user_explicit_confirm:
    acquired = True                       # ← N중 실행 원인: blanket bypass
elif r is not None:
    acquired = bool(await r.set(nx_key, str(user_id_check), nx=True, ex=int(_AUTO_TRIGGER_DEBOUNCE_SECONDS)))

# after
acquired = False
if is_user_explicit_confirm:
    # 호스트 확정도 "정확히 1회"만. stalemate용 nx_autotrigger(60s)와 키를 분리해
    # 확정 묵음 폐기 회귀 없이 N중 실행만 차단.
    snap = trigger.get("snapshot_hash") or "nosnap"
    consume_key = f"nx_confirm_consume:{room_id}:{snap}"
    if r is not None:
        try:
            acquired = bool(await r.set(consume_key, str(user_id_check), nx=True, ex=300))
        except Exception:
            logger.warning("confirm consume lock failed", exc_info=True)
            acquired = False
    else:
        acquired = _local_confirm_consume_lock.try_acquire(consume_key, ttl=300)
elif r is not None:
    nx_key = f"nx_autotrigger:{room_id}"
    acquired = bool(await r.set(nx_key, str(user_id_check), nx=True, ex=int(_AUTO_TRIGGER_DEBOUNCE_SECONDS)))
```

### 엣지 / 리스크
- snapshot_hash가 없는(구) payload → `"nosnap"` 키. 같은 publish의 N 소비자는 동일 → 1회 보장 유지. 다만 서로 다른 확정이 같은 키를 잠깐 공유할 위험은 TTL 300s 내 동일 room 재확정뿐 → 데모 시나리오상 무해(재확정은 새 snapshot).
- producer-side 멱등(`schedule_auto_trigger_fired:{room}:{snapshot}`, social.py:148)은 그대로 → 이중 안전.
- Redis 부재 로컬 개발은 process-local fallback lock으로 같은 process 내 N중 실행을 막는다. 운영 Redis 장애 시에는 room-wide 보장이 약해지므로 로그 경고를 남긴다.
- `_ensure_pending_meeting_id` race는 단일 실행으로 자연 해소(확정 경로). direct_request 다발 race는 `_room_card_generating` 플래그가 별도 보호(범위 밖).

### 검증
- 2-브라우저(호스트+멤버) qa-runtime: 확정 1회 → `MeetingSchedule` pending/confirmed **단일 row** 확인(중복 meeting_id 카드 0).
- 백엔드 로그: `[AUTO_TRIGGER] task spawned`가 확정당 **1회**만 (이전엔 연결수만큼).

---

## 버그 1 — 확정 후 멤버 화면 추천 카드 잔존

### 목표
호스트가 TimeBar로 확정하면 **모든 멤버 화면**도 즉시 확정 단계로 전환되어 옛 vote 카드가 사라지게.

### 핵심 설계 결정
멤버가 `timeConfirmed`로 가는 길이 현재 "maedeup_card 도착 + scheduleConsensus 해제" 두 조건의 타이밍 의존인데, **명시적 확정 신호**를 social 채널로 쏴 멤버가 직접 phase를 advance하게 한다(maedeup_card 지연·유실에도 강건). audit 문서 후속후보 ①과 동일 방향.

### 변경 파일·함수
- `backend/app/api/routes/rooms.py` — `schedule_confirm`: host/snapshot 검증 성공 시 social 채널에 `schedule_finalized` publish.
- `backend/app/api/ws/social.py` — `publish_schedule_finalized`: `snapshot_hash`, `host_user_id`, `manual_chosen_time`, `triggered` 포함.
- `frontend/src/hooks/useSocialWebSocket.ts` — `schedule_finalized` 핸들러 추가(타입가드 + `lastScheduleFinalized` set + `setScheduleConsensus(null)`).
- `frontend/src/components/meeting/ChatPane.tsx` — `lastScheduleFinalized` → `setInfoPanePhase("timeConfirmed")` 브릿지.
- (Context 액션 추가 불필요 — 기존 `setInfoPanePhase` 재사용. `timeConfirmed` 진입 시 MeetingContext가 scheduleConsensus도 정리(`MeetingContext.tsx:419`).)

### 변경 내용

**rooms.py** (`schedule_confirm`, line ~601):
```python
triggered = await publish_schedule_auto_trigger(
    redis, room_pk=room_id, snapshot_hash=body.snapshot_hash,
    manual_chosen_time=manual_chosen_time,
)
# after — host/snapshot 검증이 성공한 확정 요청이면 모든 멤버에게 확정 신호.
# triggered=False여도 이미 같은 snapshot trigger가 발화된 중복 클릭일 수 있으므로
# UI phase는 room-wide로 정리한다.
await publish_schedule_finalized(
    redis,
    room_pk=room_id,
    snapshot_hash=body.snapshot_hash,
    host_user_id=current_user.id,
    manual_chosen_time=manual_chosen_time,
    triggered=triggered,
)
return ScheduleConfirmResponse(triggered=triggered, snapshot_hash=body.snapshot_hash)
```

**useSocialWebSocket.ts** (onmessage 핸들러에 추가, `meeting_confirmed` 분기 근처 ~line 596):
```typescript
// 타입가드
function isScheduleFinalizedPayload(d: unknown): d is ScheduleFinalizedPayload {
  return !!d && typeof d === "object" && (d as any).type === "schedule_finalized";
}
// state
const [lastScheduleFinalized, setLastScheduleFinalized] = useState<ScheduleFinalizedPayload | null>(null);
// onmessage
if (isScheduleFinalizedPayload(data)) {
  setScheduleConsensus(null);          // 멤버 합의 배너/대기 placeholder 해제
  setLastScheduleFinalized(data);      // ChatPane이 phase advance 트리거
  return;
}
// return 객체에 lastScheduleFinalized 추가
```

**ChatPane.tsx** (브릿지 useEffect 추가):
```typescript
const setInfoPanePhase = meetingContext?.setInfoPanePhase;
// ...
useEffect(() => {
  if (!lastScheduleFinalized) return;
  setInfoPanePhase?.("timeConfirmed");
}, [lastScheduleFinalized, setInfoPanePhase]);
```

### 동작 흐름 (수정 후, 멤버 관점)
```
호스트 확정 → schedule-confirm → (triggered=True)
  → social: schedule_finalized  → 멤버 즉시 scheduleConsensus=null + infoPanePhase=timeConfirmed
                                  → vote_card 숨김 조건(timeConfirmed) 충족 → 카드 사라짐 ✅
  → agent: maedeup_card(단일, 버그2 수정 후) → 멤버 최종 카드 렌더
```

### 엣지 / 리스크
- 호스트는 본인 클릭으로 이미 `timeConfirmed` → schedule_finalized 수신해도 `setInfoPanePhase("timeConfirmed")` no-op(동일 phase 무시, `MeetingContext.tsx:403`).
- TimeBar 선택 중인 멤버가 강제 advance → TimeBar unmount. **의도된 동작**(호스트 확정 = 선택 종료).
- `🔧 직접 조율`(manual mode, `InfoPane.tsx:478`)도 schedule-confirm 호출 → 동일 신호 발화 → 일관 처리.
- 멱등: `triggered` False(중복 확정)여도 `schedule_finalized`는 발화 가능. 클라이언트의 `setInfoPanePhase("timeConfirmed")`가 no-op 처리하므로 UI 정리 신호를 잃지 않는 쪽이 안전.
- forward-only: setInfoPanePhase는 뒤로 안 감 → 늦은 신호가 placeConfirmed/done을 되돌리지 않음.

### 검증
- 2-브라우저: 호스트 확정 직후 **멤버 화면 vote 카드 사라짐 + 최종 카드 표시** 동시 확인.
- 콘솔 에러 0, 새로고침 후에도 timeConfirmed 유지(별도: refresh 복원은 기존 백로그).

---

## 버그 3 — "천안 신부동" 세부 지명 손실

### 목표
`quick_classify`가 "천안 신부동 추천해줘"를 place로 잡고, `_extract_korean_place_keyword`가 광역 지명만 반환해 세부 동/역을 버리는 것을 고쳐, "천안 신부동" → `천안 신부동`, "강남역 카페" → `강남역` 보존.

### 변경 파일·함수
- `backend/app/services/quick_classify.py` — 지명 suffix + 추천/request verb 패턴 추가.
- `backend/app/services/pipeline/helpers/places.py` — `_extract_korean_place_keyword`(line 187-201).
  (검색 쿼리 "맛집" 기본은 `entity.py:631-632` / `places.py:261`에 이미 있음 — 추가 변경 불필요.)

### 변경 내용
```python
# before (현재): _WELL_KNOWN_PLACES 먼저 → 첫 매칭 즉시 반환 → 세부 지명 손실
for place in _WELL_KNOWN_PLACES:
    if place in text:
        return place
matches = _KOREAN_PLACE_PATTERN.findall(text)
if matches:
    return max(matches, key=len)
# ... 자유 텍스트 fallback

# after: 구체 패턴 + 광역 지명을 함께 보고 더 구체적/복합으로
def _extract_korean_place_keyword(text: str) -> str | None:
    if not text:
        return None
    pattern_matches = _KOREAN_PLACE_PATTERN.findall(text)
    specific = max(pattern_matches, key=len) if pattern_matches else None
    wellknown = next((p for p in _WELL_KNOWN_PLACES if p in text), None)

    if wellknown and specific:
        # "강남역"처럼 구체 매칭이 광역명을 이미 포함 → 구체만
        if wellknown in specific:
            return specific
        # "천안 신부동"처럼 도시 + 별개 동 → 복합 보존
        return f"{wellknown} {specific}"
    if specific:
        return specific
    if wellknown:
        return wellknown
    # 3. 자유 텍스트 fallback (기존 그대로 유지)
    cleaned = re.sub(... , "", text).strip()
    if 3 <= len(cleaned) <= 20:
        return cleaned
    return None
```

### 엣지 / 리스크
- "강남"·"홍대" 단독(세부 패턴 없음) → `wellknown` 반환. **기존 동작 보존**(무회귀).
- "강남역" → `specific="강남역"`, `wellknown="강남" in "강남역"` → "강남역" 반환(개선).
- "천안 신부동" → "천안 신부동"(개선). Kakao "천안 신부동 맛집" 검색.
- "신부동"만(도시 없음) → `specific="신부동"` 반환 → Kakao "신부동 맛집"(전국 동명이동 위험 있으나 입력 한계).
- "천안 터미널"(터미널=패턴 비매칭) → `wellknown="천안"` 반환(현재와 동일, 무회귀). 추가 개선 여지는 별도.
- 다중 well-known("강남 홍대") → 첫 매칭 "강남" + 세부 없음 → "강남". 입력 모호, 수용.

### 검증
- 단위 재현(컨테이너): `_extract_korean_place_keyword` 케이스 표
  - `천안 신부동 추천` → `천안 신부동`
  - `강남역 카페` → `강남역`
  - `을지로입구 술집` → `을지로입구` 또는 `을지로`(패턴 한계 — 둘 중 무엇이든 현재보다 구체)
  - `강남` → `강남` (무회귀)
  - `홍대에서 보자` → `홍대` (무회귀)
- 회귀: `entity.py` place fast-path가 새 place_hint로 Kakao 검색 → 신부동 결과 반환 확인(라이브 1회).

---

## 버그 5 — location-first 장소 카드 private 발행

### 목표
시간 없이 장소만 먼저 묻는 direct_request의 장소 카드도 **shared**로 발행(카드 정책: 항상 공유).

### 변경 파일·함수
- `backend/app/api/ws/agent.py` — direct_request의 `is_location_first and not date_hint` 분기(line ~1296-1310).

### 변경 내용
```python
# before
if result.get("is_location_first") and not result.get("date_hint"):
    place_recommendation_payload = result.get("place_recommendation_payload")
    if place_recommendation_payload:
        await _publish_agent_message(
            r, user_channel,   # ← 요청자만
            json.dumps({"type": "place_recommendation", **place_recommendation_payload}, ensure_ascii=False),
        )
    continue
# after — 카드는 항상 shared (정책 일관)
        await _publish_agent_message(
            r, shared_channel,   # ← 방 전체
            json.dumps({"type": "place_recommendation", **place_recommendation_payload}, ensure_ascii=False),
        )
```

### 엣지 / 리스크
- private 토글로 입력한 경우에도 카드는 shared가 정책(`AiAssistantPane` 주석·`agent.py:1053`과 일치). 입력 에코는 그대로 private 유지, 카드만 shared.
- "추천 안 됨"이 **요청자 본인 화면 기준**이었다면 이 변경은 버그3과 별개(요청자는 원래 봐야 정상). 다중 동기화 일관성 개선.

### 검증
- 2-브라우저: 멤버 A가 "강남 맛집 추천"(시간 미정) → 멤버 B 화면에도 장소 카드 표시.

---

## 버그 4 — 시간 확정 후 별도 장소 요청이 새 meeting 생성 (선택/별도)

### 목표
시간이 confirmed된 meeting이 있는데 분리된 장소 발화가 **새 pending meeting**을 만드는 것을 막고 기존 confirmed에 붙이기. 단, room의 "최근 confirmed"를 맹목적으로 조회하면 오래된 모임에 장소가 붙을 수 있으므로 프론트가 현재 meeting context를 명시적으로 보내는 방식을 우선한다.

### 변경 파일·함수
- `frontend/src/hooks/useAgentWebSocket.ts` — AI user message payload에 optional `context.meeting_id` 추가.
- `frontend/src/components/meeting/AiAssistantPane.tsx` — `MeetingContext.confirmedMeetingId`를 AI 요청 context로 전달.
- `backend/app/api/ws/agent.py` — `context.meeting_id`를 현재 room/status 기준으로 검증 후 pipeline state에 저장.
- `backend/app/services/pipeline/state.py` — `context_meeting_id` optional field 추가.
- `backend/app/services/pipeline/nodes/place.py` — `place_recommendation` 진입부 meeting_id 결정(line ~197).

### 변경 내용 (스케치)
```python
meeting_id = _card_payload_meeting_id(state.get("vote_card_payload"))
if meeting_id is None:
    # 별도 장소 발화: 프론트가 보낸 현재 확정/진행 meeting을 우선 재사용.
    meeting_id = state.get("context_meeting_id")
if meeting_id is None:
    meeting_id = await _ensure_pending_meeting_id(state, title)
```

### 엣지 / 리스크 / 보류 사유
- 정상 합의-확정 경로는 이미 한 meeting으로 수렴(검증됨) — 이 버그는 **완전 분리 발화**에서만. 데모 핵심 동선 아님.
- "room 최근 confirmed" DB 조회는 잘못 매칭 시 엉뚱한 confirmed에 장소를 덮어쓸 위험이 크므로 기본 설계에서 제외. 명시 context id가 없을 때만 기존 pending 생성 fallback을 유지.
- **데모 전 필수 아님.** 데모 후 별도 PR 권장.

### 검증
- 시간 확정 meeting A 존재 상태에서 "천안 신부동 추천" → 장소가 A에 PATCH(새 B 미생성) 확인.

---

## 통합 리스크 & 롤백

- **데모 경로 영향:** 버그1·2 수정은 ACT3(시간 확정) 경로를 직접 건드림 → 머지 후 **데스크탑 ACT1~5 스모크 필수**(date_classify·agent.py 데모 경로 공유).
- **버그3:** `_extract_korean_place_keyword`는 장소 추천 전 경로 공통 → 회귀 표로 무회귀 확인.
- **롤백 단위:** 커밋 분리(버그2/1/3/5)라 문제 시 해당 커밋만 revert.
- **프론트 리빌드:** 버그1은 프론트 변경 → `docker compose up -d --build frontend` (리뷰 중 리빌드 금지, 최종 1회).

## 회귀 테스트 체크리스트 (수정 후 일괄)
- [ ] 2-브라우저 ACT3: 호스트 확정 → 멤버 카드 소멸 + 단일 최종 카드 (버그1·2)
- [ ] `MeetingSchedule` 단일 row, 중복 meeting_id 카드 0 (버그2)
- [ ] `_extract_korean_place_keyword` 케이스 표 PASS (버그3)
- [ ] "강남"·"홍대" 단독 무회귀 (버그3)
- [ ] 멤버가 안 건 장소 발화 카드가 타 멤버에 표시 (버그5)
- [ ] 데스크탑 ACT1~5 데모 스모크 GREEN (통합)

## 관련 문서
- `docs/handoff/2026-06-03-multiuser-bugs-report.md` — 버그 5건 근본원인(통합·검증본)
- `docs/handoff/2026-06-03-time-place-issue-audit.md` — 직전 라운드 정적 분석 원본
- `docs/superpowers/plans/2026-06-03-multiuser-time-place-fixes.md` — 구현 작업 순서, acceptance criteria, 테스트 명령
