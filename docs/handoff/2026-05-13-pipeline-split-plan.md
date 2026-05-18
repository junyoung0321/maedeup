# langgraph_pipeline.py 분할 작업 매뉴얼 (v2 — Claude 작업용)

작성: 2026-05-13
작업자: **Claude** (사용자 검토하에)
대상: [backend/app/services/langgraph_pipeline.py](../../backend/app/services/langgraph_pipeline.py) — **5,301줄 / 107 함수 / 23 모듈 레벨 상수 / 1 파일**
완료 목표: 2026-05-15 (시연 D-5)

---

## 🔖 이 문서 사용 방법 (Claude 필독)

이 문서는 단순 계획서가 아니라 **작업 매뉴얼**입니다. Claude는 작업 중 반드시 다음 프로토콜을 따른다:

### A. 매 Phase 시작 전
1. **§13 Resume Protocol**을 실행해 현재 상태를 자가진단
2. 해당 Phase의 **Pre-conditions**가 모두 충족되었는지 확인
3. Pre-conditions 미충족 시 → 직전 Phase로 돌아가 누락 작업 완료

### B. 매 Step 끝난 직후
4. 해당 Step의 **Self-Check 명령**을 실행 (§12)
5. 기대 출력과 실제 출력 일치 확인
6. 불일치 시 **즉시 멈추고** 원인 분석. 작업 계속 진행 금지.

### C. 매 Phase 끝
7. **Phase Verification Suite** 실행 (§12.X)
8. 시연 자동화 (§11.4) 통과 확인
9. **반드시 git commit** (§9 Rollback)
10. 사용자에게 진행 상황 보고 + 다음 Phase 진행 승인 받기

### D. 컨텍스트 초기화/단절 시
11. 이 문서 + §13 Resume Protocol만으로 어디까지 했는지 복구 가능해야 함
12. 그래서 매 Phase마다 "완료 markers" (어떤 파일이 존재 + 어떤 함수가 어디 있는지)가 명시되어 있음

### E. 절대 금지
- ❌ 함수 **로직 수정** (한 글자도 바꾸지 않음 — 순수 이동만)
- ❌ 함수 **이름 변경**
- ❌ **import 경로 추측** (반드시 grep으로 검증)
- ❌ **시연 자동화 미통과 상태로 다음 Phase 진행**
- ❌ **Phase 중간 commit 없이 다음 Phase 시작**

---

## 1. 검증된 사실 (Snapshot, 2026-05-13)

### 1.1 파일 통계 (확인됨)
- 라인: **5,301**
- 함수: **107** (def 76 + async def 31)
- 클래스/TypedDict: **2** (`MessageRecord`, `GraphState`)
- 모듈 레벨 상수: **23개** (KST, GOOGLE_FREEBUSY_URL, ..., GRAPH)
- 외부 import: **4 파일 / 6 심볼**

### 1.2 외부 import 인벤토리 (grep 검증됨)

| 사용처 | 라인 | import 심볼 |
|---|---|---|
| `backend/app/api/ws/agent.py` | 24 | `KST`, `_analyze_conversation`, `run_pipeline` |
| `backend/app/api/routes/meetings.py` | 29 | `memory_extraction`, `suggest_alternative_slots` |
| `backend/app/api/routes/rooms.py` | 741 | `run_pipeline` (inline) |
| `backend/scripts/qa_privacy_boundary.py` | 156 | `run_pipeline` (inline) |

**외부 노출되는 심볼 6개 (unique)**: `KST`, `run_pipeline`, `_analyze_conversation`, `memory_extraction`, `suggest_alternative_slots`, *(없음 — MessageRecord/GraphState는 외부 사용 X — grep 검증)*

### 1.3 시연 자동화 (실행 명령 검증됨)
```bash
# 사전 셋업 (1회): 
#   1) docker compose up -d
#   2) Chrome → localStorage.getItem('auth_token') → .gstack-demo-token 파일에 저장

# 매 검증 실행:
python .gstack-browser-launch.py   # 터미널 1
python .gstack-demo.py --fast      # 터미널 2 (분할 작업 검증용)
```

검증 시나리오: ACT 1 (방 생성+선호도) → ACT 2 (자동 트리거) → ACT 4 (vote 확정) → ACT 5 (장소 추천+확정)

### 1.4 의존성 호출 빈도 Top 20 (grep 검증)

이게 가장 자주 호출되는 헬퍼. helpers/ 위치 신중 선택:

