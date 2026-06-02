"use client";

import { Suspense } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import AgentTriggerKeepalive from "@/components/meeting/AgentTriggerKeepalive";

// 모바일 채팅 흐름(/m/chat/*) 동안 agent WS 구독자를 유지해 교착 트리거가
// 유실되지 않게 한다(AgentTriggerKeepalive 주석 참고).
// /m/chat/ai는 자체적으로 agent WS를 연결하므로 중복을 피해 제외한다.
function ChatKeepalive() {
  const roomId = useSearchParams().get("roomId") ?? "";
  const pathname = usePathname();
  if (pathname?.startsWith("/m/chat/ai")) return null;
  return <AgentTriggerKeepalive roomId={roomId} />;
}

export default function MobileChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <Suspense fallback={null}>
        <ChatKeepalive />
      </Suspense>
      {children}
    </>
  );
}
