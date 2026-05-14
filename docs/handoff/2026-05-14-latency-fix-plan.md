# 매듭 응답시간 단축 작업 매뉴얼 (v1 — Claude 작업용)

작성: 2026-05-14
작업자: **Claude** (사용자 검토하에)
대상 응답시간: **8~15s → 목표 2~4s**
선행 작업: PR #3 (langgraph_pipeline 분할) 완료 — 새 구조 `pipeline/`에서 진행
완료 목표: 2026-05-15 (시연 D-5)

---

## 🔖 이 문서 사용 방법 (Claude 필독)

이 문서는 단순 계획서가 아니라 **작업 매뉴얼**. v2 split 계획서와 동일한 패턴.

### A. 매 Fix 시작 전
1. **§7 Resume Protocol** 실행해 현재 상태 자가진단
2. 해당 Fix의 **Pre-conditions** 충족 확인
3. Pre-conditions 미충족 시 → 직전 Fix로 돌아가 누락 작업 완료

### B. 매 Fix 끝 직후
4. **Self-check 명령** 실행 (§Fix별)
5. AST syntax + 함수 카운트 확인
6. 시연 자동화 통과 (사용자 부탁) — TIER 2 Fix 4는 필수
7. **반드시 git commit** (Fix 단위)
8. 깨지면 즉시 `git revert HEAD` + 사용자 보고

### C. 컨텍스트 초기화 시
9. 이 문서 + §7 Resume Protocol로 어디까지 했는지 복구
10. 매 Fix마다 "완료 markers" (어떤 파일이 어떤 패턴인지) 명시

### D. 절대 금지
- ❌ Fix 여러 개를 한 commit에 묶기 (롤백 단위 흐려짐)
- ❌ 시연 자동화 미통과 상태로 Fix 4 머지
- ❌ `_parse_natural_date` 캐시 키에 mutable 객체 (state 등) 포함
- ❌ Gemini timeout 값을 prompt별로 다르게 (혼란)

---

## 1. 현재 상태 (검증된 사실, 2026-05-14)

### 1.1 진단된 응답시간 분포

direct_request "내일 6시 천안 맛집" 케이스:

```
quick_classify           ~1.5s  (regex 통과 시 0초, 그 외 Gemini)
entity_extraction
  ├─ _extract_entities    3~5s   Gemini
  ├─ _parse_natural_date  1.5s   Gemini (캐시 미적용)
  └─ multi-date loop      N*1.5s 직렬
function_calling
  ├─ search_place         0.5~1s Kakao
  └─ get_free_slots       1~2s   GCal (gather 이미 적용)
supervisor_validation    0초
place_recommendation
  ├─ _get_room_member_*   ~250ms 3개 직렬 DB
  ├─ ML/Gemini scoring    2~3s
  └─ self_correction      3s
vote/maedeup_card        0.5~1s

worst case 합계: 8~15s
```

### 1.2 적용된 최적화 (이미 있음 — 중복 적용 금지)

| 위치 | 최적화 |
|---|---|
| function_calling | `asyncio.gather(get_free_slots, search_place)` 병렬 ✓ |
| _parse_natural_date | regex fallback 우선 (Gemini skip 가능) ✓ |
| place_recommendation | top 10 → top 5 (시연 latency 최적화) ✓ |
| place_recommendation | 후보 ≤3개면 Gemini scoring skip ✓ |
| place_recommendation | disliked_foods 없으면 self_correction skip ✓ |
| memory_extraction | fire-and-forget (P0-2) ✓ |

### 1.3 외부 의존성 (수정 금지)

- `call_gemini`: Gemini SDK 사용. timeout 추가만 OK.
- 외부 import 4파일 (agent.py, meetings.py, rooms.py, qa_privacy.py): **무수정**
- 시연 자동화 (`.gstack-demo.py`): ACT 1~5 통과 유지

---

## 2. 작업 위치

### 2.1 브랜치 전략

