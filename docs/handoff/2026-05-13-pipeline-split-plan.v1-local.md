# 2026-05-13 — `langgraph_pipeline.py` 분리 계획서

졸업 프로젝트 시연 이후 진행할 **백엔드 LangGraph 파이프라인 모듈 분리** 작업의 계획서. 분업·소유권 경계를 명확히 하고, 단일 파일 5301줄을 패키지 구조로 점진 전환한다.

---

## 1. 상황 (Why now)

### 현재 상태
- 핵심 파이프라인이 단일 파일 **`backend/app/services/langgraph_pipeline.py` (5301줄)** 에 집중.
- 9개 LangGraph 노드 + 백그라운드 `memory_extraction` + 80여 개의 헬퍼/유틸 함수가 한 파일에 공존.
- `graph.add_node(...)` 등록: `langgraph_pipeline.py:4889-4897` (9 노드).
- 외부 분리된 의존 모듈: `intent_classifier.py`, `ml_recommend.py`, `kakao_maps.py`, `google_calendar.py`, `scheduling_round.py`.

### 통증 (Pain)
1. **머지 충돌** — 팀원이 동시에 다른 노드를 만져도 같은 파일이라 PR 충돌 잦음.
2. **리뷰 부하** — diff가 길어 코드 리뷰 집중력 저하.
3. **테스트 격리 어려움** — 노드 단위 단위테스트 작성 시 import 단위가 파일 전체.
4. **신규 합류자 onboarding 비용** — 5301줄을 한 번에 읽어야 흐름이 잡힘.

### 트리거
- 팀 분업 결정: 본인(장소 추천 + 시간 조율) + 다른 팀원(아키텍처 전반 재설계).

---

## 2. 목표 / 비목표

### 목표
- 도메인 기준 패키지 분리로 **머지 충돌 면적 최소화**.
- 노드별/도메인별 책임 명확화 → 코드 리뷰·테스트 작성 용이.
- 외부 사용처(`router`, `service`)의 import 경로는 **하위 호환 유지** (`from app.services.langgraph_pipeline import run_pipeline` 그대로 동작).

### 비목표 (이 PR에서 하지 않을 것)
- 동작 변경 / 버그 픽스 / 리팩토링.
- 시그니처 변경.
- 새로운 추상화 도입 (Protocol, ABC, DI container 등).
- 테스트 코드 추가 (분리 검증용 회귀 테스트는 별도 PR).

**원칙**: 무브 PR은 "위치 이동 + import 교정"만. 함수 본문 한 줄도 바꾸지 않는다.

---

## 3. 분리 후 디렉토리 구조

```
backend/app/services/langgraph_pipeline/
├── __init__.py            # run_pipeline, _build_graph 재노출 (하위 호환)
├── state.py               # GraphState TypedDict, _default_state
├── common.py              # JSON 파싱, _emit_assistant_message,
│                          # _handle_node_exception, 메시지 직렬화
├── graph.py               # _build_graph + _route_after_* 라우팅
│
├── domain/                # 노드 간 공유되는 도메인 로직
│   ├── __init__.py
│   ├── time_parsing.py    # 자연어 날짜/시간 파싱
│   ├── scheduling.py      # busy/free 슬롯, 캘린더, 다중 날짜 빌더
│   ├── places.py          # 장소 검색, cuisine 필터링, self-correction
│   └── constraints.py     # 멤버 식단/시간 제약, 선호 로딩
│
└── nodes/                 # 각 LangGraph 노드 1개 = 파일 1개
    ├── __init__.py
    ├── intent.py
    ├── general.py
    ├── entity.py
    ├── slot.py
    ├── function_calling.py
    ├── supervisor.py
    ├── vote_card.py
    ├── place_recommendation.py
    ├── maedeup_card.py
    └── memory.py
```

총 **17 파일** (패키지 7 + 도메인 4 + 노드 10).

### 하위 호환 보장 (`__init__.py`)
```python
# backend/app/services/langgraph_pipeline/__init__.py
from .graph import _build_graph
from .runner import run_pipeline  # 또는 .graph 내부

__all__ = ["run_pipeline", "_build_graph"]
```

