"use client";

import { useEffect } from "react";

// 모바일 채팅 흐름 동안 agent WS '구독자'를 유지한다.
//
// 배경(2026-06-02 검증): 백엔드는 교착(stalemate) 감지 시 ai_auto_trigger를
// Redis `agent:{room}` 채널로 publish한다. 이 메시지는 *구독 중인 agent WS가 있어야*
// 소비되어 파이프라인(날짜 추출·reflect-back·vote_card)이 실행된다. Redis pub/sub은
// 구독자가 없으면 메시지를 버린다.
//
// 데스크탑은 MeetingContext가 채팅+AI패널 양쪽 WS를 항상 연결하므로 트리거가 늘 소비된다.
// 그러나 모바일은 화면이 분리(/m/chat/schedule=social, /m/chat/ai=agent)돼,
// 채팅 화면에선 social WS만 붙어 교착 트리거가 유실됐다 → AI가 응답하지 않았다.
//
// 이 컴포넌트는 메시지를 *표시하지 않고* 구독자 역할만 한다. 트리거 수신 시 서버가
// 파이프라인을 돌리고, 결과는 social 채널 배너 + /m/schedule(REST) + /m/chat/ai가 보여준다.
// 서버는 다수 구독자에 대해 이미 dedup(NX 락)을 하므로 중복 카드 위험은 없다.
export default function AgentTriggerKeepalive({ roomId }: { roomId: string }) {
  useEffect(() => {
    if (!/^\d+$/.test(roomId)) return;
    const token =
      typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
    if (!token) return; // 미인증이면 조용히 skip (redirect는 페이지가 담당)

    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
    let active = true;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let attempts = 0;

    const connect = () => {
      if (!active) return;
      socket = new WebSocket(
        `${wsBase}/ws/agent/${roomId}?token=${encodeURIComponent(token)}`,
      );
      socket.onopen = () => {
        attempts = 0;
      };
      // 구독자 역할만 — 표시는 /m/chat/ai, /m/schedule이 담당.
      socket.onmessage = () => {};
      socket.onclose = (e) => {
        if (!active || e.code === 4001 || e.code === 1008) return; // 인증 실패는 재시도 안 함
        if (attempts >= 6) return;
        const delay = Math.min(1000 * 2 ** attempts, 15000);
        attempts += 1;
        reconnectTimer = window.setTimeout(connect, delay);
      };
      socket.onerror = () => {
        socket?.close();
      };
    };
    connect();

    return () => {
      active = false;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onclose = null;
        socket.onerror = null;
        socket.close();
      }
    };
  }, [roomId]);

  return null;
}
