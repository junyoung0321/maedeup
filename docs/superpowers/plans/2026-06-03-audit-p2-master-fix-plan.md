# Audit P2 Master Fix Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the 2026-06-03 audit's P2 findings into verified, test-backed fixes without mixing unrelated subsystems into one risky patch.

**Architecture:** Treat P2 as a staged program, not a single patch. First classify and verify each P2 finding with a failing test or a direct reproduction, then execute four implementation waves: security/cost controls, real-time scheduling reliability, pipeline correctness, and frontend meeting-state consistency.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy async sessions, Redis/fakeredis, pytest/pytest-asyncio, React, Vitest, TypeScript.

---

## Scope

This document is the P2 master plan for `docs/handoff/code-audit-2026-06-03`. It deliberately does not edit the Claude handoff audit documents. Any status notes should be recorded in this plan family under `docs/superpowers/plans/`.

The audit marks P2/P3 as first-pass and mostly unverified. Therefore, every P2 item must pass one of these gates before code changes:

- **Confirmed:** a failing unit/integration/frontend test reproduces the issue.
- **Code-confirmed:** a narrow code path review proves the issue and the test asserts the fixed behavior.
- **Downgraded:** the issue is real but lower severity or unreachable in normal flows.
- **Rejected:** current code contradicts the audit mechanism.

## Execution Order

1. Finish or merge the P1 plan first: `docs/superpowers/plans/2026-06-03-audit-p1-security-and-vote-fixes.md`.
2. Execute **Wave A** first because it contains security, auth, and abuse-cost controls.
3. Execute **Wave B** next because it protects live multi-user scheduling and WebSocket reliability.
4. Execute **Wave C** after B because it changes pipeline behavior and requires careful regression tests.
5. Execute **Wave D** last because most items are local frontend consistency or UX failures.

> **전시 우선순위 (2026-06-04~05)**: 이 P2 프로그램은 41건/4웨이브의 **다일 작업**이다. 내일 전시 직결은 사실상 **`cal-1`**(`free-slots` 500 → 데모 중 캘린더 깨질 수 있음, Wave A) 하나 + 별도 P1 플랜의 **chat IDOR 2건**뿐이다. **전시 전엔 `cal-1` + P1 IDOR만 cherry-pick하고, Wave A 나머지·B·C·D는 전시 후** 진행을 권장한다.

> **감사 라인번호 주의**: 1차 감사는 Codex 멀티유저 수정 *이전* 코드 기준이다. 특히 `agent.py`는 그 후 **+약 109줄** 늘어 `ws-agent-1/3/4/5/6`·`graph-2`·`ws-social-4`의 인용 라인이 이동했다. Wave B/C 구현자는 **현재 코드에서 재탐색**한 뒤 confirm/code-confirm 게이트를 통과시켜야 한다.

Do not run broad P2 work in parallel against the same files. In particular, `backend/app/api/ws/agent.py`, `backend/app/api/routes/meetings.py`, `backend/app/services/pipeline/helpers/slots.py`, and `frontend/src/contexts/MeetingContext.tsx` have overlapping workstreams.

## File Structure

Master plan:
- `docs/superpowers/plans/2026-06-03-audit-p2-master-fix-plan.md`

Recommended child plans before implementation:
- `docs/superpowers/plans/2026-06-03-audit-p2a-security-cost-controls.md`
- `docs/superpowers/plans/2026-06-03-audit-p2b-realtime-scheduling-ws.md`
- `docs/superpowers/plans/2026-06-03-audit-p2c-pipeline-correctness.md`
- `docs/superpowers/plans/2026-06-03-audit-p2d-frontend-meeting-state.md`

Implementation test targets by area:
- Backend security/API: `backend/tests/integration/test_chat_messages_security.py`, `backend/tests/integration/test_meeting_authorization.py`, `backend/tests/integration/test_refresh_route.py`, `backend/tests/unit/test_config_security.py`
- Backend scheduling/WS: `backend/tests/unit/test_scheduling_round.py`, `backend/tests/test_agent_autotrigger_idempotency.py`, new `backend/tests/unit/test_social_consensus.py`, new `backend/tests/unit/test_agent_ws_resilience.py`
- Backend pipeline: `backend/tests/unit/test_pipeline_entity_dates.py`, `backend/tests/unit/test_slots.py`, `backend/tests/unit/test_embedding_failures.py`, `backend/tests/unit/test_memory_extraction.py`
- Frontend: `frontend/src/__tests__/MeetingContext.test.tsx`, new component/hook tests near the affected components