| 호출수 | 헬퍼 | 새 위치 |
|---:|---|---|
| 16 | `_has_node_error` | `helpers/messaging.py` |
| 15 | `_emit_assistant_message` | `helpers/messaging.py` |
| 12 | `_room_id_as_int` | `helpers/formatting.py` |
| 11 | `_parse_iso_datetime` | `helpers/dates.py` |
| 10 | `_handle_node_exception` | `helpers/messaging.py` |
| 9 | `_normalize_preferred_times` | `helpers/slot_state.py` |
| 9 | `_filter_out_blocked` | `helpers/slots.py` |
| 8 | `_find_free_slots` | `helpers/slots.py` |
| 7 | `search_place` | `nodes/place.py` (또는 helpers? — §6 함정 #7 참고) |
| 7 | `_update_slot_state` | `helpers/slot_state.py` |
| 7 | `_get_korean_holiday` | `helpers/dates.py` |
| 7 | `_format_slot_label` | `helpers/formatting.py` |
| 6 | `_user_display_name` | `helpers/formatting.py` |
| 6 | `_serialize_context` | `state.py` |
| 6 | `_is_weekend` | `helpers/dates.py` |
| 6 | `_get_user_busy_periods` | `helpers/preferences.py` |
| 6 | `_filter_out_rejected` | `helpers/slots.py` |
| 6 | `_extract_korean_place_keyword` | `helpers/places.py` |
| 6 | `_build_preference_time_slots` | `helpers/slots.py` |

---

## 2. 새 디렉토리 구조 (확정)

```
backend/app/services/
├── langgraph_pipeline.py        ← 유지. 분할 후 내용 = re-export shim (~15줄)
└── pipeline/                    ← 신규 디렉토리
    ├── __init__.py              (빈 파일)
    ├── constants.py             (~30줄)   모듈 상수 12개 (KST 포함)
    ├── state.py                 (~280줄)  GraphState, MessageRecord, _default_state, 메시지 헬퍼
    ├── graph.py                 (~350줄)  _build_graph, run_pipeline, GRAPH, 라우터 5개
    ├── nodes/
    │   ├── __init__.py
    │   ├── intent.py            (~150줄)
    │   ├── entity.py            (~500줄)
    │   ├── slot.py              (~600줄)
    │   ├── function_call.py     (~150줄)
    │   ├── validation.py        (~120줄)
    │   ├── vote_card.py         (~200줄)
    │   ├── place.py             (~350줄)
    │   ├── maedeup.py           (~250줄)
    │   ├── memory.py            (~200줄)
    │   └── conversation_analyzer.py (~200줄)  ← `_analyze_conversation` + `suggest_alternative_slots`
    └── helpers/
        ├── __init__.py
        ├── dates.py             (~350줄)
        ├── places.py            (~150줄)
        ├── json_extract.py      (~100줄)
        ├── slots.py             (~400줄)
        ├── preferences.py       (~350줄)
        ├── messaging.py         (~200줄)
        ├── slot_state.py        (~150줄)
        └── formatting.py        (~120줄)
```

**합계**: 14개 모듈 + 1 shim. 약 3,800줄 (5,301보다 적은 이유: import 라인 중복 제거 후 추정).

---

## 3. 함수 → 파일 매핑 표 (완전판, 107개)

라인 범위는 **현재 langgraph_pipeline.py 기준** (Phase 진행 중 라인 번호는 변동). grep으로 정확한 함수 시그너처 검증 후 이동.

### 3.1 `pipeline/constants.py`

| 현재 라인 | 심볼 | 종류 |
|---:|---|---|
| 52 | `KST` | timezone |
| 53 | `GOOGLE_FREEBUSY_URL` | str |
| 54 | `WORK_HOUR_START` | int |
| 55 | `WORK_HOUR_END` | int |
| 56 | `SLOT_MINUTES` | int |
| 57 | `INTENT_CONFIDENCE_THRESHOLD` | float |
| 58~65 | `PREFERRED_TIME_RANGES` | dict |
| 79 | `RECENT_MESSAGE_LIMIT` | int |
| 80 | `SLOT_KEYS` | tuple |
| 81 | `MAX_SLOT_FILLING_TURNS` | int |
| 82 | `SUMMARY_TRIGGER_INTERVAL` | int |
| 83 | `FRIENDLY_ERROR_MESSAGE` | str |
| 1460 | `_SOCIAL_RECENT_LIMIT` | int |
| 1461 | `_SOCIAL_SUMMARY_THRESHOLD` | int |

### 3.2 `pipeline/state.py`

| 현재 라인 | 심볼 | 종류 |
|---:|---|---|
| 88~94 | `MessageRecord` | TypedDict |
| 96~174 | `GraphState` | TypedDict |
| 177~254 | `_default_state` | func |
| 256~280 | `_normalize_message` | func |
| 282~289 | `_split_message_context` | func |
| 291~295 | `_message_to_text` | func |
| 297~310 | `_serialize_context` | func |

### 3.3 `pipeline/helpers/dates.py`

| 현재 라인 | 심볼 |
|---:|---|
| 67 | `_KR_HOLIDAYS` (상수) |
| 70~74 | `_get_korean_holiday` |
| 76~77 | `_is_weekend` |
| 554~559 | `_is_iso_date_hint` |
| 561~565 | `_is_specific_iso_date` |
| 567~599 | `_resolve_rejected_date` |
| 601~635 | `_detect_multi_date_options` |
| 637~651 | `_weekday_from_korean` |
| 661~666 | `_next_weekday` |
| 668~752 | `_fallback_parse_natural_date` |
| 754~793 | `_normalize_parsed_natural_date` |
| 795~827 | `_parse_natural_date` (Gemini 호출 — call_gemini import 필요) |
| 1323~1333 | `_parse_iso_datetime` |
| 1621 | `_DATE_RANGE_RE` (상수) |
| 1622 | `_ISO_DATE_RE` (상수) |
| 1625~1653 | `_expand_date_hint` |

### 3.4 `pipeline/helpers/places.py`

| 현재 라인 | 심볼 |
|---:|---|
| 959~966 | `_WELL_KNOWN_PLACES` (상수) |
| 969~971 | `_KOREAN_PLACE_PATTERN` (상수) |
| 975~989 | `_CUISINE_TRIGGERS` (상수) |
| 991~1002 | `_CUISINE_CATEGORY_KEYWORDS` (상수) |
| 1004~1009 | `_PLACE_INTENT_PATTERN` (상수) |
| 1011~1021 | `_OTHER_ENTITY_SIGNAL_PATTERN` (상수) |
| 1023 | `_REJECT_SIGNAL_PATTERN` (상수) |
| 1029~1036 | `_detect_cuisine_type` |
| 1039~1047 | `_filter_places_by_cuisine` |
| 1050~1066 | `_extract_korean_place_keyword` |
| 1239~1248 | `_resolve_place_coord` (kakao_maps import) |
| 2320~2326 | `_contains_disliked_keyword` |
| 436~456 | `_resolve_place_hint` |

### 3.5 `pipeline/helpers/json_extract.py`

| 현재 라인 | 심볼 |
|---:|---|
| 482~501 | `_extract_json_object` |
| 503~524 | `_extract_json_array` |
| 526~552 | `_extract_loose_json_object` |

### 3.6 `pipeline/helpers/formatting.py`

| 현재 라인 | 심볼 |
|---:|---|
| 458~471 | `_format_slot_label` |
| 473~480 | `_format_confirmed_time` |
| 829~851 | `_infer_time_bucket` |
| 942~947 | `_room_id_as_int` |
| 949~951 | `_user_calendar_key` |
| 953~957 | `_user_display_name` |

### 3.7 `pipeline/helpers/slot_state.py`

| 현재 라인 | 심볼 |
|---:|---|
| 358~366 | `_coerce_headcount` |
| 368~407 | `_update_slot_state` |
| 409~414 | `_has_meaningful_slot_progress` |
| 653~659 | `_coerce_bool` |
| 853~868 | `_build_flexible_time_options` |
| 870~872 | `_normalize_preferred_time` |
| 874~883 | `_normalize_preferred_times` |
| 885~904 | `_preference_score_for_start` |
| 1313~1321 | `_slot_snapshot` |

### 3.8 `pipeline/helpers/messaging.py`

| 현재 라인 | 심볼 |
|---:|---|
| 312~356 | `_compress_message_history` |
| 416~418 | `_has_node_error` |
| 420~434 | `_handle_node_exception` |
| 1250~1311 | `_emit_assistant_message` |

### 3.9 `pipeline/helpers/slots.py`

| 현재 라인 | 심볼 |
|---:|---|
| 906~940 | `_build_time_option_slots` |
| 1335~1391 | `_get_user_busy_periods` |
| 1393~1458 | `_find_free_slots` |
| 1584~1608 | `_load_blocked_dates` |
| 1610~1619 | `_filter_out_blocked` |
| 1655~1667 | `_filter_out_rejected` |
| 1669~1709 | `_load_busy_by_user_for_state` |
| 1711~1936 | `get_free_slots` (큰 함수, 225줄) |
| 3420~3504 | `_build_multi_date_slots` |
| 3506~3531 | `_is_busy_during` |
| 3533~3668 | `_build_preference_time_slots` |

### 3.10 `pipeline/helpers/preferences.py`

| 현재 라인 | 심볼 |
|---:|---|
| 1464~1582 | `_load_social_context` |
| 1938~1981 | `_get_room_member_food_preferences` |
| 1983~2052 | `_get_room_member_constraints` |
| 2054~2079 | `_build_group_constraints_summary` |
| 2081~2148 | `_get_room_member_constraints_named` |
| 2150~2218 | `_build_named_constraints_summary` |
| 2220~2318 | `_load_meeting_preferences` |

### 3.11 `pipeline/nodes/intent.py`

| 현재 라인 | 심볼 |
|---:|---|
| 2453~2519 | `_try_template_response` |
| 2521~2590 | `general_response` |
| 2592~2677 | `intent_detection` |

### 3.12 `pipeline/nodes/entity.py`

| 현재 라인 | 심볼 |
|---:|---|
| 1069~1138 | `_pattern_extract_entities` |
| 1140~1237 | `_extract_entities_from_context` |
| 2679~3027 | `entity_extraction` (349줄, 가장 큼) |

### 3.13 `pipeline/nodes/slot.py`

| 현재 라인 | 심볼 |
|---:|---|
| 3029~3055 | `slot_filling` |
| 3058~3091 | `_enrich_with_preferences` |
| 3093~3189 | `_slot_filling_stalemate` |
| 3191~3214 | `_slot_filling_conclusion` |
| 3216~3279 | `_slot_filling_all_members` |
| 3281~3311 | `_slot_filling_default` |
| 3313~3324 | `_slot_filling_default_multi_date` |
| 3327~3344 | `_slot_filling_default_confirmed` |
| 3346~3365 | `_slot_filling_default_with_defaults` |
| 3367~3417 | `_slot_filling_default_partial` |

### 3.14 `pipeline/nodes/function_call.py`

| 현재 라인 | 심볼 |
|---:|---|
| 3670~3801 | `function_calling` |

### 3.15 `pipeline/nodes/validation.py`

| 현재 라인 | 심볼 |
|---:|---|
| 3803~3893 | `supervisor_validation` |

### 3.16 `pipeline/nodes/vote_card.py`

| 현재 라인 | 심볼 |
|---:|---|
| 3896~3905 | `_card_payload_meeting_id` |
| 3907~4021 | `_ensure_pending_meeting_id` |
| 4023~4148 | `vote_card_creation` |

### 3.17 `pipeline/nodes/place.py`

| 현재 라인 | 심볼 |
|---:|---|
| 2329~2361 | `_run_place_self_correction` |
| 2363~2439 | `search_place` |
| 4150~4410 | `place_recommendation` |

### 3.18 `pipeline/nodes/maedeup.py`

| 현재 라인 | 심볼 |
|---:|---|
| 2442~2451 | `_register_google_calendar` |
| 4412~4563 | `maedeup_card_creation` |

### 3.19 `pipeline/nodes/memory.py`

| 현재 라인 | 심볼 |
|---:|---|
| 4565~4574 | `_is_empty_personal_data` |
| 4576~4605 | `_publish_personal_data_updates` |
| 4607~4624 | `_spawn_memory_extraction_async` |
| 4626~4770 | `memory_extraction` |

### 3.20 `pipeline/nodes/conversation_analyzer.py`

| 현재 라인 | 심볼 |
|---:|---|
| 5042~5208 | `_analyze_conversation` |
| 5210~끝 | `suggest_alternative_slots` |

### 3.21 `pipeline/graph.py`

| 현재 라인 | 심볼 |
|---:|---|
| 4772~4786 | `_route_from_start` |
| 4788~4796 | `_route_after_intent` |
| 4799~4814 | `_route_after_slot_filling` |
| 4817~4856 | `_route_after_validation` |
| 4859~4868 | `_route_after_vote_card_creation` |
| 4871~4884 | `_route_after_place_recommendation` |
| 4887~4961 | `_build_graph` |
| 4964 | `GRAPH` (모듈 레벨 — `_build_graph()` 호출 결과) |
| 4967~5040 | `run_pipeline` |

### 3.22 `langgraph_pipeline.py` (shim, Phase 5 후 내용)

```python
"""Compatibility shim. 실제 구현은 pipeline/ 하위로 이동됨.

신규 코드는 `from app.services.pipeline.* import ...` 사용 권장.
이 파일은 외부 import 호환성만을 위한 re-export.
"""
from app.services.pipeline.constants import KST
from app.services.pipeline.graph import run_pipeline
from app.services.pipeline.nodes.conversation_analyzer import (
    _analyze_conversation,
    suggest_alternative_slots,
)
from app.services.pipeline.nodes.memory import memory_extraction

__all__ = [
    "KST",
    "run_pipeline",
    "_analyze_conversation",
    "memory_extraction",
    "suggest_alternative_slots",
]
```

---

## 4. 의존성 Layer 분석 (Phase 순서 결정 근거)

순환 import 방지 + 안전한 이동 순서:

```
Layer 0 (외부만 의존, 가장 안전)
├── constants.py            ← stdlib + zoneinfo + holidays
├── helpers/json_extract.py ← stdlib (re, json) 만
├── helpers/places.py       ← stdlib + (kakao_maps for _resolve_place_coord)
├── helpers/dates.py        ← stdlib + holidays + (call_gemini for _parse_natural_date)
└── helpers/formatting.py   ← stdlib + User 모델

Layer 1 (Layer 0 + DB models 의존)
└── state.py                ← GraphState, MessageRecord. Layer 0 헬퍼 일부 import 가능

Layer 2 (Layer 0+1 의존, 노드 함수 내부 보조)
├── helpers/slot_state.py   ← state.GraphState 의존
├── helpers/messaging.py    ← state + AsyncSessionLocal
├── helpers/slots.py        ← state + DB models + messaging
└── helpers/preferences.py  ← state + DB models

Layer 3 (모든 헬퍼 + state 의존, 노드 함수)
└── nodes/*.py              ← 9 + 1 (conversation_analyzer)

Layer 4 (모든 노드 의존)
└── graph.py                ← 노드 9개 import + 라우터 정의 + GRAPH 컴파일

Layer 5 (shim)
└── langgraph_pipeline.py   ← re-export 5개 심볼
```

**금기**: nodes/*는 서로를 import하지 않는다. 노드 간 공유 헬퍼는 모두 helpers/로.

---

## 5. Phase 작업 순서 + Pre/Post 조건

### Phase 0 — 작업 환경 준비

**Pre-conditions**:
- [ ] 사용자에게 작업 시작 승인 받음
- [ ] 팀원이 langgraph_pipeline.py를 안 만지는 상태 확인 (사용자가 카톡으로 확인)
- [ ] 시연 자동화 통과 = 기준점 (baseline) 확보

**작업**:
```bash
# 1. 기준점 commit
git status   # → clean이어야 함. 아니면 stash
git log --oneline -3   # 현재 위치 기록

# 2. 새 브랜치
git checkout -b refactor/pipeline-split

# 3. baseline 시연 자동화 실행 (사용자가 직접 — docker + chromium 필요)
# 사용자 확인: "ACT 1~5 통과" 메시지
```

**Post-conditions** (`완료 markers`):
- [ ] `git branch --show-current` → `refactor/pipeline-split`
- [ ] `git status` → clean
- [ ] 시연 자동화 baseline 통과 확인됨

---

### Phase 1 — 디렉토리 + 빈 모듈 생성

**Pre-conditions**:
- [ ] Phase 0 완료
- [ ] `pipeline/` 디렉토리 미존재 (`ls backend/app/services/pipeline` → 에러여야 정상)

**작업**:
```bash
cd backend/app/services
mkdir -p pipeline/nodes pipeline/helpers
touch pipeline/__init__.py pipeline/nodes/__init__.py pipeline/helpers/__init__.py
touch pipeline/constants.py pipeline/state.py pipeline/graph.py
touch pipeline/nodes/intent.py pipeline/nodes/entity.py pipeline/nodes/slot.py
touch pipeline/nodes/function_call.py pipeline/nodes/validation.py
touch pipeline/nodes/vote_card.py pipeline/nodes/place.py
touch pipeline/nodes/maedeup.py pipeline/nodes/memory.py
touch pipeline/nodes/conversation_analyzer.py
touch pipeline/helpers/dates.py pipeline/helpers/places.py
touch pipeline/helpers/json_extract.py pipeline/helpers/slots.py
touch pipeline/helpers/preferences.py pipeline/helpers/messaging.py
touch pipeline/helpers/slot_state.py pipeline/helpers/formatting.py
```

**Self-check**:
```bash
find backend/app/services/pipeline -type f -name '*.py' | sort | wc -l
# 기대: 22 (15 모듈 + 3 __init__ + 4 추가... 정확히 계산하자)
# 실제: pipeline/__init__.py + pipeline/constants.py + pipeline/state.py + pipeline/graph.py
#      + pipeline/nodes/__init__.py + 10 노드 모듈
#      + pipeline/helpers/__init__.py + 8 헬퍼 모듈
# = 1 + 3 + 1 + 10 + 1 + 8 = 24 파일
```

**Post-conditions**:
- [ ] 24개 빈 파일 생성됨
- [ ] git commit: `chore(refactor): Phase 1 - pipeline 디렉토리 골격`

---

### Phase 2 — Layer 0 헬퍼 이동 (5개 파일)

**Pre-conditions**:
- [ ] Phase 1 완료, 빈 파일 24개 존재
- [ ] `langgraph_pipeline.py` 라인 카운트 = **5,301** (`wc -l` 확인)

**Step 2.1**: `constants.py` 채우기
- **이동 대상**: §3.1 표의 14개 심볼
- **원본 파일에서**: **삭제하지 않음** (Phase 5에서 일괄 정리)
- 파일 상단 import 추가:
  ```python
  from zoneinfo import ZoneInfo
  ```

**Step 2.2**: `helpers/json_extract.py` 채우기
- **이동 대상**: §3.5 표의 3개 함수
- import: `import json`, `import re`, `from typing import Any`

**Step 2.3**: `helpers/formatting.py` 채우기
- **이동 대상**: §3.6 표의 6개 함수
- import: `from datetime import datetime`, `from app.models.user import User`

**Step 2.4**: `helpers/places.py` 채우기
- **이동 대상**: §3.4 표의 13개 항목 (상수 7 + 함수 6)
- import: `import re`, `from typing import Any`, `from app.services.kakao_maps import search_address`
- **주의**: `_resolve_place_hint`는 `state.get("place_hint")` 등 state 의존. **state.GraphState type import 필요** (forward reference로 `"GraphState"` 사용)

**Step 2.5**: `helpers/dates.py` 채우기
- **이동 대상**: §3.3 표의 16개 항목
- import: `import re`, `from datetime import datetime, timedelta`, `from zoneinfo import ZoneInfo`, `import holidays`, `from app.services.gemini import call_gemini`, `from app.services.pipeline.constants import KST`, `from app.services.pipeline.helpers.json_extract import _extract_json_object`
- **주의**: `_parse_natural_date`가 `call_gemini` 호출 + `_normalize_parsed_natural_date` 호출 → 같은 파일 내라 OK

**Self-check (Phase 2 완료 후)**:
```bash
# 1. import 가능한가
docker exec maedeup-api python -c "
from app.services.pipeline.constants import KST, INTENT_CONFIDENCE_THRESHOLD
from app.services.pipeline.helpers.json_extract import _extract_json_object
from app.services.pipeline.helpers.formatting import _room_id_as_int
from app.services.pipeline.helpers.places import _extract_korean_place_keyword, _WELL_KNOWN_PLACES
from app.services.pipeline.helpers.dates import _get_korean_holiday, _is_weekend
print('Phase 2 imports OK')
print(f'  KST type: {type(KST).__name__}')
print(f'  WELL_KNOWN_PLACES count: {len(_WELL_KNOWN_PLACES)}')
"
# 기대: 'Phase 2 imports OK' + 통계 출력

# 2. 원본 파일 변경 없음 (Phase 2에선 원본 안 건드림)
wc -l backend/app/services/langgraph_pipeline.py
# 기대: 5301 (변동 없음)

# 3. 시연 자동화 (원본 그대로니까 통과해야 함)
# 사용자 실행 → ACT 1~5 통과 확인
```

**Post-conditions**:
- [ ] 5개 모듈 (constants, json_extract, formatting, places, dates)이 함수/상수 채워짐
- [ ] 위 self-check import 통과
- [ ] 원본 langgraph_pipeline.py 변경 없음 (라인 = 5301)
- [ ] 시연 자동화 ACT 1~5 통과
- [ ] git commit: `refactor(pipeline): Phase 2 - Layer 0 헬퍼 5개 (constants, json_extract, formatting, places, dates)`

---

### Phase 3 — state.py + Layer 2 헬퍼 4개

**Pre-conditions**:
- [ ] Phase 2 완료, self-check 통과

**Step 3.1**: `state.py` 채우기
- **이동 대상**: §3.2 표의 7개 항목 (GraphState, MessageRecord, _default_state 등)
- import 주의 — circular 방지:
  ```python
  from typing import Any, TypedDict
  from datetime import datetime
  from sqlalchemy.ext.asyncio import AsyncSession
  from app.services.pipeline.constants import KST  # 안전 (constants → 외부 stdlib만)
  ```
- **금지**: `from app.services.pipeline.helpers.* import ...` ← Layer 2가 state import할 거라 순환

**Step 3.2**: `helpers/slot_state.py` 채우기
- **이동 대상**: §3.7 표의 9개 함수
- import: `from typing import Any`, `from datetime import datetime`, `from app.services.pipeline.state import GraphState`, `from app.services.pipeline.constants import SLOT_KEYS, PREFERRED_TIME_RANGES`

**Step 3.3**: `helpers/messaging.py` 채우기
- **이동 대상**: §3.8 표의 4개 함수
- import: `from app.services.pipeline.state import GraphState`, `from app.db.session import AsyncSessionLocal`, `from app.services.gemini import call_gemini`, `from app.services.pipeline.constants import FRIENDLY_ERROR_MESSAGE`

**Step 3.4**: `helpers/slots.py` 채우기
- **이동 대상**: §3.9 표의 11개 함수
- import: state + constants + messaging + 외부 (kakao, GCal 등)

**Step 3.5**: `helpers/preferences.py` 채우기
- **이동 대상**: §3.10 표의 7개 함수
- import: state + DB models + slots (for `_load_busy_by_user_for_state`)

**Self-check (Phase 3 완료 후)**:
```bash
docker exec maedeup-api python -c "
from app.services.pipeline.state import GraphState, MessageRecord, _default_state
from app.services.pipeline.helpers.slot_state import _update_slot_state, _normalize_preferred_times
from app.services.pipeline.helpers.messaging import _has_node_error, _emit_assistant_message
from app.services.pipeline.helpers.slots import get_free_slots, _filter_out_blocked
from app.services.pipeline.helpers.preferences import _load_meeting_preferences
print('Phase 3 imports OK')
print(f'  GraphState fields: {len(GraphState.__annotations__)}')
"
# 기대: 'Phase 3 imports OK' + GraphState fields 60+

# 원본 파일 변경 없음 확인
wc -l backend/app/services/langgraph_pipeline.py
# 기대: 5301
```

**Post-conditions**:
- [ ] state.py + 4 헬퍼 채워짐
- [ ] 위 import 통과
- [ ] 원본 라인 = 5301
- [ ] 시연 자동화 통과
- [ ] git commit: `refactor(pipeline): Phase 3 - state.py + Layer 2 헬퍼`

---

### Phase 4 — 노드 9개 + conversation_analyzer 이동

**Pre-conditions**:
- [ ] Phase 3 완료

**중요**: 노드 함수는 helper 의존성이 많아 import 정확히 잡아야 함. 각 노드별 step.

**작업 순서** (작은 노드 → 큰 노드):

**Step 4.1**: `nodes/validation.py` — `supervisor_validation` (1 함수, 91줄)
**Step 4.2**: `nodes/function_call.py` — `function_calling` (1 함수, 132줄)
**Step 4.3**: `nodes/intent.py` — 3 함수 (`general_response`, `intent_detection`, `_try_template_response`)
**Step 4.4**: `nodes/vote_card.py` — 3 함수 (vote_card_creation 외)
**Step 4.5**: `nodes/maedeup.py` — 2 함수
**Step 4.6**: `nodes/memory.py` — 4 함수
**Step 4.7**: `nodes/place.py` — 3 함수 (search_place, place_recommendation 등)
**Step 4.8**: `nodes/entity.py` — 3 함수 (entity_extraction 349줄 포함)
**Step 4.9**: `nodes/slot.py` — 10 함수 (slot_filling + 분기 9개)
**Step 4.10**: `nodes/conversation_analyzer.py` — 2 함수 (`_analyze_conversation`, `suggest_alternative_slots`)

**각 step 작업 후 자동 self-check 명령** (변수 `$NODE_FILE` = 옮긴 파일명):
```bash
# 예: Step 4.1 후
docker exec maedeup-api python -c "
from app.services.pipeline.nodes.validation import supervisor_validation
import asyncio, inspect
print(f'supervisor_validation: {inspect.iscoroutinefunction(supervisor_validation)}')
print('Step 4.1 OK')
"
```

**Phase 4 완료 self-check**:
```bash
docker exec maedeup-api python -c "
# 모든 노드 함수 import
from app.services.pipeline.nodes.intent import intent_detection, general_response
from app.services.pipeline.nodes.entity import entity_extraction
from app.services.pipeline.nodes.slot import slot_filling
from app.services.pipeline.nodes.function_call import function_calling
from app.services.pipeline.nodes.validation import supervisor_validation
from app.services.pipeline.nodes.vote_card import vote_card_creation
from app.services.pipeline.nodes.place import place_recommendation
from app.services.pipeline.nodes.maedeup import maedeup_card_creation
from app.services.pipeline.nodes.memory import memory_extraction
from app.services.pipeline.nodes.conversation_analyzer import _analyze_conversation, suggest_alternative_slots
print('All 11 node funcs importable')
"
```

**Post-conditions**:
- [ ] 10개 노드 모듈 다 채워짐
- [ ] 모든 노드 함수 import 통과
- [ ] 원본 라인 = 5301 (아직 안 건드림)
- [ ] **시연 자동화는 아직 통과 안 해도 됨** (원본 파일이 여전히 살아 있어서 동작 중)
- [ ] git commit: `refactor(pipeline): Phase 4 - 노드 10개 이동`

---

### Phase 5 — graph.py + shim 갈아끼우기 (위험도 ⚠️ 최고)

**Pre-conditions**:
- [ ] Phase 4 완료
- [ ] 모든 노드 import 통과

**Step 5.1**: `graph.py` 채우기 — §3.21 표의 9개 항목 (라우터 6 + _build_graph + GRAPH + run_pipeline)

import 순서 중요 (모듈 레벨 `GRAPH = _build_graph()` 실행 때문):
```python
# graph.py
from langgraph.graph import END, START, StateGraph
from app.services.pipeline.state import GraphState
from app.services.pipeline.nodes.intent import intent_detection, general_response
from app.services.pipeline.nodes.entity import entity_extraction
from app.services.pipeline.nodes.slot import slot_filling
from app.services.pipeline.nodes.function_call import function_calling
from app.services.pipeline.nodes.validation import supervisor_validation
from app.services.pipeline.nodes.vote_card import vote_card_creation
from app.services.pipeline.nodes.place import place_recommendation
from app.services.pipeline.nodes.maedeup import maedeup_card_creation
# (memory_extraction은 graph에서 빠짐 — fire-and-forget)
# 라우터 정의...
# _build_graph 정의...
GRAPH = _build_graph()
# run_pipeline 정의...
```

**Step 5.2**: `langgraph_pipeline.py` 갈아끼우기

원본 5,301줄 → §3.22 shim 14줄로 **완전 교체**.

```bash
# 백업
cp backend/app/services/langgraph_pipeline.py /tmp/langgraph_pipeline.py.backup
wc -l /tmp/langgraph_pipeline.py.backup
# 기대: 5301

# 갈아끼우기 (Write 도구로)
```

shim 내용:
```python
"""Compatibility shim. 실제 구현은 pipeline/ 하위로 이동됨.
신규 코드는 `from app.services.pipeline.* import ...` 사용 권장.
"""
from app.services.pipeline.constants import KST
from app.services.pipeline.graph import run_pipeline
from app.services.pipeline.nodes.conversation_analyzer import (
    _analyze_conversation,
    suggest_alternative_slots,
)
from app.services.pipeline.nodes.memory import memory_extraction

__all__ = [
    "KST",
    "run_pipeline",
    "_analyze_conversation",
    "memory_extraction",
    "suggest_alternative_slots",
]
```

**Step 5.3**: 컨테이너 재시작 + 외부 import 검증

```bash
docker compose restart maedeup-api
sleep 5
curl -fsS http://localhost:8000/health
# 기대: {"status": "ok", ...}

# 외부 import 검증
docker exec maedeup-api python -c "
from app.services.langgraph_pipeline import KST, run_pipeline, _analyze_conversation
from app.services.langgraph_pipeline import memory_extraction, suggest_alternative_slots
print('All 5 external imports OK from shim')
from app.api.ws.agent import run_pipeline as rp1
from app.api.routes.meetings import memory_extraction as me1, suggest_alternative_slots as sas1
print('Real-world import sites OK')
"
```

**Post-conditions**:
- [ ] `langgraph_pipeline.py` 라인 = ~14 (shim only)
- [ ] `wc -l backend/app/services/pipeline/**/*.py` 합계 = ~3,800 (원본 5,301에서 import 중복 제거 후)
- [ ] curl /health 통과
- [ ] **시연 자동화 ACT 1~5 통과** ← 가장 중요
- [ ] git commit: `refactor(pipeline): Phase 5 - graph.py + shim 갈아끼우기 (5301줄→14줄 shim)`

---

### Phase 6 — 최종 검증 + 함수 중복 검사

**Pre-conditions**:
- [ ] Phase 5 완료, 시연 자동화 통과

**작업**:
```bash
# 1. pytest 전체
cd backend && python -m pytest tests/ -v
# 기대: 모두 통과 (또는 알려진 실패와 동일)

# 2. 함수 중복 검사 (이중 정의 방지)
docker exec maedeup-api python -c "
import ast, glob
seen = {}
duplicates = []
for path in glob.glob('/app/app/services/pipeline/**/*.py', recursive=True):
    with open(path) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in seen:
                duplicates.append((node.name, path, seen[node.name]))
            seen[node.name] = path
print(f'Total functions in pipeline/: {len(seen)}')
print(f'Duplicates: {len(duplicates)}')
for d in duplicates: print(f'  {d}')
"
# 기대: Total functions: 107, Duplicates: 0

# 3. import graph 시각화 (선택)
docker exec maedeup-api python -c "
import importlib, sys
for mod in [
  'app.services.pipeline.constants',
  'app.services.pipeline.state',
  'app.services.pipeline.graph',
  'app.services.pipeline.nodes.entity',
  'app.services.pipeline.helpers.slots',
]:
  m = importlib.import_module(mod)
  print(f'{mod}: imported OK')
"
```

**Post-conditions**:
- [ ] pytest 통과
- [ ] 함수 107개 정확히 / 중복 0
- [ ] 시연 자동화 (사용자가 1회 더 실행) 통과
- [ ] git commit: `refactor(pipeline): Phase 6 - 최종 검증`
- [ ] PR 생성 (사용자 승인 후)

---

## 6. 함정 (Trap) 카탈로그 + Mitigation

### Trap 1: `_analyze_conversation` 외부 import (private 함수)
- agent.py:24가 `_analyze_conversation`을 import. private prefix(`_`) 무시
- **Mitigation**: `nodes/conversation_analyzer.py`에 두고 shim에서 re-export

### Trap 2: `GRAPH = _build_graph()` 모듈 레벨 실행
- 현재 [:4964](../../backend/app/services/langgraph_pipeline.py)에서 import 시점에 그래프 컴파일
- graph.py로 옮기면 노드 함수가 먼저 정의돼 있어야 함
- **Mitigation**: graph.py 상단에서 모든 노드 import → 그 다음 `_build_graph`, `GRAPH` 정의

### Trap 3: cuisine 상수 `_CUISINE_*` 위치
- entity_extraction (`places.py`)에서 cuisine 감지에 사용
- search_place (nodes/place.py)에서도 사용
- **Mitigation**: `helpers/places.py`에 통합 (state 의존 없음 → Layer 0)

### Trap 4: Circular import — nodes끼리
- nodes/*가 서로를 import하면 graph.py가 import할 때 cycle
- **Mitigation**: 노드 간 공유 함수는 모두 helpers/로. 노드는 helpers만 import.

### Trap 5: 모듈 레벨 사이드 이펙트
- `_KR_HOLIDAYS = holidays.KR(language="ko")` 객체 생성
- ML 모델 import 시도 (`try/except`)
- **Mitigation**: 원래 위치 (constants/dates/place) 그대로 모듈 레벨에 둠

### Trap 6: `_route_*` 함수가 노드 import?
- 라우터는 state만 보고 결정 — 노드 함수 직접 호출 안 함 (검증됨)
- **Mitigation**: graph.py에 둬도 안전

### Trap 7: `search_place` 위치 결정
- helper 같지만 nodes/place.py 안에서만 호출됨 + Gemini 호출 포함
- **Mitigation**: `nodes/place.py`에 둠 (노드 내부 헬퍼)

### Trap 8: state.py가 helpers를 import하면 안 됨
- helpers/slot_state.py가 state.GraphState를 import 함
- 만약 state.py가 helpers/* import하면 circular
- **Mitigation**: state.py는 `_serialize_context` 등 자체 헬퍼만 포함. 외부 헬퍼 의존 X.

### Trap 9: from __future__ import annotations
- 원본 파일 첫 줄. 이게 있어야 forward reference `"GraphState"` 사용 가능
- **Mitigation**: 모든 새 모듈 첫 줄에 동일 추가

### Trap 10: scheduling_round import (`from app.services import scheduling_round as sr`)
- 원본 L34. `sr.*` 호출이 어디 있는지 grep 필요
- **Mitigation**: 사용처 파악 후 해당 모듈에 import 추가

---

## 7. Git Commit 전략

각 Phase 끝에 commit. **Phase 4는 step마다 commit 권장** (노드 1개 옮길 때마다).

Commit 메시지 컨벤션:
```
refactor(pipeline): Phase N - <설명>

- 이동: <함수/모듈 목록>
- 검증: <self-check 통과 markers>
- 원본 파일 라인: <전후 변동>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## 8. 시간 예상 (Claude 작업 페이스)

| Phase | 작업 | 소요 | 누적 |
|---|---|---|---|
| 0 | 환경 준비 + baseline | 사용자 의존 | - |
| 1 | 디렉토리 생성 | 5분 | 5분 |
| 2 | Layer 0 헬퍼 (5 모듈) | 30분 | 35분 |
| 3 | state + Layer 2 (5 모듈) | 45분 | 1h 20m |
| 4 | 노드 10개 (step 10개) | 1.5h | 2h 50m |
| 5 | graph.py + shim | 30분 | 3h 20m |
| 6 | 최종 검증 | 20분 | 3h 40m |

**총 ~3.5~4시간** (Claude 페이스, 사용자 검증 대기 시간 별도).

---

## 9. 롤백 매뉴얼

### Level 1: Step 중 깨짐
```bash
# 마지막 commit으로
git reset --hard HEAD
```

### Level 2: Phase 중 깨짐
```bash
# Phase 시작 commit으로 (Phase N start 검색)
git log --oneline | grep "Phase N"
git reset --hard <commit_sha>
```

### Level 3: 완전 초기화
```bash
# 브랜치 자체를 main 시작점으로
git reset --hard $(git merge-base HEAD origin/main)
```

### Level 4: 브랜치 폐기
```bash
git checkout main
git branch -D refactor/pipeline-split
```

---

## 10. 시연 자동화 검증 매뉴얼

각 Phase 끝에 사용자에게 부탁:

```
🔍 Phase N 완료. 시연 자동화 검증 부탁드려요:

터미널 1: python .gstack-browser-launch.py
터미널 2: python .gstack-demo.py --fast

기대 결과:
  ACT 1: 방 생성 + 선호도 + 게스트 2명 가입 → 통과
  ACT 2: 채팅 4메시지 → 자동 트리거 + 캘린더 sync → 통과
  ACT 4: vote_card 확정 → 통과
  ACT 5: 장소 추천 → 확정 → 모임 완료 → 통과

전체 통과 확인 후 다음 Phase 진행 승인 부탁드려요.
```

---

## 11. 외부 import 사이트 수정 — **하지 않음**

분할 후에도 `from app.services.langgraph_pipeline import ...`는 그대로 동작.
agent.py / meetings.py / rooms.py / qa_privacy_boundary.py 4개 파일 수정 **금지**.

이유: 시연 깨질 위험 ↑ + Phase 분리 원칙 (한 번에 하나만).

신규 코드에서는 새 경로 (`from app.services.pipeline.* import ...`) 사용 권장 — 시연 후 마이그레이션 작업으로 분리.

---

## 12. Self-Check 명령 색인

Phase별 self-check 빠른 참조:

### 12.1 Phase 1: 파일 24개 생성 확인
```bash
find backend/app/services/pipeline -type f -name '*.py' | wc -l
# 기대: 24
```

### 12.2 Phase 2: Layer 0 import
```bash
docker exec maedeup-api python -c "
from app.services.pipeline.constants import KST
from app.services.pipeline.helpers.json_extract import _extract_json_object
from app.services.pipeline.helpers.formatting import _room_id_as_int
from app.services.pipeline.helpers.places import _extract_korean_place_keyword
from app.services.pipeline.helpers.dates import _get_korean_holiday
print('Phase 2 OK')
"
```

### 12.3 Phase 3: state + Layer 2
```bash
docker exec maedeup-api python -c "
from app.services.pipeline.state import GraphState, _default_state
from app.services.pipeline.helpers.slot_state import _update_slot_state
from app.services.pipeline.helpers.messaging import _has_node_error
from app.services.pipeline.helpers.slots import get_free_slots
from app.services.pipeline.helpers.preferences import _load_meeting_preferences
print('Phase 3 OK')
"
```

### 12.4 Phase 4: 모든 노드
```bash
docker exec maedeup-api python -c "
from app.services.pipeline.nodes.intent import intent_detection
from app.services.pipeline.nodes.entity import entity_extraction
from app.services.pipeline.nodes.slot import slot_filling
from app.services.pipeline.nodes.function_call import function_calling
from app.services.pipeline.nodes.validation import supervisor_validation
from app.services.pipeline.nodes.vote_card import vote_card_creation
from app.services.pipeline.nodes.place import place_recommendation
from app.services.pipeline.nodes.maedeup import maedeup_card_creation
from app.services.pipeline.nodes.memory import memory_extraction
from app.services.pipeline.nodes.conversation_analyzer import _analyze_conversation, suggest_alternative_slots
print('Phase 4 OK')
"
```

### 12.5 Phase 5: shim + 외부 import
```bash
docker compose restart maedeup-api
sleep 5
curl -fsS http://localhost:8000/health
docker exec maedeup-api python -c "
from app.services.langgraph_pipeline import KST, run_pipeline
from app.services.langgraph_pipeline import _analyze_conversation, memory_extraction, suggest_alternative_slots
print('Shim re-exports OK')
"
```

### 12.6 Phase 6: 중복 검사
```bash
docker exec maedeup-api python -c "
import ast, glob
seen = {}
for path in glob.glob('/app/app/services/pipeline/**/*.py', recursive=True):
    with open(path) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in seen:
                print(f'DUP: {node.name}')
            seen[node.name] = path
print(f'Total: {len(seen)}')
"
# 기대: Total: 107, no DUP
```

---

## 13. Resume Protocol — 작업 중단 후 어디까지 했는지 확인

Claude가 작업 컨텍스트를 잃었을 때 (compaction, 세션 종료 등) 이 프로토콜로 자가진단:

```bash
# Step 1: 브랜치 확인
git branch --show-current
# 기대: refactor/pipeline-split

# Step 2: 최근 commit 로그
git log --oneline | head -10
# Phase 키워드 검색해서 어디까지 완료됐는지 확인

# Step 3: pipeline/ 디렉토리 상태
find backend/app/services/pipeline -type f -name '*.py' | xargs wc -l | tail -1
# 0줄이면 Phase 1만 됨
# ~500줄이면 Phase 2 일부
# ~1000줄이면 Phase 2~3
# ~2000줄이면 Phase 4 중
# ~3800줄이면 Phase 5 완료

# Step 4: 원본 파일 상태
wc -l backend/app/services/langgraph_pipeline.py
# 5301 = Phase 1~4 단계
# ~14 = Phase 5 완료

# Step 5: 어떤 self-check까지 통과하는지 차례로 실행
# §12.1 → §12.2 → §12.3 → §12.4 → §12.5
# 마지막으로 통과하는 단계가 현재 완료된 Phase
```

진단 후 **다음 진행할 Phase의 Pre-conditions부터 점검**.

---

## 14. 완료 정의 (Definition of Done)

전체 분할 작업이 끝났다고 선언하려면 다음 8개 다 통과:

- [ ] §1.1 검증: `langgraph_pipeline.py` 라인 ~14 (shim only)
- [ ] §1.1 검증: `pipeline/` 하위 총 함수 107개 (중복 0)
- [ ] §12.5 통과: 외부 5개 심볼 shim 경유 import 동작
- [ ] §11 통과: agent.py/meetings.py/rooms.py 모두 무수정 상태로 동작
- [ ] 시연 자동화 ACT 1~5 통과 (사용자 직접 확인)
- [ ] pytest 통과
- [ ] git log에 Phase 1~6 commit 다 존재
- [ ] 사용자 최종 승인

---

## 한 줄 요약

> **5,301줄 / 107 함수 / 23 상수 → 14 모듈 + 1 shim. Layer 0~5 순서로 6 Phase. 각 Phase마다 Pre/Post conditions + self-check 명령 명시. 시연 자동화 통과가 매 Phase의 gate. 함수 로직 한 글자도 수정 금지 — 순수 이동만.**
