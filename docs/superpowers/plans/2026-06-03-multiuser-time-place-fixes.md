# Multiuser Time And Place Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the room-wide time/place coordination bugs found on 2026-06-03: stale vote cards after host TimeBar confirmation, duplicate and inconsistent AI time recommendations, incomplete Korean place extraction for "천안 신부동", and place cards attaching to the wrong or newly-created meeting.

**Architecture:** Keep Social WebSocket responsible for room coordination state, Agent WebSocket responsible for AI messages/cards, Redis NX locks responsible for room/snapshot idempotency, and pipeline helper functions responsible for one canonical place keyword.

**Tech Stack:** FastAPI, Redis pub/sub, SQLModel, Next.js 14, React Context, Vitest, pytest.

---

## Implementation Status

Implemented on 2026-06-03 in branch `fix/speaker-attribution-concurrency`.

- Done: confirm-only `nx_confirm_consume:{room}:{snapshot}` lock while preserving stalemate `nx_autotrigger:{room}` debounce.
- Done: `schedule_finalized` social event and frontend phase bridge.
- Done: `천안 신부동` composite place extraction and narrow regex fast path for no-category wording.
- Done: frontend AI message context, backend context meeting-id validation, and place recommendation meeting-id reuse.
- Done: location-first place cards publish to the shared agent channel.
- Verification passed:
  - `cd backend; pytest tests/test_agent_autotrigger_idempotency.py tests/test_places_helper.py tests/test_quick_classify.py tests/test_place_meeting_context.py -q`
  - `cd backend; python -m py_compile app\api\ws\agent.py`
  - `cd backend; python -m compileall app`
  - `cd frontend; npm test -- MeetingContext.test.tsx`
  - `cd frontend; npm test`
  - `cd frontend; npx tsc --noEmit`
- Known unrelated verification issue:
  - `cd backend; pytest -q` currently fails 6 existing `tests/unit/test_finalization_reason.py` tests because `app.services.finalization_reason` does not expose the `call_gemini` attribute those tests patch. The targeted tests added for this work pass.

## Source Reports

- Bug report: `docs/handoff/2026-06-03-multiuser-bugs-report.md`
- Audit notes: `docs/handoff/2026-06-03-time-place-issue-audit.md`
- Handoff design summary: `docs/handoff/2026-06-03-multiuser-bugs-fix-design.md`

## Verified Corrections To The Report

The report is directionally correct, but the place bug has two separate cases:

- `천안 신부동 추천해줘` is not caught by the deterministic regex fast path. It falls through to the Gemini fallback, so it can return `place` when Gemini responds well and `general` when Gemini times out or answers unexpectedly. The bug is flakiness, not deterministic `general`.
- `장소 천안 신부동 추천해달라` and `천안 신부동 맛집 추천해줘` are classified as `place`, but `_extract_korean_place_keyword()` returns only `천안`, dropping `신부동`.

When the place path does run, the current place search is therefore more likely to become `천안 맛집` than the report's stated `천안 신부동 단독` query.

## Design Decisions

1. Do not overload `meeting_confirmed` for TimeBar host finalization.

   `POST /api/v1/rooms/{room_id}/schedule-confirm` fires before a final `MeetingSchedule` may exist, while `meeting_confirmed` already means a real meeting with `meeting_id`, `proposal_id`, `scheduled_at`, and `end_at`. Add a lightweight `schedule_finalized` social event instead.

2. Idempotency must happen at the shared room/snapshot boundary.

   The current `all_members_selected` path intentionally bypasses the Redis NX lock in `backend/app/api/ws/agent.py`, so every connected websocket can run the pipeline. Include `snapshot_hash` in the trigger payload and require a Redis NX consume lock even for host-confirmed triggers.

   Keep the existing `nx_autotrigger:{room_id}` 60 second room-level debounce for non-confirm auto triggers. Do not replace it with a per-message identity key, because that would weaken stalemate debounce and let multiple nearby stalemate messages trigger multiple AI interventions.

3. The frontend should hide stale vote cards by advancing shared phase, not by relying only on card deletion.

   Other users may still have an old `vote_card` in `useAgentWebSocket.cardsByMeetingId`. Advancing `MeetingContext.infoPanePhase` to `timeConfirmed` is already the render gate used by `AiAssistantPane`, and `setInfoPanePhase("timeConfirmed")` already clears stale `scheduleConsensus`.