외부 코드는 import 경로 변경 없이 동작.

---

## 4. 함수 → 파일 매핑

> 라인 번호는 분리 시점의 `langgraph_pipeline.py` 기준.

### 4.1 `state.py`
| 함수 | 라인 |
|---|---|
| `GraphState` TypedDict (정의부 전체) | :~80-176 |
| `_default_state` | :177 |

### 4.2 `common.py`
| 함수 | 라인 |
|---|---|
| `_normalize_message` | :256 |
| `_split_message_context` | :282 |
| `_message_to_text` | :291 |
| `_serialize_context` | :297 |
| `_compress_message_history` | :312 |
| `_extract_json_object` / `_array` / `_loose_json_object` | :482 / :503 / :526 |
| `_coerce_headcount` / `_coerce_bool` | :358 / :653 |
| `_has_node_error` / `_handle_node_exception` | :416 / :420 |
| `_emit_assistant_message` | :1250 |
| `_slot_snapshot` | :1313 |
| `_load_social_context` | :1464 |
| `_room_id_as_int` / `_user_calendar_key` / `_user_display_name` | :942 / :949 / :953 |

### 4.3 `graph.py`
| 함수 | 라인 |
|---|---|
| `_route_from_start` | :4772 |
| `_route_after_intent` | :4788 |
| `_route_after_slot_filling` | :4799 |
| `_route_after_validation` | :4817 |
| `_route_after_vote_card_creation` | :4859 |
| `_route_after_place_recommendation` | :4871 |
| `_build_graph` | :4887 |
| `run_pipeline` | :4967 |
| `_analyze_conversation` | :5042 |

### 4.4 `domain/time_parsing.py`
| 함수 | 라인 |
|---|---|
| `_get_korean_holiday` / `_is_weekend` | :70 / :76 |
| `_format_slot_label` / `_format_confirmed_time` | :458 / :473 |
| `_is_iso_date_hint` / `_is_specific_iso_date` | :554 / :561 |
| `_resolve_rejected_date` | :567 |
| `_detect_multi_date_options` | :601 |
| `_weekday_from_korean` / `_next_weekday` | :637 / :661 |
| `_fallback_parse_natural_date` | :668 |
| `_normalize_parsed_natural_date` / `_parse_natural_date` | :754 / :795 |
| `_infer_time_bucket` | :829 |
| `_parse_iso_datetime` | :1323 |
| `_expand_date_hint` | :1625 |

### 4.5 `domain/scheduling.py`
| 함수 | 라인 |
|---|---|
| `_build_flexible_time_options` | :853 |
| `_normalize_preferred_time(s)` / `_preference_score_for_start` | :870 / :874 / :885 |
| `_build_time_option_slots` | :906 |
| `_get_user_busy_periods` / `_find_free_slots` | :1335 / :1393 |
| `_load_blocked_dates` / `_filter_out_blocked` / `_filter_out_rejected` | :1584 / :1610 / :1655 |
| `_load_busy_by_user_for_state` | :1669 |
| `get_free_slots` | :1711 |
| `_register_google_calendar` | :2442 |
| `_build_multi_date_slots` / `_is_busy_during` / `_build_preference_time_slots` | :3420 / :3506 / :3533 |
| `suggest_alternative_slots` | :5210 |

### 4.6 `domain/places.py`
| 함수 | 라인 |
|---|---|
| `_resolve_place_hint` | :436 |
| `_detect_cuisine_type` | :1029 |
| `_filter_places_by_cuisine` | :1039 |
| `_extract_korean_place_keyword` | :1050 |
| `_resolve_place_coord` | :1239 |
| `_get_room_member_food_preferences` | :1938 |
| `_contains_disliked_keyword` | :2320 |
| `_run_place_self_correction` | :2329 |
| `search_place` | :2363 |

### 4.7 `domain/constraints.py` (회색지대 — §6 참조)
| 함수 | 라인 |
|---|---|
| `_load_meeting_preferences` | :2220 |
| `_get_room_member_constraints` | :1983 |
| `_get_room_member_constraints_named` | :2081 |
| `_build_group_constraints_summary` | :2054 |
| `_build_named_constraints_summary` | :2150 |