- 신규 브랜치: `perf/latency-reduction`
- Base: `refactor/pipeline-split` (PR #3, 머지 전)
- 이유: PR #3 머지되면 자동으로 main 위에 올라옴

### 2.2 worktree 점유 충돌 처리

현재 상태:
- worktree (`.claude/worktrees/optimistic-agnesi-9aa632/`): detached HEAD at `dce4357`
- 메인 dir: `refactor/pipeline-split` 점유 가능 (사용자 환경에 따라)

작업 위치 결정:
- 메인 dir에서 `refactor/pipeline-split` 점유 중이면 → 메인에서 새 브랜치
- worktree에서 작업하려면 → 메인을 다른 branch로 옮긴 후 worktree에서 `git checkout -b perf/latency-reduction`

```bash
# 옵션 A: 메인에서 작업
cd C:\Users\dnflt\Desktop\jjy\workspace\maedeup
git checkout -b perf/latency-reduction

# 옵션 B: worktree에서 작업 (메인이 main branch로 가야 함)
cd C:\Users\dnflt\Desktop\jjy\workspace\maedeup
git checkout main
cd .claude\worktrees\optimistic-agnesi-9aa632
git checkout refactor/pipeline-split
git checkout -b perf/latency-reduction
```

### 2.3 시연 자동화 검증 환경

- `.env` + `.gstack-demo-token` 셋업된 곳에서 docker compose
- worktree에 `.env` 없으면 메인 dir 또는 worktree에 복사

---

## 3. Fix 명세 (6개)

각 Fix는 1 commit. Pre-conditions / Before-After / Self-check / 롤백 명시.

### Fix 1. `_parse_natural_date` 메모이즈 — **−1.5s/호출**

**위치**: `backend/app/services/pipeline/helpers/dates.py` (현 줄 291~327)
**위험도**: 🟢 Low
**우선순위**: P0 (가장 자주 hit)

#### 문제
"내일", "다음주", "5월 14일" 같은 표현이 fallback에서 잡혀도 매번 함수 진입. fallback이 안 잡히면 Gemini 호출 (~1.5s). 같은 입력 반복 시 캐시 없음.

#### Before (현재 코드)
```python
async def _parse_natural_date(text: str) -> dict[str, Any] | None:
    normalized = str(text or "").strip()
    if not normalized:
        return None

    now_kst = datetime.now(KST)

    # --- OPTIMIZATION: Try pattern-based parsing first, skip Gemini if successful ---
    fallback_result = _fallback_parse_natural_date(normalized, now_kst)
    if fallback_result and fallback_result.get("date"):
        logger.info("[OPT] _parse_natural_date resolved by pattern fallback, skipping Gemini")
        return fallback_result

    today = now_kst.strftime("%Y-%m-%d")
    prompt = (...)
    try:
        raw = await call_gemini(prompt)
    except Exception as exc:
        logger.warning("Failed to parse natural date with Gemini: %s", exc)
        return fallback_result
    # ...
```

#### After (변경 코드)
파일 상단 import 추가:
```python
from functools import lru_cache
```

함수 위에 동기 헬퍼 추가:
```python
@lru_cache(maxsize=256)
def _parse_natural_date_sync(text: str, today_iso: str) -> dict[str, Any] | None:
    """동기 fallback 결과를 캐시. today_iso 키로 날짜 바뀌면 자동 invalidate.

    Returns: fallback_result (Gemini 호출은 캐시 외부에서 처리).
    """
    try:
        now_kst = datetime.fromisoformat(f"{today_iso}T00:00:00").replace(tzinfo=KST)
    except ValueError:
        return None
    result = _fallback_parse_natural_date(text, now_kst)
    return result if (result and result.get("date")) else None
```

`_parse_natural_date` 본문 변경:
```python
async def _parse_natural_date(text: str) -> dict[str, Any] | None:
    normalized = str(text or "").strip()
    if not normalized:
        return None

    today_iso = datetime.now(KST).date().isoformat()

    # --- OPTIMIZATION: Try cached pattern-based parsing first ---
    cached = _parse_natural_date_sync(normalized, today_iso)
    if cached:
        return cached

    # 캐시 miss + fallback 못 잡음 → Gemini 호출
    now_kst = datetime.now(KST)
    today = now_kst.strftime("%Y-%m-%d")
    prompt = (...)  # 기존 그대로
    # ... 이하 기존 코드
```

#### 효과
- "내일/다음주/5월 14일" 같은 fallback 패턴 → 2번째 호출부터 0초
- Multi-date hint loop에서 같은 패턴 반복 시 누적 효과

#### Pre-conditions
- [ ] `backend/app/services/pipeline/helpers/dates.py` 존재
- [ ] `from functools import lru_cache` 미존재 (이미 있으면 skip)

#### Self-check
```bash
python -c "
import ast, importlib.util
spec = importlib.util.spec_from_file_location('dates', 'backend/app/services/pipeline/helpers/dates.py')
mod = importlib.util.module_from_spec(spec)
# AST만 검증 (실제 import는 의존성 필요)
src = open('backend/app/services/pipeline/helpers/dates.py', encoding='utf-8').read()
tree = ast.parse(src)
funcs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
assert '_parse_natural_date_sync' in funcs, 'helper missing'
assert '_parse_natural_date' in funcs, 'main missing'
print('Fix 1 syntax OK')
"
```

#### 위험 + Mitigation
- **위험**: `lru_cache` 키에 datetime 객체 넣으면 매번 다른 객체 → 캐시 무효. `today_iso` 문자열로 키 분리해 해결.
- **위험**: 자정 넘어가는 시점 캐시 stale. `today_iso` 키로 자동 invalidate (날짜 바뀌면 키 다름).

#### 롤백
```bash
git revert HEAD  # Fix 1 commit
```

---

### Fix 2. Entity multi-date hint 병렬화 — **N개 → max(1.5s)**

**위치**: `backend/app/services/pipeline/nodes/entity.py:480-490`
**위험도**: 🟢 Low
**우선순위**: P0 (stalemate multi-date 케이스 큰 효과)

#### 문제
Multi-date hint resolve가 직렬 `for` 루프. 4개 hint면 6초.

#### Before
```python
# Multi-date: resolve each date hint to ISO dates
if len(raw_date_hints) >= 2:
    resolved_hints: list[str] = []
    for hint in raw_date_hints:
        if _is_iso_date_hint(hint):
            resolved_hints.append(hint)
        else:
            parsed = await _parse_natural_date(hint)
            if parsed and parsed.get("date"):
                resolved_hints.append(parsed["date"])
            else:
                resolved_hints.append(hint)  # keep raw if can't resolve
    extracted["date_hints"] = resolved_hints
    # Set date_hint to first resolved date for compatibility
    if resolved_hints:
        extracted["date_hint"] = resolved_hints[0]
        extracted["date_is_flexible"] = True
```

#### After
```python
# Multi-date: resolve each date hint to ISO dates (병렬)
if len(raw_date_hints) >= 2:
    async def _resolve_one(hint: str) -> str:
        if _is_iso_date_hint(hint):
            return hint
        parsed = await _parse_natural_date(hint)
        if parsed and parsed.get("date"):
            return parsed["date"]
        return hint  # keep raw if can't resolve

    resolved_hints = list(await asyncio.gather(*[_resolve_one(h) for h in raw_date_hints]))
    extracted["date_hints"] = resolved_hints
    if resolved_hints:
        extracted["date_hint"] = resolved_hints[0]
        extracted["date_is_flexible"] = True
```

import 추가 필요 시:
```python
import asyncio
```
이미 있으면 skip.

#### 효과
- 4개 hint × 1.5s = 6s → max(1.5s) = **−4.5s**
- Fix 1과 결합: 같은 hint 반복이면 0초

#### Pre-conditions
- [ ] Fix 1 적용 완료 (캐시 활용 위해)
- [ ] `import asyncio` 존재 확인

#### Self-check
```bash
grep -n "asyncio.gather" backend/app/services/pipeline/nodes/entity.py
# 기대: 1개 이상 match
```

#### 위험 + Mitigation
- **위험**: 병렬 호출 시 같은 input이 동시에 Gemini hit → rate limit 위험. Fix 1 캐시로 동일 input은 한 번만 Gemini hit.
- **위험**: `asyncio.gather` 중 하나가 raise → 전체 fail. `_resolve_one`은 raise 안 함 (raw 반환).

#### 롤백
```bash
git revert HEAD
```

---

### Fix 3. Place 멤버 정보 3개 병렬화 — **−150ms**

**위치**: `backend/app/services/pipeline/nodes/place.py:147-159`
**위험도**: 🟢 Low
**우선순위**: P1 (작은 효과지만 거의 공짜)

#### 문제
3개 DB lookup이 직렬. 각 50~100ms.

#### Before
```python
disliked_foods = await _get_room_member_food_preferences(state)
# 6 카테고리 personal data 합산 (Gemini prompt용 — 익명).
member_constraints = await _get_room_member_constraints(state)
# ... (주석)
per_user_constraints = await _get_room_member_constraints_named(state)
```

#### After
```python
disliked_foods, member_constraints, per_user_constraints = await asyncio.gather(
    _get_room_member_food_preferences(state),
    _get_room_member_constraints(state),
    _get_room_member_constraints_named(state),
)
```

import 확인:
```python
import asyncio
```

#### 효과
- 250ms → 100ms (-150ms)
- Hot path 아니지만 누적 효과

#### ⚠️ 주의: AsyncSession 동시 query 안전성
- SQLAlchemy AsyncSession은 **동시 query 불안전**. 같은 session에서 `gather`로 여러 await 묶으면 race condition.
- 3개 함수가 같은 `state["db"]` session 사용 → **위험**.

#### 대안 1: 별도 session으로 가져가기
```python
async def _fetch_member_constraints(state):
    async with AsyncSessionLocal() as session:
        new_state = {**state, "db": session}
        return await asyncio.gather(
            _get_room_member_food_preferences(new_state),
            _get_room_member_constraints(new_state),
            _get_room_member_constraints_named(new_state),
        )

disliked_foods, member_constraints, per_user_constraints = await _fetch_member_constraints(state)
```

#### 대안 2: 그냥 직렬 유지, Fix 3 폐기
효과 150ms로 작아서, AsyncSession race 위험 감수할 가치 낮음.

**결정**: Fix 3 폐기 권장. 다른 Fix들로 충분.

#### 롤백
폐기로 결정.

---

### Fix 4. `_slot_filling_default_partial` direct_request 분기 — UX 핵심 ⭐

**위치**: `backend/app/services/pipeline/nodes/slot.py:367-417`
**위험도**: 🟡 Medium (시연 시나리오 회귀 가능성 있어 검증 필수)
**우선순위**: P0 (UX 임팩트 최대 — "내일 6시" 카드 미생성 해결)

#### 문제
이전 분석 ([2026-05-13-recommend-input-catalog.md](./2026-05-13-recommend-input-catalog.md)) 발견: direct_request로 date만 또는 place만 보낸 케이스가 `_slot_filling_default_partial`에서 카드 못 만들고 ack 메시지만 emit. 사용자 체감 가장 큰 버그.

#### Before
```python
async def _slot_filling_default_partial(state: GraphState, has_date: bool, has_place: bool) -> GraphState:
    if has_date and not has_place:
        state["slot_filling_turns"] += 1
        if state["slot_filling_turns"] <= 1:
            date_display = state.get("date_hint", "")
            confirm_msg = (
                f"{date_display} 좋아요! 👍 "
                "장소나 인원이 대화에서 나오면 제가 바로 정리해드릴게요~"
            )
            await _emit_assistant_message(state["room_id"], state["db"], confirm_msg, state)

        state["awaiting_user_reply"] = False
        state["wait_timed_out"] = False
        state["message_count_since_last_trigger"] = 0
        state["status"] = "partial_info_acknowledged"
        return state
    # ... (has_place and not has_date 처리)
    # ... (default no_slots_yet)
```

#### After
함수 진입부에 direct_request 분기 추가:

```python
async def _slot_filling_default_partial(state: GraphState, has_date: bool, has_place: bool) -> GraphState:
    # FIX 4: direct_request는 부분 정보로도 카드 생성 — 사용자가 명시적으로 요청했기 때문
    if state.get("trigger_reason") == "direct_request":
        if has_date:
            # date만 있어도 단일 슬롯 vote_card 또는 maedeup 카드로 진행
            if not state.get("headcount"):
                state["headcount"] = 2  # 보수적 기본값
            if not state.get("meeting_type"):
                state["meeting_type"] = "모임"
            state["all_slots_filled"] = True
            state["missing_slots"] = []
            state["awaiting_user_reply"] = False
            state["wait_timed_out"] = False
            state["message_count_since_last_trigger"] = 0
            state["status"] = "slots_filled_with_defaults"
            logger.info("[FIX-4] direct_request with date-only → forcing card creation")
            return state
        if has_place:
            # place만 있어도 location_first로 진행 (이미 partial 후속 분기에서 처리되지만 명시적)
            state["is_location_first"] = True
            state["all_slots_filled"] = True
            state["missing_slots"] = []
            state["awaiting_user_reply"] = False
            state["wait_timed_out"] = False
            state["message_count_since_last_trigger"] = 0
            state["status"] = "location_first_ready"
            logger.info("[FIX-4] direct_request with place-only → forcing card creation")
            return state

    # 기존 로직 (auto-trigger 경로)
    if has_date and not has_place:
        # ... 기존 코드 그대로
```

#### 효과
- "내일 6시 잡아줘" → ❌ 카드 안 뜸 → ✅ vote_card 또는 maedeup 카드 뜸
- "강남에서 추천해줘" → place_recommendation 진행 (이미 동작했지만 명시적 보장)
- 시연 외 일반 입력 ~70% 살림 (이전 분석 추정)

#### Pre-conditions
- [ ] Fix 1, 2 적용 완료 (latency 줄여놓고 UX fix)
- [ ] 시연 자동화 baseline 통과 확인 (회귀 비교용)

#### Self-check
```bash
# 1. AST 검증
python -c "
import ast
src = open('backend/app/services/pipeline/nodes/slot.py', encoding='utf-8').read()
tree = ast.parse(src)
# direct_request 분기 추가 확인
assert 'direct_request' in src, 'FIX 4 branch not added'
# slot_filling_turns 기존 로직 보존 확인 (다른 분기)
assert 'slot_filling_turns' in src, 'existing logic broken'
print('Fix 4 syntax OK')
"

# 2. 시연 자동화 회귀 검증 (사용자 부탁)
# python .gstack-demo.py --fast → ACT 1~5 통과해야 success
```

#### 위험 + Mitigation
- **위험 1**: 시연 시나리오는 stalemate/conclusion/all_members 경로 → direct_request 분기 추가는 영향 0. **단** trigger_reason 매핑 변경되지 않음을 확인.
- **위험 2**: headcount 기본값 2가 합리적인지. 일반적으로 친구 모임 2~4명. 2로 시작해도 카드 UI에서 조정 가능. 안전.
- **위험 3**: 회귀 케이스 — 기존 direct_request에서 partial 의도로 ack만 받던 케이스 있는지. 인풋 카탈로그 Q1 결정 필요 ("single-slot vote_card 정책") — 일단 카드 발행하는 게 더 안전.

#### 시연 자동화 검증 절차
```bash
# 분기 추가 후
docker restart maedeup-api
sleep 5
python .gstack-browser-launch.py    # 터미널 1
python .gstack-demo.py --fast        # 터미널 2
# ACT 1~5 모두 통과해야 commit OK
```

#### 롤백
```bash
git revert HEAD
docker restart maedeup-api
```

---

### Fix 5. `call_gemini` timeout 추가 — **worst case 차단**

**위치**: `backend/app/services/gemini.py`
**위험도**: 🟢 Low
**우선순위**: P0 (운영 안정성)

#### 문제
`asyncio.to_thread(model.generate_content, content)`에 timeout 없음. Gemini SDK hang 시 백엔드 전체 멈춤. rate limit 시에도 30초+ 대기 후 fail.

#### Before
```python
async def call_gemini(content: str) -> str:
    if not settings.GEMINI_API_KEY.strip():
        return ""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(...)
    try:
        response = await asyncio.to_thread(model.generate_content, content)
    except (ResourceExhausted, GoogleAPICallError):
        return ""
    except Exception:
        return ""
    # ...
```

#### After
```python
async def call_gemini(content: str, timeout: float = 15.0) -> str:
    """Gemini API를 호출하고 응답 텍스트를 반환합니다.

    Args:
        content: prompt 텍스트
        timeout: SDK 호출 timeout (초). 기본 15s.
            - quick_classify 같이 짧은 호출은 호출처에서 명시 (1.5~3s 권장).
            - 일반 호출은 기본값 사용.
    """
    if not settings.GEMINI_API_KEY.strip():
        return ""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        system_instruction=(
            "당신은 매듭(Maedeup) AI 어시스턴트입니다. 한국인 사용자들의 모임 일정과 "
            "장소 조율을 돕는 친근하고 전문적인 어시스턴트입니다. 항상 한국어로 "
            "간결하고 자연스럽게 답변하세요."
        ),
    )
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, content),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return ""
    except (ResourceExhausted, GoogleAPICallError):
        return ""
    except Exception:
        return ""
    # ... (이하 기존 코드)
```

#### 효과
- worst case: ∞ → 15s 보장
- rate limit 시 백엔드 hang 방지
- 운영 안정성 ↑

#### Pre-conditions
- [ ] `quick_classify.py`는 자체 `asyncio.wait_for(call_gemini(...), timeout=1.5)` 사용 중. 이 wrapper와 충돌 없는지 확인 (안 충돌 — 더 짧은 timeout 적용)

#### Self-check
```bash
grep -n "asyncio.wait_for" backend/app/services/gemini.py
# 기대: 1개 match

# quick_classify 호환성 검증
grep -n "wait_for.*call_gemini" backend/app/services/quick_classify.py
# 기대: 1개 match (기존 1.5s timeout 그대로 동작)
```

#### 위험 + Mitigation
- **위험**: 15s timeout이 너무 짧을 가능성. Gemini 정상 응답 보통 1~5s. 15s면 충분.
- **위험**: rate limit 시 timeout vs ResourceExhausted exception 충돌. 둘 다 빈 문자열 반환 → 동작 동일.

#### 롤백
```bash
git revert HEAD
```

---

### Fix 6 (선택). `_load_meeting_preferences` state 캐싱 — **−100ms (재호출 시)**

**위치**: `backend/app/services/pipeline/nodes/slot.py:60` (slot_filling 진입부)
**위험도**: 🟢 Low
**우선순위**: P2 (효과 작음, 선택)

#### 문제
slot_filling이 `_load_meeting_preferences` 호출 → place_recommendation은 별도로 `_get_room_member_*` 호출. 같은 멤버 정보 일부 중복 lookup.

#### Before
```python
async def slot_filling(state: GraphState) -> GraphState:
    # ...
    _update_slot_state(state, state.get("extracted_entities", {}))
    pref_data = await _load_meeting_preferences(state)
    _enrich_with_preferences(state, pref_data)
    # ...
```

#### After
```python
async def slot_filling(state: GraphState) -> GraphState:
    # ...
    _update_slot_state(state, state.get("extracted_entities", {}))
    # FIX 6: state에 캐싱해서 place_recommendation에서 재사용
    if "_meeting_preferences_cache" not in state:
        state["_meeting_preferences_cache"] = await _load_meeting_preferences(state)
    pref_data = state["_meeting_preferences_cache"]
    _enrich_with_preferences(state, pref_data)
    # ...
```

#### 효과
- 같은 run에서 두 번째 lookup 시 0초
- 효과 작음 (~100ms)

#### 위험 + Mitigation
- **위험**: state 캐시 key가 다른 노드와 충돌. `_` prefix + 명시적 이름 사용.
- **위험**: GraphState TypedDict에 새 key 추가 — `total=False`라 OK.

#### 결정
Fix 6은 효과 작아서 **시간 남으면 적용**. 시연 D-day 압박 있으면 폐기.

---

## 4. 적용 순서 (Phase)

### Phase 0 — 환경 준비
- [ ] PR #3 (refactor/pipeline-split) 검증 통과 확인
- [ ] 시연 자동화 baseline 통과 (Fix 4 회귀 비교용)
- [ ] 새 브랜치 `perf/latency-reduction` 생성 (base: refactor/pipeline-split)

### Phase 1 — 안전한 latency fix (Fix 1+2+5)
1. **Fix 1** (`_parse_natural_date` 캐시) — commit `perf: _parse_natural_date 메모이즈`
2. **Fix 2** (multi-date 병렬화) — commit `perf: entity multi-date hint 병렬화`
3. **Fix 5** (Gemini timeout) — commit `perf(safety): call_gemini 15s timeout`

각 Fix 후:
- AST self-check
- (선택) 시연 자동화 1회

**예상 효과**: latency 8~15s → 4~9s (-3~6s)

### Phase 2 — UX 핵심 (Fix 4) ⭐
4. **Fix 4** (`_slot_filling_default_partial` direct_request) — commit `fix(slot): direct_request에서 부분 정보로도 카드 생성`

후:
- **시연 자동화 ACT 1~5 필수 통과** (사용자 부탁)
- 통과하면 commit + push
- 깨지면 `git revert HEAD`

**예상 효과**: "내일 6시 잡아줘" 같은 입력에서 카드 생성 (현재는 안 됨)

### Phase 3 (선택) — Fix 6
5. **Fix 6** (meeting_preferences state 캐시) — 시간 있으면

### Phase 4 — PR
- 전체 fix들을 별도 PR (`perf/latency-reduction` → `refactor/pipeline-split`)
- 또는 PR #3에 추가 commit으로 누적 (단순 워크플로)

---

## 5. Self-Check Protocol

### Phase 1 끝 검증
```bash
# 모든 변경 syntax OK
python -c "
import ast
for path in [
    'backend/app/services/pipeline/helpers/dates.py',
    'backend/app/services/pipeline/nodes/entity.py',
    'backend/app/services/gemini.py',
]:
    ast.parse(open(path, encoding='utf-8').read())
    print(f'{path}: OK')
"

# 핵심 패턴 확인
grep -q "lru_cache" backend/app/services/pipeline/helpers/dates.py && echo "Fix 1 ✓"
grep -q "asyncio.gather.*_resolve_one\|asyncio.gather.*hint" backend/app/services/pipeline/nodes/entity.py && echo "Fix 2 ✓"
grep -q "asyncio.wait_for" backend/app/services/gemini.py && echo "Fix 5 ✓"
```

### Phase 2 끝 검증
```bash
# Fix 4 패턴 확인
grep -q "FIX-4\|FIX 4" backend/app/services/pipeline/nodes/slot.py && echo "Fix 4 ✓"
grep -q 'trigger_reason.*direct_request' backend/app/services/pipeline/nodes/slot.py && echo "branch ✓"

# 시연 자동화 (사용자 부탁)
echo "시연 자동화 부탁: python .gstack-demo.py --fast → ACT 1~5 통과 확인"
```

---

## 6. 위험 + Rollback

### Level 1: Fix 단위 롤백
```bash
git revert HEAD
docker restart maedeup-api
```

### Level 2: Phase 단위 롤백
```bash
# Phase 1 시작 commit 검색
git log --oneline | grep "Phase 1 start"
git reset --hard <commit_sha>
docker restart maedeup-api
```

### Level 3: 브랜치 폐기
```bash
git checkout refactor/pipeline-split
git branch -D perf/latency-reduction
```

---

## 7. Resume Protocol — 작업 중단 후 자가진단

Claude가 컨텍스트 잃었을 때:

```bash
# Step 1: 브랜치
git branch --show-current
# 기대: perf/latency-reduction

# Step 2: 최근 commit
git log --oneline | head -10
# Fix 키워드 검색해서 어디까지 완료됐는지

# Step 3: 각 Fix 패턴 확인 (어느 Fix까지 적용됐나)
grep -q "lru_cache" backend/app/services/pipeline/helpers/dates.py && echo "Fix 1 done"
grep -q "asyncio.gather.*_resolve_one" backend/app/services/pipeline/nodes/entity.py && echo "Fix 2 done"
grep -q "asyncio.wait_for" backend/app/services/gemini.py && echo "Fix 5 done"
grep -q "FIX-4" backend/app/services/pipeline/nodes/slot.py && echo "Fix 4 done"
grep -q "_meeting_preferences_cache" backend/app/services/pipeline/nodes/slot.py && echo "Fix 6 done"

# Step 4: 다음 Fix Pre-conditions 점검 → 진행
```

---

## 8. Definition of Done

전체 Fix 적용 완료 조건 (5개 다 통과):

- [ ] Fix 1: `lru_cache` 적용 + AST syntax OK
- [ ] Fix 2: `asyncio.gather` multi-date 적용
- [ ] Fix 5: `asyncio.wait_for` timeout 적용
- [ ] Fix 4: direct_request 분기 + 시연 자동화 ACT 1~5 통과
- [ ] (선택) Fix 6: state 캐시 적용
- [ ] 모든 commit push 완료
- [ ] PR 생성 (또는 PR #3에 추가 commit) + 머지 가능 상태

---

## 9. 예상 효과 요약

| Fix | 효과 | 위험 | 우선순위 |
|---|---|---|---|
| 1. `_parse_natural_date` 캐시 | −1.5s/호출 | 🟢 | P0 |
| 2. multi-date 병렬화 | N개 → max(1.5s) | 🟢 | P0 |
| 3. ~~place 멤버 3개 병렬화~~ | ~~−150ms~~ | 🟡 AsyncSession race | **폐기** |
| 4. direct_request 카드 강제 | UX 100% (현재 카드 안 뜸) | 🟡 | P0 |
| 5. Gemini timeout | worst case ∞ → 15s | 🟢 | P0 |
| 6. preferences state 캐시 | −100ms (재호출 시) | 🟢 | P2 (선택) |

**Phase 1 (Fix 1+2+5)**: latency 8~15s → 4~9s
**Phase 2 (Fix 4)**: UX 임팩트 100% (시연 외 일반 입력 살림)
**Phase 3 (Fix 6, 선택)**: 추가 −100ms

---

## 한 줄 요약

> **Fix 1 (캐시) + Fix 2 (병렬) + Fix 5 (timeout) → latency 4~6s 단축**, **Fix 4 (UX 핵심) → "내일 6시" 카드 미생성 해결**. 5 fix × 1 commit, 각 commit마다 syntax check + Fix 4는 시연 자동화 통과 필수. Fix 3은 AsyncSession race 위험으로 폐기.