4. Place requests after time confirmation need explicit meeting context.

   Blindly selecting the latest confirmed meeting in a room can attach a new request to an old meeting. Send the frontend's current `confirmedMeetingId` with AI messages, validate it on the backend, then use it before creating a new pending meeting.

5. Place recommendation cards are room-shared artifacts.

   The existing direct location-first branch publishes place cards to `user_channel`. That conflicts with the current product rule that cards should be shared across the room once the AI has produced a recommendation.

---

## Implementation Tasks

### 1. Add Room-Wide `schedule_finalized` Event

- [ ] In `backend/app/api/ws/social.py`, add a publisher:

  ```python
  async def publish_schedule_finalized(
      redis,
      *,
      room_pk: int,
      snapshot_hash: str,
      host_user_id: int,
      manual_chosen_time: dict[str, Any] | None = None,
      triggered: bool,
  ) -> None:
      ...
  ```

- [ ] Publish to `social:{room_pk}` with this payload shape:

  ```json
  {
    "type": "schedule_finalized",
    "room_id": 1,
    "snapshot_hash": "hash",
    "host_user_id": 12,
    "manual_chosen_time": null,
    "triggered": true
  }
  ```

- [ ] Use a short Redis de-dupe key such as `schedule_finalized:{room_pk}:{snapshot_hash}` with a 5 minute TTL, so double-clicks do not spam clients.

- [ ] In `backend/app/api/routes/rooms.py`, call `publish_schedule_finalized()` after `schedule-confirm` validates the host/snapshot and calls `publish_schedule_auto_trigger()`.

Acceptance criteria:

- Invalid snapshot or non-host request publishes nothing.
- A valid host request publishes `schedule_finalized` even if the auto-trigger was already fired for that snapshot.
- The route response remains backward compatible: `{ triggered, snapshot_hash }`.

### 2. Consume `schedule_finalized` In Frontend Shared State

- [ ] In `frontend/src/hooks/useSocialWebSocket.ts`, add:

  ```ts
  export interface ScheduleFinalizedPayload {
    type: "schedule_finalized";
    room_id: number;
    snapshot_hash: string;
    host_user_id: number;
    manual_chosen_time?: unknown;
    triggered?: boolean;
  }
  ```

- [ ] Add a validator `isScheduleFinalizedPayload()`.

- [ ] Add hook state `lastScheduleFinalized` and return it from `useSocialWebSocket()`.

- [ ] In the websocket `onmessage` handler, when `schedule_finalized` arrives:

  ```ts
  setScheduleConsensus(null);
  setLastScheduleFinalized(data);
  ```

- [ ] In `frontend/src/components/meeting/ChatPane.tsx`, destructure `lastScheduleFinalized` from `useSocialWebSocket()`.

- [ ] Bridge it to `MeetingContext`:

  ```ts
  const setInfoPanePhase = meetingContext?.setInfoPanePhase;

  useEffect(() => {
    if (!lastScheduleFinalized) return;
    setInfoPanePhase?.("timeConfirmed");
  }, [lastScheduleFinalized, setInfoPanePhase]);
  ```

- [ ] Keep the existing `setScheduleConsensus(scheduleConsensus)` bridge unchanged. The hook state becoming `null` is what clears the consensus guard for all clients.

Acceptance criteria:

- Host TimeBar confirmation makes member clients leave the vote-card phase without waiting for a `maedeup_card`.
- `AiAssistantPane` no longer blocks phase advance due to stale `scheduleConsensusCtx`.
- Existing `meeting_confirmed` success banner behavior remains unchanged.

### 3. Restore Room/Snapshot Idempotency For Auto Triggers

- [ ] In `backend/app/api/ws/social.py`, include `snapshot_hash` in the `ai_auto_trigger` payload created by `publish_schedule_auto_trigger()`.

- [ ] Keep or add the producer-side NX key:

  ```text
  schedule_auto_trigger_fired:{room_pk}:{snapshot_hash}
  ```

- [ ] In `backend/app/api/ws/agent.py`, remove only the `all_members_selected` blanket bypass that sets `acquired = True`.

