"""LangGraph graph definition + run_pipeline entry.

원본 위치: langgraph_pipeline.py 라인 4772~4884 (_route_* 6개),
  4887~4961 (_build_graph), 4964 (GRAPH = _build_graph()),
  4967~5039 (run_pipeline).

Phase 5 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

⚠️ 주의: 이 모듈은 모듈 import 시점에 GRAPH = _build_graph()를 실행한다.
   그래서 모든 노드 함수가 import 시점에 정의돼 있어야 함 (top-level import 순서 중요).

의존:
  - langgraph.graph: START, END, StateGraph
  - state.GraphState, _default_state, _serialize_context
  - constants.INTENT_CONFIDENCE_THRESHOLD
  - helpers.messaging: _has_node_error, _compress_message_history
  - helpers.formatting._room_id_as_int
  - helpers.slot_state._slot_snapshot
  - helpers.preferences._load_social_context
  - nodes/* (9개 노드 함수)
  - app.repositories.messages.{AgentContextMessages, MessageReader}
"""
from __future__ import annotations

import logging
import time
from typing import Any, Literal
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.messages import AgentContextMessages, MessageReader
from app.services.pipeline.constants import INTENT_CONFIDENCE_THRESHOLD
from app.services.pipeline.helpers.formatting import _room_id_as_int
from app.services.pipeline.helpers.messaging import (
    _compress_message_history,
    _has_node_error,
)
from app.services.pipeline.helpers.preferences import _load_social_context
from app.services.pipeline.helpers.slot_state import _slot_snapshot
from app.services.pipeline.nodes.entity import entity_extraction
from app.services.pipeline.nodes.function_call import function_calling
from app.services.pipeline.nodes.intent import general_response, intent_detection
from app.services.pipeline.nodes.maedeup import maedeup_card_creation
from app.services.pipeline.nodes.place import place_recommendation
from app.services.pipeline.nodes.slot import slot_filling
from app.services.pipeline.nodes.validation import supervisor_validation
from app.services.pipeline.nodes.vote_card import vote_card_creation
from app.observability.snapshot import dump
from app.services.pipeline.state import GraphState, _default_state

logger = logging.getLogger(__name__)


def _route_from_start(state: GraphState) -> Literal["entity_extraction", "slot_filling", "intent_detection"]:
    """해결점 C: trigger_reason 기반 LangGraph 진입 분기.

    - stalemate_judged / conclusion_detected: 의도 자명 → 노드3 entity_extraction부터 (~1s 절약)
    - all_members_selected: TimeBar 데이터 주입됨 → 노드4 slot_filling부터 (~3s 절약)
    - direct_request: quick_classify가 이미 general을 걸렀으므로 노드3 entity_extraction부터
    - preference_toggle (PR-Z1): refresh 라우트 재호출. intent/entity 재추출 불필요 —
        confirmed slot · place_hint · preference_source 가 이미 박혀 있음.
        → vote_card scope면 slot_filling부터 (function_calling/validation 재실행),
          place scope면 entity_extraction부터 (place_hint 보존하면서 재추천).
        scope는 slot_context["partial_mode"]에 매핑됨.
    - 미지정: 기존 노드1 intent_detection 경로
    """
    trigger = state.get("trigger_reason")
    if trigger == "preference_toggle":
        # refresh 라우트는 partial_mode = "place_only" | "vote_only" | None(both) 형태로 전달.
        partial = state.get("partial_mode")
        if partial == "place_only":
            decision = "entity_extraction"
        else:
            # vote_only / both — slot_filling 진입해 function_calling→validation→vote_card 흐름.
            decision = "slot_filling"
    elif trigger in {"stalemate_judged", "conclusion_detected", "direct_request"}:
        decision = "entity_extraction"
    elif trigger == "all_members_selected":
        decision = "slot_filling"
    else:
        decision = "intent_detection"
    dump("route", state.get("run_id"), {
        "router": "_route_from_start",
        "decision": decision,
        "status": state.get("status"),
    })
    return decision  # type: ignore[return-value]