### 4.8 `nodes/*.py`
| 노드 파일 | 함수 | 라인 |
|---|---|---|
| `intent.py` | `intent_detection` | :2592 |
| `general.py` | `general_response`, `_try_template_response` | :2521 / :2453 |
| `entity.py` | `entity_extraction`, `_pattern_extract_entities`, `_extract_entities_from_context` | :2679 / :1069 / :1140 |
| `slot.py` | `slot_filling` + 모든 `_slot_filling_*` 헬퍼 + `_enrich_with_preferences` / `_has_meaningful_slot_progress` / `_update_slot_state` | :3029 외 |
| `function_calling.py` | `function_calling` | :3670 |
| `supervisor.py` | `supervisor_validation` | :3803 |
| `vote_card.py` | `vote_card_creation`, `_card_payload_meeting_id`, `_ensure_pending_meeting_id` | :4023 / :3896 / :3907 |
| `place_recommendation.py` | `place_recommendation` | :4150 |
| `maedeup_card.py` | `maedeup_card_creation` | :4412 |
| `memory.py` | `memory_extraction`, `_is_empty_personal_data`, `_publish_personal_data_updates`, `_spawn_memory_extraction_async` | :4626 / :4565 / :4576 / :4607 |

---

## 5. 분업 매핑 (Ownership)

### 본인 — 장소 추천 + 시간 조율
**Primary owner** (PR 단독 진행 가능):
- `domain/places.py`
- `domain/time_parsing.py`
- `domain/scheduling.py`
- `nodes/place_recommendation.py`
- `nodes/function_calling.py`
- `nodes/vote_card.py`

**연관 외부 파일** (기존):
- `backend/app/services/kakao_maps.py`
- `backend/app/services/ml_recommend.py`
- `backend/app/services/google_calendar.py`
- `backend/app/services/scheduling_round.py`

### 다른 팀원 — 아키텍처 재설계
**Primary owner**:
- 분리 무브 PR 자체 진행
- `state.py`, `common.py`, `graph.py`
- 나머지 노드: `intent.py`, `general.py`, `entity.py`, `slot.py`, `supervisor.py`, `maedeup_card.py`, `memory.py`
- 라우팅 로직, GraphState 스키마 진화 방향 설계

**책임 범위**:
- 패키지 부트스트래핑
- 노드 간 인터페이스(GraphState) 안정성
- 향후 모듈 경계 결정 (예: `nodes/dialog/` 하위 추가 분리 여부)

### 공동 영역 (변경 시 합의 필요)
| 파일 | 합의 사유 |
|---|---|
| `state.py` | GraphState 필드 추가는 양쪽 모두 영향 |
| `common.py` | 공유 유틸 변경은 전 노드 회귀 위험 |
| `domain/constraints.py` | 식단(장소) + 시간 제약 혼합 (§6) |

---

## 6. 회색지대 — 협의 필요 3건

분리 시점에 위치 결정이 필요한 함수들. **무브 PR 직전에 30분 미팅으로 확정**.

| 함수 | 현재 | 옵션 A | 옵션 B | 권장 |
|---|---|---|---|---|
| `_load_meeting_preferences` | :2220 | `domain/constraints.py` | 식단/시간으로 함수 분할 | **A** (분리 PR에서 동작 변경 금지) |
| `_get_room_member_constraints` | :1983 | `domain/constraints.py` | 식단(`places.py`) + 시간(`scheduling.py`)으로 함수 분할 | **A** |
| `_get_room_member_constraints_named` | :2081 | `domain/constraints.py` | 동상 | **A** |

**근거**: 이들은 DB 1회 조회로 식단·시간 제약을 동시에 반환 → 함수 분할 시 N+1 발생. 우선 한 모듈로 모으고, 후속 PR에서 필요 시 캐싱 레이어 도입.

---

## 7. 진행 절차