- [ ] Add a small pure helper in `backend/app/api/ws/agent.py` so the lock policy is unit-testable:

  ```python
  def build_auto_trigger_lock_key(
      *,
      room_id: int | str,
      trigger_reason: str,
      snapshot_hash: str | None = None,
  ) -> str:
      if trigger_reason == "all_members_selected":
          return f"nx_confirm_consume:{room_id}:{snapshot_hash or 'nosnap'}"
      return f"nx_autotrigger:{room_id}"
  ```

- [ ] Do not change the existing non-confirm debounce path:

  ```python
  nx_key = build_auto_trigger_lock_key(
      room_id=str(room_id),
      trigger_reason=trigger_reason_early,
      snapshot_hash=None,
  )
  acquired = bool(await r.set(nx_key, str(user_id_check), nx=True, ex=int(_AUTO_TRIGGER_DEBOUNCE_SECONDS)))
  ```

- [ ] Add a separate confirm-only consume lock for `trigger_reason == "all_members_selected"`:

  ```python
  snapshot_hash = trigger.get("snapshot_hash")
  consume_key = build_auto_trigger_lock_key(
      room_id=str(room_id),
      trigger_reason="all_members_selected",
      snapshot_hash=snapshot_hash if isinstance(snapshot_hash, str) else None,
  )

  if r is not None:
      try:
          acquired = bool(await r.set(consume_key, str(user_id_check), nx=True, ex=300))
      except Exception:
          logger.warning("confirm consume lock failed room=%s key=%s", room_id, consume_key, exc_info=True)
          acquired = False
  else:
      acquired = _try_local_confirm_consume_lock(consume_key, ttl_seconds=300)
  ```

- [ ] Implement `_try_local_confirm_consume_lock()` as a process-local fallback only for Redis-unavailable local development:

  ```python
  _LOCAL_CONFIRM_CONSUME_LOCKS: dict[str, float] = {}

  def _try_local_confirm_consume_lock(key: str, *, ttl_seconds: int) -> bool:
      now = time.monotonic()
      expired = [lock_key for lock_key, expires_at in _LOCAL_CONFIRM_CONSUME_LOCKS.items() if expires_at <= now]
      for lock_key in expired:
          _LOCAL_CONFIRM_CONSUME_LOCKS.pop(lock_key, None)
      if key in _LOCAL_CONFIRM_CONSUME_LOCKS:
          return False
      _LOCAL_CONFIRM_CONSUME_LOCKS[key] = now + ttl_seconds
      return True
  ```

- [ ] Make `_run_auto_trigger_pipeline()` receive and preserve `snapshot_hash` in state/log context for debugging.

Acceptance criteria:

- With N connected users, one `all_members_selected` event runs the AI pipeline exactly once.
- Stalemate and other non-confirm auto triggers still use the existing room-level `nx_autotrigger:{room_id}` debounce.
- All clients receive the same shared `vote_card` or `maedeup_card`.
- Host manual chosen time is honored by the one winning run.

### 4. Fix Korean Place Intent Classification

- [ ] Treat this as a secondary stabilization task after Task 5. The confirmed "천안 신부동" search-quality failure is primarily the extractor dropping `신부동`; this classifier task removes Gemini fallback flakiness for the no-category wording.

- [ ] In `backend/app/services/quick_classify.py`, add a narrow regex branch for known Korean place prefix plus a specific place suffix plus recommendation/request verbs. Do not add a generic suffix-only rule such as `[가-힣]+(?:동|구|역|로|길|리|면|읍|시|군).*추천`, because it misclassifies ordinary words like `친구 추천해줘`, `연구 자료 찾아줘`, and `도구 추천`.

  Suggested pattern:

  ```python
  _KNOWN_PLACE_PREFIX_RE = re.compile(
      r"(서울|부산|대구|인천|광주|대전|울산|세종|"
      r"수원|성남|고양|용인|부천|안산|안양|남양주|화성|평택|의정부|시흥|파주|김포|광명|군포|하남|"
      r"천안|아산|청주|충주|전주|군산|익산|목포|여수|순천|포항|경주|구미|창원|김해|진주|양산|"
      r"강남|홍대|신촌|건대|성수|잠실|이태원|명동|종로|을지로|여의도|판교)"
      r"\s*[가-힣]{1,12}(?:동|구|역|로|길|리|면|읍|시|군)"
  )
  _PLACE_REQUEST_VERB_RE = re.compile(r"(추천|찾|알려|보여|골라|어때|가자|갈까)")
  ```