---

## P2 Inventory And Routing

> **ID 주의 — `slot-*` 접두 충돌**: 1차 감사에서 두 영역이 같은 `slot-N` 접두를 재사용했다. 본 플랜은 혼선을 막기 위해 한정 ID를 쓴다:
> - **`sched/slot-N`** = `scheduling_round.py` 관련 (감사 문서 `07-scheduling-round.md`) — Wave B.
> - **`slots/slot-N`** = `pipeline/helpers/slots.py` 관련 (감사 문서 `01-pipeline-slot.md`) — Wave C.
>
> Status Ledger와 child plan도 이 한정 ID를 사용한다. (원본 감사 ID는 각 문서 내 그대로.)

### Wave A: Security, Auth, Cost, And Server-Side Abuse Controls

| id | audit item | primary files | initial decision |
|---|---|---|---|
| `core-3` | default `JWT_SECRET` allowed in dev env | `backend/app/core/config.py`, `docker-compose.yml` | Fix directly after config tests |
| `chat-3` | `POST /chat/messages` trusts user-controlled identity fields | `backend/app/api/routes/chat.py`, `backend/app/models/chat.py` | Fix after P1 chat read fix |
| `core-1` | HTTP rate limiter unused | `backend/app/core/rate_limit.py`, sensitive routes | Verify and apply to high-cost routes first |
| `route-meetings-1` | cancel auth uses `meeting.created_by`, not room owner | `backend/app/api/routes/meetings.py` | Verify with integration test |
| `route-meetings-5` | host confirms another user's pending meeting but `created_by` remains old user | `backend/app/api/routes/meetings.py` | Batch with `route-meetings-1` |
| `route-meetings-3` | refresh recommendations idempotency is set only after pipeline | `backend/app/api/routes/meetings.py` | Verify concurrency with fake pipeline counter |
| `rooms-1` | host leave transfer skips leaving host calendar cleanup | `backend/app/api/routes/rooms.py` | Verify DB cleanup without real Google calls |
| `cal-1` | malformed Google event without date fields causes `free-slots` 500 | `backend/app/api/routes/calendar.py` | Fix parser guard with unit test |

### Wave B: Real-Time Scheduling, Finalization, And WebSocket Resilience

| id | audit item | primary files | initial decision |
|---|---|---|---|
| `sched/slot-2` | proposal status stays `majority_reached` after like count drops | `backend/app/services/scheduling_round.py`, `FinalizationProposalCard.tsx` | Backend status fix first |
| `sched/slot-3` | stale votes from departed members remain in majority numerator | `backend/app/services/scheduling_round.py`, `backend/app/api/routes/meetings.py` | Verify with current-member filter |
| `ws-social-1` | single-cell `start==end` can block consensus | `backend/app/api/ws/social.py`, `backend/app/services/scheduling_round.py` | Confirm against current code because audit line may overlap P3 duplicate |
| `ws-social-2` | Redis failure returns `[]` and wipes peer unavailable dates in clients | `backend/app/services/scheduling_round.py`, `backend/app/api/ws/social.py`, `useSocialWebSocket.ts` | Prefer no-broadcast on uncertain write failure |
| `ws-social-4` | `consensus_ready` can fire with no computed slot | `backend/app/api/ws/social.py`, `backend/app/api/ws/agent.py` | Require concrete slot before trigger |
| `ws-agent-1` | direct request `run_pipeline` exception can close WS | `backend/app/api/ws/agent.py` | Add guarded error event path |
| `ws-agent-5` | Redis subscriber read failure breaks inbound forever | `backend/app/api/ws/agent.py` | Retry subscriber loop with bounded backoff |
| `ws-agent-3` | detached auto-trigger tasks have no strong refs | `backend/app/api/ws/agent.py` | Batch with `ws-agent-6` |
| `ws-agent-6` | detached pipeline updates shallow copy but not connection context | `backend/app/api/ws/agent.py` | Decide whether propagation is required, then test |
| `ws-agent-4` | `user=null` rejected dates are attributed to trigger sender | `backend/app/api/ws/agent.py`, `date_classify.py` | Verify with multi-speaker payload test |