def _route_after_intent(state: GraphState) -> Literal["entity_extraction", "general_response"]:
    """general 의도이고 슬롯 필링 진행 중이 아니면 일반 응답으로 분기."""
    if _has_node_error(state):
        decision = "general_response"
    elif float(state.get("confidence_score", 0.0)) < INTENT_CONFIDENCE_THRESHOLD:
        decision = "general_response"
    elif state.get("intent") == "general" and state.get("slot_filling_turns", 0) == 0:
        decision = "general_response"
    else:
        decision = "entity_extraction"
    dump("route", state.get("run_id"), {
        "router": "_route_after_intent",
        "decision": decision,
        "status": state.get("status"),
    })
    return decision  # type: ignore[return-value]


def _route_after_slot_filling(state: GraphState) -> Literal["slot_filling", "function_calling", "__end__"]:
    if _has_node_error(state):
        decision = END
    else:
        status = state.get("status", "")
        if status in ("conclusion_false_positive", "time_only_ready"):
            decision = "function_calling"
        elif state.get("is_location_first"):
            decision = "function_calling"
        elif state.get("all_slots_filled"):
            decision = "function_calling"
        # 부분 정보만 있거나 정보가 없는 경우 → 질문 없이 종료
        elif status in ("no_slots_yet", "partial_info_acknowledged"):
            decision = END
        elif state.get("wait_timed_out") or state.get("awaiting_user_reply"):
            decision = END
        else:
            decision = "slot_filling"
    dump("route", state.get("run_id"), {
        "router": "_route_after_slot_filling",
        "decision": decision,
        "status": state.get("status"),
    })
    return decision  # type: ignore[return-value]


def _route_after_validation(
    state: GraphState,
) -> Literal["vote_card_creation", "place_recommendation", "maedeup_card_creation", "function_calling", "__end__"]:
    if _has_node_error(state):
        decision = END
    else:
        status = state.get("status")
        if status == "conclusion_false_positive":
            decision = END
        elif status == "time_only_ready":
            state["partial_mode"] = "time_only"
            decision = "maedeup_card_creation"
        elif status == "needs_expansion":
            # 호스트 GCal full-block → date_hint +7일 shift 후 function_calling 재실행
            decision = "function_calling"
        elif not state.get("validation_passed"):
            decision = END
        else:
            # 해결점 C: trigger_reason 기반 라우팅 차별화
            trigger = state.get("trigger_reason")
            if trigger == "conclusion_detected":
                # 결론 합의됐으니 vote/place 스킵, 매듭 카드 직행
                decision = "maedeup_card_creation"
            elif trigger == "all_members_selected":
                # TimeBar로 시간 확정됨, 장소 추천만
                decision = "place_recommendation"
            else:
                # 해결점 E A1: direct_request로 place 분류된 경우 vote 건너뛰고 place_recommendation
                direct_kind = state.get("direct_request_kind")
                if direct_kind == "place":
                    decision = "place_recommendation"
                # 해결점 E A2: 이미 일정 확정된 상태면 vote_card 다시 만들 필요 없음 → place_recommendation
                elif state.get("confirmed_date") and state.get("place_search_results"):
                    decision = "place_recommendation"
                elif state.get("intent") == "place_suggestion" and state.get("place_search_results"):
                    decision = "place_recommendation"
                # 선호 데이터 기반 자동 제안: 투표 카드를 먼저 생성 (시간대 투표)
                elif state.get("preference_common_times") and state.get("intent") != "place_suggestion":
                    decision = "vote_card_creation"
                elif state.get("is_location_first") and not state.get("date_hint"):
                    decision = "place_recommendation"
                else:
                    decision = "vote_card_creation"
    dump("route", state.get("run_id"), {
        "router": "_route_after_validation",
        "decision": decision,
        "status": state.get("status"),
    })
    return decision  # type: ignore[return-value]


def _route_after_vote_card_creation(state: GraphState) -> Literal["place_recommendation", "maedeup_card_creation", "__end__"]:
    if _has_node_error(state):
        decision = END
    # 사용자가 이미 시간/장소를 확정한 상태에서 진입한 경우 (vote 후 별도 트리거)
    elif state.get("confirmed_place"):
        decision = "maedeup_card_creation"
    else:
        # 일반 흐름: vote_card만 발행하고 사용자 vote 대기.
        # 사용자가 vote → confirm endpoint가 새 run_pipeline 실행 시
        # confirmed_date/place 박아 보내면 그때 maedeup으로 진입.
        decision = END
    dump("route", state.get("run_id"), {
        "router": "_route_after_vote_card_creation",
        "decision": decision,
        "status": state.get("status"),
    })
    return decision  # type: ignore[return-value]