- [ ] Treat `known_place_prefix + specific_suffix + request_verb` as `place_match`.

  ```python
  composite_place_match = bool(
      _KNOWN_PLACE_PREFIX_RE.search(text or "")
      and _PLACE_REQUEST_VERB_RE.search(text or "")
  )
  place_match = bool(_PLACE_RE.search(text or "")) or composite_place_match
  ```

- [ ] Keep the rule intentionally narrow. If the project later needs suffix-only recognition, add it behind a blocklist and tests for non-place words first.

- [ ] Preserve current schedule/place combined-intent behavior. If schedule signals and place signals are both present, keep the existing combined or higher-level branch instead of forcing pure place.

Acceptance criteria:

- `quick_classify("천안 신부동 추천해줘")` returns `kind == "place"`.
- `quick_classify("친구 추천해줘")` returns `kind == "general"` or remains Gemini-classified; it must not be forced to regex `place`.
- `quick_classify("연구 자료 찾아줘")` returns `kind == "general"` or remains Gemini-classified; it must not be forced to regex `place`.
- `quick_classify("도구 추천해줘")` returns `kind == "general"` or remains Gemini-classified; it must not be forced to regex `place`.
- Existing category-based cases such as `맛집 추천해줘`, `카페 찾아줘`, and `장소 추천해줘` still return `place`.
- Date-only or time-only scheduling messages are not misclassified as place.

### 5. Preserve Specific Korean Place Keywords

- [ ] In `backend/app/services/pipeline/helpers/places.py`, change `_extract_korean_place_keyword()` to prefer composite known-place plus specific suffix matches before returning a known city/district by itself.

  Suggested algorithm:

  ```python
  known_hits = [(place, text.find(place)) for place in _WELL_KNOWN_PLACES if place in text]
  suffix_hits = [(m.group(1), m.start(1)) for m in _KOREAN_PLACE_PATTERN.finditer(text)]

  for known, known_pos in sorted(known_hits, key=lambda item: item[1]):
      for suffix, suffix_pos in sorted(suffix_hits, key=lambda item: item[1]):
          gap = suffix_pos - (known_pos + len(known))
          if 0 <= gap <= 4 and suffix != known:
              return f"{known} {suffix}"

  if suffix_hits:
      return best_suffix_hit
  if known_hits:
      return first_known_hit

  # Preserve the existing free-text fallback below this point.
  # Do not replace it with `return None`; otherwise unregistered place strings regress.
  ```

- [ ] Define `best_suffix_hit` deterministically. Prefer the earliest hit, and use longest text only to break ties.

- [ ] Do not remove `_WELL_KNOWN_PLACES`; it still handles inputs like `홍대 맛집` where no suffix appears.

- [ ] Preserve the current free-text fallback in `_extract_korean_place_keyword()` for unregistered place strings. The composite extraction must be inserted before that fallback, not replace it.

Acceptance criteria:

- `_extract_korean_place_keyword("천안 신부동 추천해줘") == "천안 신부동"`.
- `_extract_korean_place_keyword("장소 천안 신부동 추천해달라") == "천안 신부동"`.
- `_extract_korean_place_keyword("천안 신부동 맛집 추천해줘") == "천안 신부동"`.
- `_extract_korean_place_keyword("홍대 맛집") == "홍대"`.
- `_extract_korean_place_keyword("강남역 카페") == "강남역"`.
- Existing free-text fallback cases that do not match `_WELL_KNOWN_PLACES` or `_KOREAN_PLACE_PATTERN` keep their current behavior.

### 6. Send Current Meeting Context With AI Requests

- [ ] In `frontend/src/hooks/useAgentWebSocket.ts`, extend `sendMessage()` to accept optional context:

  ```ts
  interface AgentMessageContext {
    meeting_id?: number | null;
    info_pane_phase?: string | null;
  }

  const sendMessage = useCallback(
    (
      content: string,
      visibility: "public" | "private" = "public",
      context?: AgentMessageContext,
    ) => {
      ...
      ws.send(JSON.stringify({ role: "user", content, sender, visibility, context }));
    },
    [sender],
  );
  ```

- [ ] In `frontend/src/components/meeting/AiAssistantPane.tsx`, wrap the hook's raw sender so all manual AI messages include:

  ```ts
  {
    meeting_id: meetingContext?.confirmedMeetingId ?? null,
    info_pane_phase: meetingContext?.infoPanePhase ?? null
  }
  ```