### Wave C: Pipeline Correctness, Intent, Slots, Memory, And Place/Time Semantics

| id | audit item | primary files | initial decision |
|---|---|---|---|
| `entity-2` | unresolved Korean date hints survive ISO filter | `backend/app/services/pipeline/nodes/entity.py` | Fix with strict ISO filter |
| `slots/slot-1` | F1 fallback denominator differs from normal BUG-26-D path | `backend/app/services/pipeline/helpers/slots.py`, `function_call.py` | Add headcount_total through fallback |
| `slots/slot-2` | explicit `date_hint` can return extended slots on other dates | `backend/app/services/pipeline/helpers/slots.py`, `vote_card.py` | Verify desired product behavior before fixing |
| `slots/slot-3` | unknown non-consenting members counted as available | `backend/app/services/pipeline/helpers/slots.py` | Split verified/unknown counts or downgrade if UI contract says total only |
| `dates-2` | Korean weekday "today" and day-of-month "today" differ | `backend/app/services/pipeline/helpers/dates.py` | Product decision required: today allowed or rolled |
| `entity-3` | AI-pane recent messages use `role: content`, breaking speaker attribution | `backend/app/services/pipeline/state.py`, `date_classify.py` | Serialize speaker-aware context where date attribution needs it |
| `intent-2` | embedding failure becomes zero vector and silent degradation | `backend/app/services/embedding.py`, `intent_classifier.py` | Batch with overlap `intent-1` |
| `embed-1` | failed embedding zero vector persists to `IntentExample.embedding` | `backend/app/api/routes/intents.py`, `embedding.py` | Reject writes when embedding failed |
| overlap `intent-1` | zero-vector fallback skips Gemini fallback path | `backend/app/services/intent_classifier.py` | Include in same embedding failure fix |
| `memory-1` | list value written to string user columns rolls back extraction batch | `backend/app/services/pipeline/nodes/memory.py`, `personal_data_extractor.py` | Normalize scalar/list by field schema |
| overlap `memory-2` | concurrent finalization duplicates memory extraction | `backend/app/services/pipeline/nodes/maedeup.py`, `memory.py` | Add idempotency key or DB uniqueness |
| `graph-1` | route function mutates LangGraph state in-place | `backend/app/services/pipeline/graph.py` | Verify if current LangGraph version observes mutation |
| overlap `graph-2` | all-members-selected can reach maedeup without confirmed place | `backend/app/services/pipeline/graph.py`, `maedeup.py` | Verify after current multiuser fixes |
| `route-meetings-2` | Kakao result overwrites user-specified place name | `backend/app/api/routes/meetings.py` | Preserve user display name, store Kakao canonical metadata separately |

### Wave D: Frontend Meeting State, Vote Cards, And Host UX

| id | audit item | primary files | initial decision |
|---|---|---|---|
| `schedule-1` | non-host sees enabled confirm button | `ScheduleRecommendationCard.tsx` | Fix directly with component test |
| `hooks-2` | snapshot merge order can fail to overwrite stale peer state | `useSocialWebSocket.ts` | Verify with reducer-style test |
| `votecard-1` | stale `isPlaceConfirmed` capture skips done transition | `VoteCardSection.tsx` | Fix dependencies or use state ref |
| `hooks-1` | WS reconnect effect depends only on roomId and can keep stale sender | `useSocialWebSocket.ts`, `useAgentWebSocket.ts` | Check current hook after recent context changes |
| `hooks-3` | vote update before proposal loses `deadline_at`/`created_at` | `useSocialWebSocket.ts` | Store partial update without zeroing metadata |
| `context-1` | new meeting vote card can preserve old dateConfirmed phase | `MeetingContext.tsx` | Needs careful review because R6 intentionally preserves same-meeting dateConfirmed |
| `aipane-1` | active vote/place cards selected independently by latest card | `AiAssistantPane.tsx` | Select active meeting first, then cards under that meeting |
| `ctx-4` | new vote card does not clear old voteUpdate | `MeetingContext.tsx` | Batch with `context-1` |
| `reco-1` | available friends UTC-naive interpreted as KST-naive | `recommendations.py`, `datetime.ts`, home components | Decide API timezone contract and test both sides |