### Phase 1 — 사전 점검 (반나절)
- [ ] `langgraph_pipeline.py` 최신 상태에서 회귀 테스트 가능한 시나리오 정리.
- [ ] 외부 import 사용처 전수 조사:
  ```
  grep -rn "from app.services.langgraph_pipeline" backend/
  grep -rn "import langgraph_pipeline" backend/
  ```
- [ ] 회색지대 3건 확정 미팅.

### Phase 2 — 무브 PR (아키텍트 단독, 1일)
**원칙**: 단일 PR, 동작 변경 0, 함수 본문 수정 0.

순서:
1. 패키지 디렉토리 + 빈 파일 셸 생성.
2. `state.py` → `common.py` → `domain/*` → `nodes/*` → `graph.py` 순으로 이동.
3. 매 이동마다 `langgraph_pipeline.py`에서 함수 삭제 + 신규 위치로 이동 + 원본 파일에서 신규 위치 import (점진적 가능).
4. 모든 함수 이동 완료 후 `langgraph_pipeline.py` 삭제 + 패키지 `__init__.py`로 대체.
5. `from app.services.langgraph_pipeline import X`가 그대로 동작하는지 import 테스트.

### Phase 3 — 회귀 검증 (반나절)
- [ ] `python .gstack-demo-integrated.py` 시나리오 풀 자동화 통과.
- [ ] 9 노드 흐름 수동 확인 (장소/날짜/투표카드 생성).
- [ ] `docker compose up -d --build` 무에러.

### Phase 4 — 분업 시작
무브 PR 머지 직후, 본인/아키텍트가 각자 owner 파일에서 개선 작업 분기. 더 이상 `langgraph_pipeline.py` 단일 파일 접근 없음.

---

## 8. 리스크 / 완화책

| 리스크 | 완화책 |
|---|---|
| 순환 import (`nodes/* ↔ domain/*`) | 도메인 모듈은 노드를 import하지 않는다는 단방향 규칙. 위반 시 헬퍼를 `common.py`로 승격. |
| GraphState 필드 누락으로 런타임 KeyError | `_default_state` 분리 후 `GraphState`의 모든 키를 명시적으로 초기화 검증. |
| 무브 중 부분 commit으로 import 깨짐 | 무브 PR을 한 번에 (분할 머지 금지). 작업 중에는 로컬 브랜치에서만. |
| 시연 자동화 스크립트 영향 | `.gstack-demo-integrated.py`는 HTTP API만 호출하므로 영향 없음. 검증 단계에서 확인. |
| Alembic 마이그레이션 영향 | 없음 (이번 분리는 코드만, DB 무관). |

---

## 9. 성공 기준 (Definition of Done)

무브 PR이 머지되기 위한 체크리스트:

- [ ] `langgraph_pipeline.py` 단일 파일이 패키지로 대체됨.
- [ ] 외부 import 경로 (`from app.services.langgraph_pipeline import ...`) 무수정으로 동작.
- [ ] `docker compose up -d --build fastapi-app` 무에러 부팅.
- [ ] 시연 자동화 시나리오 (ACT 0~6) 통과.
- [ ] 9개 `add_node` 등록이 `graph.py`에 모두 존재.
- [ ] `git diff --stat`에서 함수 본문 변경 0 (이동만).

---

## 10. 후속 작업 (이번 PR 범위 밖)

분리 완료 후 따로 진행할 개선들:

1. 각 노드 단위 pytest 작성 (모킹 가능한 도메인 함수 위주).
2. `GraphState`를 dataclass 또는 Pydantic 모델로 마이그레이션 (타입 안정성).
3. `domain/places.py`의 ML/Kakao 폴백 전략을 Strategy 패턴으로 정리.
4. `nodes/function_calling.py`의 시간대 조율 로직을 별도 도메인 모듈로 추가 분리 검토.

---

## 부록 — 참고 문서

- `docs/handoff/audit-findings.md` — 해결점 A~P
- `docs/handoff/demo-scenario.md` — 시연 시나리오 SoT
- `docs/handoff/diagrams/02-langgraph-flow.mmd` — 9 노드 흐름도
- `backend/app/services/langgraph_pipeline.py:4887` — 현재 `_build_graph` 위치