- [ ] Register the wrapped sender through `setSendMessageToAi`, so messages sent from `CalendarPane` or other bridged components carry the same context.

- [ ] In `backend/app/api/ws/agent.py`, parse `context.meeting_id` from incoming user messages.

- [ ] Validate that the meeting id belongs to the current room and has `status in ("pending", "confirmed")`. Ignore it if validation fails.

- [ ] Store the validated id in pipeline state as `context_meeting_id`.

Acceptance criteria:

- A place request after time confirmation carries the current meeting id to the backend.
- A stale or tampered meeting id from another room is ignored.
- Public/private visibility semantics do not change.

### 7. Reuse Context Meeting Id In Place Recommendation

- [ ] In `backend/app/services/pipeline/state.py`, add optional `context_meeting_id: int | None` to `GraphState` and the default state.

- [ ] In `backend/app/services/pipeline/nodes/place.py`, centralize meeting id selection:

  ```python
  async def _resolve_place_meeting_id(state: GraphState, title: str) -> int:
      card_id = _card_payload_meeting_id(state.get("vote_card_payload"))
      if card_id is not None:
          return card_id

      context_id = state.get("context_meeting_id")
      if context_id is not None:
          return int(context_id)

      return await _ensure_pending_meeting_id(state, title)
  ```

- [ ] Use `_resolve_place_meeting_id()` everywhere `place.py` currently calls `_card_payload_meeting_id(...)` followed by `_ensure_pending_meeting_id(...)`.

- [ ] Do not add a broad "latest confirmed meeting in room" fallback unless it is guarded by a product rule such as "only one future confirmed meeting without location exists". The explicit context id is the safe path.

Acceptance criteria:

- After a time is confirmed, `천안 신부동 추천해줘` creates a place recommendation attached to the same meeting id.
- A location-first request before any schedule exists still creates or reuses a pending meeting as before.
- Refreshing pending place state returns the same meeting id.

### 8. Broadcast Location-First Place Cards To The Room

- [ ] In `backend/app/api/ws/agent.py`, update the branch:

  ```python
  if result.get("is_location_first") and not result.get("date_hint"):
      ...
  ```

- [ ] Publish `place_recommendation_payload` to `shared_channel` instead of `user_channel`.

- [ ] Keep private chat text private, but keep AI cards shared. The existing comment in `useAgentWebSocket.ts` already states this rule: `카드는 항상 공유`.

Acceptance criteria:

- When one member asks for `천안 신부동 추천해줘`, all users in the room receive the same place recommendation card.
- The card has the same `meeting_id` for every client.

---

## Tests To Add

### Backend

- [ ] Create `backend/tests/test_quick_classify.py`:

  ```python
  import pytest
  import app.services.quick_classify as qc

  @pytest.mark.asyncio
  async def test_known_place_plus_neighborhood_recommendation_is_regex_place():
      result = await qc.quick_classify("천안 신부동 추천해줘")
      assert result["kind"] == "place"
      assert result["method"] == "regex"

  @pytest.mark.asyncio
  @pytest.mark.parametrize("text", [
      "친구 추천해줘",
      "연구 자료 찾아줘",
      "도구 추천해줘",
  ])
  async def test_common_suffix_words_are_not_forced_to_regex_place(monkeypatch, text):
      async def fake_call_llm_tier(*args, **kwargs):
          return "general"

      monkeypatch.setattr(qc, "call_llm_tier", fake_call_llm_tier)

      result = await qc.quick_classify(text)

      assert result["kind"] == "general"
      assert result["method"] == "gemini"
  ```

- [ ] Create `backend/tests/test_places_helper.py`:

  ```python
  from app.services.pipeline.helpers.places import _extract_korean_place_keyword

  def test_extracts_composite_known_city_and_neighborhood():
      assert _extract_korean_place_keyword("천안 신부동 추천해줘") == "천안 신부동"

  def test_keeps_known_place_without_suffix():
      assert _extract_korean_place_keyword("홍대 맛집") == "홍대"

  def test_preserves_free_text_fallback_for_unregistered_place():
      assert _extract_korean_place_keyword("동탄 센트럴파크 추천해줘") == "동탄센트럴파크"
  ```