---

## Task 1: Create P2 Verification Ledger

**Files:**
- Modify: `docs/superpowers/plans/2026-06-03-audit-p2-master-fix-plan.md`

- [ ] **Step 1: Add a status ledger section before implementation**

Append a `P2 Status Ledger` section to this document when execution begins. Use exactly these columns:

```markdown
## P2 Status Ledger

| id | wave | status | evidence | fix commit |
|---|---|---|---|---|
| core-3 | A | unstarted | audit INDEX line item, conf 8 | |
| chat-3 | A | unstarted | audit INDEX line item, conf 7 | |
| core-1 | A | unstarted | audit INDEX line item, conf 9 | |
```

Then add the remaining P2 IDs from the routing tables above. Use the **한정 ID** (`sched/slot-N`, `slots/slot-N`) so the two `slot-*` families never collide in one row. Status values are limited to `unstarted`, `confirmed`, `code-confirmed`, `downgraded`, `rejected`, `fixed`, and `verified`.

- [ ] **Step 2: Keep ledger updates scoped**

When a finding is handled, update only that row. Do not edit `docs/handoff/code-audit-2026-06-03/*` unless explicitly asked.

---

## Task 2: Write Wave A Child Plan

**Files:**
- Create: `docs/superpowers/plans/2026-06-03-audit-p2a-security-cost-controls.md`
- Reference: `docs/handoff/code-audit-2026-06-03/10-route-rooms-auth.md`
- Reference: `docs/handoff/code-audit-2026-06-03/08-route-meetings.md`
- Reference: `docs/handoff/code-audit-2026-06-03/09-route-calendar-reco.md`
- Reference: `docs/handoff/code-audit-2026-06-03/12-models-core.md`

- [ ] **Step 1: Create the Wave A implementation plan**

The child plan must contain concrete failing tests and fixes for this order:

1. `core-3`: reject default JWT secret regardless of `APP_ENV`.
2. `chat-3`: server-overwrite `user_id`, `sender`, and disallow client `role="assistant"` unless the route is intentionally internal.
3. `core-1`: apply rate limiting to the smallest high-cost surface first: guest join, place/recommendation refresh, and public LLM-triggering endpoints. **同伴 필수**: 감사 `core-2`(P3)에서 `check_rate_limit`이 `request.state.user_sub`를 참조하는데 아무도 세팅하지 않아 항상 IP 폴백이다 — per-user 제한이 실제로 동작하려면 `user_sub` 주입(미들웨어/의존성)을 같이 처리하라.
4. `route-meetings-1` and `route-meetings-5`: make confirmed meeting ownership consistent with room host authority.
5. `route-meetings-3`: set idempotency/lock before `run_pipeline`.
6. `rooms-1`: clean leaving host's calendar event IDs during host transfer.
7. `cal-1`: skip or normalize Google events missing both `dateTime` and `date`.

- [ ] **Step 2: Required tests in Wave A**

The child plan must create or extend these tests:

```text
backend/tests/unit/test_config_security.py
backend/tests/integration/test_chat_messages_security.py
backend/tests/integration/test_rate_limited_routes.py
backend/tests/integration/test_meeting_authorization.py
backend/tests/integration/test_refresh_route.py
backend/tests/integration/test_rooms_leave_calendar_cleanup.py
backend/tests/unit/test_calendar_event_parsing.py
```

- [ ] **Step 3: Required verification commands in Wave A**

The child plan must require:

```bash
cd backend
pytest tests/unit/test_config_security.py tests/integration/test_chat_messages_security.py tests/integration/test_meeting_authorization.py tests/integration/test_refresh_route.py tests/unit/test_calendar_event_parsing.py -q
python -m compileall app
```

---

## Task 3: Write Wave B Child Plan

