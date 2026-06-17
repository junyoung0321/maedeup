"""qa용 — 게스트가 agent WS에 public 메시지 1개 전송 (cross-user 렌더 검증).
사용: python guest_agent_send.py <room_id> <guest_token> "<message>"
"""
import asyncio
import json
import sys
import websockets

WS = "ws://localhost:8000"


async def main(rid, token, msg):
    async with websockets.connect(f"{WS}/ws/agent/{rid}?token={token}") as ws:
        await asyncio.sleep(0.3)
        await ws.send(json.dumps({"role": "user", "content": msg, "sender": "게스트B", "visibility": "public"}))
        await asyncio.sleep(0.8)
    print("sent")


asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