- [ ] Add `backend/tests/test_agent_autotrigger_idempotency.py` with a fake Redis object that records `set(..., nx=True, ex=...)` calls and covers both key paths:

  ```python
  class FakeRedis:
      def __init__(self):
          self.keys = set()
          self.calls = []

      async def set(self, key, value, *, nx=False, ex=None):
          self.calls.append((key, value, nx, ex))
          if nx and key in self.keys:
              return False
          self.keys.add(key)
          return True

  def test_confirm_trigger_uses_snapshot_consume_key():
      key = build_auto_trigger_lock_key(
          room_id=1,
          trigger_reason="all_members_selected",
          snapshot_hash="snap-1",
      )
      assert key == "nx_confirm_consume:1:snap-1"

  def test_stalemate_trigger_keeps_room_debounce_key():
      key = build_auto_trigger_lock_key(
          room_id=1,
          trigger_reason="stalemate",
          snapshot_hash=None,
      )
      assert key == "nx_autotrigger:1"
  ```

  If no `build_auto_trigger_lock_key()` helper exists yet, create it in `backend/app/api/ws/agent.py` as part of Task 3 so the lock policy is unit-testable without opening real websockets.

- [ ] Add `backend/tests/test_place_meeting_context.py` with monkeypatched `_ensure_pending_meeting_id()` to assert it is not called when `state["context_meeting_id"]` is present.

Run:

```powershell
cd backend
pytest tests/test_quick_classify.py tests/test_places_helper.py -q
pytest tests/test_agent_autotrigger_idempotency.py tests/test_place_meeting_context.py -q
```

### Frontend

- [ ] Extend `frontend/src/__tests__/MeetingContext.test.tsx` with a stale-consensus regression:

  ```ts
  it("timeConfirmed clears stale scheduleConsensus", () => {
    const { result } = renderHook(() => useMeeting(), { wrapper });

    act(() => result.current.setScheduleConsensus({
      type: "schedule_consensus_ready",
      room_id: 1,
      snapshot_hash: "snapshot",
      host_user_id: 1,
      member_count: 2,
    }));

    act(() => result.current.setInfoPanePhase("timeConfirmed"));

    expect(result.current.scheduleConsensus).toBeNull();
    expect(result.current.infoPanePhase).toBe("timeConfirmed");
  });
  ```

- [ ] Add or extend a hook/component test for `useSocialWebSocket` if the project already has a websocket mock helper. If no helper exists, cover the bridge through a focused `ChatPane` test only after introducing a small websocket mock.

Run:

```powershell
cd frontend
npm test -- MeetingContext.test.tsx
```

---

## Manual QA Script

1. Start backend, frontend, and Redis locally.
2. Open the same room in two browser sessions as host and member.
3. Have both users select times until `schedule_consensus_ready` appears.
4. Host clicks TimeBar confirmation.
5. Verify both clients:
   - `scheduleConsensus` disappears.
   - Info pane moves to time confirmed state.
   - stale vote card no longer renders.
6. Verify backend logs:
   - one `ai_auto_trigger` is consumed for the snapshot.
   - one pipeline run creates the shared recommendation.
7. Send `천안 신부동 추천해줘`.
8. Verify both clients receive the same place card.
9. Verify the card's `place_hint` is `천안 신부동`.
10. Verify the card's `meeting_id` equals the time-confirmed meeting id.

---

## Rollout Order

1. Add auto-trigger lock tests that prove confirm uses `nx_confirm_consume:{room}:{snapshot}` while stalemate keeps `nx_autotrigger:{room}`.
2. Restore confirm-only Redis idempotency. This fixes inconsistent time recommendations and duplicate meetings without weakening stalemate debounce.
3. Implement `schedule_finalized` event and frontend bridge. This fixes the visible stale-card bug.
4. Add place helper tests and implement Task 5 first, preserving the existing free-text fallback.
5. Add narrow quick-classifier tests and implement Task 4 only with the known-prefix guard, so `친구/연구/도구` are not regex-forced to place.
6. Add AI request meeting context and place meeting-id resolution.
7. Change location-first place recommendation publishing from user channel to shared channel.
8. Run automated tests and the two-user manual QA script.

## Non-Goals

- Do not redesign the whole AI pipeline.
- Do not replace `meeting_confirmed`; keep it for actual persisted meeting confirmation.
- Do not add broad "latest meeting in room" fallback unless the product explicitly defines room lifecycle rules for old meetings.
