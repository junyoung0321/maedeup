"""K3.3 onboarding 측정 runner.

신규 참여자(guest-join) 흐름 시뮬레이션 → 막힘 지점(HTTP error / WS 연결 실패) 자동 감지.

주의:
  - 진짜 'Google OAuth 신규 가입' 시뮬 불가 (backend mock endpoint 없음).
    guest-join 신규 참여자 흐름으로 대체. Phase 3 에서 backend dev-mode
    endpoint 추가 검토 필요.
  - WS 채팅 메시지 형식: {"role": "user", "content": "..."} — type 필드 없음.
    social.py 핸들러 기준 (known msg_type: time_selection / unavailable_toggle /
    date_selection / reminder / vote_reminder — 그 외는 content 필드 처리).
  - leave_room = DELETE /api/v1/rooms/{room_id}/leave 시도.
    404/405 가 반환되면 graceful (endpoint 미구현 시 block 미기록).

사용:
  ~/.venv-maedeup-demo/bin/python3 .gstack-k3-onboarding-runner.py
  ~/.venv-maedeup-demo/bin/python3 .gstack-k3-onboarding-runner.py --fixture .gstack-fixtures/k3-onboarding-users.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

import httpx
import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000"

# guest-join 이 반환하는 token 키 우선순위 (백엔드 응답 구조에 맞게)
_TOKEN_KEYS = ("access_token", "token")

# leave_room 에서 graceful 로 처리할 HTTP 상태 코드 (endpoint 미구현 포함)
_LEAVE_GRACEFUL_STATUSES = (200, 204, 404, 405)

# wait_trigger 가 AI 개입으로 인정하는 WS 이벤트 타입
_TRIGGER_TYPES = {"ai_auto_trigger", "vote_card", "agent_message"}


def load_fixture(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_host_token() -> str:
    return Path(".gstack-demo-token").read_text().strip()


async def setup_host_room(
    client: httpx.AsyncClient, host_token: str, name: str
) -> int:
    """호스트 토큰으로 룸 생성 → room_id 반환.

    Task 4(.gstack-k3-concurrency-runner.py) 에서 확인된 path 재사용:
    POST /api/v1/rooms (trailing slash 없음, follow_redirects=True)
    """
    resp = await client.post(
        f"{API}/api/v1/rooms",
        json={"name": name, "description": "K3.3 onboarding 테스트 룸"},
        headers={"Authorization": f"Bearer {host_token}"},
        follow_redirects=True,
        timeout=10.0,
    )
    resp.raise_for_status()
    return int(resp.json()["id"])


def _extract_token(resp_json: dict) -> str | None:
    for key in _TOKEN_KEYS:
        if resp_json.get(key):
            return resp_json[key]
    return None


async def simulate_user_onboarding(
    client: httpx.AsyncClient,
    user: dict,
    host_room_map: dict,
    host_token: str,
) -> dict:
    """1 사용자 onboarding 흐름 시뮬 → 막힘 지점 dict 반환.

    host_room_map: {"host_room_1": 226, ...}
    fixture 의 room_id_target placeholder → 실제 room_id 매핑.
    """
    blocks: list[dict] = []
    trigger_observed = False
    graceful_error_observed = False

    # 사용자별 런타임 상태
    room_id: int | None = None
    token: str | None = None

    for action in user["actions"]:
        action_type = action["type"]
        try:
            if action_type == "guest_join":
                target = action["room_id_target"]
                if target == "invalid_room_id":
                    actual_room_id = 999999
                else:
                    actual_room_id = host_room_map.get(target)
                    if actual_room_id is None:
                        blocks.append({
                            "action": action_type,
                            "reason": f"unknown room_id_target: {target}",
                        })
                        continue

                resp = await client.post(
                    f"{API}/api/v1/rooms/{actual_room_id}/guest-join",
                    json={"display_name": user["name"]},
                    timeout=10.0,
                )
                expected_status = action.get("expected_status", 200)

                if resp.status_code == expected_status:
                    if resp.status_code == 200:
                        resp_json = resp.json()
                        room_id = actual_room_id
                        token = _extract_token(resp_json)
                        if token is None:
                            blocks.append({
                                "action": action_type,
                                "reason": "guest-join 200 but no token in response",
                                "keys": list(resp_json.keys()),
                            })
                    else:
                        # expected non-200 (예: 404) → graceful
                        graceful_error_observed = True
                else:
                    blocks.append({
                        "action": action_type,
                        "status": resp.status_code,
                        "expected": expected_status,
                        "body": resp.text[:200],
                    })

            elif action_type == "first_chat":
                if room_id is None or token is None:
                    blocks.append({
                        "action": action_type,
                        "reason": "no room/token (guest_join 실패 또는 미실행)",
                    })
                    continue

                # WS 채팅 send — social.py 핸들러 형식: role + content (type 필드 없음)
                ws_url = f"{WS}/ws/social/{room_id}?token={token}"
                try:
                    async with websockets.connect(ws_url) as ws:
                        payload = json.dumps(
                            {"role": "user", "content": action["content"]},
                            ensure_ascii=False,
                        )
                        await ws.send(payload)
                        # 서버가 broadcast 하는 echo 메시지 잠시 대기
                        try:
                            await asyncio.wait_for(ws.recv(), timeout=2.0)
                        except asyncio.TimeoutError:
                            pass  # echo 없어도 전송 자체는 성공으로 간주
                except Exception as ws_err:
                    blocks.append({
                        "action": action_type,
                        "error": f"{type(ws_err).__name__}: {ws_err}",
                    })

            elif action_type == "wait_trigger":
                if room_id is None or token is None:
                    blocks.append({
                        "action": action_type,
                        "reason": "no room/token (guest_join 실패 또는 미실행)",
                    })
                    continue

                timeout = action.get("timeout_s", 5)
                ws_url = f"{WS}/ws/social/{room_id}?token={token}"
                try:
                    async with websockets.connect(ws_url) as ws:
                        deadline = time.monotonic() + timeout
                        while time.monotonic() < deadline:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                break
                            try:
                                raw = await asyncio.wait_for(
                                    ws.recv(), timeout=remaining
                                )
                                data = json.loads(raw)
                                if data.get("type") in _TRIGGER_TYPES:
                                    trigger_observed = True
                                    break
                            except asyncio.TimeoutError:
                                break
                            except json.JSONDecodeError:
                                continue
                except Exception as ws_err:
                    blocks.append({
                        "action": action_type,
                        "error": f"{type(ws_err).__name__}: {ws_err}",
                    })

            elif action_type == "leave_room":
                if room_id is None or token is None:
                    # token 없어도 leave 시도 불가이므로 skip (block 미기록)
                    continue

                headers = {"Authorization": f"Bearer {token}"}
                resp = await client.delete(
                    f"{API}/api/v1/rooms/{room_id}/leave",
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code not in _LEAVE_GRACEFUL_STATUSES:
                    blocks.append({
                        "action": action_type,
                        "status": resp.status_code,
                        "body": resp.text[:200],
                    })

            else:
                blocks.append({
                    "action": action_type,
                    "reason": f"unknown action_type: {action_type}",
                })

        except Exception as e:
            blocks.append({
                "action": action_type,
                "error": f"{type(e).__name__}: {e}",
            })

    return {
        "id": user["id"],
        "blocks": blocks,
        "trigger_observed": trigger_observed,
        "graceful_error": graceful_error_observed,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="K3.3 onboarding 측정 runner (guest-join 신규 참여자 흐름)"
    )
    parser.add_argument(
        "--fixture",
        default=".gstack-fixtures/k3-onboarding-users.json",
        help="fixture JSON 경로",
    )
    args = parser.parse_args()

    fixture = load_fixture(args.fixture)
    host_token = load_host_token()

    print(f"[K3.3] === N={len(fixture)} users ===", flush=True)
    print(
        "[K3.3] NOTE: Google OAuth 신규 가입 시뮬 불가 (backend mock endpoint 없음).",
        flush=True,
    )
    print("[K3.3]       guest-join 신규 참여자 흐름으로 대체.", flush=True)

    # fixture 에서 사용되는 room_id_target placeholder 수집
    targets: set[str] = set()
    for u in fixture:
        for a in u["actions"]:
            if a.get("type") == "guest_join":
                tgt = a.get("room_id_target", "")
                if tgt and tgt != "invalid_room_id":
                    targets.add(tgt)

    # 호스트 토큰으로 placeholder 마다 룸 1개씩 생성
    host_room_map: dict[str, int] = {}
    async with httpx.AsyncClient() as client:
        print(f"\n[setup] {len(targets)} 개 룸 생성 중...", flush=True)
        for tgt in sorted(targets):
            room_name = f"K3.3 onb {tgt} {uuid.uuid4().hex[:6]}"
            try:
                rid = await setup_host_room(client, host_token, room_name)
                host_room_map[tgt] = rid
                print(f"  {tgt} → room_id={rid}", flush=True)
            except Exception as e:
                print(f"  ERROR setup {tgt}: {type(e).__name__}: {e}", flush=True)

        print(f"\n[run] 사용자 시나리오 실행 중...", flush=True)
        results: list[dict] = []
        for u in fixture:
            print(f"  [{u['id']}] {u['scenario']}", flush=True)
            try:
                r = await simulate_user_onboarding(client, u, host_room_map, host_token)
                results.append(r)
                mark = "OK" if len(r["blocks"]) == 0 else "NG"
                print(
                    f"    {mark} blocks={len(r['blocks'])} "
                    f"trigger={r['trigger_observed']} "
                    f"graceful_err={r['graceful_error']}",
                    flush=True,
                )
                for b in r["blocks"]:
                    print(f"      block: {b}", flush=True)
            except Exception as e:
                print(f"    ERROR: {type(e).__name__}: {e}", flush=True)
                results.append({
                    "id": u["id"],
                    "blocks": [{"error": str(e)}],
                    "trigger_observed": False,
                    "graceful_error": False,
                })

    total_blocks = sum(len(r["blocks"]) for r in results)
    users_clean = sum(1 for r in results if len(r["blocks"]) == 0)

    print(f"\n[K3.3.SUMMARY] === N={len(results)} users ===", flush=True)
    print(f"  total blocks : {total_blocks}", flush=True)
    print(f"  clean users  : {users_clean}/{len(results)}", flush=True)
    print(
        f"  trigger seen : {sum(1 for r in results if r['trigger_observed'])} users",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