**Files:**
- Create: `docs/superpowers/plans/2026-06-03-audit-p2b-realtime-scheduling-ws.md`
- Reference: `docs/handoff/code-audit-2026-06-03/05-ws-social.md`
- Reference: `docs/handoff/code-audit-2026-06-03/06-ws-agent.md`
- Reference: `docs/handoff/code-audit-2026-06-03/07-scheduling-round.md`

- [ ] **Step 1: Create the Wave B implementation plan**

The child plan must preserve the all-members-selected snapshot lock added in the multiuser fix. It must not collapse `nx_confirm_consume:{room}:{snapshot}` back into the old room-wide `nx_autotrigger:{room}` behavior.

Fix order:

1. `sched/slot-2`: recompute proposal status both upward and downward after every vote.
2. `sched/slot-3`: majority checks must count votes only from current room members.
3. `ws-social-1`: align explicit selection detection with `compute_majority_slot` for single-cell ranges.
4. `ws-social-4`: do not publish/trigger `consensus_ready` without a concrete majority/transient slot.
5. `ws-social-2`: on Redis write failure, do not broadcast an empty unavailable list as if it were authoritative.
6. `ws-agent-1`: catch direct `run_pipeline` exceptions and emit a structured error message without closing the socket.
7. `ws-agent-5`: retry Redis subscription reads with bounded backoff instead of permanently breaking inbound.
8. `ws-agent-3` and `ws-agent-6`: maintain strong refs for detached tasks and explicitly define which task results propagate back to connection `slot_context`.
9. `ws-agent-4`: prevent `user=null` rejected-date events from being assigned to an unrelated trigger sender.

- [ ] **Step 2: Required tests in Wave B**

The child plan must create or extend:

```text
backend/tests/unit/test_scheduling_round.py
backend/tests/integration/test_finalization_api.py
backend/tests/unit/test_social_consensus.py
backend/tests/unit/test_agent_ws_resilience.py
backend/tests/test_agent_autotrigger_idempotency.py
```

- [ ] **Step 3: Required verification commands in Wave B**

```bash
cd backend
pytest tests/unit/test_scheduling_round.py tests/integration/test_finalization_api.py tests/unit/test_social_consensus.py tests/unit/test_agent_ws_resilience.py tests/test_agent_autotrigger_idempotency.py -q
python -m compileall app
```

---

## Task 4: Write Wave C Child Plan

**Files:**
- Create: `docs/superpowers/plans/2026-06-03-audit-p2c-pipeline-correctness.md`
- Reference: `docs/handoff/code-audit-2026-06-03/01-pipeline-slot.md`
- Reference: `docs/handoff/code-audit-2026-06-03/02-pipeline-entity-intent.md`
- Reference: `docs/handoff/code-audit-2026-06-03/03-pipeline-validation-maedeup.md`
- Reference: `docs/handoff/code-audit-2026-06-03/04-pipeline-graph-helpers.md`
- Reference: `docs/handoff/code-audit-2026-06-03/11-services-external.md`

- [ ] **Step 1: Create the Wave C implementation plan**

Fix order:

1. `entity-2`: drop unresolved non-ISO multi-date hints before downstream slot logic.
2. `slots/slot-1`: pass full `headcount_total` into F1 fallback denominator.
3. `slots/slot-2`: define product behavior for explicit date hints before code: strict date only, or extended dates with `confirmed_date` updated to actual slot date.
4. `slots/slot-3`: stop claiming unknown/non-consenting members are verified available; expose `verified_available_count` and `unknown_count` if product needs both.
5. `dates-2`: choose one "today" policy and make weekday/day-of-month parsing consistent.
6. `entity-3`: preserve real sender names in AI-panel recent-message context where date speaker attribution consumes the text.
7. `intent-2`, `embed-1`, and overlap `intent-1`: replace zero-vector failure sentinel with an explicit embedding-failed path.
8. `memory-1` and overlap `memory-2`: normalize memory values by schema and make finalization memory extraction idempotent.
9. `graph-1` and overlap `graph-2`: remove router in-place mutation and block maedeup completion without required confirmed place.
10. `route-meetings-2`: preserve user-entered place display name while using Kakao result for address/coordinates metadata.

