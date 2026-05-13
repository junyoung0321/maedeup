"""place_recommendation 노드 + self-correction 헬퍼.

원본 위치: langgraph_pipeline.py 라인 2329~2360 (_run_place_self_correction),
  4150~4410 (place_recommendation).

Phase 4 분할 (2026-05-13). 로직 변경 없음 — 순수 이동.

조정 (v2 §3.17 대비):
  - search_place는 helpers/places.py로 이동됨 (Phase 4.2 commit f318805 참고).

의존:
  - state.GraphState
  - constants.settings.REDIS_URL
  - helpers.messaging: _has_node_error, _emit_assistant_message, _handle_node_exception
  - helpers.places: _contains_disliked_keyword, _resolve_place_hint
  - helpers.preferences: _get_room_member_food_preferences,
    _get_room_member_constraints, _get_room_member_constraints_named,
    _build_group_constraints_summary, _build_named_constraints_summary
  - helpers.json_extract: _extract_json_array
  - nodes.vote_card: _card_payload_meeting_id, _ensure_pending_meeting_id
  - app.db.session.AsyncSessionLocal
  - app.services.gemini.call_gemini
  - (옵션) app.services.ml_recommend.ml_place_search
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.gemini import call_gemini
from app.services.pipeline.helpers.json_extract import _extract_json_array
from app.services.pipeline.helpers.messaging import (
    _emit_assistant_message,
    _handle_node_exception,
    _has_node_error,
)
from app.services.pipeline.helpers.places import (
    _contains_disliked_keyword,
    _resolve_place_hint,
)
from app.services.pipeline.helpers.preferences import (
    _build_group_constraints_summary,
    _build_named_constraints_summary,
    _get_room_member_constraints,
    _get_room_member_constraints_named,
    _get_room_member_food_preferences,
)
from app.services.pipeline.nodes.vote_card import (
    _card_payload_meeting_id,
    _ensure_pending_meeting_id,
)
from app.services.pipeline.state import GraphState

logger = logging.getLogger(__name__)

try:
    from app.services.ml_recommend import ml_place_search as _ml_place_search
    _ML_AVAILABLE = True
except Exception:
    _ml_place_search = None  # type: ignore[assignment]
    _ML_AVAILABLE = False


async def _run_place_self_correction(
    place_list: list[dict[str, Any]],
    disliked_foods: list[str],
) -> list[dict[str, Any]]:
    if not place_list or not disliked_foods:
        return place_list

    prompt = (
        "다음 장소 추천 목록에서 "
        f"{json.dumps(disliked_foods, ensure_ascii=False)}"
        "에 해당하는 항목이 있으면 제거하고, 제거된 경우 그 이유를 reason 필드에 추가해줘: "
        f"{json.dumps(place_list, ensure_ascii=False)}\n"
        "반드시 JSON 배열만 반환하세요."
    )
    try:
        corrected_places = _extract_json_array(await call_gemini(prompt))
    except Exception:
        return place_list
    if not corrected_places:
        return place_list

    original_by_id = {
        str(place.get("place_id")): dict(place)
        for place in place_list
        if place.get("place_id") not in (None, "")
    }
    merged_places: list[dict[str, Any]] = []
    for corrected_place in corrected_places:
        place_id = str(corrected_place.get("place_id", ""))
        base_place = original_by_id.get(place_id, {})
        merged_places.append({**base_place, **corrected_place})
    return merged_places


async def place_recommendation(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    try:
        if _has_node_error(state):
            return state
        # Fix J: place cards join the same lifecycle as vote/maedeup cards.
        # If no upstream vote exists, create a pending meeting row so the card
        # still has a non-null meeting_id for frontend upsert.
        meeting_id = _card_payload_meeting_id(state.get("vote_card_payload"))
        if state.get("confirmed_place"):
            if meeting_id is None:
                meeting_id = await _ensure_pending_meeting_id(
                    state,
                    f"{state.get('meeting_type') or '모임'} 장소 추천",
                )
            state["place_recommendation_payload"] = {
                "type": "place_recommendation",
                "room_id": state["room_id"],
                "meeting_id": meeting_id,
                "place_hint": state.get("place_hint"),
                "recommendations": [
                    {
                        "name": state.get("confirmed_place"),
                        "score": 1.0,
                        "is_confirmed": True,
                    }
                ],
            }
            state["status"] = "place_recommended"
            logger.info("[TIMING] place_recommendation (confirmed): %.2fs", time.monotonic() - _t0)
            return state

        if not state.get("place_hint"):
            resolved = _resolve_place_hint(state)
            if not resolved:
                # 장소 힌트가 없으면 추천 건너뜀
                state["status"] = "place_skipped"
                logger.info("[TIMING] place_recommendation (skipped, no hint): %.2fs", time.monotonic() - _t0)
                return state
            state["place_hint"] = resolved

        place_results = list(state.get("place_search_results", []))
        ranked_places = place_results
        disliked_foods = await _get_room_member_food_preferences(state)
        # 6 카테고리 personal data 합산 (Gemini prompt용 — 익명).
        member_constraints = await _get_room_member_constraints(state)
        # 해결점 A5-2: 카드 reasoning은 강도순 차등 (강한 제약은 이름 명시 + ✨, 약한 선호는 익명).
        # ⚠ Privacy trade-off (Codex review 2026-05-07 P1, 시연용 의도적 수용):
        # group_constraints_summary는 place_recommendation_payload에 포함되어 shared agent
        # 채널로 broadcast + Redis 24h 캐시. 즉 다른 멤버들이 누가 어떤 식단/지역 제약을
        # 갖는지 보게 됨 — 이전 _build_group_constraints_summary 익명 톤의 의도와 충돌.
        # 사용자 결정 (2026-05-07): 시연 magical moment를 위해 노출 허용. 시연 후 정교화 항목:
        #   - User에 share_name_in_recommendations 플래그 추가 + opt-in 멤버만 이름 노출
        #   - 또는 trigger 사용자에게만 named version, 다른 멤버는 anonymous 표기
        per_user_constraints = await _get_room_member_constraints_named(state)
        group_constraints_summary = (
            _build_named_constraints_summary(per_user_constraints)
            or _build_group_constraints_summary(member_constraints)
        )

        _ml_ranked = False
        headcount = state.get("headcount") or 0
        meeting_type = state.get("meeting_type") or "모임"

        if _ML_AVAILABLE and state.get("place_hint"):
            try:
                ml_results = await _ml_place_search(
                    location=state.get("place_hint"),
                    meeting_type=meeting_type,
                    headcount=headcount,
                    top_k=5,
                )
                if ml_results:
                    ranked_places = ml_results
                    _ml_ranked = True
                    logger.info("[ML] ml_place_search 성공: %d개", len(ml_results))
            except Exception as _ml_err:
                logger.warning("[ML] ml_place_search 실패, Gemini fallback: %s", _ml_err)

        if not _ml_ranked and place_results:
            # 시연 latency 최적화 (2026-05-08): top 10 → top 5.
            # 측정상 place_recommendation 노드가 ~40s 단일 병목, prompt + output 토큰 절반 줄임.
            # frontend는 어차피 top 5만 노출 (line 아래 ranked_places[:5]).
            # Kakao API 응답이 이미 relevance/distance 정렬이라 top 5도 양질.
            top_candidates = place_results[:5]

            # --- OPTIMIZATION: Skip Gemini scoring for small result sets (<=3) ---
            if len(top_candidates) <= 3:
                logger.info("[OPT] Skipping Gemini place scoring: only %d candidates, using distance-based scores", len(top_candidates))
                reranked: list[dict[str, Any]] = []
                for place in top_candidates:
                    place_copy = dict(place)
                    # Apply disliked food penalty using rule-based check
                    disliked_keyword = _contains_disliked_keyword(
                        str(place_copy.get("category", "")),
                        disliked_foods,
                    )
                    if disliked_keyword:
                        place_copy["score"] = 0.1
                        place_copy["reason"] = (
                            f"멤버 비선호 음식인 {disliked_keyword} 카테고리와 겹쳐 점수를 낮췄어요."
                        )
                    reranked.append(place_copy)
                reranked.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
                ranked_places = reranked + place_results[5:]
            else:
                # Gemini scoring for larger result sets (>3)
                scoring_payload = [
                    {
                        "place_id": place.get("place_id", ""),
                        "name": place.get("name", ""),
                        "address": place.get("address", ""),
                        "category": place.get("category", ""),
                    }
                    for place in top_candidates
                ]
                time_context = ""
                if state.get("confirmed_date") and state.get("confirmed_time"):
                    time_context = (
                        f"이 모임은 {state['confirmed_date']} {state['confirmed_time']}에 예정되어 있습니다. "
                        "해당 시간대에 영업하는 장소를 우선 추천해주세요.\n"
                    )
                elif state.get("confirmed_date"):
                    time_context = (
                        f"이 모임은 {state['confirmed_date']}에 예정되어 있습니다. "
                        "해당 일정에 어울리는 장소를 우선 추천해주세요.\n"
                    )
                dislike_context = ""
                if disliked_foods:
                    dislike_context = (
                        f"멤버 중 {', '.join(disliked_foods)}을(를) 못 먹는 사람이 있으니 "
                        "해당 카테고리 장소 점수를 낮춰줘.\n"
                    )
                # 6 카테고리 personal data를 prompt에 추가 — 익명 합산 형태.
                constraints_context = ""
                if member_constraints.get("food_restrictions"):
                    constraints_context += (
                        f"멤버 중 {', '.join(member_constraints['food_restrictions'])} "
                        "회피가 있으니 해당 음식 식당 점수를 강하게 낮춰줘.\n"
                    )
                if member_constraints.get("disliked_areas"):
                    constraints_context += (
                        f"멤버 중 {', '.join(member_constraints['disliked_areas'])} "
                        "지역을 회피하는 사람이 있으니 해당 지역 점수를 낮춰줘.\n"
                    )
                if member_constraints.get("liked_areas"):
                    constraints_context += (
                        f"멤버 중 {', '.join(member_constraints['liked_areas'])} "
                        "지역을 선호하는 사람이 있으니 해당 지역 점수를 살짝 올려줘.\n"
                    )
                if member_constraints.get("transport_mode"):
                    transports = ", ".join(member_constraints["transport_mode"])
                    constraints_context += (
                        f"멤버 이동수단: {transports}. 대중교통이 있으면 역세권을, "
                        "도보가 있으면 가까운 곳을 우선.\n"
                    )
                scoring_prompt = (
                    "당신은 매듭 AI입니다. 한국인들의 모임 일정과 장소 조율을 돕는 "
                    "어시스턴트입니다.\n"
                    f"아래 장소 후보들을 {headcount}명 {meeting_type} 모임에 얼마나 적합한지 "
                    "0부터 1 사이 점수로 평가하세요.\n"
                    f"{time_context}"
                    f"{dislike_context}"
                    f"{constraints_context}"
                    "반드시 JSON 배열만 반환하세요.\n"
                    '형식: [{\"place_id\": \"...\", \"score\": 0.9}]\n'
                    "place_id는 입력과 동일해야 하며, 모든 후보를 빠짐없이 포함하세요.\n\n"
                    f"장소 후보:\n{json.dumps(scoring_payload, ensure_ascii=False)}"
                )
                try:
                    score_items = _extract_json_array(await call_gemini(scoring_prompt))
                    score_map = {
                        str(item.get("place_id")): float(item.get("score"))
                        for item in score_items
                        if item.get("place_id") not in (None, "")
                    }
                    reranked = []
                    for place in top_candidates:
                        place_copy = dict(place)
                        place_copy["score"] = score_map.get(str(place.get("place_id")), 0.5)
                        disliked_keyword = _contains_disliked_keyword(
                            str(place_copy.get("category", "")),
                            disliked_foods,
                        )
                        if disliked_keyword and float(place_copy.get("score", 0.0)) > 0.6:
                            place_copy["score"] = 0.1
                            place_copy["reason"] = (
                                f"멤버 비선호 음식인 {disliked_keyword} 카테고리와 겹쳐 점수를 낮췄어요."
                            )
                        reranked.append(place_copy)
                    reranked.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
                    ranked_places = reranked + place_results[5:]
                except Exception:
                    ranked_places = []
                    for place in place_results:
                        place_copy = dict(place)
                        place_copy["score"] = 0.5
                        ranked_places.append(place_copy)
        elif not _ml_ranked:
            ranked_places = []

        # --- OPTIMIZATION: Skip self-correction Gemini call when no disliked foods ---
        if ranked_places and disliked_foods:
            top_ranked_places = [dict(place) for place in ranked_places[:5]]
            corrected_places = await _run_place_self_correction(top_ranked_places, disliked_foods)
            remaining_places = ranked_places[5:]
            ranked_places = corrected_places + remaining_places
        elif ranked_places:
            logger.info("[OPT] Skipping place self-correction: no disliked foods")

        state["place_search_results"] = ranked_places
        if meeting_id is None:
            meeting_id = await _ensure_pending_meeting_id(
                state,
                f"{state.get('meeting_type') or '모임'} 장소 추천",
            )
        state["place_recommendation_payload"] = {
            "type": "place_recommendation",
            "room_id": state["room_id"],
            "meeting_id": meeting_id,
            "place_hint": state.get("place_hint"),
            "recommendations": ranked_places[:5],
            # 익명 group constraint 요약 (디자인 P2). 누가 어떤 값을 가졌는지는
            # 식별되지 않음. 프론트는 추천 카드 옆에 이 문장을 reasoning으로 노출.
            "group_constraints_summary": group_constraints_summary,
        }
        state["status"] = "place_recommended"

        # 새로고침 복구용 — 장소 추천 페이로드를 Redis에 캐시 (24h TTL).
        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            try:
                await r.set(
                    f"room_place_rec:{state['room_id']}",
                    json.dumps(state["place_recommendation_payload"], ensure_ascii=False),
                    ex=86400,
                )
            finally:
                await r.aclose()
        except Exception:
            logger.debug("place_rec cache failed", exc_info=True)

        # Narrator: 카드만 띄우고 끝내면 사용자가 "AI가 대답 안 했나?" 헷갈림.
        try:
            count = len(ranked_places[:5])
            hint = state.get("place_hint") or "요청하신 지역"
            narrator = (
                f"{hint} 근처 추천 장소 {count}개를 정리했어요. 📍 아래 카드에서 확인해 주세요."
                if count > 0
                else "추천 장소를 정리해봤어요. 📍 아래 카드를 확인해 주세요."
            )
            async with AsyncSessionLocal() as db:
                await _emit_assistant_message(state["room_id"], db, narrator, state, shared=True)
        except Exception:
            logger.debug("place_recommendation narrator emit failed", exc_info=True)

        logger.info("[TIMING] place_recommendation: %.2fs", time.monotonic() - _t0)
        return state
    except Exception as exc:
        return await _handle_node_exception("place_recommendation", state, exc)
