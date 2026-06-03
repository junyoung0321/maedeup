"""방 1개의 다자 대화를 끝까지 구동하며 카드 관찰·불변조건 체크·전사 기록."""
from __future__ import annotations

import asyncio
import json
import time

from sweep.client import SweepClient
from sweep.invariants import (
    check_card_payload,
    check_frame,
    check_state_consistency,
    check_vote_storm,
)
from sweep.personas import Persona
from sweep.scenarios import Scenario, assert_expected
from sweep.simulator import GeminiCall, generate_utterance
from sweep.transcript import RoomTranscript, Turn

_CARD_TYPES = {"vote_card", "place_recommendation", "maedeup_card"}


async def _collect_frames(
    ws, *, window_s: float, grace_s: float = 1.0
) -> tuple[list[dict], float | None]:
    """window_s 동안 프레임 수집. 첫 카드 도착 후엔 grace_s만 더 대기(공동 발급 카드 포착).

    반환: (frames, 첫 카드 수신 monotonic 시각 또는 None).
    첫 카드 시각을 따로 반환하므로 트리거→카드 지연을 window 길이가 아닌
    실제 도착 시점으로 측정할 수 있다(K1 SLA 측정 정확도).
    """
    frames: list[dict] = []
    first_card_t: float | None = None
    deadline = time.monotonic() + window_s
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic())
        except asyncio.TimeoutError:
            break
        try:
            frame = json.loads(raw)
        except json.JSONDecodeError:
            continue
        frames.append(frame)
        if first_card_t is None and frame.get("type") in _CARD_TYPES:
            first_card_t = time.monotonic()
            # 첫 카드 도착 — grace 후 종료해 런타임 절약 + 지연을 정확히 측정
            deadline = min(deadline, first_card_t + grace_s)
    return frames, first_card_t


async def run_room(
    client: SweepClient,
    room_id: int,
    members: list[tuple[Persona, dict]],   # (persona, guest_join_result)
    *,
    gemini_call: GeminiCall,
    max_turns: int = 12,
    card_window_s: float = 8.0,
    enable_vote_storm: bool = False,
) -> RoomTranscript:
    transcript = RoomTranscript(room_id=room_id,
                                persona_keys=[p.key for p, _ in members])
    host_persona, host_join = members[0]
    history: list[str] = []

    # GOAL 4: 이 방에서 카드가 발급된 적 있는지 추적 (coarse proxy)
    # NOTE: WS 레벨 하네스는 다른 사용자 화면의 카드 소거 이벤트를 관찰할 수 없다.
    # maedeup_card 직전 window 내에서 vote_card/place_recommendation 가 함께 보인 경우만
    # stale_cards 검사를 수행한다 — 다른 창의 소거 여부는 알 수 없으므로 과탐(false positive)
    # 방지를 위해 동일 window 동시 관측 한정으로만 체크한다.
    _seen_vote_card = False
    _seen_place_card = False

    # host가 /ws/agent 리스너를 열어 트리거 후 카드를 수신
    async with client.agent_listener(room_id, host_join["token"]) as agent_ws:
        for turn_i in range(max_turns):
            persona, join = members[turn_i % len(members)]
            text = await generate_utterance(persona, history, turn_i, gemini_call=gemini_call)
            history.append(f"{persona.label}: {text}")

            t0 = time.monotonic()
            # host 차례엔 direct_request(트리거), 그 외엔 social 발화
            if persona.key == "host":
                await client.direct_request(room_id, join["token"], join["name"], text)
                trigger = "direct_request"
                window = card_window_s
            else:
                await client.send_social(room_id, join["token"], join["name"], text)
                trigger = None
                # 비-호스트 발화 후 짧게만 대기해 런타임 절약 (트리거 아님)
                window = 2.0

            frames, first_card_t = await _collect_frames(agent_ws, window_s=window)
            cards = [f for f in frames if f.get("type") in _CARD_TYPES]
            latency = (first_card_t - t0) if first_card_t is not None else None

            # 불변조건: 프레임 에러 + 카드 payload
            for f in frames:
                transcript.violations.extend(check_frame(f))
            for c in cards:
                transcript.violations.extend(check_card_payload(c))
            # 트리거를 쐈는데 어떤 응답도 없으면 침묵 드롭
            if trigger and not frames:
                from sweep.invariants import Violation
                transcript.violations.append(Violation("silent_drop", f"turn {turn_i} 트리거 무응답"))

            transcript.add_turn(Turn(speaker=persona.key, text=text,
                                     trigger_reason=trigger, cards=cards, latency_s=latency))

            # GOAL 4: 카드 누적 추적 (이전 턴에서 발급된 카드 기억)
            for c in cards:
                if c.get("type") == "vote_card":
                    _seen_vote_card = True
                elif c.get("type") == "place_recommendation":
                    _seen_place_card = True

            # maedeup_card가 나오면 확정 → 종료
            if any(c.get("type") == "maedeup_card" for c in cards):
                # GOAL 4: 동일 window 내 vote_card/place_card와 maedeup_card가 함께 관측된
                # 경우만 stale 체크 (같은 frame batch이므로 소거가 안 된 상황에 해당).
                # 이전 턴에서만 봤던 카드는 이미 소거됐을 가능성이 있으므로 검사에서 제외.
                this_window_vote = any(c.get("type") == "vote_card" for c in cards)
                this_window_place = any(c.get("type") == "place_recommendation" for c in cards)
                transcript.violations.extend(check_state_consistency(
                    finalized=True,
                    active_reco_cards=1 if this_window_place else 0,
                    active_vote_cards=1 if this_window_vote else 0,
                ))
                break

            # GOAL 3: vote_card가 처음 관측됐을 때 동시 투표 경합 검사
            if enable_vote_storm:
                for c in cards:
                    if c.get("type") == "vote_card" and c.get("meeting_id"):
                        meeting_id = int(c["meeting_id"])
                        voters = [(join_["token"], 0) for _, join_ in members]
                        try:
                            storm_results = await concurrent_vote_storm(
                                client, meeting_id, voters
                            )
                            transcript.violations.extend(
                                check_vote_storm(storm_results)
                            )
                        except Exception as exc:
                            from sweep.invariants import Violation
                            transcript.violations.append(
                                Violation("vote_storm_error", repr(exc))
                            )
                        # 한 turn에 vote_card 1개만 처리
                        break

    return transcript


