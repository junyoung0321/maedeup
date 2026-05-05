"""
멀티 계정 시뮬레이션 헬퍼 (시연 검증용, 임시 도구).
방장(브라우저)이 보고 있는 채팅방에 게스트 계정으로 메시지를 발화시켜
3명 채팅 환경을 재현한다.

사용:
    python .gstack-multi-sim.py join <room_id> <name>
        → 게스트 가입, 토큰 출력
    python .gstack-multi-sim.py send <room_id> <token> <message>
        → 해당 게스트 토큰으로 채팅 메시지 1개 전송
    python .gstack-multi-sim.py scenario <room_id>
        → 시연 시나리오 ACT 2 5메시지를 3명이 나눠 보냄
"""
import asyncio
import json
import sys
import urllib.request

import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000"


def join_guest(room_id: str, name: str) -> dict:
    req = urllib.request.Request(
        f"{API}/api/v1/rooms/{room_id}/guest-join",
        data=json.dumps({"display_name": name}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


async def send_chat(room_id: str, token: str, sender: str, content: str) -> None:
    uri = f"{WS}/ws/social/{room_id}?token={token}"
    async with websockets.connect(uri) as ws:
        # 서버가 보내는 초기 스냅샷들 잠깐 흘려보냄
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            pass
        await ws.send(json.dumps({
            "role": "user",
            "content": content,
            "sender": sender,
        }))
        # 발행 확인용 1초 대기
        await asyncio.sleep(1.0)


async def run_scenario(room_id: str) -> None:
    """ACT 2 5메시지 — 지민(방장)/수현/민수 시뮬."""
    suhyun = join_guest(room_id, "수현")
    minsu = join_guest(room_id, "민수")
    print(f"수현 user_id={suhyun['user_id']}")
    print(f"민수 user_id={minsu['user_id']}")
    # 방장은 브라우저에서 직접 보냄 (이 스크립트는 게스트 2명만 담당)
    print("\n방장(지민)은 브라우저에서 1, 5번 메시지를 직접 보내주세요.")
    print("이 스크립트는 게스트(수현, 민수)의 2, 3, 4번 메시지를 보냅니다.\n")

    input("방장이 1번 메시지 보냈으면 Enter: ")
    await send_chat(room_id, suhyun["token"], "수현", "나는 금요일 저녁이 좋은데")
    print("✓ 수현: 나는 금요일 저녁이 좋은데")

    await asyncio.sleep(1)
    await send_chat(room_id, minsu["token"], "민수", "금요일은 알바 있어서 안 돼 ㅠ 토요일은?")
    print("✓ 민수: 금요일은 알바 있어서 안 돼 ㅠ 토요일은?")

    await asyncio.sleep(1)
    await send_chat(room_id, suhyun["token"], "수현", "토요일은 가족 모임이라 힘들어")
    print("✓ 수현: 토요일은 가족 모임이라 힘들어")

    print("\n방장(지민)이 5번 메시지 보내면 stalemate 트리거 예상.")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "join":
        room_id, name = sys.argv[2], sys.argv[3]
        print(json.dumps(join_guest(room_id, name), ensure_ascii=False, indent=2))
    elif cmd == "send":
        room_id, token, content = sys.argv[2], sys.argv[3], sys.argv[4]
        sender = sys.argv[5] if len(sys.argv) > 5 else "Guest"
        asyncio.run(send_chat(room_id, token, sender, content))
        print("sent")
    elif cmd == "scenario":
        asyncio.run(run_scenario(sys.argv[2]))
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
