"""
잡담↔모임 전환 트리거 시나리오 검증 (브라우저 없음).

5개 시나리오를 각각 새 방에서 돌려서 게이트 1/2/4 발화 여부 측정.

시나리오:
  A. 잡담3 + 모임1 → 60s 대기 → 모임2 (쿨다운 만료 후 재시도)
  B. 잡담3 + '금요일 7시로 하자'(conclusion 키워드) (게이트 2)
  C. 잡담1 + 모임3 (모임 메시지 우세 시 judge 판정)
  D. 모임4 (baseline — 데모와 동일, 비교 기준)
  E. 잡담3 + 'AI야 정해줘'(AI 패널 direct) — direct_request 경로 (게이트 4 quick_classify)

사전조건:
  - docker compose healthy
  - .gstack-demo-token 존재
"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import redis.asyncio as aioredis
import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000"
REDIS_URL = "redis://localhost:6379/0"


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def hr(label: str, char: str = "=") -> None:
    bar = char * 72
    print(f"\n{bar}\n  {label}\n{bar}", flush=True)


@dataclass
class Sender:
    user_id: int
    name: str
    token: str


def host_create_room(host_token: str, name: str) -> int:
    req = urllib.request.Request(
        f"{API}/api/v1/rooms/",
        data=json.dumps({"name": name, "category": "식사"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {host_token}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return int(json.loads(r.read())["id"])


def host_sender(host_token: str) -> Sender:
    parts = host_token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + "===").decode())
    return Sender(user_id=int(payload["sub"]), name=payload.get("name", "host"), token=host_token)


def join_guest(room_id: int, name: str) -> Sender:
    req = urllib.request.Request(
        f"{API}/api/v1/rooms/{room_id}/guest-join",
        data=json.dumps({"display_name": name}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        body = json.loads(r.read())
    return Sender(user_id=body["user_id"], name=body["name"], token=body["token"])


async def send_chat(room_id: int, sender: Sender, content: str) -> None:
    uri = f"{WS}/ws/social/{room_id}?token={sender.token}"
    async with websockets.connect(uri) as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({"role": "user", "content": content, "sender": sender.name}))
        await asyncio.sleep(0.8)


async def send_ai_direct(room_id: int, sender: Sender, content: str) -> None:
    """AI 패널 직접 입력 (direct_request 경로)."""
    uri = f"{WS}/ws/agent/{room_id}?token={sender.token}"
    async with websockets.connect(uri) as ws:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({"role": "user", "content": content, "sender": sender.name}))
        await asyncio.sleep(0.8)


async def watch_agent_channel(redis: aioredis.Redis, room_id: int, captured: list) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"agent:{room_id}")
    try:
        async for msg in pubsub.listen():
            if msg["type"] != "message":
                continue
            try:
                data = json.loads(msg["data"])
            except (json.JSONDecodeError, TypeError):
                continue
            if data.get("type") == "ai_auto_trigger":
                ts = time.strftime("%H:%M:%S")
                captured.append({"ts": ts, **data})
                log(f"  >>> TRIGGER: reason={data.get('trigger_reason')} "
                    f"intent={data.get('intent')} judge={data.get('judge_reason', '')!r}")
    except asyncio.CancelledError:
        pass
    finally:
        with __import__("contextlib").suppress(Exception):
            await pubsub.unsubscribe(f"agent:{room_id}")
            await pubsub.aclose()


async def show_state(redis: aioredis.Redis, room_id: int, label: str) -> None:
    counter = await redis.get(f"social_msg_count:{room_id}")
    cooldown = await redis.get(f"social_judge_cooldown:{room_id}")
    counter_val = counter.decode() if isinstance(counter, bytes) else counter or "0"
    cooldown_val = "ON" if cooldown else "off"
    log(f"  [{label}] counter={counter_val} cooldown={cooldown_val}")


async def run_scenario(
    name: str,
    purpose: str,
    messages: list,  # [(idx, content)]
    senders: list,
    host_token: str,
    extra: callable | None = None,
) -> dict:
    """단일 시나리오 실행 → {triggers, fired_at_msg, counter_final, room_id}."""
    hr(f"{name}", "─")
    log(f"  목적: {purpose}")

    room_id = host_create_room(host_token, name)
    log(f"  방 생성: id={room_id}")

    redis = aioredis.from_url(REDIS_URL)
    await redis.delete(f"social_msg_count:{room_id}", f"social_judge_cooldown:{room_id}")

    captured: list = []
    watch_task = asyncio.create_task(watch_agent_channel(redis, room_id, captured))
    await asyncio.sleep(0.3)

    for i, (idx, content) in enumerate(messages, 1):
        sender = senders[idx]
        log(f"  msg{i} [{sender.name}]: {content!r}")
        try:
            await send_chat(room_id, sender, content)
        except Exception as e:
            log(f"  [ERROR] WS send failed: {e}")
        await asyncio.sleep(2.5)  # judge 호출/응답 시간
        await show_state(redis, room_id, f"after msg{i}")

    if extra:
        await extra(room_id, senders, redis)

    await asyncio.sleep(3.0)  # 최종 trigger 잡기
    watch_task.cancel()
    with __import__("contextlib").suppress(asyncio.CancelledError):
        await watch_task
    await redis.aclose()

    return {
        "name": name,
        "room_id": room_id,
        "msg_count": len(messages),
        "triggers": captured,
    }


async def main() -> None:
    token_path = Path(".gstack-demo-token")
    if not token_path.exists():
        print("[ERROR] .gstack-demo-token 없음", file=sys.stderr)
        sys.exit(1)
    host_token = token_path.read_text().strip()

    hr("Setup")
    host = host_sender(host_token)

    # 한 번만 게스트 생성 (방 ID 무관하게 토큰 발급되니 시나리오마다 새 게스트)
    # 단순화를 위해 각 시나리오별 방 + 그 방 게스트로 진행
    log(f"호스트: {host.name}(uid={host.user_id})")

    results = []

    # ─── 시나리오 D: baseline (모임4) ────────────────────────────
    room_d_setup = host_create_room(host_token, "D-baseline-setup-room")
    sd_g1 = join_guest(room_d_setup, "수현_D")
    sd_g2 = join_guest(room_d_setup, "민수_D")
    # 실제 시나리오는 새 방에서. 위는 게스트 토큰만 빌림 (게스트는 가입한 방에서만 쓸 수 있음)
    # → 방별로 게스트 새로 만들어야 함

    async def scenario_with_fresh_guests(name, purpose, msgs, extra=None):
        room = host_create_room(host_token, name)
        g1 = join_guest(room, "수현")
        g2 = join_guest(room, "민수")
        senders = [host, g1, g2]

        redis = aioredis.from_url(REDIS_URL)
        await redis.delete(f"social_msg_count:{room}", f"social_judge_cooldown:{room}")

        captured: list = []
        watch_task = asyncio.create_task(watch_agent_channel(redis, room, captured))
        await asyncio.sleep(0.3)

        hr(f"{name}", "─")
        log(f"  목적: {purpose}")
        log(f"  방 id={room}, 참가자: {host.name}/{g1.name}/{g2.name}")

        for i, (idx, content) in enumerate(msgs, 1):
            sender = senders[idx]
            log(f"  msg{i} [{sender.name}]: {content!r}")
            try:
                await send_chat(room, sender, content)
            except Exception as e:
                log(f"  [ERROR] {e}")
            await asyncio.sleep(4.5)  # classify_intent gemini fallback ~3s + 여유
            await show_state(redis, room, f"after msg{i}")

        if extra:
            await extra(room, senders, redis)

        await asyncio.sleep(10.0)  # 마지막 메시지 classify + judge LLM 완료 대기
        watch_task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await watch_task
        await redis.aclose()
        return {"name": name, "room": room, "msg_count": len(msgs), "triggers": captured}

    # ─── F. 원 실패 케이스 재현 (잡담3 + 모임5 fast) ─────────────
    results.append(await scenario_with_fresh_guests(
        "F. 잡담3 + 모임5 fast (원 버그)",
        "픽스 전 NO TRIGGER였던 원 케이스. 픽스 후엔 모임 카운터로 모임4에서 trigger 기대.",
        [
            (0, "오늘 점심 뭐 먹었어?"),
            (1, "치킨 시켜먹었어 ㅎㅎ"),
            (2, "ㅋㅋ 나는 김밥"),
            (0, "근데 우리 이번 주에 한번 모이자"),
            (1, "오 좋아 금요일 저녁 어때?"),
            (2, "금요일은 알바라 안 돼"),
            (1, "그럼 토요일?"),
            (0, "토요일은 가족 모임"),
        ],
    ))

    # ─── D. baseline ─────────────────────────────────────────────
    results.append(await scenario_with_fresh_guests(
        "D. 모임4 baseline",
        "데모와 동일. 처음부터 모임 + stalemate. 기준점.",
        [
            (0, "우리 이번 주에 밥 먹자! 언제가 좋아?"),
            (1, "나는 금요일 저녁이 좋은데"),
            (2, "금요일은 알바 있어서 안 돼 ㅠ 토요일은?"),
            (1, "토요일은 가족 모임이라 힘들어"),
        ],
    ))

    # ─── C. 잡담1 + 모임3 ────────────────────────────────────────
    results.append(await scenario_with_fresh_guests(
        "C. 잡담1 + 모임3",
        "judge가 호출될 때 모임 메시지가 많으면 stalemate 인식하는지",
        [
            (0, "오늘 점심 뭐 먹었어?"),
            (1, "근데 우리 이번 주에 밥 먹자"),
            (2, "금요일은 알바라 안 돼 ㅠ 토요일은?"),
            (1, "토요일은 가족 모임"),
        ],
    ))

    # ─── B. 잡담3 + conclusion 키워드 ────────────────────────────
    results.append(await scenario_with_fresh_guests(
        "B. 잡담3 + conclusion('하자')",
        "게이트 2 정규식 — 잡담 뒤에도 '확정/하자' 키워드면 즉시 트리거",
        [
            (0, "오늘 점심 뭐 먹었어?"),
            (1, "치킨 시켜먹었어 ㅎㅎ"),
            (2, "나는 김밥"),
            (0, "그럼 우리 금요일 저녁 7시로 하자!"),  # '하자' → 게이트 2
        ],
    ))

    # ─── A. 잡담3 + 모임1 + wait 60s + 모임2 ─────────────────────
    async def wait_60s_then_two(room, senders, redis):
        log(f"  [WAIT] 60초 쿨다운 만료 대기 중...")
        await asyncio.sleep(62.0)
        await show_state(redis, room, "post-wait")
        log(f"  msg5 [{senders[1].name}]: '금요일 저녁 어때?'")
        try:
            await send_chat(room, senders[1], "금요일 저녁 어때?")
        except Exception as e:
            log(f"  [ERROR] {e}")
        await asyncio.sleep(3.0)
        await show_state(redis, room, "after msg5")
        log(f"  msg6 [{senders[2].name}]: '금요일은 알바라 안 돼ㅠ'")
        try:
            await send_chat(room, senders[2], "금요일은 알바라 안 돼ㅠ")
        except Exception as e:
            log(f"  [ERROR] {e}")
        await asyncio.sleep(3.0)
        await show_state(redis, room, "after msg6")

    results.append(await scenario_with_fresh_guests(
        "A. 잡담3 + 모임1 + 60s 대기 + 모임2",
        "쿨다운 만료 후 후속 모임 메시지가 judge를 재호출하는지",
        [
            (0, "오늘 점심 뭐 먹었어?"),
            (1, "치킨 시켜먹었어 ㅎㅎ"),
            (2, "나는 김밥"),
            (0, "근데 우리 이번 주에 한번 모이자"),
        ],
        extra=wait_60s_then_two,
    ))

    # ─── E. 잡담3 + AI 패널 직접 ──────────────────────────────
    async def ai_panel_direct(room, senders, redis):
        log(f"  msg4 [AI 패널, {senders[0].name}]: '금요일 저녁 약속 잡아줘'")
        try:
            await send_ai_direct(room, senders[0], "금요일 저녁 약속 잡아줘")
        except Exception as e:
            log(f"  [ERROR] WS agent send: {e}")
        await asyncio.sleep(3.0)
        await show_state(redis, room, "after AI direct")

    results.append(await scenario_with_fresh_guests(
        "E. 잡담3 + AI 패널 direct",
        "사용자가 AI 패널에 직접 '약속 잡아줘' → quick_classify direct_request",
        [
            (0, "오늘 점심 뭐 먹었어?"),
            (1, "치킨 시켜먹었어"),
            (2, "나는 김밥"),
        ],
        extra=ai_panel_direct,
    ))

    # ─── 결과 ──────────────────────────────────────────────────
    hr("최종 요약")
    for r in results:
        label = "✓ FIRED" if r["triggers"] else "✗ NO TRIGGER"
        log(f"{label} | {r['name']} (방 {r['room']}, 메시지 {r['msg_count']}, 트리거 {len(r['triggers'])}건)")
        for t in r["triggers"]:
            log(f"      reason={t.get('trigger_reason')} intent={t.get('intent')} judge={t.get('judge_reason','')!r}")


if __name__ == "__main__":
    asyncio.run(main())
