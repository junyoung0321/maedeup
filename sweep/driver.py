"""방 1개의 다자 대화를 끝까지 구동하며 카드 관찰·불변조건 체크·전사 기록."""
from __future__ import annotations

import asyncio
import json
import time

from sweep.client import SweepClient
from sweep.invariants import check_card_payload, check_frame, check_state_consistency
from sweep.personas import Persona
from sweep.simulator import GeminiCall, generate_utterance
from sweep.transcript import RoomTranscript, Turn

_CARD_TYPES = {"vote_card", "place_recommendation", "maedeup_card"}


async def _collect_frames(ws, *, window_s: float) -> list[dict]:
    """window_s 동안 들어오는 프레임 수집 (트리거 후 카드 대기)."""
    frames: list[dict] = []
    deadline = time.monotonic() + window_s
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic())
        except asyncio.TimeoutError:
            break
        try:
            frames.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return frames


async def run_room(
    client: SweepClient,
    room_id: int,
    members: list[tuple[Persona, dict]],   # (persona, guest_join_result)
    *,
    gemini_call: GeminiCall,
    max_turns: int = 12,
    card_window_s: float = 8.0,
) -> RoomTranscript:
    transcript = RoomTranscript(room_id=room_id,
                                persona_keys=[p.key for p, _ in members])
    host_persona, host_join = members[0]
    history: list[str] = []

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
            else:
                await client.send_social(room_id, join["token"], join["name"], text)
                trigger = None

            frames = await _collect_frames(agent_ws, window_s=card_window_s)
            cards = [f for f in frames if f.get("type") in _CARD_TYPES]
            latency = (time.monotonic() - t0) if cards else None

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

            # maedeup_card가 나오면 확정 → 종료
            if any(c.get("type") == "maedeup_card" for c in cards):
                break

    return transcript