async def concurrent_vote_storm(
    client: SweepClient,
    meeting_id: int,
    voters: list[tuple[str, int]],   # (token, option_index)
) -> list[dict]:
    """전원이 동시에 투표 — race condition 검증 (스펙 §6, K3.1)."""
    results = await asyncio.gather(
        *[client.vote(meeting_id, tok, opt) for tok, opt in voters],
        return_exceptions=True,
    )
    return [r if not isinstance(r, Exception) else {"error": repr(r)} for r in results]


async def run_scenario(
    client: SweepClient,
    scenario: Scenario,
    *,
    host_token: str,
    persona_label_by_key: dict[str, str],
) -> tuple[str, list[str]]:
    """시나리오 1개를 실행하고 (scenario.key, failures) 반환.

    - 발화 순서대로 주입 (host=direct_request, 기타=send_social)
    - host agent_listener를 열어 각 발화 후 카드/assistant 메시지 수집
    - assert_expected로 기대 카드 타입·포함·제외 검증
    - 예외는 잡아서 scenario_crashed로 반환 (전체 스윗을 죽이지 않음)
    """
    try:
        room_id = await client.create_room(f"scenario-{scenario.key}")

        # 발화에 등장하는 unique persona_key → guest_join
        unique_keys: list[str] = []
        for u in scenario.utterances:
            if u.persona_key not in unique_keys:
                unique_keys.append(u.persona_key)

        # host는 반드시 포함
        if "host" not in unique_keys:
            unique_keys.insert(0, "host")

        join_by_key: dict[str, dict] = {}
        for key in unique_keys:
            label = persona_label_by_key.get(key, key)
            join_by_key[key] = await client.guest_join(room_id, label)

        # host join dict (host_token을 사용하므로 guest_join 토큰은 send_social용)
        host_join = join_by_key["host"]

        observed_cards: list[dict] = []
        assistant_text_parts: list[str] = []

        async with client.agent_listener(room_id, host_join["token"]) as agent_ws:
            for u in scenario.utterances:
                join = join_by_key[u.persona_key]
                if u.persona_key == "host":
                    await client.direct_request(room_id, join["token"], join["name"], u.text)
                    window = 8.0
                else:
                    await client.send_social(room_id, join["token"], join["name"], u.text)
                    window = 2.0

                frames, _first_card_t = await _collect_frames(agent_ws, window_s=window)
                for f in frames:
                    if f.get("type") in _CARD_TYPES:
                        observed_cards.append(f)
                    if f.get("role") == "assistant" and f.get("type") not in _CARD_TYPES:
                        assistant_text_parts.append(f.get("content", ""))

        assistant_text = " ".join(assistant_text_parts)
        failures = assert_expected(scenario, observed_cards, assistant_text)
        return (scenario.key, failures)

    except Exception as exc:
        return (scenario.key, [f"scenario_crashed: {repr(exc)}"])


async def observe_broadcast(
    client: SweepClient,
    room_id: int,
    member_tokens: list[str],
    trigger: "asyncio.Future | None" = None,
    *,
    window_s: float = 8.0,
) -> list[int]:
    """전 멤버가 /ws/agent를 동시에 구독한 상태에서 카드 이벤트 수신 수를 반환.

    각 멤버 리스너가 window_s 동안 받은 카드 프레임 개수 리스트.
    스펙 §5.6: 전원이 동일 카드 이벤트를 받아야 함 → 수신 수가 멤버마다 같아야 함.
    """
    async def _listen(token: str) -> int:
        count = 0
        async with client.agent_listener(room_id, token) as ws:
            deadline = time.monotonic() + window_s
            while time.monotonic() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic())
                except asyncio.TimeoutError:
                    break
                try:
                    if json.loads(raw).get("type") in _CARD_TYPES:
                        count += 1
                except json.JSONDecodeError:
                    continue
        return count

    return await asyncio.gather(*[_listen(t) for t in member_tokens])
