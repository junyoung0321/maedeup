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
from app.observability.snapshot import dump
from app.services.gemini import call_gemini
from app.services.pipeline.helpers.json_extract import _extract_json_array
from app.services.pipeline.helpers.messaging import (
    _emit_assistant_message,
    _handle_node_exception,
    _has_node_error,
)
from app.services.kakao_maps import KakaoApiError
from app.services.pipeline.helpers.places import (
    _contains_disliked_keyword,
    _filter_out_rejected_places,
    _resolve_place_hint,
)
from app.services.pipeline.helpers.preference_toggle import (
    compute_preference_source,
    compute_preference_toggle_enabled,
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


def _compute_final_score(item: dict[str, Any]) -> float:
    """PR-V1.5 / S20 (Q4=A): 점수 통합 공식.

    final_score = 0.4 * ml_score + 0.3 * gemini_score + 0.3 * distance_score

    Missing 값은 0.0 처리. distance_score는 search_place에서 항상 채움.
    ml_score는 ml_place_search 성공 시 박힘. gemini_score는 Gemini scoring
    분기에서 박힘. 둘 다 없으면 distance만으로 final = 0.3 * distance.
    """
    try:
        ml = float(item.get("ml_score") or 0.0)
    except (TypeError, ValueError):
        ml = 0.0
    try:
        gemini = float(item.get("gemini_score") or 0.0)
    except (TypeError, ValueError):
        gemini = 0.0
    try:
        distance = float(item.get("distance_score") or 0.0)
    except (TypeError, ValueError):
        distance = 0.0
    return round(0.4 * ml + 0.3 * gemini + 0.3 * distance, 4)


def _sort_by_final_score(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PR-V1.5 / F8 — 명시적 tiebreaker.

    1차: final_score 내림차순
    2차: distance_m 오름차순 (가까운 순)
    3차: place_id 사전순 (결정적 — 동률 시 매 실행 같은 순서)
    """
    return sorted(
        items,
        key=lambda p: (
            -float(p.get("final_score") or 0.0),
            float(p.get("distance_m") or 99999),
            str(p.get("place_id") or ""),
        ),
    )


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

    # P1 fix (2026-05-16 review): corrected 결과가 너무 짧으면 (입력의 절반 미만)
    #   Gemini가 disliked 외 항목까지 임의 누락한 회귀로 간주, 원본 유지.
    #   ex: 입력 5개 → corrected 1개 = 사용자 카드 후보 80% 손실 silently.
    if len(corrected_places) < max(1, len(place_list) // 2):
        logger.warning(
            "[OPT] self_correction returned %d items (input %d) — too few, keeping original",
            len(corrected_places), len(place_list),
        )
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
        merged = {**base_place, **corrected_place}
        # Fix #2: corrected_place에 x/y가 없으면 base 값 복원 (place_id mismatch 시 base_place={} → 증발 방지)
        for coord_key in ("x", "y"):
            if not merged.get(coord_key) and base_place.get(coord_key):
                merged[coord_key] = base_place[coord_key]
        merged_places.append(merged)
    return merged_places


def _build_place_cache_key(state: dict) -> str:
    """T5: place_search Redis cache key 생성.
    location/meeting_type/headcount normalize 후 key string 반환."""
    location = (state.get("place_hint") or "global").strip().lower()
    meeting_type = (state.get("meeting_type") or "general").strip().lower()
    headcount = state.get("headcount") or 0
    return f"maedeup:place_cache:{location}:{meeting_type}:{headcount}"


async def place_recommendation(state: GraphState) -> GraphState:
    _t0 = time.monotonic()
    dump("node_in", state.get("run_id"), {
        "node": "place_recommendation",
        "status": state.get("status"),
        "trigger_reason": state.get("trigger_reason"),
        "has_card": bool(state.get("maedeup_card_payload") or state.get("vote_card_payload")),
        "message_count": len(state.get("message_records", [])),
    })
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
            # Fix #1: confirmed_place path — x/y를 place_coord에서 보존
            _place_coord = state.get("place_coord") or {}
            _confirmed_item: dict[str, Any] = {
                "name": state.get("confirmed_place"),
                "score": 1.0,
                "is_confirmed": True,
            }
            if _place_coord.get("x"):
                _confirmed_item["x"] = _place_coord["x"]
            if _place_coord.get("y"):
                _confirmed_item["y"] = _place_coord["y"]
            state["place_recommendation_payload"] = {
                "type": "place_recommendation",
                "room_id": state["room_id"],
                "meeting_id": meeting_id,
                "place_hint": state.get("place_hint"),
                "recommendations": [_confirmed_item],
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

        # T5: place_search Redis 캐싱 — 동일 (location, type, headcount) 재호출 시 즉시 응답
        _place_cache_key = _build_place_cache_key(state)
        _t5_cached_recommendations: list[dict] | None = None
        try:
            _r_t5 = aioredis.from_url(
                settings.REDIS_URL, decode_responses=True,
                socket_connect_timeout=1, socket_timeout=1,
            )
            try:
                _cached_str = await _r_t5.get(_place_cache_key)
                if _cached_str:
                    _t5_cached_recommendations = json.loads(_cached_str)
                    logger.info(
                        "[T5_CACHE_HIT] key=%s place_count=%d",
                        _place_cache_key,
                        len(_t5_cached_recommendations) if isinstance(_t5_cached_recommendations, list) else 0,
                    )
            finally:
                await _r_t5.aclose()
        except (NameError, AttributeError, ImportError):
            raise
        except Exception:
            logger.warning("[T5_CACHE] Redis GET 실패 (cache miss 처리)", exc_info=True)

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

        if _t5_cached_recommendations is not None:
            # T5 cache hit: ML/Gemini scoring 전체 skip, cached recommendations 사용.
            ranked_places = list(_t5_cached_recommendations)
            _ml_ranked = True  # 아래 elif not _ml_ranked 블록 진입 방지
        else:
            # T5 cache miss: 기존 ML/Gemini 흐름 진행.
            # PR-V1.5 / F9: ML 비활성 메트릭 로깅 (structured log).
            if not _ML_AVAILABLE:
                logger.info(
                    "[FALLBACK] ml_disabled=true room_id=%s meeting_type=%s "
                    "headcount=%d — using Gemini + distance only",
                    state.get("room_id"), meeting_type, headcount,
                )

        if _t5_cached_recommendations is None and _ML_AVAILABLE and state.get("place_hint"):
            try:
                ml_results = await _ml_place_search(
                    location=state.get("place_hint"),
                    meeting_type=meeting_type,
                    headcount=headcount,
                    top_k=5,
                )
                if ml_results:
                    # PR-V1.5 / S20 (Q4=A): ML 결과의 score를 ml_score 슬롯에 박음.
                    # 후속 final_score = 0.4*ml_score + 0.3*gemini_score + 0.3*distance_score.
                    ranked_places = []
                    for item in ml_results:
                        item_copy = dict(item)
                        if "ml_score" not in item_copy:
                            item_copy["ml_score"] = float(item_copy.get("score") or 0.0)
                        ranked_places.append(item_copy)
                    _ml_ranked = True
                    logger.info("[ML] ml_place_search 성공: %d개", len(ml_results))
            except Exception as _ml_err:
                logger.warning("[ML] ml_place_search 실패, Gemini fallback: %s", _ml_err)

        if _t5_cached_recommendations is None and not _ml_ranked and place_results:
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
                    # PR-V1.5 / S20: Gemini 스코어 없음 → 0.0 (distance만 final에 기여).
                    place_copy.setdefault("gemini_score", 0.0)
                    if disliked_keyword:
                        # Codex P1 (2026-05-15): disliked 페널티는 final_score 자체에
                        # 반영해야 _sort_by_final_score가 disliked 항목을 뒤로 밀어냄.
                        # 기존: score=0.1만 설정했고 _compute_final_score는 disliked를
                        # 모름 → distance가 가까우면 disliked 매장이 1위로 올라가는
                        # 회귀. 명시적으로 score+final_score 둘 다 0.0으로 고정.
                        place_copy["score"] = 0.0
                        place_copy["final_score"] = 0.0
                        place_copy["reason"] = (
                            f"멤버 비선호 음식인 {disliked_keyword} 카테고리와 겹쳐 점수를 낮췄어요."
                        )
                    else:
                        place_copy["final_score"] = _compute_final_score(place_copy)
                    reranked.append(place_copy)
                # PR-V1.5 / F8: tiebreaker sort.
                reranked = _sort_by_final_score(reranked)
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
                        gemini_score = score_map.get(str(place.get("place_id")), 0.5)
                        # PR-V1.5 / S20 (Q4=A): Gemini 점수를 gemini_score 슬롯에 박음.
                        place_copy["gemini_score"] = gemini_score
                        place_copy["score"] = gemini_score  # legacy 호환
                        disliked_keyword = _contains_disliked_keyword(
                            str(place_copy.get("category", "")),
                            disliked_foods,
                        )
                        if disliked_keyword and float(place_copy.get("score", 0.0)) > 0.6:
                            place_copy["score"] = 0.1
                            place_copy["gemini_score"] = 0.1
                            place_copy["reason"] = (
                                f"멤버 비선호 음식인 {disliked_keyword} 카테고리와 겹쳐 점수를 낮췄어요."
                            )
                        # PR-V1.5 / S20: 통합 final_score 계산.
                        place_copy["final_score"] = _compute_final_score(place_copy)
                        reranked.append(place_copy)
                    # PR-V1.5 / F8: tiebreaker sort.
                    reranked = _sort_by_final_score(reranked)
                    ranked_places = reranked + place_results[5:]
                except Exception:
                    ranked_places = []
                    for place in place_results:
                        place_copy = dict(place)
                        place_copy["score"] = 0.5
                        place_copy.setdefault("gemini_score", 0.0)
                        place_copy["final_score"] = _compute_final_score(place_copy)
                        ranked_places.append(place_copy)
        elif _t5_cached_recommendations is None and not _ml_ranked:
            ranked_places = []

        # --- OPTIMIZATION: Skip self-correction Gemini call when no disliked foods ---
        if ranked_places and disliked_foods:
            top_ranked_places = [dict(place) for place in ranked_places[:5]]
            corrected_places = await _run_place_self_correction(top_ranked_places, disliked_foods)
            remaining_places = ranked_places[5:]
            ranked_places = corrected_places + remaining_places
        elif ranked_places:
            logger.info("[OPT] Skipping place self-correction: no disliked foods")

        # PR-V1.5 / S20 (Q4=A) + F8: ML ranked 또는 self_correction 후에도
        # final_score 누락 가능 → 일괄 채우고 tiebreaker 정렬.
        for place_copy in ranked_places:
            if "final_score" not in place_copy:
                place_copy.setdefault("gemini_score", 0.0)
                place_copy["final_score"] = _compute_final_score(place_copy)
        ranked_places = _sort_by_final_score(list(ranked_places))

        # PR-V1.5 / §6.15: rejected_places 최종 필터 (검색 단계에서 한 번,
        # ranking 후에도 다시 — ML/Gemini 결과에 거부 키워드가 섞일 수 있음).
        rejected_places = state.get("rejected_places") or []
        if rejected_places:
            ranked_places = _filter_out_rejected_places(ranked_places, rejected_places)

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
            # PR-Z1 (Q7=B): hybrid 그룹/발화자 토글 메타.
            "preference_source": compute_preference_source(state),
            "preference_toggle_enabled": compute_preference_toggle_enabled(state),
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

        # T5: cache miss 경로 — 결과를 Redis에 SET (TTL 30min).
        if _t5_cached_recommendations is None and ranked_places:
            try:
                _r_t5_set = aioredis.from_url(
                    settings.REDIS_URL, decode_responses=True,
                    socket_connect_timeout=1, socket_timeout=1,
                )
                try:
                    await _r_t5_set.set(
                        _place_cache_key,
                        json.dumps(ranked_places[:5], ensure_ascii=False),
                        ex=1800,
                    )
                    logger.info("[T5_CACHE_SET] key=%s ttl=1800s count=%d", _place_cache_key, len(ranked_places[:5]))
                finally:
                    await _r_t5_set.aclose()
            except (NameError, AttributeError, ImportError):
                raise
            except Exception:
                logger.warning("[T5_CACHE] Redis SET 실패 (graceful)", exc_info=True)

        # Narrator: 카드만 띄우고 끝내면 사용자가 "AI가 대답 안 했나?" 헷갈림.
        # PR-V1.5 / F7 + S18 + §6.15: narrator 분기.
        #   - kakao_api_error → "장소 검색 서비스 일시 불가".
        #   - cuisine 2개 이상 → ambiguity 안내 + 정상 추천 narrator.
        #   - place_search_empty (0건 정상 응답) → "다른 지역" 유도.
        #   - count == 0 (필터 후 0건) → 기존 fallback.
        try:
            count = len(ranked_places[:5])
            hint = state.get("place_hint") or "요청하신 지역"
            cuisines = state.get("detected_cuisines") or []
            place_empty = bool(state.get("place_search_empty"))
            kakao_error = bool(state.get("kakao_api_error"))

            narrator_parts: list[str] = []
            # F7: 장애가 최우선 — 다른 narrator 무력화.
            if kakao_error and count == 0:
                narrator_parts.append(
                    "장소 검색 서비스가 일시적으로 불가합니다. 잠시 후 다시 시도해주세요."
                )
            else:
                # S18: 다중 cuisine ambiguity narrator (정상 추천 앞에 prefix).
                if isinstance(cuisines, list) and len(cuisines) >= 2:
                    cuisine_label = "·".join(cuisines)
                    narrator_parts.append(
                        f"{cuisine_label} 모두 추천 중이에요. 한 종류만 원하시면 말씀해주세요."
                    )
                # §6.15: 정상 0건 → 지역 변경 유도.
                if place_empty and count == 0:
                    narrator_parts.append(
                        f"{hint}에서 추천 결과를 찾지 못했어요. 다른 지역을 알려주실래요?"
                    )
                elif count > 0:
                    narrator_parts.append(
                        f"{hint} 근처 추천 장소 {count}개를 정리했어요. 아래 카드에서 확인해 주세요."
                    )
                else:
                    narrator_parts.append("추천 장소를 정리해봤어요. 아래 카드를 확인해 주세요.")

            narrator = " ".join(narrator_parts).strip()
            async with AsyncSessionLocal() as db:
                await _emit_assistant_message(state["room_id"], db, narrator, state, shared=True)
        except Exception:
            # BUG-26-4 패턴 재발 방지: narrator emit 전체 try 가 NameError 묻으면
            # place 카드만 뜨고 안내 문구 없는 회귀를 무음으로 흘려보냄.
            logger.warning("place_recommendation narrator emit failed", exc_info=True)

        logger.info("[TIMING] place_recommendation: %.2fs", time.monotonic() - _t0)
        dump("node_out", state.get("run_id"), {
            "node": "place_recommendation",
            "status_after": state.get("status"),
            "card_type": (state.get("place_recommendation_payload") or {}).get("type"),
            "slot_count": len(state.get("place_search_results", [])),
        })
        return state
    except Exception as exc:
        return await _handle_node_exception("place_recommendation", state, exc)