- [ ] **Step 2: Required tests in Wave C**

The child plan must create or extend:

```text
backend/tests/unit/test_pipeline_entity_dates.py
backend/tests/unit/test_slots.py
backend/tests/unit/test_calendar_dates.py
backend/tests/unit/test_pipeline_speaker_context.py
backend/tests/unit/test_embedding_failures.py
backend/tests/unit/test_memory_extraction.py
backend/tests/unit/test_pipeline_graph_routing.py
backend/tests/integration/test_meeting_place_patch.py
```

- [ ] **Step 3: Required verification commands in Wave C**

```bash
cd backend
pytest tests/unit/test_pipeline_entity_dates.py tests/unit/test_slots.py tests/unit/test_calendar_dates.py tests/unit/test_pipeline_speaker_context.py tests/unit/test_embedding_failures.py tests/unit/test_memory_extraction.py tests/unit/test_pipeline_graph_routing.py tests/integration/test_meeting_place_patch.py -q
python -m compileall app
```

---

## Task 5: Write Wave D Child Plan

**Files:**
- Create: `docs/superpowers/plans/2026-06-03-audit-p2d-frontend-meeting-state.md`
- Reference: `docs/handoff/code-audit-2026-06-03/13-fe-state-hooks.md`
- Reference: `docs/handoff/code-audit-2026-06-03/14-fe-components.md`

- [ ] **Step 1: Create the Wave D implementation plan**

Fix order:

1. `schedule-1`: non-host users see disabled/waiting state instead of an enabled confirm button.
2. `votecard-1`: ensure `handleConfirmSchedule` reads current `isPlaceConfirmed`, `activeMeetingId`, and setters.
3. `context-1` and `ctx-4`: reset stale vote update and phase only when `meeting_id` changes; preserve the R6 same-meeting `dateConfirmed` behavior.
4. `aipane-1`: choose an active meeting first, then select vote/place cards for that same meeting.
5. `hooks-2`: snapshot application must replace stale peer state when snapshot is newer or authoritative.
6. `hooks-3`: merge early `finalization_vote_update` without zeroing missing metadata.
7. `hooks-1`: include sender identity dependencies in WebSocket reconnect effects or use stable refs that update before sends.
8. `reco-1`: establish an explicit timezone contract for `available_at` and update backend/frontend together.

- [ ] **Step 2: Required tests in Wave D**

The child plan must create or extend:

```text
frontend/src/__tests__/MeetingContext.test.tsx
frontend/src/__tests__/ScheduleRecommendationCard.test.tsx
frontend/src/__tests__/VoteCardSection.test.tsx
frontend/src/__tests__/AiAssistantPane.test.tsx
frontend/src/__tests__/useSocialWebSocket.test.tsx
frontend/src/__tests__/datetime.test.ts
```

- [ ] **Step 3: Required verification commands in Wave D**

```bash
cd frontend
npm test
npx tsc --noEmit
```

---

## Global Verification Gate

After each wave:

```bash
cd backend
pytest -q
python -m compileall app
```

```bash
cd frontend
npm test
npx tsc --noEmit
```

Known current baseline note:
- `tests/unit/test_finalization_reason.py` (patched removed `call_gemini`) is **already fixed separately** → patches `call_llm_tier` now, 6 tests pass. Not P2 debt.
- Container `maedeup-api`의 full `pytest -q`는 환경 artifact로 추가 실패가 난다: deprecated `event_loop` fixture(pytest-asyncio 0.23) 격리 오염 + `.env`의 `PREFERENCE_TOGGLE_ENABLED=false`(C0 flag가 toggle 테스트를 False로 강제). **회귀 아님** — 타깃 파일 단위 실행으로 깨끗한 신호를 보라.

## Self-Review

- Spec coverage: every active P2 row from the audit INDEX is routed to Wave A, B, C, or D; Codex-overlap P2 items are included in Wave C as recheck items.
- Scope control: each wave maps to a distinct subsystem and can be implemented with targeted tests.
- Risk control: P2 items are not fixed until confirmed or code-confirmed, which protects against false positives in the first-pass audit.
