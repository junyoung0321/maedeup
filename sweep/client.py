"""실 백엔드 REST + WS 래퍼. 백엔드 import 없이 HTTP/WS로만 통신."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

import httpx
import websockets

API = "http://localhost:8000"
WS = "ws://localhost:8000"


class SweepClient:
    def __init__(self, host_token: str):
        self.host_token = host_token
        self._http = httpx.AsyncClient(timeout=15.0)

    async def aclose(self) -> None:
        await self._http.aclose()

    def _auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    async def create_room(self, name: str) -> int:
        r = await self._http.post(f"{API}/api/v1/rooms",
                                  json={"name": name, "description": "robustness sweep"},
                                  headers=self._auth(self.host_token))
        r.raise_for_status()
        return int(r.json()["id"])

    async def guest_join(self, room_id: int, display_name: str) -> dict:
        r = await self._http.post(f"{API}/api/v1/rooms/{room_id}/guest-join",
                                  json={"display_name": display_name})
        r.raise_for_status()
        return r.json()  # {token, user_id, name}

    async def send_social(self, room_id: int, token: str, sender: str, content: str) -> None:
        uri = f"{WS}/ws/social/{room_id}?token={token}"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"role": "user", "content": content, "sender": sender}))

    @asynccontextmanager
    async def agent_listener(self, room_id: int, token: str):
        """/ws/agent 구독 — 카드/메시지 프레임을 yield하는 컨텍스트."""
        uri = f"{WS}/ws/agent/{room_id}?token={token}"
        async with websockets.connect(uri) as ws:
            yield ws

    async def direct_request(self, room_id: int, token: str, sender: str, content: str) -> None:
        """AI 패널 직접 요청 (trigger_reason=direct_request)."""
        uri = f"{WS}/ws/agent/{room_id}?token={token}"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"role": "user", "content": content, "sender": sender}))

    async def vote(self, meeting_id: int, token: str, option_index: int) -> dict:
        r = await self._http.post(f"{API}/api/v1/meetings/{meeting_id}/vote",
                                  json={"option_index": option_index},
                                  headers=self._auth(token))
        r.raise_for_status()
        return r.json()  # {votes, total_voters, selected_option_index}

    async def confirm(self, room_id: int, title: str, scheduled_at: str,
                      end_at: str, vote_options: list[dict]) -> dict:
        r = await self._http.post(f"{API}/api/v1/meetings/confirm",
                                  json={"room_id": room_id, "title": title,
                                        "scheduled_at": scheduled_at, "end_at": end_at,
                                        "vote_options": vote_options},
                                  headers=self._auth(self.host_token))
        r.raise_for_status()
        return r.json()