def _route_after_place_recommendation(state: GraphState) -> Literal["maedeup_card_creation", "__end__"]:
    if _has_node_error(state):
        decision = END
    elif state.get("is_location_first") and not state.get("date_hint"):
        decision = END
    # 사용자가 이미 장소를 확정한 상태에서 진입한 경우만 매듭 카드로 직진
    elif state.get("confirmed_place"):
        decision = "maedeup_card_creation"
    # direct_request로 진입한 경우 — vote_card 패턴과 일관되게 사용자 confirm 대기.
    # 사용자가 place 카드에서 "이 장소로 확정" 클릭 → confirm endpoint가 별도 trigger로
    # maedeup_card_creation 발화시킴. 자동 진행하면 confirmed_date와 데이터 불일치 가능.
    elif state.get("trigger_reason") == "direct_request":
        decision = END
    else:
        decision = "maedeup_card_creation"
    dump("route", state.get("run_id"), {
        "router": "_route_after_place_recommendation",
        "decision": decision,
        "status": state.get("status"),
    })
    return decision  # type: ignore[return-value]


def _build_graph() -> Any:
    graph = StateGraph(GraphState)
    graph.add_node("intent_detection", intent_detection)
    graph.add_node("general_response", general_response)
    graph.add_node("entity_extraction", entity_extraction)
    graph.add_node("slot_filling", slot_filling)
    graph.add_node("function_calling", function_calling)
    graph.add_node("supervisor_validation", supervisor_validation)
    graph.add_node("vote_card_creation", vote_card_creation)
    graph.add_node("place_recommendation", place_recommendation)
    graph.add_node("maedeup_card_creation", maedeup_card_creation)
    # P0-2 (2026-05-08): memory_extraction 노드를 graph에서 분리.
    # maedeup_card_creation 안에서 fire-and-forget으로 spawn 됨 (~4s 사용자 인식 latency 제거).

    # 해결점 C: trigger_reason 기반 진입 분기 (노드1 스킵 가능)
    graph.add_conditional_edges(
        START,
        _route_from_start,
        {
            "entity_extraction": "entity_extraction",
            "slot_filling": "slot_filling",
            "intent_detection": "intent_detection",
        },
    )
    graph.add_conditional_edges(
        "intent_detection",
        _route_after_intent,
        {
            "entity_extraction": "entity_extraction",
            "general_response": "general_response",
        },
    )
    graph.add_edge("general_response", END)
    graph.add_edge("entity_extraction", "slot_filling")
    graph.add_conditional_edges(
        "slot_filling",
        _route_after_slot_filling,
        {
            "slot_filling": "slot_filling",
            "function_calling": "function_calling",
            END: END,
        },
    )
    graph.add_edge("function_calling", "supervisor_validation")
    graph.add_conditional_edges(
        "supervisor_validation",
        _route_after_validation,
        {
            "vote_card_creation": "vote_card_creation",
            "place_recommendation": "place_recommendation",
            "maedeup_card_creation": "maedeup_card_creation",  # 해결점 C: conclusion 직행
            "function_calling": "function_calling",             # next-week expansion redirect
            END: END,
        },
    )
    graph.add_conditional_edges(
        "vote_card_creation",
        _route_after_vote_card_creation,
        {
            "place_recommendation": "place_recommendation",
            "maedeup_card_creation": "maedeup_card_creation",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "place_recommendation",
        _route_after_place_recommendation,
        {
            "maedeup_card_creation": "maedeup_card_creation",
            END: END,
        },
    )
    # P0-2 (2026-05-08): 매듭 카드 즉시 종결. memory_extraction은 카드 노드 내부에서
    # asyncio.create_task로 fire-and-forget — graph latency에서 ~4s 빠짐.
    graph.add_edge("maedeup_card_creation", END)
    return graph.compile()


GRAPH = _build_graph()


async def run_pipeline(
    room_id: str,
    context: AgentContextMessages,
    db: AsyncSession,
    slot_context: dict | None = None,
) -> dict[str, Any]:
    """Run the AI pipeline.

    `context` MUST be built via `MessageReader.load_agent_context` so the privacy
    boundary (visibility + user_id filter) is enforced at the query layer. Raw
    `list[ChatMessage]` is rejected — see docs/ai-separation.md §9.4.
    """
    MessageReader.ensure_branded(context)
    _pipeline_t0 = time.monotonic()
    run_id = uuid4().hex[:8]
    initial_state = _default_state(
        room_id=room_id,
        db=db,
        messages=context.messages,
        slot_context=slot_context,
        viewer_user_id=context.viewer_user_id,
    )
    initial_state["run_id"] = run_id
    dump("pipeline_start", run_id, {
        "initial_keys": list(initial_state.keys()),
        "trigger": initial_state.get("trigger_reason"),
    })
    logger.debug("[run=%s] pipeline_start room=%s trigger=%s", run_id, room_id, initial_state.get("trigger_reason"))
    await _compress_message_history(initial_state)
    # 소셜(방 전체) 채팅 컨텍스트 preload — entity/general 노드가 _serialize_context로 읽음.
    try:
        room_pk = _room_id_as_int(room_id)
        social_recent, social_summary = await _load_social_context(db, room_pk)
        initial_state["social_recent"] = social_recent
        initial_state["social_summary"] = social_summary
    except Exception:
        logger.debug("social context preload failed room=%s", room_id, exc_info=True)
    final_state = await GRAPH.ainvoke(initial_state)
    _elapsed = time.monotonic() - _pipeline_t0
    logger.info(
        "[run=%s] [TIMING] run_pipeline TOTAL: %.2fs | intent=%s status=%s",
        run_id,
        _elapsed,
        final_state.get("intent"),
        final_state.get("status"),
    )
    dump("pipeline_end", run_id, {
        "final_status": final_state.get("status"),
        "card_type": (final_state.get("maedeup_card_payload") or final_state.get("vote_card_payload") or final_state.get("place_recommendation_payload") or {}).get("type"),
        "elapsed": round(_elapsed, 3),
    })
    return {
        "status": final_state.get("status"),
        "intent": final_state.get("intent"),
        "intent_confidence": final_state.get("intent_confidence"),
        "confidence_score": final_state.get("confidence_score"),
        "slots": _slot_snapshot(final_state),
        "missing_slots": final_state.get("missing_slots", []),
        "awaiting_user_reply": final_state.get("awaiting_user_reply", False),
        "validation_errors": final_state.get("validation_errors", []),
        "vote_card_payload": final_state.get("vote_card_payload"),
        "place_recommendation_payload": final_state.get("place_recommendation_payload"),
        "maedeup_card_payload": final_state.get("maedeup_card_payload"),
        "calendar_registration": final_state.get("calendar_registration"),
        "conversation_summary": final_state.get("conversation_summary", ""),
        "recent_messages": final_state.get("recent_messages", []),
        # 슬롯 컨텍스트 – agent.py가 다음 호출에 이어받을 값들
        "slot_filling_turns": final_state.get("slot_filling_turns", 0),
        "message_count_since_last_trigger": final_state.get("message_count_since_last_trigger", 0),
        "summary_message_count": final_state.get("summary_message_count", 0),
        "date_hint": final_state.get("date_hint"),
        "place_hint": final_state.get("place_hint"),
        "place_coord": final_state.get("place_coord"),
        "default_place_hint": final_state.get("default_place_hint"),
        "confirmed_date": final_state.get("confirmed_date"),
        "confirmed_time": final_state.get("confirmed_time"),
        "confirmed_place": final_state.get("confirmed_place"),
        "parsed_time_hint": final_state.get("parsed_time_hint"),
        "date_is_flexible": final_state.get("date_is_flexible", False),
        "date_hint_source_text": final_state.get("date_hint_source_text"),
        "headcount": final_state.get("headcount"),
        "meeting_type": final_state.get("meeting_type"),
        "is_location_first": final_state.get("is_location_first", False),
        "blocker_notification_payload": final_state.get("blocker_notification_payload"),
        "time_options": final_state.get("time_options", []),
        "new_assistant_messages": final_state.get("new_assistant_messages", []),  # type: ignore[typeddict-item]
    }
